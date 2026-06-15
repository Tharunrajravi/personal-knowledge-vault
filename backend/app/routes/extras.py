"""
routes/tags.py — Tag management
routes/dashboard.py — Analytics
routes/export.py — PDF export to S3
(All in one file to keep things organised at this stage)
"""
import io
import json
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db, get_redis, CacheManager
from app.models import Link, Tag, User
from app.routes.auth import get_current_user

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# TAGS
# ══════════════════════════════════════════════════════════════════
tags_router = APIRouter(prefix="/tags", tags=["tags"])


class CreateTagRequest(BaseModel):
    name: str
    color: Optional[str] = "#6366f1"


class TagResponse(BaseModel):
    id: str
    name: str
    color: str
    link_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


@tags_router.get("", response_model=list[TagResponse])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(
            Tag,
            func.count(Link.id).label("link_count")
        )
        .outerjoin(Tag.links)
        .where(Tag.user_id == current_user.id)
        .group_by(Tag.id)
        .order_by(Tag.name)
    )
    rows = result.all()
    return [
        TagResponse(
            id=str(row.Tag.id),
            name=row.Tag.name,
            color=row.Tag.color,
            link_count=row.link_count,
            created_at=row.Tag.created_at,
        )
        for row in rows
    ]


@tags_router.post("", status_code=status.HTTP_201_CREATED, response_model=TagResponse)
async def create_tag(
    body: CreateTagRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate color
    name = body.name.strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="Tag name cannot be empty")

    # Check duplicate
    existing = await db.execute(
        select(Tag).where(Tag.user_id == current_user.id, Tag.name == name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Tag already exists")

    tag = Tag(user_id=current_user.id, name=name, color=body.color or "#6366f1")
    db.add(tag)
    await db.flush()

    return TagResponse(
        id=str(tag.id),
        name=tag.name,
        color=tag.color,
        link_count=0,
        created_at=tag.created_at,
    )


@tags_router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Tag).where(Tag.id == uuid.UUID(tag_id), Tag.user_id == current_user.id)
    )
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    await db.delete(tag)


# ══════════════════════════════════════════════════════════════════
# DASHBOARD ANALYTICS
# ══════════════════════════════════════════════════════════════════
dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@dashboard_router.get("")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all dashboard analytics in a single query batch.
    Cached per user for 5 minutes.
    """
    redis_client = await get_redis()
    cache = CacheManager(redis_client)
    cache_key = f"dashboard:{current_user.id}"

    cached = await cache.get(cache_key)
    if cached:
        return json.loads(cached)

    # ── Total counts ──────────────────────────────────────────────
    total_links = (await db.execute(
        select(func.count(Link.id)).where(Link.user_id == current_user.id)
    )).scalar()

    total_favorites = (await db.execute(
        select(func.count(Link.id)).where(
            Link.user_id == current_user.id,
            Link.is_favorite == True
        )
    )).scalar()

    total_unread = (await db.execute(
        select(func.count(Link.id)).where(
            Link.user_id == current_user.id,
            Link.is_read == False,
            Link.is_archived == False,
        )
    )).scalar()

    total_archived = (await db.execute(
        select(func.count(Link.id)).where(
            Link.user_id == current_user.id,
            Link.is_archived == True,
        )
    )).scalar()

    # ── Links by type ────────────────────────────────────────────
    type_counts_result = await db.execute(
        select(Link.link_type, func.count(Link.id).label("count"))
        .where(Link.user_id == current_user.id)
        .group_by(Link.link_type)
        .order_by(desc("count"))
    )
    links_by_type = [
        {"type": row.link_type, "count": row.count}
        for row in type_counts_result.all()
    ]

    # ── Links saved per day (last 30 days) ────────────────────────
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    daily_result = await db.execute(
        select(
            func.date_trunc("day", Link.created_at).label("day"),
            func.count(Link.id).label("count")
        )
        .where(
            Link.user_id == current_user.id,
            Link.created_at >= thirty_days_ago
        )
        .group_by("day")
        .order_by("day")
    )
    links_per_day = [
        {"date": row.day.strftime("%Y-%m-%d"), "count": row.count}
        for row in daily_result.all()
    ]

    # ── Top domains ───────────────────────────────────────────────
    top_domains_result = await db.execute(
        select(Link.domain, func.count(Link.id).label("count"))
        .where(Link.user_id == current_user.id, Link.domain.isnot(None))
        .group_by(Link.domain)
        .order_by(desc("count"))
        .limit(10)
    )
    top_domains = [
        {"domain": row.domain, "count": row.count}
        for row in top_domains_result.all()
    ]

    # ── Top tags ──────────────────────────────────────────────────
    top_tags_result = await db.execute(
        select(Tag.name, Tag.color, func.count(Link.id).label("count"))
        .outerjoin(Tag.links)
        .where(Tag.user_id == current_user.id)
        .group_by(Tag.id)
        .order_by(desc("count"))
        .limit(10)
    )
    top_tags = [
        {"name": row.name, "color": row.color, "count": row.count}
        for row in top_tags_result.all()
    ]

    # ── Recent links ──────────────────────────────────────────────
    recent_result = await db.execute(
        select(Link)
        .where(Link.user_id == current_user.id)
        .order_by(desc(Link.created_at))
        .limit(5)
    )
    recent_links = [
        {"id": str(l.id), "title": l.title, "domain": l.domain, "url": l.url, "created_at": l.created_at.isoformat()}
        for l in recent_result.scalars().all()
    ]

    response = {
        "summary": {
            "total_links": total_links,
            "total_favorites": total_favorites,
            "total_unread": total_unread,
            "total_archived": total_archived,
        },
        "links_by_type": links_by_type,
        "links_per_day": links_per_day,
        "top_domains": top_domains,
        "top_tags": top_tags,
        "recent_links": recent_links,
    }

    await cache.set(cache_key, json.dumps(response, default=str), ttl=300)
    return response


# ══════════════════════════════════════════════════════════════════
# EXPORT TO PDF
# ══════════════════════════════════════════════════════════════════
export_router = APIRouter(prefix="/export", tags=["export"])


@export_router.post("/pdf")
async def export_to_pdf(
    background_tasks: BackgroundTasks,
    tag_id: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger PDF export as a background job.
    Returns a job ID. Frontend polls /export/status/{job_id}.
    When done, returns a presigned S3 URL to download the PDF.
    """
    job_id = str(uuid.uuid4())

    redis_client = await get_redis()
    cache = CacheManager(redis_client)

    # Set initial job status
    await cache.set(
        f"export_job:{job_id}",
        json.dumps({"status": "pending", "user_id": str(current_user.id)}),
        ttl=3600
    )

    background_tasks.add_task(
        _generate_pdf_job,
        job_id=job_id,
        user_id=str(current_user.id),
        tag_id=tag_id,
        is_favorite=is_favorite,
    )

    return {"job_id": job_id, "status": "pending"}


