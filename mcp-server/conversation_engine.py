"""
AI 对话引擎 — 10轮内完成客户意向判断和私域引流

流程:
1. 根据客户画像生成个性化打招呼消息
2. 管理多轮对话状态
3. 每轮对话后 AI 判断客户意向阶段
4. 10轮以内引导客户加 WhatsApp/Telegram
5. 识别到购买意向后立即推进

意向阶段:
  cold → curious → interested → qualified → ready_to_connect
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_BASE_URL = os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
KIMI_MODEL = os.environ.get("KIMI_MODEL", "kimi-latest")
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_CONTACT_NUMBER", "+8613800138000")

# 加载人设配置
PERSONA_FILE = Path(__file__).parent / "persona.json"
LEADFLOW_BASE_URL = os.environ.get("LEADFLOW_BASE_URL", "http://localhost:8000")
LEADFLOW_EMAIL = os.environ.get("LEADFLOW_EMAIL", "admin@leadflow.com")
LEADFLOW_PASSWORD = os.environ.get("LEADFLOW_PASSWORD", "admin123456")


def load_persona() -> dict:
    """从后端 API 加载人设，失败则回退到本地 persona.json。"""
    # 优先从后端 API 读取（网页后台设置的数据）
    try:
        with httpx.Client(base_url=LEADFLOW_BASE_URL, timeout=5) as client:
            token_resp = client.post("/auth/login", json={"email": LEADFLOW_EMAIL, "password": LEADFLOW_PASSWORD})
            token = token_resp.json().get("access_token", "")
            if token:
                resp = client.get("/persona", headers={"Authorization": f"Bearer {token}"})
                if resp.status_code == 200:
                    return resp.json()
    except Exception:
        pass

    # 回退到本地文件
    if PERSONA_FILE.exists():
        return json.loads(PERSONA_FILE.read_text(encoding="utf-8"))
    return {}

# 对话状态持久化
CONV_DIR = Path.home() / ".leadflow" / "conversations"
CONV_DIR.mkdir(parents=True, exist_ok=True)

MAX_TURNS = 10


# ============================================================
# 对话状态管理
# ============================================================

class ConversationState:
    """一个客户的对话状态。"""

    def __init__(self, lead_id: str, lead_name: str, lead_company: str = "",
                 lead_industry: str = "", lead_language: str = "en",
                 our_company: str = "", our_products: str = ""):
        self.lead_id = lead_id
        self.lead_name = lead_name
        self.lead_company = lead_company
        self.lead_industry = lead_industry
        self.lead_language = lead_language
        self.our_company = our_company
        self.our_products = our_products
        self.messages: list[dict] = []  # {"role": "us"/"them", "content": "...", "ts": ...}
        self.stage = "cold"  # cold → curious → interested → qualified → ready_to_connect → converted
        self.intent_score = 0  # 0-100
        self.intent_signals: list[str] = []
        self.whatsapp_sent = False
        self.created_at = time.time()
        self.turn_count = 0

    @property
    def file_path(self) -> Path:
        return CONV_DIR / f"{self.lead_id}.json"

    def save(self):
        data = {
            "lead_id": self.lead_id,
            "lead_name": self.lead_name,
            "lead_company": self.lead_company,
            "lead_industry": self.lead_industry,
            "lead_language": self.lead_language,
            "our_company": self.our_company,
            "our_products": self.our_products,
            "messages": self.messages,
            "stage": self.stage,
            "intent_score": self.intent_score,
            "intent_signals": self.intent_signals,
            "whatsapp_sent": self.whatsapp_sent,
            "created_at": self.created_at,
            "turn_count": self.turn_count,
        }
        self.file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    @classmethod
    def load(cls, lead_id: str) -> "ConversationState | None":
        path = CONV_DIR / f"{lead_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        state = cls(
            lead_id=data["lead_id"],
            lead_name=data["lead_name"],
            lead_company=data.get("lead_company", ""),
            lead_industry=data.get("lead_industry", ""),
            lead_language=data.get("lead_language", "en"),
            our_company=data.get("our_company", ""),
            our_products=data.get("our_products", ""),
        )
        state.messages = data.get("messages", [])
        state.stage = data.get("stage", "cold")
        state.intent_score = data.get("intent_score", 0)
        state.intent_signals = data.get("intent_signals", [])
        state.whatsapp_sent = data.get("whatsapp_sent", False)
        state.created_at = data.get("created_at", time.time())
        state.turn_count = data.get("turn_count", 0)
        return state

    def add_our_message(self, content: str):
        self.messages.append({"role": "us", "content": content, "ts": time.time()})
        self.turn_count += 1
        self.save()

    def add_their_reply(self, content: str):
        self.messages.append({"role": "them", "content": content, "ts": time.time()})
        self.save()

    def get_chat_history_text(self) -> str:
        lines = []
        for msg in self.messages:
            who = "我方" if msg["role"] == "us" else "客户"
            lines.append(f"{who}: {msg['content']}")
        return "\n".join(lines)


# ============================================================
# AI 对话生成
# ============================================================

def _call_kimi(prompt: str, max_tokens: int = 800) -> str:
    """调用 Kimi API。"""
    if not KIMI_API_KEY:
        raise ValueError("KIMI_API_KEY not configured")
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{KIMI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {KIMI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": KIMI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


def generate_opening_message(state: ConversationState) -> str:
    """生成第一条打招呼消息，基于 persona.json 配置。"""
    persona = load_persona()
    company = persona.get("company", {})
    sales = persona.get("salesperson", {})
    style = persona.get("conversation_style", {})
    opening_rules = style.get("opening_rules", [])

    prompt = f"""你是一个专业的B2B外贸业务开发人员。

