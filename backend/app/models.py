"""SQLAlchemy ORM models."""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------- Enums ----------

class PlatformEnum(str, enum.Enum):
    facebook = "facebook"
    twitter = "twitter"
    instagram = "instagram"


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    stopped = "stopped"


class LeadStatus(str, enum.Enum):
    found = "found"
    analyzing = "analyzing"
    pending_review = "pending_review"
    messaged = "messaged"
    replied = "replied"
    converted = "converted"
    rejected = "rejected"
    failed = "failed"
    blacklisted = "blacklisted"  # 永久跳过：非活跃/无法私信/被平台限制


class MessageDirection(str, enum.Enum):
    outbound = "outbound"
    inbound = "inbound"


# ---------- Models ----------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=True)
    company_description: Mapped[str] = mapped_column(Text, nullable=True)
    products: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    salesperson_name: Mapped[str] = mapped_column(String(100), nullable=True)
    salesperson_title: Mapped[str] = mapped_column(String(100), nullable=True)
    tone: Mapped[str] = mapped_column(String(50), nullable=True)
    greeting_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    conversation_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_language: Mapped[str] = mapped_column(String(20), default="auto", nullable=False)
    whatsapp_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    telegram_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="persona")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=True)
    platform: Mapped[PlatformEnum] = mapped_column(
        Enum(PlatformEnum, name="platform_enum"), nullable=False
    )
    search_keywords: Mapped[str] = mapped_column(String(500), nullable=True)
    search_region: Mapped[str] = mapped_column(String(100), nullable=True)
    search_industry: Mapped[str] = mapped_column(String(100), nullable=True)
    persona_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("personas.id", ondelete="SET NULL"), nullable=True
    )
    send_limit: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    max_per_hour: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    review_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    send_hour_start: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    send_hour_end: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Shanghai", nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status_enum"),
        default=CampaignStatus.draft,
        nullable=False,
    )
    progress_current: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    persona: Mapped["Persona | None"] = relationship(back_populates="campaigns")
    leads: Mapped[list["Lead"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_campaigns_status", "status"),
        Index("ix_campaigns_platform", "platform"),
    )


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[PlatformEnum] = mapped_column(
        Enum(PlatformEnum, name="platform_enum", create_type=False), nullable=False
    )
    platform_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    profile_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status_enum"),
        default=LeadStatus.found,
        nullable=False,
    )
    raw_profile_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="leads")
    messages: Mapped[list["Message"]] = relationship(back_populates="lead", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_leads_campaign_id", "campaign_id"),
        Index("ix_leads_status", "status"),
        Index("ix_leads_platform_user_id", "platform_user_id"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, name="message_direction_enum"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lead: Mapped["Lead"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_messages_lead_id", "lead_id"),
    )
