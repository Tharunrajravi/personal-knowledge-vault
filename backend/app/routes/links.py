"""
routes/links.py — Link CRUD + search + tagging + favorites

Architecture notes:
  - Saving a URL is instant (returns immediately)
  - Scraping happens async via background task (doesn't block the response)
  - Full-text search uses PostgreSQL tsvector (GIN index, fast)
  - Search results are cached in Redis for 60 seconds
"""
import uuid
import json
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, status
from pydantic import BaseModel, HttpUrl, field_validator
from sqlalchemy import select, func, desc, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db, get_redis, CacheManager
from app.models import Link, Tag, User, Favorite, link_tags
from app.routes.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/links", tags=["links"])


# ── Schemas ───────────────────────────────────────────────────────────────────
class SaveLinkRequest(BaseModel):
    url: str
    notes: Optional[str] = None
    tag_ids: Optional[list[str]] = []

    @field_validator("url")
    @classmethod
    def url_valid(cls, v):
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must start with http:// or https://")
        return v


class UpdateLinkRequest(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None
    is_read: Optional[bool] = None
    is_archived: Optional[bool] = None
    tag_ids: Optional[list[str]] = None


class TagSchema(BaseModel):
    id: str
    name: str
    color: str

    class Config:
        from_attributes = True


class LinkResponse(BaseModel):
    id: str
    url: str
    title: Optional[str]
    description: Optional[str]
    favicon_url: Optional[str]
    image_url: Optional[str]
    domain: Optional[str]
    link_type: str
    notes: Optional[str]
    is_favorite: bool
    is_archived: bool
    is_read: bool
    scrape_status: str
    tags: list[TagSchema]
    created_at: datetime
    updated_at: datetime

    # YouTube extras
    yt_video_id: Optional[str] = None
    yt_channel: Optional[str] = None

    # GitHub extras
    gh_stars: Optional[int] = None
    gh_language: Optional[str] = None

    class Config:
        from_attributes = True


def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        return domain
    except Exception:
        return ""


def _detect_link_type(url: str) -> str:
    url_lower = url.lower()
    if "youtube.com/watch" in url_lower or "youtu.be/" in url_lower:
        return "youtube"
    if "github.com/" in url_lower:
        return "github"
    if url_lower.endswith(".pdf"):
        return "pdf"
    if any(url_lower.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
        return "image"
    return "article"


def _link_to_response(link: Link) -> LinkResponse:
    return LinkResponse(
        id=str(link.id),
        url=link.url,
        title=link.title,
        description=link.description,
        favicon_url=link.favicon_url,
        image_url=link.image_url,
        domain=link.domain,
        link_type=link.link_type,
        notes=link.notes,
        is_favorite=link.is_favorite,
        is_archived=link.is_archived,
        is_read=link.is_read,
        scrape_status=link.scrape_status,
        tags=[TagSchema(id=str(t.id), name=t.name, color=t.color) for t in link.tags],
        created_at=link.created_at,
        updated_at=link.updated_at,
        yt_video_id=link.yt_video_id,
        yt_channel=link.yt_channel,
        gh_stars=link.gh_stars,
        gh_language=link.gh_language,
    )


# ── Routes ────────────────────────────────────────────────────────────────────
@router.post("", status_code=status.HTTP_201_CREATED, response_model=LinkResponse)
async def save_link(
    body: SaveLinkRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Save a URL. Returns immediately with basic info.
    Metadata (title, description, image) is scraped in the background.
    """
    domain = _extract_domain(body.url)
    link_type = _detect_link_type(body.url)

    link = Link(
        user_id=current_user.id,
        url=body.url,
        domain=domain,
        link_type=link_type,
        notes=body.notes,
        scrape_status="pending",
    )

    # Attach tags if provided
    if body.tag_ids:
        result = await db.execute(
            select(Tag).where(
                Tag.id.in_([uuid.UUID(tid) for tid in body.tag_ids]),
                Tag.user_id == current_user.id
            )
        )
        link.tags = result.scalars().all()

    db.add(link)
    await db.flush()

    # Eagerly reload the link with tags to avoid lazy load outside async context
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Link).where(Link.id == link.id).options(selectinload(Link.tags))
    )
    link = result.scalar_one()

    # Scrape metadata in background (doesn't block response)
    background_tasks.add_task(_scrape_and_update, str(link.id), body.url)

    # Invalidate the user's link list cache
    redis_client = await get_redis()
    cache = CacheManager(redis_client)
    await cache.delete_pattern(f"links:{current_user.id}:*")

    logger.info(f"Link saved: {domain} by {current_user.username}")
    return _link_to_response(link)


@router.get("", response_model=dict)
async def list_links(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    link_type: Optional[str] = Query(None),
    tag_id: Optional[str] = Query(None),
    is_favorite: Optional[bool] = Query(None),
    is_archived: Optional[bool] = Query(False),
    is_read: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List links with filtering and pagination.
    Results cached per user+filter combination for 5 minutes.
    """
    settings = get_settings()
    cache_key = f"links:{current_user.id}:{page}:{per_page}:{link_type}:{tag_id}:{is_favorite}:{is_archived}:{is_read}"

    # Try cache first
    redis_client = await get_redis()
    cache = CacheManager(redis_client)
    cached = await cache.get(cache_key)
    if cached:
        return json.loads(cached)

    # Build query
    query = (
        select(Link)
        .where(Link.user_id == current_user.id)
        .options(selectinload(Link.tags))
    )

    if link_type:
        query = query.where(Link.link_type == link_type)
    if tag_id:
        query = query.where(Link.tags.any(Tag.id == uuid.UUID(tag_id)))
    if is_favorite is not None:
        query = query.where(Link.is_favorite == is_favorite)
    if is_archived is not None:
        query = query.where(Link.is_archived == is_archived)
    if is_read is not None:
        query = query.where(Link.is_read == is_read)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # Paginate
    query = query.order_by(desc(Link.created_at))
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    links = result.scalars().all()

    response = {
        "items": [_link_to_response(l).model_dump() for l in links],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }

    # Serialize dates for JSON cache
    response_json = json.dumps(response, default=str)
    await cache.set(cache_key, response_json, ttl=settings.cache_ttl_seconds)

    return response


@router.get("/search", response_model=dict)
async def search_links(
    q: str = Query(..., min_length=1, max_length=200),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Full-text search using PostgreSQL tsvector.
    Weighted: title (A) > description (B) > notes (C) > domain (D)
    Results cached for 60 seconds.
    """
    settings = get_settings()
    cache_key = f"search:{current_user.id}:{q}:{page}:{per_page}"

    redis_client = await get_redis()
    cache = CacheManager(redis_client)
    cached = await cache.get(cache_key)
    if cached:
        return json.loads(cached)

    # PostgreSQL full-text search with ranking
    search_query = (
        select(Link)
        .where(
            Link.user_id == current_user.id,
            Link.search_vector.op("@@")(func.plainto_tsquery("english", q))
        )
        .options(selectinload(Link.tags))
        .order_by(
            desc(func.ts_rank(Link.search_vector, func.plainto_tsquery("english", q)))
        )
    )

    count_query = select(func.count()).select_from(search_query.subquery())
    total = (await db.execute(count_query)).scalar()

    search_query = search_query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(search_query)
    links = result.scalars().all()

    response = {
        "items": [_link_to_response(l).model_dump() for l in links],
        "total": total,
        "query": q,
        "page": page,
        "per_page": per_page,
    }

    await cache.set(cache_key, json.dumps(response, default=str), ttl=settings.search_cache_ttl)
    return response


@router.get("/{link_id}", response_model=LinkResponse)
async def get_link(
    link_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Link)
        .where(Link.id == uuid.UUID(link_id), Link.user_id == current_user.id)
        .options(selectinload(Link.tags))
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    return _link_to_response(link)


@router.patch("/{link_id}", response_model=LinkResponse)
async def update_link(
    link_id: str,
    body: UpdateLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Link)
        .where(Link.id == uuid.UUID(link_id), Link.user_id == current_user.id)
        .options(selectinload(Link.tags))
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    if body.title is not None:
        link.title = body.title
    if body.notes is not None:
        link.notes = body.notes
    if body.is_read is not None:
        link.is_read = body.is_read
    if body.is_archived is not None:
        link.is_archived = body.is_archived

    if body.tag_ids is not None:
        tag_result = await db.execute(
            select(Tag).where(
                Tag.id.in_([uuid.UUID(tid) for tid in body.tag_ids]),
                Tag.user_id == current_user.id
            )
        )
        link.tags = tag_result.scalars().all()

    # Invalidate cache
    redis_client = await get_redis()
    cache = CacheManager(redis_client)
    await cache.delete_pattern(f"links:{current_user.id}:*")

    return _link_to_response(link)


@router.post("/{link_id}/favorite", status_code=status.HTTP_200_OK)
async def toggle_favorite(
    link_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Link).where(Link.id == uuid.UUID(link_id), Link.user_id == current_user.id)
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    link.is_favorite = not link.is_favorite

    redis_client = await get_redis()
    cache = CacheManager(redis_client)
    await cache.delete_pattern(f"links:{current_user.id}:*")

    return {"is_favorite": link.is_favorite}


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    link_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Link).where(Link.id == uuid.UUID(link_id), Link.user_id == current_user.id)
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    await db.delete(link)

    redis_client = await get_redis()
    cache = CacheManager(redis_client)
    await cache.delete_pattern(f"links:{current_user.id}:*")


# ── Background scraper task ───────────────────────────────────────────────────
async def _scrape_and_update(link_id: str, url: str):
    """
    Called as a background task after saving a URL.
    Fetches metadata and updates the link record.
    Import here to avoid circular imports.
    """
    from app.routes.scraper import scrape_metadata
    from app.database import get_session_factory

    session_factory = get_session_factory()
    async with session_factory() as db:
        try:
            result = await db.execute(select(Link).where(Link.id == uuid.UUID(link_id)))
            link = result.scalar_one_or_none()
            if not link:
                return

            metadata = await scrape_metadata(url)

            link.title = metadata.get("title")
            link.description = metadata.get("description")
            link.favicon_url = metadata.get("favicon_url")
            link.image_url = metadata.get("image_url")
            link.scrape_status = "done"

            # YouTube extras
            if metadata.get("yt_video_id"):
                link.yt_video_id = metadata["yt_video_id"]
                link.yt_channel = metadata.get("yt_channel")

            # GitHub extras
            if metadata.get("gh_stars") is not None:
                link.gh_stars = metadata["gh_stars"]
                link.gh_language = metadata.get("gh_language")
                link.gh_description = metadata.get("gh_description")

            await db.commit()
            logger.info(f"Scraped: {url} → {link.title}")

        except Exception as e:
            logger.error(f"Scrape failed for {url}: {e}")
            try:
                link.scrape_status = "failed"
                await db.commit()
            except Exception:
                pass
