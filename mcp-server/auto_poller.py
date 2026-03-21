"""
自动轮询器 — 每5分钟检查 Facebook 新回复并自动 AI 回复

运行方式:
  python auto_poller.py                # 默认5分钟间隔
  python auto_poller.py --interval 3   # 自定义间隔（分钟）
  python auto_poller.py --once         # 只执行一次

可以和 MCP Server 同时运行，互不冲突。
MCP Server 负责手动触发（用户在 WhatsApp 说"检查回复"），
auto_poller 负责后台自动轮询。
"""

import asyncio
import argparse
import json
import logging
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

# 添加当前目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from conversation_engine import (
    ConversationState,
    generate_reply,
    list_active_conversations,
    MAX_TURNS,
)

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("poller")

STATE_DIR = Path.home() / ".leadflow" / "fb-state"
CHROME_DATA = STATE_DIR / "chrome-data"
LOG_FILE = STATE_DIR / "poller.log"

LEADFLOW_BASE_URL = os.environ.get("LEADFLOW_BASE_URL", "http://localhost:8000")
LEADFLOW_EMAIL = os.environ.get("LEADFLOW_EMAIL", "admin@leadflow.com")
LEADFLOW_PASSWORD = os.environ.get("LEADFLOW_PASSWORD", "admin123456")

_api_token: str | None = None


def _get_api_token() -> str:
    global _api_token
    if _api_token:
        return _api_token
    with httpx.Client(base_url=LEADFLOW_BASE_URL, timeout=10) as client:
        resp = client.post("/auth/login", json={"email": LEADFLOW_EMAIL, "password": LEADFLOW_PASSWORD})
        resp.raise_for_status()
        _api_token = resp.json()["access_token"]
        return _api_token


def sync_to_backend(lead_id: str, state: ConversationState, new_reply: str, our_reply: str):
    """把对话数据同步到后端数据库。"""
    try:
        token = _get_api_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        with httpx.Client(base_url=LEADFLOW_BASE_URL, timeout=10) as client:
            # 查找对应的 conversation
            convs = client.get("/conversations", headers=headers).json()
            conv_id = None
            for c in convs:
                if str(c["lead_id"]) == str(lead_id):
                    conv_id = c["id"]
                    break

            if conv_id:
                # 添加客户回复消息
                client.post(f"/conversations/{conv_id}/messages", headers=headers,
                            json={"role": "them", "content": new_reply})
                # 添加我方回复消息
                client.post(f"/conversations/{conv_id}/messages", headers=headers,
                            json={"role": "us", "content": our_reply})
                # 更新对话状态
                client.put(f"/conversations/{conv_id}", headers=headers,
                           json={
                               "stage": state.stage,
                               "intent_score": state.intent_score,
                               "intent_signals": state.intent_signals,
                               "whatsapp_pushed": state.whatsapp_sent,
                           })
                logger.info(f"    📡 已同步到后端 (conversation #{conv_id})")
            else:
                logger.warning(f"    ⚠️ 后端未找到对应对话记录 (lead_id={lead_id})")
    except Exception as e:
        logger.warning(f"    ⚠️ 同步失败: {str(e)[:50]}")


