import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from app.database import Base


class LeadStatus(str, enum.Enum):
    new = "new"
    analyzed = "analyzed"
    contacted = "contacted"
    replied = "replied"
    converted = "converted"


class LeadSource(str, enum.Enum):
    csv = "csv"
    graph_api = "graph_api"


class CampaignStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    paused = "paused"
    completed = "completed"


class MessageStatus(str, enum.Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    sent = "sent"
    delivered = "delivered"
    read = "read"
    replied = "replied"
    failed = "failed"


class MessageMode(str, enum.Enum):
    click_to_chat = "click_to_chat"
    business_api = "business_api"


class UserPlan(str, enum.Enum):
    free = "free"
    basic = "basic"
    pro = "pro"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    company_name = Column(String(255), default="")
    wa_business_id = Column(String(255), default="")
    plan = Column(Enum(UserPlan), default=UserPlan.free)
    created_at = Column(DateTime, default=datetime.utcnow)

    leads = relationship("Lead", back_populates="user")
    campaigns = relationship("Campaign", back_populates="user")
    templates = relationship("Template", back_populates="user")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    company = Column(String(255), default="")
    phone = Column(String(50), default="")
    email = Column(String(255), default="")
    source = Column(Enum(LeadSource), default=LeadSource.csv)
    source_url = Column(String(500), default="")
    profile_data = Column(JSON, default=dict)
    score = Column(Float, default=0)
    status = Column(Enum(LeadStatus), default=LeadStatus.new, index=True)
    language = Column(String(10), default="en")
    ai_analysis = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="leads")
    messages = relationship("Message", back_populates="lead")

    __table_args__ = (
        Index("ix_leads_user_status", "user_id", "status"),
        Index("ix_leads_user_score", "user_id", "score"),
    )


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    target_criteria = Column(JSON, default=dict)
    message_template_id = Column(Integer, ForeignKey("templates.id"), nullable=True)
    status = Column(Enum(CampaignStatus), default=CampaignStatus.draft, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="campaigns")
    template = relationship("Template")
    messages = relationship("Message", back_populates="campaign")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    channel = Column(String(20), default="whatsapp")
    content = Column(Text, nullable=False)
    mode = Column(Enum(MessageMode), default=MessageMode.click_to_chat)
    approved_by_user = Column(Boolean, default=False)
    click_to_chat_link = Column(String(500), default="")
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    replied_at = Column(DateTime, nullable=True)
    status = Column(Enum(MessageStatus), default=MessageStatus.draft, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("Lead", back_populates="messages")
    campaign = relationship("Campaign", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_user_status", "user_id", "status"),
    )


class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    variables = Column(JSON, default=list)
    language = Column(String(10), default="en")
    wa_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="templates")


class Suppression(Base):
    __tablename__ = "suppressions"

    id = Column(Integer, primary_key=True, index=True)
    contact = Column(String(255), nullable=False, index=True)
    channel = Column(String(20), default="whatsapp")
    reason = Column(String(255), default="opt_out")
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)


class ConversationStage(str, enum.Enum):
    cold = "cold"
    curious = "curious"
    interested = "interested"
    qualified = "qualified"
    ready_to_connect = "ready_to_connect"
    converted = "converted"


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, unique=True)
    profile_url = Column(String(500), default="")
    stage = Column(Enum(ConversationStage), default=ConversationStage.cold)
    intent_score = Column(Float, default=0)
    intent_signals = Column(JSON, default=list)
    turn_count = Column(Integer, default=0)
    max_turns = Column(Integer, default=10)
    whatsapp_pushed = Column(Boolean, default=False)
    our_company = Column(String(255), default="")
    our_products = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    lead = relationship("Lead")
    chat_messages = relationship("ChatMessage", back_populates="conversation", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(10), nullable=False)  # "us" or "them"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="chat_messages")


class Persona(Base):
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(255), default="")
    company_name_en = Column(String(255), default="")
    company_description = Column(Text, default="")
    products = Column(String(500), default="")
    advantages = Column(JSON, default=list)
    website = Column(String(500), default="")
    sales_name = Column(String(100), default="Alex")
    sales_title = Column(String(100), default="International Sales Manager")
    personality = Column(Text, default="专业但友好，善于倾听客户需求，不急于推销")
    whatsapp = Column(String(50), default="")
    tone = Column(String(50), default="professional_friendly")
    max_message_length = Column(Integer, default=200)
    emoji_usage = Column(String(20), default="moderate")
    opening_rules = Column(JSON, default=list)
    conversation_rules = Column(JSON, default=list)
    whatsapp_push_rules = Column(JSON, default=list)
    positive_signals = Column(JSON, default=list)
    negative_signals = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
