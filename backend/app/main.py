import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext

from app.database import Base, engine, SessionLocal
from app.models import User
from app.routers import analytics, auth, campaigns, conversations, leads, messages, persona, templates

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

Base.metadata.create_all(bind=engine)


def seed_default_admin():
    """Create default admin account if it doesn't exist."""
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == "admin@leadflow.com").first():
            admin = User(
                email="admin@leadflow.com",
                hashed_password=pwd_context.hash("admin123456"),
                company_name="LeadFlow Demo",
            )
            db.add(admin)
            db.commit()
            logger.info("Default admin account created: admin@leadflow.com")
    finally:
        db.close()


seed_default_admin()

app = FastAPI(
    title="LeadFlow AI",
    description="Facebook-to-WhatsApp AI Lead Generation Platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(leads.router, prefix="/leads", tags=["Leads"])
app.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])
app.include_router(messages.router, prefix="/messages", tags=["Messages"])
app.include_router(templates.router, prefix="/templates", tags=["Templates"])
app.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])
app.include_router(persona.router, prefix="/persona", tags=["Persona"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
