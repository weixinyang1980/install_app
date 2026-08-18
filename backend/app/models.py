from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Software(Base):
    __tablename__ = "software"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), default="binary")
    version_source: Mapped[str] = mapped_column(String(40), default="ai")
    source_key: Mapped[str] = mapped_column(String(200), default="")
    winget_id: Mapped[str] = mapped_column(String(200), default="")
    brew_formula: Mapped[str] = mapped_column(String(200), default="")
    brew_cask: Mapped[str] = mapped_column(String(200), default="")
    official_url: Mapped[str] = mapped_column(String(500), default="")
    use_official_link: Mapped[bool] = mapped_column(Boolean, default=False)
    aliases: Mapped[str] = mapped_column(Text, default="")
    platforms: Mapped[str] = mapped_column(String(80), default="windows,macos,linux")
    notes: Mapped[str] = mapped_column(Text, default="")
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    versions = relationship("VersionCache", back_populates="software", cascade="all, delete-orphan")
    plans = relationship("InstallPlan", back_populates="software", cascade="all, delete-orphan")


class VersionCache(Base):
    __tablename__ = "version_cache"
    __table_args__ = (UniqueConstraint("software_id", "version", name="uq_software_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    software_id: Mapped[int] = mapped_column(ForeignKey("software.id"), index=True)
    version: Mapped[str] = mapped_column(String(80))
    channel: Mapped[str] = mapped_column(String(40), default="stable")
    is_latest_stable: Mapped[bool] = mapped_column(Boolean, default=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    software = relationship("Software", back_populates="versions")


class InstallPlan(Base):
    __tablename__ = "install_plans"
    __table_args__ = (
        UniqueConstraint("software_id", "version", "platform", name="uq_plan_soft_ver_plat"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    software_id: Mapped[int] = mapped_column(ForeignKey("software.id"), index=True)
    version: Mapped[str] = mapped_column(String(80), index=True)
    platform: Mapped[str] = mapped_column(String(20), index=True)
    markdown: Mapped[str] = mapped_column(Text)
    script: Mapped[str] = mapped_column(Text, default="")
    script_language: Mapped[str] = mapped_column(String(20), default="")
    official_url: Mapped[str] = mapped_column(String(500), default="")
    source: Mapped[str] = mapped_column(String(20), default="recipe")
    select_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    software = relationship("Software", back_populates="plans")
    feedbacks = relationship("Feedback", back_populates="plan", cascade="all, delete-orphan")


class Feedback(Base):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("install_plans.id"), index=True)
    is_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    comment: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    plan = relationship("InstallPlan", back_populates="feedbacks")


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
