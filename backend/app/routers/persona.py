from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Persona, User
from app.routers.auth import get_current_user

router = APIRouter()

DEFAULT_OPENING_RULES = [
    "第一条消息不超过3句话",
    "提到一个具体的合作切入点",
    "以轻松的问题结尾引导对方回复",
    "绝对不要在第一条消息推销产品或提WhatsApp",
]

DEFAULT_CONVERSATION_RULES = [
    "每条消息只问一个问题",
    "先了解客户需求再介绍产品",
    "用客户的语言回复（英语客户用英语，西语客户用西语）",
    "提到价格时给一个范围而不是具体数字",
    "不要主动提折扣，除非客户讨价还价",
    "当客户问到技术细节时展示专业性",
]

DEFAULT_WA_RULES = [
    "至少对话3轮以上才考虑推WhatsApp",
    "客户表达了具体采购意向才推",
    "推的时候说'方便的话加个WhatsApp详聊'，不要太强硬",
    "如果客户拒绝加WhatsApp，不要再推，继续在当前渠道聊",
]

DEFAULT_POSITIVE_SIGNALS = [
    {"signal": "询问价格/报价", "score_boost": 20},
    {"signal": "询问MOQ/最低起订量", "score_boost": 20},
    {"signal": "询问样品", "score_boost": 15},
    {"signal": "提到具体产品型号", "score_boost": 15},
    {"signal": "提到采购计划/时间", "score_boost": 25},
    {"signal": "询问交货期", "score_boost": 15},
    {"signal": "询问付款方式", "score_boost": 20},
    {"signal": "主动要联系方式", "score_boost": 30},
]

DEFAULT_NEGATIVE_SIGNALS = [
    {"signal": "明确说不需要", "score_penalty": -30},
    {"signal": "只是礼貌回复无实质内容", "score_penalty": -5},
    {"signal": "长时间不回复", "score_penalty": -10},
]


def _get_or_create(db: Session, user: User) -> Persona:
    persona = db.query(Persona).filter(Persona.user_id == user.id).first()
    if not persona:
        persona = Persona(
            user_id=user.id,
            opening_rules=DEFAULT_OPENING_RULES,
            conversation_rules=DEFAULT_CONVERSATION_RULES,
            whatsapp_push_rules=DEFAULT_WA_RULES,
            positive_signals=DEFAULT_POSITIVE_SIGNALS,
            negative_signals=DEFAULT_NEGATIVE_SIGNALS,
        )
        db.add(persona)
        db.commit()
        db.refresh(persona)
    return persona


def _to_dict(p: Persona) -> dict:
    return {
        "id": p.id,
        "company": {
            "name": p.company_name,
            "name_en": p.company_name_en,
            "description": p.company_description,
            "products": p.products,
            "advantages": p.advantages or [],
            "website": p.website,
        },
        "salesperson": {
            "name": p.sales_name,
            "title": p.sales_title,
            "personality": p.personality,
            "whatsapp": p.whatsapp,
        },
        "conversation_style": {
            "tone": p.tone,
            "max_message_length": p.max_message_length,
            "emoji_usage": p.emoji_usage,
            "opening_rules": p.opening_rules or [],
            "conversation_rules": p.conversation_rules or [],
            "whatsapp_push_rules": p.whatsapp_push_rules or [],
        },
        "intent_scoring": {
            "signals_positive": p.positive_signals or [],
            "signals_negative": p.negative_signals or [],
        },
        "updated_at": p.updated_at.isoformat() if p.updated_at else "",
    }


@router.get("")
def get_persona(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    persona = _get_or_create(db, current_user)
    return _to_dict(persona)


@router.put("")
def update_persona(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    persona = _get_or_create(db, current_user)

    # 公司信息
    company = data.get("company", {})
    if "name" in company:
        persona.company_name = company["name"]
    if "name_en" in company:
        persona.company_name_en = company["name_en"]
    if "description" in company:
        persona.company_description = company["description"]
    if "products" in company:
        persona.products = company["products"]
    if "advantages" in company:
        persona.advantages = company["advantages"]
    if "website" in company:
        persona.website = company["website"]

    # 销售人设
    sales = data.get("salesperson", {})
    if "name" in sales:
        persona.sales_name = sales["name"]
    if "title" in sales:
        persona.sales_title = sales["title"]
    if "personality" in sales:
        persona.personality = sales["personality"]
    if "whatsapp" in sales:
        persona.whatsapp = sales["whatsapp"]

    # 对话风格
    style = data.get("conversation_style", {})
    if "tone" in style:
        persona.tone = style["tone"]
    if "max_message_length" in style:
        persona.max_message_length = style["max_message_length"]
    if "emoji_usage" in style:
        persona.emoji_usage = style["emoji_usage"]
    if "opening_rules" in style:
        persona.opening_rules = style["opening_rules"]
    if "conversation_rules" in style:
        persona.conversation_rules = style["conversation_rules"]
    if "whatsapp_push_rules" in style:
        persona.whatsapp_push_rules = style["whatsapp_push_rules"]

    # 意向评分
    scoring = data.get("intent_scoring", {})
    if "signals_positive" in scoring:
        persona.positive_signals = scoring["signals_positive"]
    if "signals_negative" in scoring:
        persona.negative_signals = scoring["signals_negative"]

    db.commit()
    db.refresh(persona)
    return _to_dict(persona)
