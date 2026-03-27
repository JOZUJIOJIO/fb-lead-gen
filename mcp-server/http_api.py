"""
LeadFlow Automation HTTP API

为前端网页提供自动化操控接口。
运行在端口 3001，前端通过 Next.js rewrite 代理访问。

启动方式: python http_api.py
"""

import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 确保能导入同目录的模块
sys.path.insert(0, str(Path(__file__).parent))

import browser_agent_opencli
import browser_agent as browser_agent_playwright
from conversation_engine import (
    ConversationState,
    generate_opening_message,
    generate_reply,
    get_conversation_summary,
    list_active_conversations,
    MAX_TURNS,
)

# --- 配置 ---
LEADFLOW_BASE_URL = os.environ.get("LEADFLOW_BASE_URL", "http://localhost:8000")
LEADFLOW_EMAIL = os.environ.get("LEADFLOW_EMAIL", "admin@leadflow.com")
LEADFLOW_PASSWORD = os.environ.get("LEADFLOW_PASSWORD", "admin123456")
FB_EMAIL = os.environ.get("FB_EMAIL", "")
FB_PASSWORD = os.environ.get("FB_PASSWORD", "")

# --- 浏览器后端选择 ---
_browser_backend = "auto"


def _get_browser_module():
    if _browser_backend == "playwright":
        return browser_agent_playwright
    if _browser_backend == "opencli":
        return browser_agent_opencli
    if browser_agent_opencli._opencli_available():
        return browser_agent_opencli
    return browser_agent_playwright


# --- HTTP Client (复用 server.py 的逻辑) ---
import httpx

_token: Optional[str] = None


def _get_token() -> str:
    global _token
    if _token:
        return _token
    with httpx.Client(base_url=LEADFLOW_BASE_URL, timeout=30) as client:
        resp = client.post(
            "/auth/login",
            json={"email": LEADFLOW_EMAIL, "password": LEADFLOW_PASSWORD},
        )
        resp.raise_for_status()
        _token = resp.json()["access_token"]
        return _token


def _api(method: str, path: str, **kwargs):
    global _token
    token = _get_token()
    with httpx.Client(base_url=LEADFLOW_BASE_URL, timeout=60) as client:
        resp = client.request(
            method, path,
            headers={"Authorization": f"Bearer {token}"},
            **kwargs,
        )
        if resp.status_code == 401:
            _token = None
            token = _get_token()
            resp = client.request(
                method, path,
                headers={"Authorization": f"Bearer {token}"},
                **kwargs,
            )
        resp.raise_for_status()
        return resp.json()


# --- Auto Poller 状态 ---
_poller_task: Optional[asyncio.Task] = None
_poller_running = False
_poller_log: list[str] = []