def log_event(event: str):
    """记录轮询日志。"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {event}\n")


async def poll_once():
    """执行一次轮询：检查所有活跃对话的新回复。"""
    convos = list_active_conversations()
    active = [c for c in convos if c["turn_count"] < MAX_TURNS]

    if not active:
        logger.info("没有活跃对话，跳过本轮")
        return {"checked": 0, "replied": 0, "errors": 0}

    logger.info(f"检查 {len(active)} 个活跃对话...")

    pw = await async_playwright().start()
    context = await pw.chromium.launch_persistent_context(
        user_data_dir=str(CHROME_DATA),
        headless=False,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        viewport={"width": 1280, "height": 900},
    )
    page = context.pages[0] if context.pages else await context.new_page()

    checked = 0
    replied = 0
    errors = 0

    for conv_info in active:
        lead_id = conv_info["lead_id"]
        state = ConversationState.load(str(lead_id))
        if not state:
            continue

        # 需要 profile_url 来访问对话
        # 从对话文件中获取（如果有的话）
        conv_file = Path.home() / ".leadflow" / "conversations" / f"{lead_id}.json"
        if not conv_file.exists():
            continue

        conv_data = json.loads(conv_file.read_text())
        # profile_url 可能存在 messages 或其他字段中
        # 我们用 lead_id 构造 messenger URL
        profile_url = ""
        for msg in state.messages:
            if "profile_url" in str(msg):
                break

        # 从 LeadFlow API 获取 profile_url
        try:
            token = _get_api_token()
            with httpx.Client(base_url=LEADFLOW_BASE_URL, timeout=10) as client:
                lead_resp = client.get(f"/leads/{lead_id}",
                                       headers={"Authorization": f"Bearer {token}"})
                if lead_resp.status_code == 200:
                    lead_data = lead_resp.json()
                    profile_url = lead_data.get("source_url", "")
        except Exception:
            pass

        if not profile_url:
            continue

        checked += 1
        logger.info(f"  检查 [{lead_id}] {state.lead_name}...")

        try:
            # 从 profile URL 提取用户名
            username = profile_url.rstrip("/").split("/")[-1].split("?")[0]
            messenger_url = f"https://www.facebook.com/messages/t/{username}"
            await page.goto(messenger_url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(4000)

            # 读取最新消息
            # 获取所有消息气泡
            all_msgs = await page.query_selector_all('div[dir="auto"]')
            latest_texts = []
            for msg_el in all_msgs[-10:]:
                try:
                    text = (await msg_el.inner_text()).strip()
                    if text and len(text) > 1 and len(text) < 500:
                        latest_texts.append(text)
                except Exception:
                    continue

            # 检查是否有新消息（不在已有记录中的）
            existing_contents = {m["content"] for m in state.messages}
            new_reply = None
            for text in reversed(latest_texts):
                if text not in existing_contents:
                    # 检查是否是对方发的（不是我们发的）
                    our_msgs = {m["content"] for m in state.messages if m["role"] == "us"}
                    if text not in our_msgs:
                        new_reply = text
                        break

            if not new_reply:
                logger.info(f"    暂无新回复")
                continue

            logger.info(f"    💬 收到回复: {new_reply[:50]}...")
            state.add_their_reply(new_reply)

            # AI 生成回复
            result = generate_reply(state, new_reply)
            our_reply = result["reply"]
            state.stage = result["stage"]
            state.intent_score = result["intent_score"]
            state.intent_signals = result.get("intent_signals", [])

            if result.get("should_push_whatsapp"):
                state.whatsapp_sent = True

            # 发送回复
            input_box = await page.query_selector(
                'div[contenteditable="true"][role="textbox"], '
                'div[contenteditable="true"]'
            )

            if input_box:
                await input_box.click()
                await page.wait_for_timeout(500)
                await page.keyboard.type(our_reply, delay=random.randint(15, 35))
                await page.wait_for_timeout(random.randint(500, 1000))
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(2000)

                state.add_our_message(our_reply)
                replied += 1

                stage_emoji = {"cold": "❄️", "curious": "🤔", "interested": "👀",
                               "qualified": "✅", "ready_to_connect": "🔥"}.get(state.stage, "❓")
                logger.info(f"    → 已回复 | {stage_emoji} {state.stage} | 意向:{state.intent_score}分")
                if state.whatsapp_sent:
                    logger.info(f"    📱 WhatsApp 已推送！")

                # 同步到后端数据库
                sync_to_backend(lead_id, state, new_reply, our_reply)

                log_event(f"REPLY [{lead_id}] {state.lead_name} | {state.stage} | {state.intent_score}分")
            else:
                logger.warning(f"    找不到输入框，跳过")
                errors += 1

            # 随机等待，避免过快操作
            wait = random.randint(5, 15)
            await page.wait_for_timeout(wait * 1000)

        except Exception as e:
            logger.error(f"    处理失败: {str(e)[:60]}")
            errors += 1

    try:
        await context.close()
    except Exception:
        pass
    await pw.stop()

    return {"checked": checked, "replied": replied, "errors": errors}


async def run_poller(interval_minutes: int = 5, once: bool = False):
    """主循环：定时轮询。"""
    logger.info("=" * 50)
    logger.info(f"🤖 LeadFlow 自动轮询器启动")
    logger.info(f"   间隔: {interval_minutes} 分钟")
    logger.info(f"   模式: {'单次执行' if once else '持续运行'}")
    logger.info(f"   日志: {LOG_FILE}")
    logger.info("=" * 50)
    log_event(f"POLLER_START interval={interval_minutes}m")

    round_num = 0
    while True:
        round_num += 1
        logger.info(f"\n🔄 第 {round_num} 轮轮询 [{datetime.now().strftime('%H:%M:%S')}]")

        try:
            result = await poll_once()
            logger.info(
                f"   结果: 检查 {result['checked']} 个对话, "
                f"回复 {result['replied']} 条, "
                f"错误 {result['errors']} 个"
            )
            log_event(
                f"POLL_DONE round={round_num} checked={result['checked']} "
                f"replied={result['replied']} errors={result['errors']}"
            )
        except Exception as e:
            logger.error(f"   轮询出错: {str(e)[:80]}")
            log_event(f"POLL_ERROR round={round_num} error={str(e)[:80]}")

        if once:
            logger.info("单次执行完毕，退出。")
            break

        # 随机化下一轮等待时间（±30秒）
        jitter = random.randint(-30, 30)
        wait = interval_minutes * 60 + jitter
        next_time = datetime.now().strftime("%H:%M:%S")
        logger.info(f"   ⏳ 下一轮: {wait}秒后 (约{wait/60:.1f}分钟)")
        await asyncio.sleep(wait)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LeadFlow 自动轮询器")
    parser.add_argument("--interval", type=int, default=5, help="轮询间隔（分钟），默认5")
    parser.add_argument("--once", action="store_true", help="只执行一次")
    args = parser.parse_args()

    try:
        asyncio.run(run_poller(interval_minutes=args.interval, once=args.once))
    except KeyboardInterrupt:
        logger.info("\n👋 轮询器已停止")
        log_event("POLLER_STOP")