## 你的身份
- 姓名: {sales.get('name', 'Alex')}
- 职位: {sales.get('title', 'Sales Manager')}
- 性格: {sales.get('personality', '专业但友好')}
- 公司: {company.get('name_en', state.our_company) or '一家中国领先的制造商'}
- 产品: {company.get('products', state.our_products) or '各类工业品和消费品'}
- 公司优势: {', '.join(company.get('advantages', []))}

## 目标客户
- 姓名: {state.lead_name}
- 公司: {state.lead_company or '未知'}
- 行业: {state.lead_industry or '未知'}

## 打招呼规则
{chr(10).join(f'- {r}' for r in opening_rules) if opening_rules else '- 简短友好，2-3句话，以问题结尾'}

## 语气
- 风格: {style.get('tone', 'professional_friendly')}
- 消息长度: 不超过{style.get('max_message_length', 200)}字
- 语言: 用 {state.lead_language} 语言

只输出消息内容，不要任何解释。"""

    return _call_kimi(prompt, max_tokens=300)


def generate_reply(state: ConversationState, their_message: str) -> dict:
    """根据对话历史和客户最新消息，生成回复。

    Returns:
        {
            "reply": str,          # 回复内容
            "stage": str,          # 意向阶段
            "intent_score": int,   # 意向分 0-100
            "intent_signals": [],  # 发现的意向信号
            "should_push_whatsapp": bool,  # 是否该推WhatsApp了
            "analysis": str,       # 分析说明
        }
    """
    persona = load_persona()
    company = persona.get("company", {})
    sales = persona.get("salesperson", {})
    style = persona.get("conversation_style", {})
    conv_rules = style.get("conversation_rules", [])
    wa_rules = style.get("whatsapp_push_rules", [])
    scoring = persona.get("intent_scoring", {})
    wa_number = sales.get("whatsapp", WHATSAPP_NUMBER)

    history = state.get_chat_history_text()

    prompt = f"""你是一个B2B外贸业务开发AI助手，正在和一个潜在海外客户对话。

## 你的身份
- 姓名: {sales.get('name', 'Alex')}
- 职位: {sales.get('title', 'Sales Manager')}
- 性格: {sales.get('personality', '专业但友好')}
- 公司: {company.get('name_en', state.our_company) or '一家中国制造商'}
- 产品: {company.get('products', state.our_products) or '各类工业品和消费品'}
- 公司优势: {', '.join(company.get('advantages', []))}

## 客户信息
- 姓名: {state.lead_name}
- 公司: {state.lead_company or '未知'}
- 行业: {state.lead_industry or '未知'}

## 对话历史
{history}

## 客户最新消息
客户: {their_message}

## 当前状态
- 对话轮次: {state.turn_count}/{MAX_TURNS}
- 当前意向阶段: {state.stage}
- 已知意向信号: {json.dumps(state.intent_signals, ensure_ascii=False)}

## 对话规则
{chr(10).join(f'- {r}' for r in conv_rules) if conv_rules else '- 自然对话，每条消息只问一个问题'}

## 你的任务

