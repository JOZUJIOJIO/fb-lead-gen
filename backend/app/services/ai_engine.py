import json
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy-loaded Anthropic client
_anthropic_client = None


def _call_kimi(prompt: str, max_tokens: int = 500) -> str:
    """Call Kimi 2.5 API (OpenAI-compatible format)."""
    url = f"{settings.kimi_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.kimi_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.kimi_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    with httpx.Client(timeout=60) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


def _call_anthropic(prompt: str, max_tokens: int = 500) -> str:
    """Call Anthropic Claude API."""
    global _anthropic_client
    import anthropic

    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = _anthropic_client.messages.create(
        model="claude-sonnet-4-6-20260320",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def _call_openai(prompt: str, max_tokens: int = 500) -> str:
    """Call OpenAI GPT / Codex API (works with any OpenAI-compatible endpoint)."""
    url = f"{settings.openai_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openai_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    with httpx.Client(timeout=60) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


def _call_ai(prompt: str, max_tokens: int = 500) -> str:
    """Route to configured AI provider."""
    provider = settings.ai_provider.lower()

    # 按指定 provider 优先
    if provider == "kimi" and settings.kimi_api_key:
        return _call_kimi(prompt, max_tokens)
    elif provider == "openai" and settings.openai_api_key:
        return _call_openai(prompt, max_tokens)
    elif provider == "anthropic" and settings.anthropic_api_key:
        return _call_anthropic(prompt, max_tokens)
    # 自动回退：按优先级尝试所有可用的
    elif settings.openai_api_key:
        return _call_openai(prompt, max_tokens)
    elif settings.kimi_api_key:
        return _call_kimi(prompt, max_tokens)
    elif settings.anthropic_api_key:
        return _call_anthropic(prompt, max_tokens)
    else:
        raise ValueError("No AI API key configured. Set OPENAI_API_KEY, KIMI_API_KEY, or ANTHROPIC_API_KEY.")


def _parse_json_response(text: str) -> dict:
    """Extract JSON from AI response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def _load_persona(user_id: int | None = None) -> dict[str, Any] | None:
    """Load persona config for scoring context."""
    try:
        from app.database import SessionLocal
        from app.models import Persona
        db = SessionLocal()
        try:
            query = db.query(Persona)
            if user_id:
                query = query.filter(Persona.user_id == user_id)
            persona = query.first()
            if persona:
                return {
                    "company_name": persona.company_name or persona.company_name_en or "",
                    "products": persona.products or "",
                    "advantages": persona.advantages or [],
                    "description": persona.company_description or "",
                }
        finally:
            db.close()
    except Exception:
        pass
    return None


def analyze_lead(
    name: str,
    company: str,
    profile_data: dict[str, Any],
    email: str = "",
    user_id: int | None = None,
) -> dict:
    """Analyze a lead using AI and return score, analysis, and detected language.

    When a Persona is configured, scoring is tailored to the user's specific
    products and target market instead of using generic criteria.
    """
    if not settings.kimi_api_key and not settings.openai_api_key and not settings.anthropic_api_key:
        return {
            "score": 50,
            "analysis": "AI analysis unavailable — no API key configured. Set KIMI_API_KEY or ANTHROPIC_API_KEY.",
            "language": "en",
        }

    profile_str = json.dumps(profile_data, ensure_ascii=False) if profile_data else "No additional data"

    # Build persona-aware context
    persona = _load_persona(user_id)
    if persona and (persona.get("company_name") or persona.get("products")):
        seller_context = f"""Our company information:
- Company: {persona.get('company_name', '')}
- Products we sell: {persona.get('products', '')}
- Our advantages: {json.dumps(persona.get('advantages', []), ensure_ascii=False)}
- Description: {persona.get('description', '')}

Evaluate whether this lead is a good match for OUR specific products and business."""
        scoring_criteria = f"""Scoring criteria (tailored to our business):
- Does their company likely need our products ({persona.get('products', 'N/A')})?
- Are they in a relevant industry or supply chain for what we sell?
- Role seniority (decision-maker vs. junior)
- Geographic market fit for our products
- Any engagement signals (comments on trade posts, etc.)"""
    else:
        seller_context = "Context: A B2B export company wants to evaluate this potential buyer."
        scoring_criteria = """Scoring criteria:
- Company relevance to B2B importing/wholesale/distribution
- Role seniority (decision-maker vs. junior)
- Industry alignment
- Geographic market (emerging markets often have stronger demand)
- Any engagement signals (comments on trade posts, etc.)"""

    prompt = f"""Analyze this potential B2B buyer lead.

{seller_context}

Lead information:
- Name: {name}
- Company: {company}
- Email: {email}
- Additional profile data: {profile_str}

Please evaluate this lead and respond in JSON format with these fields:
1. "score": An intent score from 0-100 indicating how likely this person is a qualified buyer for our products.
   - 80-100: High priority - clear buyer signals matching our business
   - 60-79: Medium priority - some relevant signals present
   - 40-59: Low priority - limited signals but possible buyer
   - 0-39: Not a likely buyer for our products
2. "analysis": A 2-3 sentence analysis explaining your scoring rationale. Mention specific signals and how they relate to our business.
3. "language": The detected primary language of this person (ISO 639-1 code, e.g., "en", "es", "fr", "ar", "pt").
   Detect from their name, company name, and any profile data. Default to "en" if uncertain.

{scoring_criteria}

Respond ONLY with valid JSON, no other text."""

    try:
        response_text = _call_ai(prompt)
        result = _parse_json_response(response_text)
        return {
            "score": max(0, min(100, float(result.get("score", 50)))),
            "analysis": result.get("analysis", ""),
            "language": result.get("language", "en"),
        }
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        return {
            "score": 50,
            "analysis": f"AI analysis error: {str(e)}",
            "language": "en",
        }


def generate_message(
    lead_name: str,
    lead_company: str,
    lead_data: dict[str, Any],
    template_body: str,
    language: str = "en",
    user_id: int | None = None,
) -> str:
    """Generate a personalized outreach message using AI."""
    if not settings.kimi_api_key and not settings.openai_api_key and not settings.anthropic_api_key:
        return template_body.replace("{{name}}", lead_name).replace("{{company}}", lead_company)

    profile_str = json.dumps(lead_data, ensure_ascii=False) if lead_data else "No additional data"

    persona = _load_persona(user_id)
    if persona and persona.get("company_name"):
        seller_info = f"Our company: {persona['company_name']}. Products: {persona.get('products', '')}. Advantages: {json.dumps(persona.get('advantages', []), ensure_ascii=False)}"
    else:
        seller_info = "A B2B export company"

    prompt = f"""Generate a personalized outreach message for a B2B lead.

Context: {seller_info} wants to connect with this potential buyer.

Lead information:
- Name: {lead_name}
- Company: {lead_company}
- Additional data: {profile_str}

Message template to personalize:
{template_body}

Requirements:
1. Write the message in {language} language
2. Keep it professional but warm and conversational (WhatsApp style, not email style)
3. Personalize based on the lead's company and any available profile data
4. Include a clear reason why connecting would benefit them
5. Keep it under 200 words
6. End with a soft call-to-action (e.g., "Would you be open to a quick chat?")
7. Do NOT include any opt-out text (that will be added automatically)
8. Replace any {{{{variable}}}} placeholders with actual personalized content

Respond with ONLY the message text, no quotes or explanation."""

    try:
        return _call_ai(prompt, max_tokens=400)
    except Exception as e:
        logger.error(f"Message generation failed: {e}")
        return template_body.replace("{{name}}", lead_name).replace("{{company}}", lead_company)
