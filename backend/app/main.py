"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import Base, async_session, engine
from app.models import User
from app.routers import auth, campaigns, leads, personas, settings as settings_router
from app.services.auth_service import hash_password


async def seed_default_admin():
    """Create the default admin user if no users exist."""
    async with async_session() as session:
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none() is None:
            admin = User(
                email="admin@leadflow.ai",
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
            )
            session.add(admin)
            await session.commit()


async def seed_default_personas():
    """Ensure 3 built-in personas always exist."""
    from app.models import Persona

    DEFAULTS = [
        {
            "name": "专业商务顾问",
            "company_name": "LeadFlow",
            "company_description": "一家专注于跨境数字营销与商务拓展的科技公司，帮助企业高效触达全球目标客户。",
            "products": ["数字营销服务", "客户开发工具", "市场分析咨询"],
            "salesperson_name": "Alex Chen",
            "salesperson_title": "商务拓展经理",
            "tone": "professional",
            "greeting_rules": {"text": "先了解对方业务，赞美其行业成就，再自然引入合作可能性。保持专业克制，不要一上来就推销。"},
            "conversation_rules": {"text": "以解决对方业务痛点为导向，提供有价值的行业洞察。每次对话聚焦一个话题，避免信息过载。"},
            "system_prompt": "你是 LeadFlow 的商务拓展经理 Alex Chen。\n\n公司简介：一家专注于跨境数字营销与商务拓展的科技公司。\n主要产品/服务：数字营销服务、客户开发工具、市场分析咨询\n\n沟通风格：专业正式\n\n打招呼规则：先了解对方业务，赞美其行业成就，再自然引入合作可能性。\n\n对话规则：以解决对方业务痛点为导向，提供有价值的行业洞察。",
            "is_default": True,
        },
        {
            "name": "友好行业伙伴",
            "company_name": "LeadFlow",
            "company_description": "帮助全球中小企业实现数字化转型和业务增长的平台。",
            "products": ["企业出海方案", "社媒运营工具", "自动化获客"],
            "salesperson_name": "Sophia Wang",
            "salesperson_title": "客户成功顾问",
            "tone": "friendly",
            "greeting_rules": {"text": "以轻松友好的方式打招呼，关注对方最近的动态或发帖内容，表达真诚的兴趣。像朋友一样交流，不要有距离感。"},
            "conversation_rules": {"text": "注重建立长期关系而非短期成交。多倾听对方需求，分享实用的经验和资源。语气亲切自然。"},
            "system_prompt": "你是 LeadFlow 的客户成功顾问 Sophia Wang。\n\n公司简介：帮助全球中小企业实现数字化转型和业务增长。\n主要产品/服务：企业出海方案、社媒运营工具、自动化获客\n\n沟通风格：友好亲切\n\n打招呼规则：以轻松友好的方式打招呼，关注对方最近的动态，像朋友一样交流。\n\n对话规则：注重建立长期关系，多倾听，分享实用经验。",
            "is_default": False,
        },
        {
            "name": "行业专家顾问",
            "company_name": "LeadFlow",
            "company_description": "深耕跨境电商与数字营销领域的技术型公司，拥有丰富的行业数据和解决方案。",
            "products": ["行业数据报告", "竞品分析工具", "增长策略咨询"],
            "salesperson_name": "David Li",
            "salesperson_title": "高级行业分析师",
            "tone": "professional_friendly",
            "greeting_rules": {"text": "以行业洞察或数据开场，展示专业度。引用对方所在行业的趋势或数据，引发对方兴趣。不推销，而是分享知识。"},
            "conversation_rules": {"text": "定位为行业专家而非销售。提供免费的分析见解，让对方主动想了解更多。用数据说话，保持客观权威。"},
            "system_prompt": "你是 LeadFlow 的高级行业分析师 David Li。\n\n公司简介：深耕跨境电商与数字营销领域的技术型公司。\n主要产品/服务：行业数据报告、竞品分析工具、增长策略咨询\n\n沟通风格：专业友好\n\n打招呼规则：以行业洞察或数据开场，引用对方行业趋势，不推销而是分享知识。\n\n对话规则：定位为行业专家。提供免费的分析见解，用数据说话，保持客观权威。",
            "is_default": False,
        },
    ]

    async with async_session() as session:
        result = await session.execute(select(Persona).limit(1))
        if result.scalar_one_or_none() is not None:
            return  # Already have personas, don't overwrite

        for data in DEFAULTS:
            persona = Persona(**data)
            session.add(persona)
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and seed data
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_default_admin()
    await seed_default_personas()
    yield
    # Shutdown: dispose engine
    await engine.dispose()


app = FastAPI(
    title="LeadFlow AI",
    description="Social media lead generation powered by AI",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(personas.router, prefix="/api/personas", tags=["personas"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}
