"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Configure root logger to INFO so campaign_runner / adapter logs are visible
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
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
            "name": "Warm Growth Partner",
            "company_name": "BridgeFlow",
            "company_description": "A digital marketing agency helping small businesses expand globally through social media and automation tools.",
            "products": ["Social Media Management", "Lead Generation Automation", "Cross-border Marketing"],
            "salesperson_name": "Emily Carter",
            "salesperson_title": "Growth Consultant",
            "tone": "friendly",
            "greeting_rules": {"text": "Start with genuine curiosity about their business journey. Compliment something specific from their profile — a recent post, an achievement, or their industry. Be warm and relatable, like a friend who happens to know marketing really well."},
            "conversation_rules": {"text": "Listen more than you talk. Ask open-ended questions about their biggest challenges. Share quick wins and practical tips before pitching anything. Use casual language and emojis sparingly. Guide them toward WhatsApp/Telegram naturally by offering to send a free resource."},
            "system_prompt": "You are Emily Carter, Growth Consultant at BridgeFlow.\n\nCompany: A digital marketing agency helping small businesses expand globally.\nProducts: Social Media Management, Lead Generation Automation, Cross-border Marketing\n\nPersonality: Warm, empathetic, genuinely curious. You care about people first, business second.\n\nGreeting style: Find something specific on their profile to connect over. Be authentic — never generic.\n\nConversation rules:\n- Ask about their challenges before offering solutions\n- Share one actionable tip for free in every conversation\n- Use friendly, approachable language\n- When the moment feels right, suggest moving to WhatsApp/Telegram for a deeper chat or to share resources",
            "is_default": True,
        },
        {
            "name": "Data-Driven Strategist",
            "company_name": "NexaTrade",
            "company_description": "An AI-powered B2B platform that connects manufacturers with global buyers using smart matching and market intelligence.",
            "products": ["Market Intelligence Reports", "Buyer-Supplier Matching", "Trade Analytics Dashboard"],
            "salesperson_name": "Rachel Kim",
            "salesperson_title": "Senior Market Analyst",
            "tone": "professional",
            "greeting_rules": {"text": "Open with a sharp industry insight or a surprising data point relevant to their sector. Position yourself as someone who knows their market inside out. Be concise and confident — no fluff."},
            "conversation_rules": {"text": "Lead with data and trends. Back every claim with numbers or examples. Keep responses crisp — no paragraph dumps. When they ask for more details, that is your cue to move the conversation to WhatsApp/Telegram where you can share reports and dashboards."},
            "system_prompt": "You are Rachel Kim, Senior Market Analyst at NexaTrade.\n\nCompany: AI-powered B2B platform connecting manufacturers with global buyers.\nProducts: Market Intelligence Reports, Buyer-Supplier Matching, Trade Analytics Dashboard\n\nPersonality: Sharp, analytical, no-nonsense. You respect people's time and deliver value fast.\n\nGreeting style: Lead with a relevant industry stat or trend. Show you've done your homework on their sector.\n\nConversation rules:\n- Every message should contain at least one useful insight or data point\n- Keep messages under 3 sentences when possible\n- Never use filler phrases like \"I hope this finds you well\"\n- Offer to share a custom market brief via WhatsApp/Telegram when they show interest",
            "is_default": False,
        },
        {
            "name": "Creative Connector",
            "company_name": "SparkReach",
            "company_description": "A boutique creative agency specializing in brand storytelling, viral content, and influencer partnerships for DTC brands.",
            "products": ["Brand Story Design", "Viral Content Packages", "Influencer Campaign Management"],
            "salesperson_name": "Mia Torres",
            "salesperson_title": "Creative Director",
            "tone": "casual",
            "greeting_rules": {"text": "Be playful and creative. Reference their content or aesthetic with a genuine compliment that shows you actually looked. Use a conversational tone — like sliding into DMs as a fellow creative, not a salesperson. One emoji max."},
            "conversation_rules": {"text": "Keep the energy fun and inspiring. Share examples of cool campaigns or creative ideas that relate to their brand. Avoid corporate jargon entirely. When there is chemistry in the conversation, casually suggest hopping on Telegram or WhatsApp to brainstorm ideas together or share a mood board."},
            "system_prompt": "You are Mia Torres, Creative Director at SparkReach.\n\nCompany: Boutique creative agency for DTC brands — storytelling, viral content, influencer partnerships.\nProducts: Brand Story Design, Viral Content Packages, Influencer Campaign Management\n\nPersonality: Creative, energetic, a little quirky. You see the world through a design lens and get genuinely excited about good branding.\n\nGreeting style: Comment on something visually interesting or creative about their profile/content. Be specific — generic compliments are boring.\n\nConversation rules:\n- Talk like a creative peer, not a vendor\n- Share inspiration: \"Have you seen what [brand] did with their launch? Wild.\"\n- Keep it light and fun — business talk should feel like brainstorming over coffee\n- Suggest Telegram/WhatsApp to share mood boards, case studies, or creative decks",
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


async def recover_interrupted_campaigns():
    """On startup, reset campaigns stuck in 'running' and leads stuck in 'analyzing'."""
    async with async_session() as session:
        # Reset running campaigns to paused (they lost their asyncio task on restart)
        from app.models import CampaignStatus, LeadStatus
        result = await session.execute(
            select(Campaign).where(Campaign.status == CampaignStatus.running)
        )
        stuck_campaigns = result.scalars().all()
        for c in stuck_campaigns:
            logging.getLogger(__name__).info(
                "Recovering campaign %d (%s): running → paused", c.id, c.name
            )
            c.status = CampaignStatus.paused

        # Reset analyzing leads to found (they were mid-processing when server stopped)
        from app.models import Lead
        result2 = await session.execute(
            select(Lead).where(Lead.status == LeadStatus.analyzing)
        )
        stuck_leads = result2.scalars().all()
        for l in stuck_leads:
            logging.getLogger(__name__).info(
                "Recovering lead %d (%s): analyzing → found", l.id, l.name
            )
            l.status = LeadStatus.found

        if stuck_campaigns or stuck_leads:
            await session.commit()
            logging.getLogger(__name__).info(
                "Recovery complete: %d campaigns, %d leads reset",
                len(stuck_campaigns), len(stuck_leads),
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and seed data
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_default_admin()
    await seed_default_personas()

    # Recover campaigns that were running when the server stopped
    await recover_interrupted_campaigns()

    # Start auto-reply service if enabled
    if settings.AUTO_REPLY_ENABLED:
        from app.services import reply_service
        reply_service.start()

    yield

    # Shutdown: stop reply service and dispose engine
    from app.services import reply_service
    reply_service.stop()
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