# --- FastAPI App ---
app = FastAPI(title="LeadFlow Automation API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Request / Response Models
# ============================================================

class SearchRequest(BaseModel):
    query: str
    search_type: str = "all"
    max_results: int = 20
    auto_import: bool = True


class PipelineRequest(BaseModel):
    keyword: str
    our_company: str = ""
    our_products: str = ""
    max_dm: int = 5
    auto_dm: bool = True


class ConversationRequest(BaseModel):
    lead_id: int
    profile_url: str
    our_company: str = ""
    our_products: str = ""


class ManualReplyRequest(BaseModel):
    lead_id: int
    profile_url: str
    message: str


class PollerConfig(BaseModel):
    interval_minutes: int = 5


class TaskResult(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None


# ============================================================
# 自动化端点
# ============================================================

@app.get("/status")
async def automation_status():
    """获取自动化系统整体状态。"""
    opencli_ready = await browser_agent_opencli.is_opencli_ready()
    pw_available = True
    try:
        import playwright
    except ImportError:
        pw_available = False

    if _browser_backend != "auto":
        browser_mode = _browser_backend
    elif opencli_ready:
        browser_mode = "opencli"
    else:
        browser_mode = "playwright"

    convos = list_active_conversations()
    active_convos = [c for c in convos if c["turn_count"] < MAX_TURNS]

    return {
        "browser": {
            "mode": browser_mode,
            "opencli_ready": opencli_ready,
            "playwright_available": pw_available,
        },
        "poller": {
            "running": _poller_running,
            "log": _poller_log[-20:],
        },
        "conversations": {
            "total": len(convos),
            "active": len(active_convos),
            "items": [
                {
                    "lead_id": c["lead_id"],
                    "lead_name": c["lead_name"],
                    "lead_company": c.get("lead_company", ""),
                    "stage": c["stage"],
                    "intent_score": c["intent_score"],
                    "turn_count": c["turn_count"],
                    "whatsapp_sent": c.get("whatsapp_sent", False),
                }
                for c in convos
            ],
        },
    }


@app.post("/search")
async def facebook_search(req: SearchRequest) -> TaskResult:
    """在 Facebook 搜索潜在客户。"""
    try:
        find_customers = _get_browser_module().find_customers
        result = await find_customers(
            query=req.query,
            search_type=req.search_type,
            max_results=req.max_results,
            headless=True,
            fb_email=FB_EMAIL,
            fb_password=FB_PASSWORD,
        )

        if not result["success"]:
            return TaskResult(success=False, message=result["message"])

        profiles = result["profiles"]
        imported_count = 0

        if req.auto_import and profiles:
            for p in profiles:
                try:
                    _api("POST", "/leads", json={
                        "name": p.get("name", "Unknown"),
                        "company": p.get("company", ""),
                        "phone": p.get("phone", ""),
                        "email": p.get("email", ""),
                        "source": "graph_api",
                        "source_url": p.get("profile_url", ""),
                        "profile_data": {
                            "bio": p.get("bio", ""),
                            "ai_reason": p.get("ai_reason", ""),
                            "search_query": req.query,
                        },
                        "language": p.get("language", "en"),
                    })
                    imported_count += 1
                except Exception:
                    continue

        return TaskResult(
            success=True,
            message=f"找到 {len(profiles)} 个客户，导入 {imported_count} 条",
            data={
                "profiles_found": len(profiles),
                "groups_found": len(result.get("groups", [])),
                "imported": imported_count,
                "profiles": [
                    {
                        "name": p.get("name"),
                        "company": p.get("company"),
                        "score": p.get("score"),
                        "ai_reason": p.get("ai_reason"),
                    }
                    for p in profiles[:20]
                ],
            },
        )
    except Exception as e:
        return TaskResult(success=False, message=f"搜索失败: {str(e)}")


@app.post("/pipeline")
async def full_pipeline(req: PipelineRequest) -> TaskResult:
    """全自动获客流水线：搜索 → 分析 → 筛选 → 私信。"""
    try:
        steps = []

        # Step 1: Facebook 搜索
        find_customers = _get_browser_module().find_customers
        search_result = await find_customers(
            query=req.keyword,
            search_type="all",
            max_results=20,
            headless=True,
            fb_email=FB_EMAIL,
            fb_password=FB_PASSWORD,
        )

        if not search_result["success"]:
            return TaskResult(success=False, message=f"搜索失败: {search_result['message']}")

        profiles = search_result["profiles"]
        steps.append(f"搜索完成: {len(profiles)} 个客户")

        if not profiles:
            return TaskResult(success=False, message="未找到客户，换个关键词试试")

        # Step 2: 导入 + AI 分析
        imported_ids = []
        for p in profiles:
            try:
                lead = _api("POST", "/leads", json={
                    "name": p.get("name", "Unknown"),
                    "company": p.get("company", ""),
                    "phone": p.get("phone", ""),
                    "email": p.get("email", ""),
                    "source": "graph_api",
                    "source_url": p.get("profile_url", ""),
                    "profile_data": {
                        "bio": p.get("bio", ""),
                        "ai_reason": p.get("ai_reason", ""),
                    },
                    "language": p.get("language", "en"),
                })
                imported_ids.append(lead["id"])
            except Exception:
                continue

        analyzed = 0
        if imported_ids:
            try:
                result = _api("POST", "/leads/batch-analyze", json={"ids": imported_ids[:20]})
                analyzed = result.get("analyzed", 0)
            except Exception:
                pass

        steps.append(f"导入 {len(imported_ids)} 条，分析 {analyzed} 条")

        # Step 3: 筛选高分客户
        qualified_data = _api("GET", "/leads", params={
            "min_score": 50,
            "sort_by": "score",
            "sort_order": "desc",
            "page_size": req.max_dm,
        })
        qualified = qualified_data.get("items", [])
        steps.append(f"高质量客户: {len(qualified)} 个")

        # Step 4: 发私信
        dm_sent = 0
        if req.auto_dm and qualified:
            FacebookBrowser = _get_browser_module().FacebookBrowser
            fb = FacebookBrowser()
            try:
                await fb.start(headless=True)
                if await fb.is_logged_in():
                    for q in qualified[:req.max_dm]:
                        profile_url = q.get("source_url", "")
                        if not profile_url:
                            continue

                        state = ConversationState(
                            lead_id=str(q["id"]),
                            lead_name=q["name"],
                            lead_company=q.get("company", ""),
                            lead_language=q.get("language", "en"),
                            our_company=req.our_company,
                            our_products=req.our_products,
                        )

                        opening = generate_opening_message(state)
                        sent = await fb.send_dm(profile_url, opening)
                        if sent:
                            state.add_our_message(opening)
                            dm_sent += 1
                            try:
                                _api("PUT", f"/leads/{q['id']}", json={"status": "contacted"})
                            except Exception:
                                pass

                        await asyncio.sleep(3)
                else:
                    steps.append("未登录 Facebook，跳过私信")
            finally:
                await fb.close()

        steps.append(f"私信发送: {dm_sent} 条")

        return TaskResult(
            success=True,
            message=" → ".join(steps),
            data={
                "profiles_found": len(profiles),
                "imported": len(imported_ids),
                "analyzed": analyzed,
                "qualified": len(qualified),
                "dm_sent": dm_sent,
            },
        )
    except Exception as e:
        return TaskResult(success=False, message=f"流水线失败: {str(e)}")


@app.post("/conversation/start")
async def start_conversation(req: ConversationRequest) -> TaskResult:
    """给指定客户发起对话。"""
    try:
        state = ConversationState(
            lead_id=str(req.lead_id),
            lead_name=f"Lead-{req.lead_id}",
            our_company=req.our_company,
            our_products=req.our_products,
        )

        # 从 API 获取客户信息
        try:
            lead = _api("GET", f"/leads/{req.lead_id}")
            state.lead_name = lead.get("name", state.lead_name)
            state.lead_company = lead.get("company", "")
            state.lead_language = lead.get("language", "en")
        except Exception:
            pass

        opening = generate_opening_message(state)

        FacebookBrowser = _get_browser_module().FacebookBrowser
        fb = FacebookBrowser()
        try:
            await fb.start(headless=True)
            if not await fb.is_logged_in():
                return TaskResult(success=False, message="未登录 Facebook")

            sent = await fb.send_dm(req.profile_url, opening)
            if sent:
                state.add_our_message(opening)
                try:
                    _api("PUT", f"/leads/{req.lead_id}", json={"status": "contacted"})
                except Exception:
                    pass
                return TaskResult(
                    success=True,
                    message=f"已向 {state.lead_name} 发送开场消息",
                    data={"opening_message": opening},
                )
            return TaskResult(success=False, message="消息发送失败")
        finally:
            await fb.close()
    except Exception as e:
        return TaskResult(success=False, message=f"发起对话失败: {str(e)}")


@app.post("/conversation/reply")
async def manual_reply(req: ManualReplyRequest) -> TaskResult:
    """手动发送消息给客户。"""
    try:
        state = ConversationState.load(str(req.lead_id))
        if not state:
            state = ConversationState(lead_id=str(req.lead_id), lead_name=f"Lead-{req.lead_id}")

        FacebookBrowser = _get_browser_module().FacebookBrowser
        fb = FacebookBrowser()
        try:
            await fb.start(headless=True)
            if not await fb.is_logged_in():
                return TaskResult(success=False, message="未登录 Facebook")

            sent = await fb.send_dm(req.profile_url, req.message)
            if sent:
                state.add_our_message(req.message)
                return TaskResult(success=True, message="消息已发送")
            return TaskResult(success=False, message="发送失败")
        finally:
            await fb.close()
    except Exception as e:
        return TaskResult(success=False, message=f"回复失败: {str(e)}")


@app.post("/follow-up")
async def follow_up_all() -> TaskResult:
    """一键跟进所有活跃对话。"""
    try:
        convos = list_active_conversations()
        if not convos:
            return TaskResult(success=True, message="暂无活跃对话")

        active = [c for c in convos if c["turn_count"] < MAX_TURNS]
        if not active:
            return TaskResult(success=True, message=f"所有对话已达 {MAX_TURNS} 轮上限")

        # 获取 profile_url
        tasks_info = []
        for c in active:
            try:
                lead = _api("GET", f"/leads/{c['lead_id']}")
                profile_url = lead.get("source_url", "")
                if profile_url:
                    tasks_info.append((c, profile_url))
            except Exception:
                pass

        if not tasks_info:
            return TaskResult(success=True, message="没有可跟进的对话")

        new_progress = 0
        waiting = 0
        failed = 0

        FacebookBrowser = _get_browser_module().FacebookBrowser
        fb = FacebookBrowser()
        try:
            await fb.start(headless=True)
            if not await fb.is_logged_in():
                return TaskResult(success=False, message="未登录 Facebook")

            for conv_info, url in tasks_info:
                try:
                    state = ConversationState.load(str(conv_info["lead_id"]))
                    if not state:
                        continue

                    replies = await fb.read_latest_replies(url, since_count=5)
                    if replies:
                        new_msg = replies[-1]
                        state.add_their_reply(new_msg)
                        result = generate_reply(state, new_msg)
                        our_reply = result["reply"]
                        await fb.send_dm(url, our_reply)
                        state.add_our_message(our_reply)
                        state.stage = result["stage"]
                        state.intent_score = result["intent_score"]
                        new_progress += 1
                    else:
                        waiting += 1
                except Exception:
                    failed += 1

                await asyncio.sleep(2)
        finally:
            await fb.close()

        return TaskResult(
            success=True,
            message=f"跟进完成: {new_progress} 有新进展, {waiting} 等待中, {failed} 失败",
            data={
                "total": len(tasks_info),
                "new_progress": new_progress,
                "waiting": waiting,
                "failed": failed,
            },
        )
    except Exception as e:
        return TaskResult(success=False, message=f"跟进失败: {str(e)}")


# ============================================================
# Auto Poller 控制
# ============================================================

async def _poller_loop(interval_minutes: int):
    """后台自动轮询循环。"""
    global _poller_running, _poller_log
    _poller_running = True
    _poller_log.append(f"Auto Poller 启动 (间隔 {interval_minutes} 分钟)")

    while _poller_running:
        try:
            convos = list_active_conversations()
            active = [c for c in convos if c["turn_count"] < MAX_TURNS]
            _poller_log.append(f"检查 {len(active)} 个活跃对话...")

            for c in active:
                if not _poller_running:
                    break
                try:
                    lead = _api("GET", f"/leads/{c['lead_id']}")
                    profile_url = lead.get("source_url", "")
                    if not profile_url:
                        continue

                    state = ConversationState.load(str(c["lead_id"]))
                    if not state:
                        continue

                    FacebookBrowser = _get_browser_module().FacebookBrowser
                    fb = FacebookBrowser()
                    try:
                        await fb.start(headless=True)
                        if not await fb.is_logged_in():
                            _poller_log.append("未登录 Facebook，跳过本轮")
                            break

                        replies = await fb.read_latest_replies(profile_url, since_count=5)
                        if replies:
                            new_msg = replies[-1]
                            state.add_their_reply(new_msg)
                            result = generate_reply(state, new_msg)
                            await fb.send_dm(profile_url, result["reply"])
                            state.add_our_message(result["reply"])
                            state.stage = result["stage"]
                            state.intent_score = result["intent_score"]
                            _poller_log.append(f"回复 {c['lead_name']}: {result['stage']}")
                    finally:
                        await fb.close()

                    await asyncio.sleep(2)
                except Exception as e:
                    _poller_log.append(f"处理 {c['lead_name']} 失败: {str(e)[:50]}")

        except Exception as e:
            _poller_log.append(f"轮询异常: {str(e)[:50]}")

        # 等待下一轮
        for _ in range(interval_minutes * 60):
            if not _poller_running:
                break
            await asyncio.sleep(1)

    _poller_log.append("Auto Poller 已停止")


@app.post("/poller/start")
async def start_poller(config: PollerConfig) -> TaskResult:
    """启动自动回复轮询。"""
    global _poller_task, _poller_running

    if _poller_running and _poller_task and not _poller_task.done():
        return TaskResult(success=False, message="Auto Poller 已在运行中")

    _poller_task = asyncio.create_task(_poller_loop(config.interval_minutes))
    return TaskResult(
        success=True,
        message=f"Auto Poller 已启动 (每 {config.interval_minutes} 分钟检查一次)",
    )


@app.post("/poller/stop")
async def stop_poller() -> TaskResult:
    """停止自动回复轮询。"""
    global _poller_running
    if not _poller_running:
        return TaskResult(success=False, message="Auto Poller 未在运行")
    _poller_running = False
    return TaskResult(success=True, message="Auto Poller 正在停止...")


@app.get("/poller/log")
async def poller_log():
    """获取 Auto Poller 日志。"""
    return {"running": _poller_running, "log": _poller_log[-50:]}


# ============================================================
# 浏览器后端管理
# ============================================================

@app.post("/browser/switch")
async def switch_browser(backend: str = "auto") -> TaskResult:
    """切换浏览器后端。"""
    global _browser_backend
    if backend not in ("auto", "opencli", "playwright"):
        raise HTTPException(400, f"无效后端: {backend}")
    _browser_backend = backend
    return TaskResult(success=True, message=f"已切换到 {backend}")


@app.post("/browser/login")
async def facebook_login(email: str = "", password: str = "") -> TaskResult:
    """登录 Facebook。"""
    fb_email = email or FB_EMAIL
    fb_password = password or FB_PASSWORD

    if not fb_email or not fb_password:
        return TaskResult(success=False, message="请提供 Facebook 账号密码")

    try:
        FacebookBrowser = _get_browser_module().FacebookBrowser
        fb = FacebookBrowser()
        await fb.start(headless=False)
        success = await fb.login(fb_email, fb_password)
        await fb.close()

        if success:
            return TaskResult(success=True, message="Facebook 登录成功")
        return TaskResult(success=False, message="登录失败，请检查账号密码")
    except Exception as e:
        return TaskResult(success=False, message=f"登录异常: {str(e)}")


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("AUTOMATION_PORT", "3001"))
    print(f"🤖 LeadFlow Automation API starting on port {port}...")
    print(f"   Backend: {LEADFLOW_BASE_URL}")
    print(f"   Browser: auto-detect")
    uvicorn.run(app, host="0.0.0.0", port=port)
