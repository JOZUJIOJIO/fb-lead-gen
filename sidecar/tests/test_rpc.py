"""Tests for JSON-RPC handler wiring in main.py."""

import asyncio

import pytest
import pytest_asyncio

import main
from db import Database


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def isolated_db(tmp_path):
    """Create a fresh in-memory-ish DB for each test and inject it into main._db."""
    db_path = str(tmp_path / "test_rpc.db")
    db = Database(db_path)
    await db.initialize()
    # Override the module-level _db so all handlers use this test database
    original = main._db
    main._db = db
    yield db
    main._db = original
    await db.close()


# ---------------------------------------------------------------------------
# Helper: call a registered RPC handler by name
# ---------------------------------------------------------------------------

async def call(method: str, **kwargs):
    """Directly invoke a registered handler on main.server."""
    handler = main.server._handlers[method]
    return await handler(**kwargs)


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ping():
    result = await call("ping")
    assert result == "pong"


@pytest.mark.asyncio
async def test_get_status():
    result = await call("get_status")
    assert result["version"] == "0.1.0"
    assert result["db"] == "connected"
    assert "messages_sent_today" in result
    assert result["messages_sent_today"] == 0


# ---------------------------------------------------------------------------
# Campaigns
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_campaign_roundtrip():
    """create_campaign should return a dict; get_campaign should include leads."""
    created = await call(
        "create_campaign",
        platform="facebook",
        search_keywords="python dev",
        search_region="US",
        search_industry="Tech",
        persona_id=None,
        send_limit=25,
    )
    assert created["platform"] == "facebook"
    assert created["search_keywords"] == "python dev"
    assert created["status"] == "draft"
    assert created["send_limit"] == 25

    campaign_id = created["id"]

    fetched = await call("get_campaign", campaign_id=campaign_id)
    assert fetched is not None
    assert fetched["id"] == campaign_id
    assert fetched["platform"] == "facebook"
    assert "leads" in fetched
    assert fetched["leads"] == []  # No leads yet


@pytest.mark.asyncio
async def test_get_campaign_includes_leads(isolated_db):
    """get_campaign should embed the leads list."""
    campaign_id = await isolated_db.create_campaign(
        platform="linkedin",
        search_keywords="sales",
        send_limit=10,
    )
    await isolated_db.create_lead(
        campaign_id=campaign_id,
        platform="linkedin",
        name="Alice",
        platform_user_id="li_alice",
    )
    await isolated_db.create_lead(
        campaign_id=campaign_id,
        platform="linkedin",
        name="Bob",
        platform_user_id="li_bob",
    )

    result = await call("get_campaign", campaign_id=campaign_id)
    assert len(result["leads"]) == 2
    names = {lead["name"] for lead in result["leads"]}
    assert names == {"Alice", "Bob"}


@pytest.mark.asyncio
async def test_list_campaigns():
    await call("create_campaign", platform="facebook", send_limit=5)
    await call("create_campaign", platform="linkedin", send_limit=10)
    campaigns = await call("list_campaigns")
    assert len(campaigns) == 2


@pytest.mark.asyncio
async def test_list_campaigns_filtered_by_status(isolated_db):
    cid = await isolated_db.create_campaign(platform="facebook", send_limit=5)
    await isolated_db.update_campaign(cid, status="running")
    await isolated_db.create_campaign(platform="linkedin", send_limit=10)  # draft

    running = await call("list_campaigns", status="running")
    assert len(running) == 1
    assert running[0]["status"] == "running"

    drafts = await call("list_campaigns", status="draft")
    assert len(drafts) == 1


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_persona_roundtrip():
    """create_persona + list_personas roundtrip."""
    created = await call(
        "create_persona",
        name="Promo Bot",
        company_name="Acme",
        tone="friendly",
    )
    assert created["name"] == "Promo Bot"
    assert created["company_name"] == "Acme"
    assert created["tone"] == "friendly"

    personas = await call("list_personas")
    assert len(personas) == 1
    assert personas[0]["id"] == created["id"]
    assert personas[0]["name"] == "Promo Bot"


@pytest.mark.asyncio
async def test_get_persona():
    created = await call("create_persona", name="Getter Bot")
    fetched = await call("get_persona", persona_id=created["id"])
    assert fetched is not None
    assert fetched["id"] == created["id"]
    assert fetched["name"] == "Getter Bot"


