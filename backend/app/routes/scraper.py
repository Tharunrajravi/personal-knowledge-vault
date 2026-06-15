"""
routes/scraper.py — Article/URL metadata scraper

Handles:
  - Generic articles: og:title, og:description, og:image, favicon
  - YouTube: video ID, channel, thumbnail via oEmbed (no API key needed)
  - GitHub: repo stars, language, description via GitHub API (no auth for public)
"""
import re
import logging
from typing import Optional
from urllib.parse import urlparse, urljoin

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.routes.auth import get_current_user
from app.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scraper", tags=["scraper"])

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; PKVBot/1.0; +https://github.com/pkv)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# ── Core scraper ──────────────────────────────────────────────────────────────
async def scrape_metadata(url: str) -> dict:
    """
    Main entry point. Detects URL type and dispatches to the right scraper.
    Returns a dict of metadata fields to update on the Link model.
    """
    url_lower = url.lower()

    if "youtube.com/watch" in url_lower or "youtu.be/" in url_lower:
        return await _scrape_youtube(url)

    if "github.com/" in url_lower:
        return await _scrape_github(url)

    return await _scrape_generic(url)


async def _scrape_generic(url: str) -> dict:
    """Scrape Open Graph + standard HTML meta tags."""
    settings = get_settings()
    result = {}

    try:
        async with httpx.AsyncClient(
            timeout=settings.scraper_timeout_seconds,
            follow_redirects=True,
            headers=HEADERS,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Check content type — only parse HTML
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type:
                return result

            # Limit parse size (don't parse 50MB pages)
            content = response.text[:settings.scraper_max_content_length]
            soup = BeautifulSoup(content, "lxml")

            # Open Graph tags (priority)
            og = {
                tag.get("property", ""): tag.get("content", "")
                for tag in soup.find_all("meta")
                if tag.get("property", "").startswith("og:")
            }

            # Twitter Card tags (fallback)
            twitter = {
                tag.get("name", ""): tag.get("content", "")
                for tag in soup.find_all("meta")
                if tag.get("name", "").startswith("twitter:")
            }

            # Title: og:title > twitter:title > <title> tag
            result["title"] = (
                og.get("og:title")
                or twitter.get("twitter:title")
                or (soup.title.string.strip() if soup.title else None)
            )

            # Description
            result["description"] = (
                og.get("og:description")
                or twitter.get("twitter:description")
                or _get_meta(soup, "description")
            )

            # Image
            result["image_url"] = (
                og.get("og:image")
                or twitter.get("twitter:image")
            )

            # Favicon
            result["favicon_url"] = _extract_favicon(soup, url)

            # Truncate long fields
            if result.get("title"):
                result["title"] = result["title"][:500]
            if result.get("description"):
                result["description"] = result["description"][:2000]

    except httpx.TimeoutException:
        logger.warning(f"Scrape timeout: {url}")
    except httpx.HTTPStatusError as e:
        logger.warning(f"Scrape HTTP error {e.response.status_code}: {url}")
    except Exception as e:
        logger.error(f"Scrape error for {url}: {e}")

    return result


async def _scrape_youtube(url: str) -> dict:
    """
    Use YouTube oEmbed API — no API key required.
    Returns video title, author (channel), thumbnail.
    """
    result = {}

    # Extract video ID
    video_id = None
    if "youtu.be/" in url:
        video_id = url.split("youtu.be/")[1].split("?")[0]
    elif "v=" in url:
        match = re.search(r"v=([a-zA-Z0-9_-]{11})", url)
        if match:
            video_id = match.group(1)

    if not video_id:
        return await _scrape_generic(url)

    try:
        oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(oembed_url)
            response.raise_for_status()
            data = response.json()

        result["title"] = data.get("title")
        result["yt_channel"] = data.get("author_name")
        result["yt_video_id"] = video_id
        result["image_url"] = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
        result["favicon_url"] = "https://www.youtube.com/favicon.ico"
        result["description"] = f"YouTube video by {data.get('author_name', 'Unknown')}"

    except Exception as e:
        logger.warning(f"YouTube oEmbed failed for {url}: {e}")
        result = await _scrape_generic(url)
        result["yt_video_id"] = video_id

    return result


async def _scrape_github(url: str) -> dict:
    """
    Use GitHub API for public repo metadata.
    No auth token needed for public repos (60 req/hr unauthenticated).
    """
    result = {}

    # Extract owner/repo from URL
    # e.g. https://github.com/owner/repo → owner/repo
    path = urlparse(url).path.strip("/")
    parts = path.split("/")

    if len(parts) < 2:
        return await _scrape_generic(url)

    owner, repo = parts[0], parts[1]
    # Remove .git suffix if present
    repo = repo.replace(".git", "")

    try:
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        async with httpx.AsyncClient(
            timeout=10,
            headers={"Accept": "application/vnd.github.v3+json"}
        ) as client:
            response = await client.get(api_url)
            response.raise_for_status()
            data = response.json()

        result["title"] = data.get("full_name")
        result["description"] = data.get("description")
        result["gh_stars"] = data.get("stargazers_count", 0)
        result["gh_language"] = data.get("language")
        result["gh_description"] = data.get("description")
        result["image_url"] = data.get("owner", {}).get("avatar_url")
        result["favicon_url"] = "https://github.com/favicon.ico"

        # Build a rich description
        topics = data.get("topics", [])
        if topics:
            result["description"] = f"{data.get('description', '')} | Topics: {', '.join(topics[:5])}"

    except Exception as e:
        logger.warning(f"GitHub API failed for {url}: {e}")
        result = await _scrape_generic(url)

    return result


def _get_meta(soup: BeautifulSoup, name: str) -> Optional[str]:
    tag = soup.find("meta", attrs={"name": name})
    return tag.get("content") if tag else None


def _extract_favicon(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """Try multiple favicon locations."""
    # 1. <link rel="icon"> or <link rel="shortcut icon">
    for rel in ["icon", "shortcut icon", "apple-touch-icon"]:
        tag = soup.find("link", rel=lambda r: r and rel in r.lower() if r else False)
        if tag and tag.get("href"):
            href = tag["href"]
            if href.startswith("http"):
                return href
            return urljoin(base_url, href)

    # 2. Default /favicon.ico
    parsed = urlparse(base_url)
    return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"


# ── API endpoint: manual scrape trigger ──────────────────────────────────────
class ScrapeRequest(BaseModel):
    url: str


class ScrapeResponse(BaseModel):
    title: Optional[str]
    description: Optional[str]
    favicon_url: Optional[str]
    image_url: Optional[str]
    link_type: str


@router.post("/preview", response_model=ScrapeResponse)
async def preview_url(
    body: ScrapeRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Preview metadata for a URL before saving.
    Used by the frontend to show a preview card while the user is typing.
    """
    from app.routes.links import _detect_link_type
    metadata = await scrape_metadata(body.url)
    return ScrapeResponse(
        title=metadata.get("title"),
        description=metadata.get("description"),
        favicon_url=metadata.get("favicon_url"),
        image_url=metadata.get("image_url"),
        link_type=_detect_link_type(body.url),
    )
