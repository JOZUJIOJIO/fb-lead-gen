from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr


# --- Auth ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    company_name: str = ""


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    company_name: str
    wa_business_id: str
    plan: str
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Lead ---
class LeadCreate(BaseModel):
    name: str
    company: str = ""
    phone: str = ""
    email: str = ""
    telegram_username: str = ""
    source: str = "csv"
    source_url: str = ""
    source_detail: dict[str, Any] = {}
    industry: str = ""
    country: str = ""
    profile_data: dict[str, Any] = {}
    language: str = "en"


class LeadUpdate(BaseModel):
    name: str | None = None
    company: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str | None = None
    language: str | None = None
    profile_data: dict[str, Any] | None = None


class LeadResponse(BaseModel):
    id: int
    name: str
    company: str
    phone: str
    email: str
    source: str
    source_url: str
    telegram_username: str = ""
    source_detail: dict[str, Any] = {}
    industry: str = ""
    country: str = ""
    profile_data: dict[str, Any]
    score: float
    status: str
    language: str
    ai_analysis: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeadListResponse(BaseModel):
    items: list[LeadResponse]
    total: int
    page: int
    page_size: int


# --- Campaign ---
class CampaignCreate(BaseModel):
    name: str
    target_criteria: dict[str, Any] = {}
    message_template_id: int | None = None


class CampaignUpdate(BaseModel):
    name: str | None = None
    target_criteria: dict[str, Any] | None = None
    message_template_id: int | None = None
    status: str | None = None


class CampaignResponse(BaseModel):
    id: int
    name: str
    target_criteria: dict[str, Any]
    message_template_id: int | None
    status: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    sent_count: int = 0
    replied_count: int = 0

    model_config = {"from_attributes": True}


# --- Message ---
class MessageResponse(BaseModel):
    id: int
    lead_id: int
    campaign_id: int | None
    channel: str
    content: str
    mode: str
    approved_by_user: bool
    click_to_chat_link: str
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    replied_at: datetime | None
    status: str
    created_at: datetime
    lead_name: str = ""
    lead_company: str = ""

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    total: int
    page: int
    page_size: int


class MessageStats(BaseModel):
    total: int = 0
    draft: int = 0
    pending_approval: int = 0
    approved: int = 0
    sent: int = 0
    delivered: int = 0
    read: int = 0
    replied: int = 0
    failed: int = 0


# --- Template ---
class TemplateCreate(BaseModel):
    name: str
    body: str
    variables: list[str] = []
    language: str = "en"


class TemplateUpdate(BaseModel):
    name: str | None = None
    body: str | None = None
    variables: list[str] | None = None
    language: str | None = None


class TemplateResponse(BaseModel):
    id: int
    name: str
    body: str
    variables: list[str]
    language: str
    wa_approved: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Batch operations ---
class BatchIds(BaseModel):
    ids: list[int]


class ImportResult(BaseModel):
    total: int
    imported: int
    duplicates: int
    errors: int
    source: str = "csv"


class DataSourceInfo(BaseModel):
    id: str
    name: str
    description: str


# --- Conversation ---
class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: int
    lead_id: int
    profile_url: str
    stage: str
    intent_score: float
    intent_signals: list[str]
    turn_count: int
    max_turns: int
    whatsapp_pushed: bool
    our_company: str
    our_products: str
    created_at: datetime
    updated_at: datetime
    lead_name: str = ""
    lead_company: str = ""
    messages: list[ChatMessageResponse] = []
    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    lead_id: int
    profile_url: str
    our_company: str = ""
    our_products: str = ""


class ConversationUpdate(BaseModel):
    stage: str | None = None
    intent_score: float | None = None
    intent_signals: list[str] | None = None
    whatsapp_pushed: bool | None = None


class AddChatMessage(BaseModel):
    role: str  # "us" or "them"
    content: str


class ConversationStats(BaseModel):
    total: int = 0
    cold: int = 0
    curious: int = 0
    interested: int = 0
    qualified: int = 0
    ready_to_connect: int = 0
    converted: int = 0
    whatsapp_pushed: int = 0
