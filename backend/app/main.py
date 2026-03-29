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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and seed data
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_default_admin()
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
