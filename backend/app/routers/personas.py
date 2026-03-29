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
