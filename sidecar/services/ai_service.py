"""Unified AI calling layer supporting multiple providers."""

import json
import logging

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class AIConfig:
    def __init__(self, provider: str, api_key: str, base_url: str | None = None):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_openai_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _build_anthropic_headers(api_key: str) -> dict:
    return {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }


def _persona_to_system_prompt(persona: dict) -> str:
    """Convert a persona dict into a coherent system prompt in Chinese."""
    if persona.get("system_prompt"):
        return persona["system_prompt"]

    parts: list[str] = []
    parts.append("你是一位专业的社交媒体销售代表，请严格按照以下人设进行对话。")

    if persona.get("salesperson_name"):
        parts.append(f"你的名字是{persona['salesperson_name']}。")
    if persona.get("salesperson_title"):
        parts.append(f"你的职位是{persona['salesperson_title']}。")
    if persona.get("company_name"):
        parts.append(f"你所在的公司是{persona['company_name']}。")
    if persona.get("company_description"):
        parts.append(f"公司简介：{persona['company_description']}")
    if persona.get("products"):
        products = persona["products"]
        if isinstance(products, list):
            parts.append(f"你负责的产品/服务：{'、'.join(str(p) for p in products)}")
        elif isinstance(products, dict):
            parts.append(f"你负责的产品/服务：{json.dumps(products, ensure_ascii=False)}")
    if persona.get("tone"):
        parts.append(f"说话风格：{persona['tone']}。")
    if persona.get("greeting_rules"):
        rules = persona["greeting_rules"]
        if isinstance(rules, list):
            parts.append("打招呼规则：" + "；".join(str(r) for r in rules))
        elif isinstance(rules, dict):
            parts.append(f"打招呼规则：{json.dumps(rules, ensure_ascii=False)}")
    if persona.get("conversation_rules"):
        rules = persona["conversation_rules"]
        if isinstance(rules, list):
            parts.append("对话规则：" + "；".join(str(r) for r in rules))
        elif isinstance(rules, dict):
            parts.append(f"对话规则：{json.dumps(rules, ensure_ascii=False)}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Provider-specific call functions
# ---------------------------------------------------------------------------

async def _call_openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Call any OpenAI-compatible API (OpenAI, Kimi, etc.)."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=_build_openai_headers(api_key), json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


async def _call_openai_compatible_multi(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
) -> str:
    """Call OpenAI-compatible API with a full messages list."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=_build_openai_headers(api_key), json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


async def _call_anthropic(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    url = "https://api.anthropic.com/v1/messages"
    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=_build_anthropic_headers(api_key), json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()


async def _call_anthropic_multi(
    api_key: str,
    model: str,
    system_prompt: str,
    messages: list[dict],
) -> str:
    url = "https://api.anthropic.com/v1/messages"
    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": system_prompt,
        "messages": messages,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=_build_anthropic_headers(api_key), json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()


# ---------------------------------------------------------------------------
# Router: pick the right provider
# ---------------------------------------------------------------------------

def _get_provider_config(config: AIConfig) -> tuple[str, str, str]:
    """Returns (provider, base_url, api_key) based on AIConfig."""
    provider = config.provider.lower()
    if provider == "kimi":
        return "kimi", "https://api.moonshot.cn/v1", config.api_key or ""
    elif provider == "anthropic":
        return "anthropic", "", config.api_key or ""
    else:
        # openai or any openai-compatible
        base = config.base_url or "https://api.openai.com/v1"
        return "openai", base, config.api_key or ""


def _default_model(provider: str) -> str:
    if provider == "anthropic":
        return "claude-sonnet-4-20250514"
    elif provider == "kimi":
        return "moonshot-v1-8k"
    return "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_greeting(profile_data: dict, persona: dict, config: AIConfig) -> str:
    """生成个性化的首次打招呼消息。

    Args:
        profile_data: 目标用户的资料 (name, bio, industry, interests, recent_topics).
        persona: 人设配置，字段对应 Persona 模型。
        config: AI provider configuration.
    """
    system_prompt = _persona_to_system_prompt(persona)

    user_prompt_parts = [
        "请根据以下目标用户信息，生成一条自然、个性化的首次打招呼私信。",
        "要求：不超过150字，语气真诚自然，不要过于推销，找到与对方的共同话题或切入点。",
        "",
        f"目标用户姓名：{profile_data.get('name', '未知')}",
    ]
    if profile_data.get("bio"):
        user_prompt_parts.append(f"个人简介：{profile_data['bio']}")
    if profile_data.get("industry"):
        user_prompt_parts.append(f"行业：{profile_data['industry']}")
    if profile_data.get("interests"):
        interests = profile_data["interests"]
        if isinstance(interests, list):
            user_prompt_parts.append(f"兴趣爱好：{'、'.join(interests)}")
        else:
            user_prompt_parts.append(f"兴趣爱好：{interests}")
    if profile_data.get("recent_topics"):
        topics = profile_data["recent_topics"]
        if isinstance(topics, list):
            user_prompt_parts.append(f"最近话题：{'、'.join(topics)}")
        else:
            user_prompt_parts.append(f"最近话题：{topics}")
    if profile_data.get("work"):
        user_prompt_parts.append(f"工作经历：{profile_data['work']}")
    if profile_data.get("education"):
        user_prompt_parts.append(f"教育背景：{profile_data['education']}")

    user_prompt = "\n".join(user_prompt_parts)

    provider, base_url, api_key = _get_provider_config(config)
    model = _default_model(provider)

    logger.info("generate_greeting: provider=%s, model=%s, target=%s", provider, model, profile_data.get("name"))

    if provider == "anthropic":
        return await _call_anthropic(api_key, model, system_prompt, user_prompt)
    else:
        return await _call_openai_compatible(base_url, api_key, model, system_prompt, user_prompt)


async def generate_reply(conversation_history: list, persona: dict, config: AIConfig) -> str:
    """根据对话上下文生成回复。

    Args:
        conversation_history: 消息列表，每条为 {"role": "user"|"assistant", "content": "..."}.
        persona: 人设配置。
        config: AI provider configuration.
    """
    system_prompt = _persona_to_system_prompt(persona)
    system_prompt += "\n\n请根据以上人设和下面的对话历史，生成一条合适的回复。保持对话自然流畅，不要生硬推销。"

    provider, base_url, api_key = _get_provider_config(config)
    model = _default_model(provider)

    logger.info("generate_reply: provider=%s, model=%s, history_len=%d", provider, model, len(conversation_history))

    if provider == "anthropic":
        # Anthropic requires alternating user/assistant messages
        messages = []
        for msg in conversation_history:
            role = msg.get("role", "user")
            if role not in ("user", "assistant"):
                role = "user"
            messages.append({"role": role, "content": msg["content"]})
        return await _call_anthropic_multi(api_key, model, system_prompt, messages)
    else:
        messages = [{"role": "system", "content": system_prompt}]
        for msg in conversation_history:
            role = msg.get("role", "user")
            if role not in ("user", "assistant", "system"):
                role = "user"
            messages.append({"role": role, "content": msg["content"]})
        return await _call_openai_compatible_multi(base_url, api_key, model, messages)


async def analyze_profile(raw_html: str, config: AIConfig) -> dict:
    """从个人资料页面 HTML 中提取结构化信息。

    Args:
        raw_html: 个人资料页面的 HTML 内容。
        config: AI provider configuration.

    Returns:
        dict with keys: name, bio, industry, interests, recent_topics
    """
    system_prompt = (
        "你是一个社交媒体资料分析助手。请从提供的 HTML 内容中提取用户的结构化信息。"
        "只返回 JSON 格式，不要附加任何解释文字。"
    )

    # Truncate HTML to avoid token limits (keep first ~8000 chars)
    truncated = raw_html[:8000] if len(raw_html) > 8000 else raw_html

    user_prompt = (
        "请从以下 HTML 中提取用户资料信息，返回 JSON 格式，包含以下字段：\n"
        '- name: 用户名\n'
        '- bio: 个人简介\n'
        '- industry: 所在行业\n'
        '- interests: 兴趣爱好（列表）\n'
        '- recent_topics: 最近讨论的话题（列表）\n'
        '- work: 工作经历\n'
        '- education: 教育背景\n'
        '- location: 所在地\n\n'
        f"HTML 内容：\n{truncated}"
    )

    provider, base_url, api_key = _get_provider_config(config)
    model = _default_model(provider)

    logger.info("analyze_profile: provider=%s, model=%s, html_len=%d", provider, model, len(raw_html))

    if provider == "anthropic":
        result_text = await _call_anthropic(api_key, model, system_prompt, user_prompt)
    else:
        result_text = await _call_openai_compatible(base_url, api_key, model, system_prompt, user_prompt)

    # Parse JSON from response (handle markdown code blocks)
    cleaned = result_text.strip()
    if cleaned.startswith("```"):
        # Remove ```json ... ``` wrapper
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("AI returned non-JSON for analyze_profile, returning raw text")
        return {
            "name": "",
            "bio": cleaned,
            "industry": "",
            "interests": [],
            "recent_topics": [],
        }


async def evaluate_intent(conversation: list, persona: dict, config: AIConfig) -> dict:
    """分析对话意图，决定下一步动作。

    Args:
        conversation: 对话历史，每条为 {"role": "user"|"assistant", "content": "..."}.
        persona: 人设配置。
        config: AI provider configuration.

    Returns:
        dict with keys:
          - action: "reply" | "transfer" | "stop"
          - reason: str — 决策原因
          - contact: str | None — 联系方式（transfer 时提取）
          - reply: str | None — 回复内容（action 为 reply 时）
    """
    transfer_conditions = ""
    if persona.get("transfer_conditions"):
        tc = persona["transfer_conditions"]
        if isinstance(tc, list):
            transfer_conditions = "转化条件：" + "；".join(str(c) for c in tc)
        elif isinstance(tc, str):
            transfer_conditions = f"转化条件：{tc}"
        else:
            transfer_conditions = f"转化条件：{json.dumps(tc, ensure_ascii=False)}"

    system_prompt = (
        "你是一个销售对话意图分析助手。请分析对话历史，判断潜在客户的意向，并决定下一步动作。\n\n"
        "可能的动作：\n"
        "- reply：继续对话，生成一条合适的回复\n"
        "- transfer：客户表现出强烈兴趣或已提供联系方式（Telegram/WhatsApp/微信等），应转交人工跟进\n"
        "- stop：客户明确拒绝或态度冷淡，停止继续联系\n\n"
        "请只返回 JSON 格式，包含以下字段：\n"
        '- action: "reply" | "transfer" | "stop"\n'
        "- reason: 决策原因（中文）\n"
        "- contact: 客户提供的联系方式（若有，否则为 null）\n"
        "- reply: 若 action 为 reply，生成的回复内容；否则为 null\n\n"
    )

    if transfer_conditions:
        system_prompt += transfer_conditions + "\n\n"

    system_prompt += _persona_to_system_prompt(persona)

    conversation_text = ""
    for msg in conversation:
        role_label = "客户" if msg.get("role") == "user" else "销售"
        conversation_text += f"{role_label}：{msg.get('content', '')}\n"

    user_prompt = f"请分析以下对话并返回 JSON 决策：\n\n{conversation_text}"

    provider, base_url, api_key = _get_provider_config(config)
    model = _default_model(provider)

    logger.info("evaluate_intent: provider=%s, model=%s, history_len=%d", provider, model, len(conversation))

    if provider == "anthropic":
        result_text = await _call_anthropic(api_key, model, system_prompt, user_prompt)
    else:
        result_text = await _call_openai_compatible(base_url, api_key, model, system_prompt, user_prompt)

    # Parse JSON from response (handle markdown code blocks)
    cleaned = result_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("AI returned non-JSON for evaluate_intent, defaulting to reply")
        return {
            "action": "reply",
            "reason": "无法解析 AI 返回结果，默认继续对话",
            "contact": None,
            "reply": result_text,
        }


async def generate_persona_from_description(description: str, config: AIConfig) -> dict:
    """根据自然语言描述生成完整的人设配置。

    Args:
        description: 自然语言描述，如"我向东南亚零售商销售家具"。
        config: AI provider configuration.

    Returns:
        dict with persona fields: name, company_name, company_description,
        salesperson_name, salesperson_title, tone, greeting_rules,
        conversation_rules, transfer_conditions, system_prompt
    """
    system_prompt = (
        "你是一个销售人设生成助手。根据用户提供的业务描述，生成一套完整的销售人设配置。\n\n"
        "请只返回 JSON 格式，包含以下字段：\n"
        "- name: 人设名称（简短，如"东南亚家具销售"）\n"
        "- company_name: 公司名称\n"
        "- company_description: 公司简介（1-2句话）\n"
        "- salesperson_name: 销售人员名字\n"
        "- salesperson_title: 职位头衔\n"
        "- tone: 说话风格（如"专业友好"、"轻松随和"）\n"
        "- greeting_rules: 打招呼规则（列表，每条为字符串）\n"
        "- conversation_rules: 对话规则（列表，每条为字符串）\n"
        "- transfer_conditions: 转化条件（列表，描述何时应转交人工跟进）\n"
        "- system_prompt: 完整的系统提示词（中文，综合以上所有信息）\n\n"
        "生成的人设应专业、自然，符合实际销售场景。"
    )

    user_prompt = f"请根据以下业务描述生成销售人设：\n\n{description}"

    provider, base_url, api_key = _get_provider_config(config)
    model = _default_model(provider)

    logger.info("generate_persona_from_description: provider=%s, model=%s", provider, model)

    if provider == "anthropic":
        result_text = await _call_anthropic(api_key, model, system_prompt, user_prompt)
    else:
        result_text = await _call_openai_compatible(base_url, api_key, model, system_prompt, user_prompt)

    # Parse JSON from response (handle markdown code blocks)
    cleaned = result_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("AI returned non-JSON for generate_persona_from_description, returning fallback")
        return {
            "name": "Custom Persona",
            "system_prompt": result_text,
        }