@export_router.get("/status/{job_id}")
async def get_export_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    redis_client = await get_redis()
    cache = CacheManager(redis_client)
    job_data = await cache.get(f"export_job:{job_id}")

    if not job_data:
        raise HTTPException(status_code=404, detail="Export job not found")

    job = json.loads(job_data)

    # Security: only the owner can check their job
    if job.get("user_id") != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    return job


async def _generate_pdf_job(
    job_id: str,
    user_id: str,
    tag_id: Optional[str],
    is_favorite: Optional[bool],
):
    """Background task: generate PDF and upload to S3."""
    from app.database import get_session_factory
    from sqlalchemy.orm import selectinload

    settings = get_settings()
    redis_client = await get_redis()
    cache = CacheManager(redis_client)

    async def _update_status(status: str, **kwargs):
        data = {"status": status, "user_id": user_id, **kwargs}
        await cache.set(f"export_job:{job_id}", json.dumps(data), ttl=3600)

    try:
        await _update_status("generating")

        session_factory = get_session_factory()
        async with session_factory() as db:
            query = (
                select(Link)
                .where(Link.user_id == uuid.UUID(user_id))
                .options(selectinload(Link.tags))
                .order_by(desc(Link.created_at))
            )
            if tag_id:
                query = query.where(Link.tags.any(Tag.id == uuid.UUID(tag_id)))
            if is_favorite is not None:
                query = query.where(Link.is_favorite == is_favorite)

            result = await db.execute(query)
            links = result.scalars().all()

        # Build HTML for WeasyPrint
        html_content = _build_pdf_html(links)

        # Generate PDF
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_content).write_pdf()

        # Upload to S3
        await _update_status("uploading")
        s3 = boto3.client("s3", region_name=settings.aws_region)
        s3_key = f"exports/{user_id}/{job_id}.pdf"

        s3.put_object(
            Bucket=settings.s3_uploads_bucket,
            Key=s3_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
            ContentDisposition=f'attachment; filename="pkv-export-{job_id[:8]}.pdf"',
        )

        # Generate presigned URL (valid 1 hour)
        presigned_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_uploads_bucket, "Key": s3_key},
            ExpiresIn=3600,
        )

        await _update_status("done", download_url=presigned_url, link_count=len(links))
        logger.info(f"PDF export done: {len(links)} links for user {user_id}")

    except Exception as e:
        logger.error(f"PDF export failed for job {job_id}: {e}")
        await _update_status("failed", error=str(e))


def _build_pdf_html(links) -> str:
    rows = ""
    for i, link in enumerate(links, 1):
        tags_html = " ".join(
            f'<span class="tag">{t.name}</span>'
            for t in (link.tags or [])
        )
        fav = "★" if link.is_favorite else ""
        rows += f"""
        <tr class="{'alt' if i % 2 == 0 else ''}">
          <td>{i}</td>
          <td>
            <div class="title">{fav} {link.title or 'Untitled'}</div>
            <div class="url"><a href="{link.url}">{link.domain or link.url[:60]}</a></div>
            <div class="tags">{tags_html}</div>
          </td>
          <td>{link.link_type}</td>
          <td>{link.created_at.strftime('%b %d, %Y') if link.created_at else ''}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, sans-serif; font-size: 12px; color: #1f2937; margin: 40px; }}
  h1 {{ font-size: 24px; color: #4f46e5; border-bottom: 2px solid #4f46e5; padding-bottom: 8px; }}
  .meta {{ color: #6b7280; font-size: 11px; margin-bottom: 20px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #4f46e5; color: white; padding: 8px 12px; text-align: left; font-size: 11px; }}
  td {{ padding: 8px 12px; vertical-align: top; border-bottom: 1px solid #e5e7eb; }}
  tr.alt td {{ background: #f9fafb; }}
  .title {{ font-weight: 600; margin-bottom: 2px; }}
  .url {{ color: #6b7280; font-size: 10px; word-break: break-all; }}
  .tag {{ background: #e0e7ff; color: #4338ca; padding: 1px 6px; border-radius: 9999px;
          font-size: 10px; margin-right: 4px; }}
  .tags {{ margin-top: 4px; }}
</style>
</head>
<body>
  <h1>Personal Knowledge Vault</h1>
  <p class="meta">Exported {len(links)} links on {datetime.now().strftime('%B %d, %Y')}</p>
  <table>
    <thead><tr><th>#</th><th>Link</th><th>Type</th><th>Saved</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""
