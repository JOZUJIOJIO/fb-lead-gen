"""Personas router — CRUD for AI persona configurations."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Persona, User
from app.services.auth_service import get_current_user

router = APIRouter()


class PersonaCreate(BaseModel):
    name: str
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    products: Optional[list[str]] = None
    salesperson_name: Optional[str] = None
    salesperson_title: Optional[str] = None
    tone: str = "professional_friendly"
    greeting_rules: Optional[dict] = None
    conversation_rules: Optional[dict] = None
    system_prompt: Optional[str] = None
    output_language: str = "auto"
    whatsapp_id: Optional[str] = None
    telegram_id: Optional[str] = None
    is_default: bool = False


class PersonaResponse(BaseModel):
    id: int
    name: str
    company_name: Optional[str]
    company_description: Optional[str]
    products: Optional[list]
    salesperson_name: Optional[str]
    salesperson_title: Optional[str]
    tone: Optional[str]
    greeting_rules: Optional[dict]
    conversation_rules: Optional[dict]
    system_prompt: Optional[str]
    output_language: str
    whatsapp_id: Optional[str]
    telegram_id: Optional[str]
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.post("/", response_model=PersonaResponse, status_code=201)
async def create_persona(
    body: PersonaCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # If setting as default, unset previous default
    if body.is_default:
        result = await db.execute(select(Persona).where(Persona.is_default == True))
        for p in result.scalars().all():
            p.is_default = False

    persona = Persona(
        name=body.name,
        company_name=body.company_name,
        company_description=body.company_description,
        products=body.products,
        salesperson_name=body.salesperson_name,
        salesperson_title=body.salesperson_title,
        tone=body.tone,
        greeting_rules=body.greeting_rules,
        conversation_rules=body.conversation_rules,
        system_prompt=body.system_prompt,
        output_language=body.output_language,
        whatsapp_id=body.whatsapp_id,
        telegram_id=body.telegram_id,
        is_default=body.is_default,
    )
    db.add(persona)
    await db.commit()
    await db.refresh(persona)
    return persona


@router.get("/", response_model=list[PersonaResponse])
async def list_personas(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Persona).order_by(Persona.is_default.desc(), Persona.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    persona_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    if persona is None:
        raise HTTPException(status_code=404, detail="人设不存在")
    return persona


@router.put("/{persona_id}", response_model=PersonaResponse)
async def update_persona(
    persona_id: int,
    body: PersonaCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    if persona is None:
        raise HTTPException(status_code=404, detail="人设不存在")

    # If setting as default, unset previous default
    if body.is_default and not persona.is_default:
        result2 = await db.execute(select(Persona).where(Persona.is_default == True))
        for p in result2.scalars().all():
            p.is_default = False

    persona.name = body.name
    persona.company_name = body.company_name
    persona.company_description = body.company_description
    persona.products = body.products
    persona.salesperson_name = body.salesperson_name
    persona.salesperson_title = body.salesperson_title
    persona.tone = body.tone
    persona.greeting_rules = body.greeting_rules
    persona.conversation_rules = body.conversation_rules
    persona.system_prompt = body.system_prompt
    persona.output_language = body.output_language
    persona.whatsapp_id = body.whatsapp_id
    persona.telegram_id = body.telegram_id
    persona.is_default = body.is_default

    await db.commit()
    await db.refresh(persona)
    return persona


@router.delete("/{persona_id}", status_code=204)
async def delete_persona(
    persona_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    if persona is None:
        raise HTTPException(status_code=404, detail="人设不存在")
    await db.delete(persona)
    await db.commit()


class PersonaGenerateRequest(BaseModel):
    """Input for AI persona generation — user provides a brief description."""
    description: str  # e.g. "跨境电商行业，专业风格"


@router.post("/generate", response_model=PersonaCreate)
async def generate_persona_with_ai(
    body: PersonaGenerateRequest,
    user: User = Depends(get_current_user),
):
    """Use the configured AI to generate a complete persona from a brief description."""
    from app.services.ai_service import _get_provider_config, _default_model, _call_openai_compatible, _call_anthropic

    provider, base_url, api_key = _get_provider_config()
    if not api_key:
        raise HTTPException(status_code=400, detail="请先在设置中配置 AI API Key")

    model = _default_model(provider)

    system_prompt = "你是一个专业的销售人设设计师。根据用户描述，生成一个完整的 AI 销售代表人设配置。必须返回纯 JSON，不要包含 markdown。"

    user_prompt = f"""根据以下描述，生成一个完整的销售人设 JSON：

描述：{body.description}

要求返回的 JSON 格式（所有字段必须有值，不要留空）：
{{
  "name": "人设名称（4-8字，如：跨境电商专家）",
  "company_name": "公司名称",
  "company_description": "公司简介（1-2句话）",
  "products": ["产品1", "产品2", "产品3"],
  "salesperson_name": "一个合适的英文或中文名字",
  "salesperson_title": "职位头衔",
  "tone": "professional 或 friendly 或 professional_friendly 或 casual 四选一",
  "greeting_rules": {{"text": "打招呼策略（2-3句话）"}},
  "conversation_rules": {{"text": "对话策略（2-3句话）"}}
}}

只返回 JSON，不要任何其他文字。"""

    try:
        if provider == "anthropic":
            raw = await _call_anthropic(api_key, model, system_prompt, user_prompt)
        else:
            raw = await _call_openai_compatible(base_url, api_key, model, system_prompt, user_prompt)

        # Parse JSON from response (strip markdown fences if present)
        import json
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0]
        data = json.loads(clean)

        return PersonaCreate(
            name=data.get("name", "AI 生成人设"),
            company_name=data.get("company_name"),
            company_description=data.get("company_description"),
            products=data.get("products"),
            salesperson_name=data.get("salesperson_name"),
            salesperson_title=data.get("salesperson_title"),
            tone=data.get("tone", "professional_friendly"),
            greeting_rules=data.get("greeting_rules"),
            conversation_rules=data.get("conversation_rules"),
            system_prompt=None,
            is_default=False,
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI 返回格式错误，请重试")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 生成失败：{e}")
