"""
models.py — SQLAlchemy ORM models
All tables for the Personal Knowledge Vault.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer,
    String, Text, Table, UniqueConstraint, Index,
    func, text
)
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR, ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Association table: Link ↔ Tag (many-to-many) ──────────────────────────────
link_tags = Table(
    "link_tags",
    Base.metadata,
    Column("link_id", UUID(as_uuid=True), ForeignKey("links.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id",  UUID(as_uuid=True), ForeignKey("tags.id",  ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email      = Column(String(255), unique=True, nullable=False, index=True)
    username   = Column(String(50),  unique=True, nullable=False, index=True)
    hashed_pw  = Column(String(255), nullable=False)
    is_active  = Column(Boolean, default=True, nullable=False)
    is_verified= Column(Boolean, default=False, nullable=False)
    avatar_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    links      = relationship("Link",     back_populates="user", cascade="all, delete-orphan")
    tags       = relationship("Tag",      back_populates="user", cascade="all, delete-orphan")
    favorites  = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username}>"


class Tag(Base):
    __tablename__ = "tags"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name       = Column(String(50), nullable=False)
    color      = Column(String(7), default="#6366f1")  # hex color
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Each user can only have one tag with a given name
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_tag_name"),
        Index("ix_tags_user_id", "user_id"),
    )

    user  = relationship("User",  back_populates="tags")
    links = relationship("Link",  secondary=link_tags, back_populates="tags")

    def __repr__(self):
        return f"<Tag {self.name}>"


class Link(Base):
    __tablename__ = "links"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Core fields
    url          = Column(Text, nullable=False)
    title        = Column(String(500), nullable=True)
    description  = Column(Text, nullable=True)
    favicon_url  = Column(String(500), nullable=True)
    image_url    = Column(String(500), nullable=True)  # og:image
    domain       = Column(String(255), nullable=True)  # extracted from URL

    # Classification
    link_type    = Column(String(20), default="article")
    # article | youtube | github | image | pdf | other

    # YouTube-specific metadata
    yt_video_id  = Column(String(20), nullable=True)
    yt_channel   = Column(String(255), nullable=True)
    yt_duration  = Column(String(20), nullable=True)

    # GitHub-specific metadata
    gh_stars     = Column(Integer, nullable=True)
    gh_language  = Column(String(50), nullable=True)
    gh_description = Column(Text, nullable=True)

    # User fields
    notes        = Column(Text, nullable=True)       # user's own notes
    is_favorite  = Column(Boolean, default=False, nullable=False)
    is_archived  = Column(Boolean, default=False, nullable=False)
    is_read      = Column(Boolean, default=False, nullable=False)

    # Scraping status
    scrape_status = Column(String(20), default="pending")
    # pending | done | failed

    # Full-text search vector (auto-updated by trigger)
    search_vector = Column(TSVECTOR, nullable=True)

    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    updated_at   = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_links_user_id",      "user_id"),
        Index("ix_links_domain",       "domain"),
        Index("ix_links_type",         "link_type"),
        Index("ix_links_is_favorite",  "is_favorite"),
        Index("ix_links_created_at",   "created_at"),
        # GIN index for full-text search — this is what makes search fast
        Index("ix_links_search_vector", "search_vector", postgresql_using="gin"),
    )

    user      = relationship("User",     back_populates="links")
    tags      = relationship("Tag",      secondary=link_tags, back_populates="links")
    favorites = relationship("Favorite", back_populates="link", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Link {self.domain}: {self.title[:40] if self.title else 'untitled'}>"


class Favorite(Base):
    """
    Separate table so we can track WHEN something was favorited
    and support future features like favorite collections.
    """
    __tablename__ = "favorites"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    link_id    = Column(UUID(as_uuid=True), ForeignKey("links.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "link_id", name="uq_user_link_favorite"),
        Index("ix_favorites_user_id", "user_id"),
    )

    user = relationship("User", back_populates="favorites")
    link = relationship("Link", back_populates="favorites")


# ── SQL for full-text search trigger ──────────────────────────────────────────
# Run this after creating tables (see database.py init_db)
# Each entry is one SQL statement — split by ";\n\n" in database.py
SEARCH_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION links_search_vector_update() RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
    setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(NEW.notes, '')), 'C') ||
    setweight(to_tsvector('english', coalesce(NEW.domain, '')), 'D');
  RETURN NEW;
END
$$ LANGUAGE plpgsql

DROP TRIGGER IF EXISTS links_search_vector_trigger ON links

CREATE TRIGGER links_search_vector_trigger
  BEFORE INSERT OR UPDATE OF title, description, notes, domain
  ON links
  FOR EACH ROW EXECUTE FUNCTION links_search_vector_update()
"""
