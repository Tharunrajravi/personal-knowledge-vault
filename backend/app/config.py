"""
config.py — Application configuration
Reads secrets from AWS SSM Parameter Store at startup.
Falls back to environment variables for local development.

Architect note:
  In production (ECS), no env vars are hardcoded.
  The app calls SSM on startup and builds the config from there.
  Locally, docker-compose sets env vars directly.
"""
import os
import logging
from functools import lru_cache
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def _get_ssm_parameter(name: str, with_decryption: bool = True) -> str | None:
    """Fetch a single SSM parameter. Returns None if not found or not on AWS."""
    try:
        import boto3
        ssm = boto3.client("ssm", region_name=os.getenv("AWS_REGION", "ap-south-1"))
        response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)
        return response["Parameter"]["Value"]
    except Exception as e:
        logger.debug(f"SSM fetch failed for {name}: {e}")
        return None


def _load_from_ssm(project: str = "pkv") -> dict:
    """
    Load all app secrets from SSM Parameter Store.
    Returns empty dict if SSM is unavailable (local dev).
    """
    params = {}
    try:
        import boto3
        ssm = boto3.client("ssm", region_name=os.getenv("AWS_REGION", "ap-south-1"))
        paginator = ssm.get_paginator("get_parameters_by_path")

        for page in paginator.paginate(
            Path=f"/{project}/",
            Recursive=True,
            WithDecryption=True,
        ):
            for param in page["Parameters"]:
                # /pkv/db/url → db_url
                key = param["Name"].replace(f"/{project}/", "").replace("/", "_")
                params[key] = param["Value"]

        logger.info(f"Loaded {len(params)} parameters from SSM /{project}/")
    except Exception as e:
        logger.warning(f"SSM unavailable, using env vars: {e}")

    return params


class Settings(BaseSettings):
    # ── App ────────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_name: str = "Personal Knowledge Vault"
    app_version: str = "1.0.0"
    debug: bool = False

    # ── Database ───────────────────────────────────────────────────────────────
    db_url: str = "postgresql+asyncpg://pkvadmin:localpassword@localhost:5432/pkv_db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    # ── Redis ──────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 300          # 5 min default cache
    search_cache_ttl: int = 60            # 1 min for search results
    session_ttl_seconds: int = 86400 * 7  # 7 days for refresh tokens

    # ── Auth ───────────────────────────────────────────────────────────────────
    jwt_secret: str = "change-me-in-production-use-ssm"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # ── AWS ────────────────────────────────────────────────────────────────────
    aws_region: str = "ap-south-1"
    s3_uploads_bucket: str = "pkv-uploads-local"
    s3_frontend_bucket: str = "pkv-frontend-local"
    presigned_url_expiry: int = 3600  # 1 hour

    # ── CORS ───────────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # ── Scraper ────────────────────────────────────────────────────────────────
    scraper_timeout_seconds: int = 10
    scraper_max_content_length: int = 5_000_000  # 5MB

    # ── SES Email ─────────────────────────────────────────────────────────────
    ses_from_email: str = "noreply@yourdomain.com"
    ses_enabled: bool = False  # enable after SES domain verification

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    class Config:
        extra = "ignore"
        extra = 'ignore'
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Build settings: SSM first (production), env vars as fallback (local dev).
    Cached after first call — SSM is only hit once per process startup.
    """
    ssm_params = _load_from_ssm()

    # SSM params override defaults; env vars override SSM for local dev
    env_overrides = {}
    for key, value in ssm_params.items():
        if not os.getenv(key.upper()):  # don't override explicit env vars
            env_overrides[key] = value

    return Settings(**env_overrides)
