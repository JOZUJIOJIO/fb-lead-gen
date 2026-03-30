"""
SQLite database layer using aiosqlite.
Replaces PostgreSQL used in the Docker version.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite


class Database:
    def __init__(self, db_path: str = "fb_lead_gen.db"):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    def _now(self) -> str:
        """Return current UTC time as ISO format string."""
        return datetime.now(timezone.utc).isoformat()

    async def initialize(self) -> None:
        """Open connection and create tables + indexes."""
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._create_tables()
        await self._conn.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _create_tables(self) -> None:
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS personas (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                company_name    TEXT,
                company_description TEXT,
                products        TEXT,
                salesperson_name TEXT,
                salesperson_title TEXT,
                tone            TEXT,
                greeting_rules  TEXT,
                conversation_rules TEXT,
                transfer_conditions TEXT,
                system_prompt   TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS campaigns (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                platform         TEXT NOT NULL,
                search_keywords  TEXT,
                search_region    TEXT,
                search_industry  TEXT,
                persona_id       INTEGER REFERENCES personas(id),
                send_limit       INTEGER DEFAULT 50,
                status           TEXT NOT NULL DEFAULT 'draft',
                progress_current INTEGER DEFAULT 0,
                progress_total   INTEGER DEFAULT 0,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS leads (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id       INTEGER NOT NULL REFERENCES campaigns(id),
                platform          TEXT NOT NULL,
                platform_user_id  TEXT,
                name              TEXT,
                profile_url       TEXT,
                bio               TEXT,
                industry          TEXT,
                status            TEXT NOT NULL DEFAULT 'found',
                intent_score      REAL,
                transfer_contact  TEXT,
                profile_data      TEXT,
                created_at        TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id      INTEGER NOT NULL REFERENCES leads(id),
                direction    TEXT NOT NULL,
                content      TEXT,
                ai_generated INTEGER NOT NULL DEFAULT 0,
                created_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE INDEX IF NOT EXISTS ix_leads_campaign_id       ON leads(campaign_id);
            CREATE INDEX IF NOT EXISTS ix_leads_status            ON leads(status);
            CREATE INDEX IF NOT EXISTS ix_leads_platform_user_id  ON leads(platform_user_id);
            CREATE INDEX IF NOT EXISTS ix_messages_lead_id        ON messages(lead_id);
            CREATE INDEX IF NOT EXISTS ix_campaigns_status        ON campaigns(status);
        """)

    # -------------------------------------------------------------------------
    # Campaigns
    # -------------------------------------------------------------------------

    async def create_campaign(
        self,
        platform: str,
        search_keywords: str = None,
        search_region: str = None,
        search_industry: str = None,
        persona_id: int = None,
        send_limit: int = 50,
        status: str = "draft",
        progress_current: int = 0,
        progress_total: int = 0,
    ) -> int:
        now = self._now()
        cursor = await self._conn.execute(
            """
            INSERT INTO campaigns
                (platform, search_keywords, search_region, search_industry,
                 persona_id, send_limit, status, progress_current, progress_total,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (platform, search_keywords, search_region, search_industry,
             persona_id, send_limit, status, progress_current, progress_total,
             now, now),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_campaign(self, campaign_id: int) -> Optional[aiosqlite.Row]:
        cursor = await self._conn.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        )
        return await cursor.fetchone()

    async def list_campaigns(self, status: str = None) -> list:
        if status:
            cursor = await self._conn.execute(
                "SELECT * FROM campaigns WHERE status = ? ORDER BY created_at DESC", (status,)
            )
        else:
            cursor = await self._conn.execute(
                "SELECT * FROM campaigns ORDER BY created_at DESC"
            )
        return await cursor.fetchall()

    async def update_campaign(self, campaign_id: int, **kwargs) -> None:
        if not kwargs:
            return
        kwargs["updated_at"] = self._now()
        set_clauses = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [campaign_id]
        await self._conn.execute(
            f"UPDATE campaigns SET {set_clauses} WHERE id = ?", values
        )
        await self._conn.commit()

    # -------------------------------------------------------------------------
    # Leads
    # -------------------------------------------------------------------------

    async def create_lead(
        self,
        campaign_id: int,
        platform: str,
        platform_user_id: str = None,
        name: str = None,
        profile_url: str = None,
        bio: str = None,
        industry: str = None,
        status: str = "found",
        intent_score: float = None,
        transfer_contact: str = None,
        profile_data: Any = None,
    ) -> int:
        now = self._now()
        profile_data_str = json.dumps(profile_data) if profile_data is not None else None
        cursor = await self._conn.execute(
            """
            INSERT INTO leads
                (campaign_id, platform, platform_user_id, name, profile_url,
                 bio, industry, status, intent_score, transfer_contact,
                 profile_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (campaign_id, platform, platform_user_id, name, profile_url,
             bio, industry, status, intent_score, transfer_contact,
             profile_data_str, now),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_lead(self, lead_id: int) -> Optional[aiosqlite.Row]:
        cursor = await self._conn.execute(
            "SELECT * FROM leads WHERE id = ?", (lead_id,)
        )
        return await cursor.fetchone()

    async def list_leads(
        self,
        campaign_id: int = None,
        status: str = None,
        intent: float = None,
    ) -> list:
        conditions = []
        params = []
        if campaign_id is not None:
            conditions.append("campaign_id = ?")
            params.append(campaign_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if intent is not None:
            conditions.append("intent_score >= ?")
            params.append(intent)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cursor = await self._conn.execute(
            f"SELECT * FROM leads {where} ORDER BY created_at DESC", params
        )
        return await cursor.fetchall()

    async def update_lead(self, lead_id: int, **kwargs) -> None:
        if not kwargs:
            return
        set_clauses = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [lead_id]
        await self._conn.execute(
            f"UPDATE leads SET {set_clauses} WHERE id = ?", values
        )
        await self._conn.commit()

    async def lead_already_messaged(self, platform_user_id: str) -> bool:
        """Check if a lead with this platform_user_id has been contacted."""
        cursor = await self._conn.execute(
            """
            SELECT 1 FROM leads
            WHERE platform_user_id = ?
              AND status IN ('messaged', 'in_conversation', 'high_intent', 'transferred')
            LIMIT 1
            """,
            (platform_user_id,),
        )
        row = await cursor.fetchone()
        return row is not None

    # -------------------------------------------------------------------------
    # Messages
    # -------------------------------------------------------------------------

    async def create_message(
        self,
        lead_id: int,
        direction: str,
        content: str = None,
        ai_generated: bool = False,
    ) -> int:
        now = self._now()
        cursor = await self._conn.execute(
            """
            INSERT INTO messages (lead_id, direction, content, ai_generated, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (lead_id, direction, content, 1 if ai_generated else 0, now),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_conversation(self, lead_id: int) -> list:
        cursor = await self._conn.execute(
            "SELECT * FROM messages WHERE lead_id = ? ORDER BY created_at ASC",
            (lead_id,),
        )
        return await cursor.fetchall()

    async def count_messages_today(self) -> int:
        """Count outbound messages where created_at starts with today's UTC date."""
        today = datetime.now(timezone.utc).date().isoformat()
        cursor = await self._conn.execute(
            """
            SELECT COUNT(*) FROM messages
            WHERE direction = 'outbound'
              AND created_at LIKE ?
            """,
            (f"{today}%",),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    # -------------------------------------------------------------------------
    # Personas
    # -------------------------------------------------------------------------

    async def create_persona(
        self,
        name: str,
        company_name: str = None,
        company_description: str = None,
        products: str = None,
        salesperson_name: str = None,
        salesperson_title: str = None,
        tone: str = None,
        greeting_rules: str = None,
        conversation_rules: str = None,
        transfer_conditions: str = None,
        system_prompt: str = None,
    ) -> int:
        now = self._now()
        cursor = await self._conn.execute(
            """
            INSERT INTO personas
                (name, company_name, company_description, products,
                 salesperson_name, salesperson_title, tone, greeting_rules,
                 conversation_rules, transfer_conditions, system_prompt,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, company_name, company_description, products,
             salesperson_name, salesperson_title, tone, greeting_rules,
             conversation_rules, transfer_conditions, system_prompt,
             now, now),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_persona(self, persona_id: int) -> Optional[aiosqlite.Row]:
        cursor = await self._conn.execute(
            "SELECT * FROM personas WHERE id = ?", (persona_id,)
        )
        return await cursor.fetchone()

    async def list_personas(self) -> list:
        cursor = await self._conn.execute(
            "SELECT * FROM personas ORDER BY created_at DESC"
        )
        return await cursor.fetchall()

    async def update_persona(self, persona_id: int, **kwargs) -> None:
        if not kwargs:
            return
        kwargs["updated_at"] = self._now()
        set_clauses = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [persona_id]
        await self._conn.execute(
            f"UPDATE personas SET {set_clauses} WHERE id = ?", values
        )
        await self._conn.commit()

    # -------------------------------------------------------------------------
    # Settings
    # -------------------------------------------------------------------------

    async def get_setting(self, key: str) -> Optional[str]:
        cursor = await self._conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        await self._conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        await self._conn.commit()
