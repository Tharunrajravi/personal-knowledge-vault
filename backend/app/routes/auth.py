"""
routes/auth.py — Authentication
Register, login, refresh token, logout, get current user.

Security design:
  - Passwords: bcrypt (never stored in plaintext)
  - Access token: short-lived JWT (15 min), stateless
  - Refresh token: long-lived (7 days), stored in Redis
    → allows logout/revocation without a database call
"""
import uuid
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
import bcrypt as _bcrypt
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db, get_redis, CacheManager
from app.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# ── Security setup ────────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def _hash_pw(pw): return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt()).decode()
def _verify_pw(pw, h): return _bcrypt.checkpw(pw.encode(), h.encode())


# ── Pydantic schemas ──────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v):
        v = v.strip()
        if len(v) < 3 or len(v) > 30:
            raise ValueError("Username must be 3-30 characters")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, - and _")
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_strong(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    avatar_url: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ── JWT helpers ───────────────────────────────────────────────────────────────
def create_access_token(user_id: str, username: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "username": username,
        "exp": expire,
        "type": "access",
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token() -> str:
    """Refresh token is just a random UUID stored in Redis."""
    return str(uuid.uuid4())


async def store_refresh_token(
    user_id: str,
    refresh_token: str,
    cache: CacheManager
) -> None:
    settings = get_settings()
    await cache.set(
        f"refresh:{refresh_token}",
        user_id,
        ttl=settings.session_ttl_seconds
    )


async def verify_refresh_token(
    refresh_token: str,
    cache: CacheManager
) -> str | None:
    """Returns user_id if token is valid, None otherwise."""
    return await cache.get(f"refresh:{refresh_token}")


async def revoke_refresh_token(refresh_token: str, cache: CacheManager) -> None:
    await cache.delete(f"refresh:{refresh_token}")


# ── Current user dependency ───────────────────────────────────────────────────
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency — validates JWT and returns the User object.
    Use this on any protected endpoint:
        current_user: User = Depends(get_current_user)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        settings = get_settings()
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "access":
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    return user


# ── Routes ────────────────────────────────────────────────────────────────────
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    # Check email uniqueness
    existing = await db.execute(
        select(User).where(User.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    # Check username uniqueness
    existing = await db.execute(
        select(User).where(User.username == body.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken"
        )

    user = User(
        email=body.email,
        username=body.username,
        hashed_pw=_hash_pw(body.password),
    )
    db.add(user)
    await db.flush()  # get the ID before commit

    logger.info(f"New user registered: {user.username} ({user.email})")

    return {
        "message": "Account created successfully",
        "user_id": str(user.id),
        "username": user.username,
    }


@router.post("/login", response_model=LoginResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    # OAuth2PasswordRequestForm uses 'username' field — we accept email OR username
    result = await db.execute(
        select(User).where(
            (User.email == form.username) | (User.username == form.username)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not _verify_pw(form.password, user.hashed_pw):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )

    # Generate tokens
    access_token = create_access_token(str(user.id), user.username)
    refresh_token = create_refresh_token()

    # Store refresh token in Redis
    redis_client = await get_redis()
    cache = CacheManager(redis_client)
    await store_refresh_token(str(user.id), refresh_token, cache)

    logger.info(f"User logged in: {user.username}")

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": str(user.id),
            "email": user.email,
            "username": user.username,
            "avatar_url": user.avatar_url,
        }
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    redis_client = await get_redis()
    cache = CacheManager(redis_client)

    user_id = await verify_refresh_token(body.refresh_token, cache)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Rotate refresh token (old one is revoked, new one issued)
    await revoke_refresh_token(body.refresh_token, cache)
    new_access_token = create_access_token(str(user.id), user.username)
    new_refresh_token = create_refresh_token()
    await store_refresh_token(str(user.id), new_refresh_token, cache)

    return LoginResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        user={"id": str(user.id), "email": user.email, "username": user.username}
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    current_user: User = Depends(get_current_user),
):
    redis_client = await get_redis()
    cache = CacheManager(redis_client)
    await revoke_refresh_token(body.refresh_token, cache)
    logger.info(f"User logged out: {current_user.username}")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        username=current_user.username,
        avatar_url=current_user.avatar_url,
        created_at=current_user.created_at,
    )