@pytest.mark.asyncio
async def test_update_persona():
    created = await call("create_persona", name="Before Update")
    updated = await call(
        "update_persona",
        persona_id=created["id"],
        name="After Update",
        tone="professional",
    )
    assert updated["name"] == "After Update"
    assert updated["tone"] == "professional"


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_leads(isolated_db):
    campaign_id = await isolated_db.create_campaign(platform="facebook", send_limit=5)
    await isolated_db.create_lead(
        campaign_id=campaign_id, platform="facebook", name="Lead1", platform_user_id="u1"
    )
    await isolated_db.create_lead(
        campaign_id=campaign_id, platform="facebook", name="Lead2", platform_user_id="u2",
        status="messaged",
    )

    all_leads = await call("list_leads", campaign_id=campaign_id)
    assert len(all_leads) == 2

    found_only = await call("list_leads", campaign_id=campaign_id, status="found")
    assert len(found_only) == 1
    assert found_only[0]["name"] == "Lead1"


@pytest.mark.asyncio
async def test_get_lead(isolated_db):
    campaign_id = await isolated_db.create_campaign(platform="facebook", send_limit=5)
    lead_id = await isolated_db.create_lead(
        campaign_id=campaign_id, platform="facebook", name="Specific Lead",
        platform_user_id="specific_u",
    )
    result = await call("get_lead", lead_id=lead_id)
    assert result is not None
    assert result["id"] == lead_id
    assert result["name"] == "Specific Lead"


@pytest.mark.asyncio
async def test_get_conversation(isolated_db):
    campaign_id = await isolated_db.create_campaign(platform="facebook", send_limit=5)
    lead_id = await isolated_db.create_lead(
        campaign_id=campaign_id, platform="facebook", name="Conv Lead",
        platform_user_id="conv_u",
    )
    await isolated_db.create_message(lead_id=lead_id, direction="outbound", content="Hi!")
    await isolated_db.create_message(lead_id=lead_id, direction="inbound", content="Hello!")

    msgs = await call("get_conversation", lead_id=lead_id)
    assert len(msgs) == 2
    assert msgs[0]["direction"] == "outbound"
    assert msgs[1]["direction"] == "inbound"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_and_set_setting():
    result = await call("get_setting", key="test_key")
    assert result is None

    set_result = await call("set_setting", key="test_key", value="hello")
    assert set_result["ok"] is True

    val = await call("get_setting", key="test_key")
    assert val == "hello"


# ---------------------------------------------------------------------------
# Campaign control
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_campaign_returns_message():
    """start_campaign should enqueue a background task and return a message."""
    created = await call("create_campaign", platform="facebook", send_limit=5)
    campaign_id = created["id"]

    result = await call("start_campaign", campaign_id=campaign_id)
    # The RPC handler returns the campaign row merged with a message key.
    assert "message" in result
    assert str(campaign_id) in result["message"]


@pytest.mark.asyncio
async def test_pause_campaign_sets_status(isolated_db):
    """pause_campaign should set DB status to paused."""
    campaign_id = await isolated_db.create_campaign(platform="facebook", send_limit=5)

    paused = await call("pause_campaign", campaign_id=campaign_id)
    assert paused["status"] == "paused"
    assert "message" in paused


@pytest.mark.asyncio
async def test_stop_campaign_sets_status(isolated_db):
    """stop_campaign should set DB status to stopped."""
    campaign_id = await isolated_db.create_campaign(platform="facebook", send_limit=5)

    stopped = await call("stop_campaign", campaign_id=campaign_id)
    assert stopped["status"] == "stopped"
    assert "message" in stopped


@pytest.mark.asyncio
async def test_start_campaign_concurrent_limit(isolated_db):
    """Starting more than MAX_CONCURRENT_CAMPAIGNS should raise an error."""
    from services import campaign_runner

    # Temporarily inject fake running tasks to hit the limit
    fake_tasks: dict = {}
    for i in range(campaign_runner.MAX_CONCURRENT_CAMPAIGNS):
        # Create a never-ending coroutine as a fake task
        async def _never():
            await asyncio.sleep(9999)
        t = asyncio.create_task(_never())
        fake_tasks[-(i + 1)] = t

    original = campaign_runner._running_tasks.copy()
    campaign_runner._running_tasks.update(fake_tasks)
    try:
        campaign_id = await isolated_db.create_campaign(platform="facebook", send_limit=5)
        with pytest.raises(ValueError, match="concurrent limit"):
            await campaign_runner.start_campaign(campaign_id, isolated_db, None)
    finally:
        for t in fake_tasks.values():
            t.cancel()
        campaign_runner._running_tasks.clear()
        campaign_runner._running_tasks.update(original)


# ---------------------------------------------------------------------------
# get_status messages_sent_today
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_status_messages_sent_today(isolated_db):
    campaign_id = await isolated_db.create_campaign(platform="facebook", send_limit=5)
    lead_id = await isolated_db.create_lead(
        campaign_id=campaign_id, platform="facebook",
        name="Msg Lead", platform_user_id="msg_u",
    )
    await isolated_db.create_message(lead_id=lead_id, direction="outbound", content="Hey!")
    await isolated_db.create_message(lead_id=lead_id, direction="outbound", content="Follow up!")

    status = await call("get_status")
    assert status["messages_sent_today"] == 2
