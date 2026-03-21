from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import auth, campaigns, conversations, leads, messages, persona, templates

Base.metadata.create_all(bind=engine)

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


@app.get("/health")
def health_check():
    return {"status": "ok"}