### 1. 分析客户意向
判断客户处于哪个阶段:
- cold: 还没有兴趣，只是礼貌回复
- curious: 开始好奇，问了一些问题
- interested: 表达了具体需求或兴趣
- qualified: 确认有采购需求、预算或决策权
- ready_to_connect: 愿意深入交流，可以推WhatsApp了

意向加分信号: {json.dumps([s['signal'] for s in scoring.get('signals_positive', [])], ensure_ascii=False)}
意向减分信号: {json.dumps([s['signal'] for s in scoring.get('signals_negative', [])], ensure_ascii=False)}

### 2. 生成回复
- 用 {state.lead_language} 语言
- 风格: {style.get('tone', 'professional_friendly')}
- 消息长度不超过 {style.get('max_message_length', 200)} 字
- 根据意向阶段调整策略:
  * cold/curious: 多问问题了解需求，不急着推销
  * interested: 给出有价值的信息，建立专业形象
  * qualified: 提供具体方案
  * ready_to_connect: 引导加WhatsApp，号码是 {wa_number}

### 3. 推WhatsApp规则
{chr(10).join(f'- {r}' for r in wa_rules) if wa_rules else '- 客户表达具体采购意向时推WhatsApp'}

请返回JSON格式:
{{
    "reply": "你的回复内容",
    "stage": "当前意向阶段",
    "intent_score": 0到100的意向分,
    "intent_signals": ["发现的意向信号列表"],
    "should_push_whatsapp": true或false,
    "analysis": "一句话分析当前状况"
}}

只返回JSON，不要其他内容。"""

    try:
        text = _call_kimi(prompt, max_tokens=600)
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        result = json.loads(text)

        # 如果该推WhatsApp了，在回复中加入联系方式
        if result.get("should_push_whatsapp") and WHATSAPP_NUMBER:
            reply = result["reply"]
            if WHATSAPP_NUMBER not in reply and "whatsapp" not in reply.lower():
                reply += f"\n\nBy the way, feel free to reach me on WhatsApp for quicker response: {WHATSAPP_NUMBER}"
                result["reply"] = reply

        return result
    except Exception as e:
        logger.error(f"AI reply generation failed: {e}")
        return {
            "reply": "Thanks for your message! Could you tell me more about your needs?",
            "stage": state.stage,
            "intent_score": state.intent_score,
            "intent_signals": state.intent_signals,
            "should_push_whatsapp": False,
            "analysis": f"AI error: {str(e)}",
        }


def get_conversation_summary(state: ConversationState) -> str:
    """生成对话摘要。"""
    if not state.messages:
        return "尚未开始对话。"

    stage_labels = {
        "cold": "❄️ 冷淡",
        "curious": "🤔 好奇",
        "interested": "👀 感兴趣",
        "qualified": "✅ 已确认需求",
        "ready_to_connect": "🔥 准备转私域",
        "converted": "🎉 已转化",
    }

    lines = [
        f"📊 与 {state.lead_name} 的对话摘要",
        f"{'='*40}",
        f"公司: {state.lead_company or '未知'}",
        f"轮次: {state.turn_count}/{MAX_TURNS}",
        f"意向: {stage_labels.get(state.stage, state.stage)}",
        f"评分: {state.intent_score}/100",
        f"WhatsApp已推送: {'是' if state.whatsapp_sent else '否'}",
    ]

    if state.intent_signals:
        lines.append(f"意向信号: {', '.join(state.intent_signals)}")

    lines.append(f"\n最近对话:")
    for msg in state.messages[-6:]:
        who = "→ 我方" if msg["role"] == "us" else "← 客户"
        content = msg["content"][:80] + ("..." if len(msg["content"]) > 80 else "")
        lines.append(f"  {who}: {content}")

    return "\n".join(lines)


def list_active_conversations() -> list[dict]:
    """列出所有活跃对话。"""
    conversations = []
    for f in CONV_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            conversations.append({
                "lead_id": data["lead_id"],
                "lead_name": data["lead_name"],
                "lead_company": data.get("lead_company", ""),
                "stage": data.get("stage", "cold"),
                "turn_count": data.get("turn_count", 0),
                "intent_score": data.get("intent_score", 0),
                "whatsapp_sent": data.get("whatsapp_sent", False),
                "last_message": data["messages"][-1]["content"][:50] if data.get("messages") else "",
            })
        except Exception:
            continue

    conversations.sort(key=lambda x: x["intent_score"], reverse=True)
    return conversations
