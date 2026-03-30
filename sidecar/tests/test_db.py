import pytest
import pytest_asyncio
from db import Database


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest_asyncio.fixture
async def db(db_path):
    database = Database(db_path)
    await database.initialize()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_create_and_get_campaign(db):
    campaign_id = await db.create_campaign(
        platform="facebook",
        search_keywords="software engineer",
        search_region="US",
        search_industry="Tech",
        persona_id=None,
        send_limit=50,
    )
    assert campaign_id is not None

    campaign = await db.get_campaign(campaign_id)
    assert campaign is not None
    assert campaign["platform"] == "facebook"
    assert campaign["search_keywords"] == "software engineer"
    assert campaign["search_region"] == "US"
    assert campaign["search_industry"] == "Tech"
    assert campaign["send_limit"] == 50
    assert campaign["status"] == "draft"
    assert campaign["id"] == campaign_id


@pytest.mark.asyncio
async def test_create_and_get_lead(db):
    campaign_id = await db.create_campaign(
        platform="facebook",
        search_keywords="python developer",
        search_region="CA",
        search_industry="Software",
        persona_id=None,
        send_limit=10,
    )

    lead_id = await db.create_lead(
        campaign_id=campaign_id,
        platform="facebook",
        platform_user_id="fb_user_123",
        name="Jane Doe",
        profile_url="https://facebook.com/janedoe",
        bio="Python developer at Acme",
        industry="Software",
        intent_score=0.85,
        profile_data={"followers": 500},
    )
    assert lead_id is not None

    lead = await db.get_lead(lead_id)
    assert lead is not None
    assert lead["campaign_id"] == campaign_id
    assert lead["platform"] == "facebook"
    assert lead["platform_user_id"] == "fb_user_123"
    assert lead["name"] == "Jane Doe"
    assert lead["profile_url"] == "https://facebook.com/janedoe"
    assert lead["bio"] == "Python developer at Acme"
    assert lead["industry"] == "Software"
    assert lead["status"] == "found"
    assert lead["intent_score"] == 0.85
    assert lead["id"] == lead_id


@pytest.mark.asyncio
async def test_create_and_list_personas(db):
    persona_id = await db.create_persona(
        name="Sales Bot Alpha",
        company_name="Acme Corp",
        company_description="We build stuff",
        products="Widget Pro",
        salesperson_name="Alice",
        salesperson_title="Account Executive",
        tone="professional",
        greeting_rules="Say hi first",
        conversation_rules="Be helpful",
        transfer_conditions="When customer asks for pricing",
        system_prompt="You are a helpful sales assistant.",
    )
    assert persona_id is not None

    personas = await db.list_personas()
    assert len(personas) == 1
    p = personas[0]
    assert p["name"] == "Sales Bot Alpha"
    assert p["company_name"] == "Acme Corp"
    assert p["salesperson_name"] == "Alice"
    assert p["tone"] == "professional"
    assert p["id"] == persona_id


@pytest.mark.asyncio
async def test_count_messages_today(db):
    campaign_id = await db.create_campaign(
        platform="facebook",
        search_keywords="test",
        search_region="US",
        search_industry="Tech",
        persona_id=None,
        send_limit=5,
    )
    lead_id = await db.create_lead(
        campaign_id=campaign_id,
        platform="facebook",
        platform_user_id="fb_count_test",
        name="Count Tester",
        profile_url="https://facebook.com/counttester",
    )

    # No messages yet
    count = await db.count_messages_today()
    assert count == 0

    # Add an outbound message
    await db.create_message(lead_id=lead_id, direction="outbound", content="Hello!", ai_generated=True)
    count = await db.count_messages_today()
    assert count == 1

    # Add another outbound message
    await db.create_message(lead_id=lead_id, direction="outbound", content="Follow up!", ai_generated=False)
    count = await db.count_messages_today()
    assert count == 2

    # Inbound message should NOT count
    await db.create_message(lead_id=lead_id, direction="inbound", content="Hi back!", ai_generated=False)
    count = await db.count_messages_today()
    assert count == 2  # Still 2, inbound not counted


@pytest.mark.asyncio
async def test_lead_already_messaged(db):
    campaign_id = await db.create_campaign(
        platform="facebook",
        search_keywords="dedup",
        search_region="US",
        search_industry="Tech",
        persona_id=None,
        send_limit=5,
    )

    # Lead not yet in system
    result = await db.lead_already_messaged("fb_dedup_user")
    assert result is False

    # Create lead with 'found' status — not yet messaged
    lead_id = await db.create_lead(
        campaign_id=campaign_id,
        platform="facebook",
        platform_user_id="fb_dedup_user",
        name="Dedup User",
        profile_url="https://facebook.com/dedupuser",
    )
    result = await db.lead_already_messaged("fb_dedup_user")
    assert result is False

    # Update lead to 'messaged' status
    await db.update_lead(lead_id, status="messaged")
    result = await db.lead_already_messaged("fb_dedup_user")
    assert result is True


@pytest.mark.asyncio
async def test_settings(db):
    # Get non-existent key returns None
    val = await db.get_setting("nonexistent_key")
    assert val is None

    # Set a setting
    await db.set_setting("api_key", "secret123")
    val = await db.get_setting("api_key")
    assert val == "secret123"

    # Overwrite a setting
    await db.set_setting("api_key", "new_secret456")
    val = await db.get_setting("api_key")
    assert val == "new_secret456"

    # Multiple settings
    await db.set_setting("another_key", "another_value")
    val = await db.get_setting("another_key")
    assert val == "another_value"
    # Original still intact
    val = await db.get_setting("api_key")
    assert val == "new_secret456"
