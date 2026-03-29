# LeadFlow Mac App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Docker-based LeadFlow into a native Mac .dmg application with built-in AI conversation engine, persona studio, and OpenClaw MCP remote control.

**Architecture:** Tauri shell (Rust, system WebView) + Python sidecar (PyInstaller binary) communicating via JSON-RPC over stdin/stdout. SQLite replaces PostgreSQL. Embedded MCP server for OpenClaw remote control. Playwright browser automation for Facebook/Instagram.

**Tech Stack:** Tauri 2.x, React 18 + Vite + TypeScript + Tailwind CSS, Python 3.11 + aiosqlite + Patchright + FastMCP, PyInstaller

---

## Phase 1: Foundation — Tauri + Python Sidecar + SQLite

The skeleton: a Mac app that launches, shows a React UI, talks to a Python backend over IPC, and stores data in SQLite.

---

### Task 1: Initialize Tauri Project

**Files:**
- Create: `tauri/src-tauri/Cargo.toml`
- Create: `tauri/src-tauri/src/main.rs`
- Create: `tauri/src-tauri/src/ipc.rs`
- Create: `tauri/src-tauri/tauri.conf.json`
- Create: `tauri/src-tauri/capabilities/default.json`
- Create: `tauri/package.json`
- Create: `tauri/vite.config.ts`
- Create: `tauri/tsconfig.json`
- Create: `tauri/index.html`

- [ ] **Step 1: Install Tauri CLI**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
npm create tauri-app@latest tauri -- --template react-ts --manager npm
```

Expected: `tauri/` directory created with Tauri + React + Vite scaffold.

- [ ] **Step 2: Verify scaffold builds**

```bash
cd tauri && npm install && npm run tauri build -- --debug 2>&1 | tail -20
```

Expected: Debug build succeeds, `.app` bundle created in `tauri/src-tauri/target/debug/bundle/macos/`.

- [ ] **Step 3: Configure Tauri for sidecar**

Edit `tauri/src-tauri/tauri.conf.json` to register the Python sidecar:

```json
{
  "app": {
    "withGlobalTauri": true,
    "windows": [
      {
        "title": "LeadFlow",
        "width": 1280,
        "height": 800,
        "minWidth": 1024,
        "minHeight": 600
      }
    ]
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "identifier": "com.leadflow.app",
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ],
    "externalBin": [
      "binaries/leadflow-sidecar"
    ]
  },
  "plugins": {
    "shell": {
      "sidecar": true
    },
    "notification": {}
  }
}
```

- [ ] **Step 4: Write Rust IPC bridge**

Create `tauri/src-tauri/src/ipc.rs`:

```rust
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use tauri::Manager;

static REQUEST_ID: AtomicU64 = AtomicU64::new(1);

#[derive(Serialize)]
struct JsonRpcRequest {
    jsonrpc: String,
    id: u64,
    method: String,
    params: Value,
}

#[derive(Deserialize, Debug)]
struct JsonRpcResponse {
    jsonrpc: String,
    id: u64,
    result: Option<Value>,
    error: Option<Value>,
}

pub struct Sidecar {
    child: Child,
}

impl Sidecar {
    pub fn spawn(binary_path: &str) -> Result<Self, String> {
        let child = Command::new(binary_path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to spawn sidecar: {}", e))?;
        Ok(Sidecar { child })
    }

    pub fn call(&mut self, method: &str, params: Value) -> Result<Value, String> {
        let id = REQUEST_ID.fetch_add(1, Ordering::SeqCst);
        let request = JsonRpcRequest {
            jsonrpc: "2.0".to_string(),
            id,
            method: method.to_string(),
            params,
        };

        let stdin = self.child.stdin.as_mut()
            .ok_or("Sidecar stdin not available")?;
        let request_json = serde_json::to_string(&request)
            .map_err(|e| format!("Serialize error: {}", e))?;
        writeln!(stdin, "{}", request_json)
            .map_err(|e| format!("Write error: {}", e))?;
        stdin.flush().map_err(|e| format!("Flush error: {}", e))?;

        let stdout = self.child.stdout.as_mut()
            .ok_or("Sidecar stdout not available")?;
        let mut reader = BufReader::new(stdout);
        let mut line = String::new();
        reader.read_line(&mut line)
            .map_err(|e| format!("Read error: {}", e))?;

        let response: JsonRpcResponse = serde_json::from_str(&line)
            .map_err(|e| format!("Deserialize error: {}: {}", e, line))?;

        if let Some(error) = response.error {
            return Err(format!("Sidecar error: {}", error));
        }
        Ok(response.result.unwrap_or(Value::Null))
    }
}

pub struct SidecarState(pub Mutex<Sidecar>);
```

- [ ] **Step 5: Write main.rs with Tauri commands**

Create `tauri/src-tauri/src/main.rs`:

```rust
mod ipc;

use ipc::{Sidecar, SidecarState};
use serde_json::{json, Value};
use tauri::{Manager, State};
use std::sync::Mutex;

#[tauri::command]
fn call_sidecar(
    state: State<SidecarState>,
    method: String,
    params: Value,
) -> Result<Value, String> {
    let mut sidecar = state.0.lock().map_err(|e| e.to_string())?;
    sidecar.call(&method, params)
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // Resolve sidecar binary path
            let resource_path = app.path()
                .resource_dir()
                .expect("failed to resolve resource dir");
            let sidecar_path = resource_path
                .join("binaries")
                .join("leadflow-sidecar");

            let sidecar = Sidecar::spawn(
                sidecar_path.to_str().unwrap()
            ).expect("Failed to start Python sidecar");

            app.manage(SidecarState(Mutex::new(sidecar)));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![call_sidecar])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 6: Add Rust dependencies to Cargo.toml**

Ensure `tauri/src-tauri/Cargo.toml` includes:

```toml
[dependencies]
tauri = { version = "2", features = ["shell-sidecar", "notification"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"

[dependencies.tauri-plugin-shell]
version = "2"

[dependencies.tauri-plugin-notification]
version = "2"
```

- [ ] **Step 7: Commit**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
git add tauri/
git commit -m "feat: initialize Tauri project with sidecar IPC bridge"
```

---

### Task 2: Python Sidecar with JSON-RPC Server

**Files:**
- Create: `sidecar/main.py`
- Create: `sidecar/jsonrpc.py`
- Create: `sidecar/requirements.txt`
- Create: `sidecar/pyproject.toml`

- [ ] **Step 1: Create sidecar directory and requirements**

Create `sidecar/requirements.txt`:

```
aiosqlite==0.20.0
patchright==0.1.0
httpx==0.27.0
mcp[cli]>=1.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
keyring>=25.0.0
```

Create `sidecar/pyproject.toml`:

```toml
[project]
name = "leadflow-sidecar"
version = "0.1.0"
requires-python = ">=3.11"
```

- [ ] **Step 2: Write JSON-RPC server (stdin/stdout)**

Create `sidecar/jsonrpc.py`:

```python
"""Minimal JSON-RPC 2.0 server over stdin/stdout."""

import asyncio
import json
import sys
from typing import Any, Callable, Coroutine

Handler = Callable[..., Coroutine[Any, Any, Any]]

class JsonRpcServer:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def method(self, name: str):
        """Decorator to register an RPC method."""
        def decorator(fn: Handler):
            self._handlers[name] = fn
            return fn
        return decorator

    async def _handle_request(self, data: dict) -> dict:
        method = data.get("method", "")
        params = data.get("params", {})
        req_id = data.get("id")

        handler = self._handlers.get(method)
        if handler is None:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        try:
            if isinstance(params, dict):
                result = await handler(**params)
            elif isinstance(params, list):
                result = await handler(*params)
            else:
                result = await handler()
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)},
            }

    async def run(self) -> None:
        """Read JSON-RPC requests from stdin, write responses to stdout."""
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)

        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                data = json.loads(line.decode().strip())
            except json.JSONDecodeError:
                continue

            response = await self._handle_request(data)
            response_json = json.dumps(response, ensure_ascii=False)
            sys.stdout.write(response_json + "\n")
            sys.stdout.flush()
```

- [ ] **Step 3: Write sidecar entry point with stub handlers**

Create `sidecar/main.py`:

```python
"""LeadFlow Python sidecar — JSON-RPC server for Tauri IPC."""

import asyncio
import logging
import sys

from jsonrpc import JsonRpcServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,  # stdout is reserved for JSON-RPC
)
logger = logging.getLogger("leadflow")

server = JsonRpcServer()


@server.method("ping")
async def ping() -> str:
    return "pong"


@server.method("get_status")
async def get_status() -> dict:
    return {
        "version": "0.1.0",
        "database": "ok",
        "browser_sessions": {},
    }


if __name__ == "__main__":
    asyncio.run(server.run())
```

- [ ] **Step 4: Test sidecar locally**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen/sidecar"
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
echo '{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}' | python3 main.py
```

Expected output: `{"jsonrpc": "2.0", "id": 1, "result": "pong"}`

- [ ] **Step 5: Commit**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
git add sidecar/
git commit -m "feat: add Python sidecar with JSON-RPC server"
```

---

### Task 3: SQLite Database Layer

**Files:**
- Create: `sidecar/db.py`
- Create: `sidecar/models.py`
- Create: `sidecar/tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Create `sidecar/tests/__init__.py` (empty) and `sidecar/tests/test_db.py`:

```python
import asyncio
import pytest
from db import Database

@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    asyncio.get_event_loop().run_until_complete(database.initialize())
    yield database
    asyncio.get_event_loop().run_until_complete(database.close())

def test_create_and_get_campaign(db):
    async def _test():
        campaign_id = await db.create_campaign(
            platform="facebook",
            search_keywords="深圳外贸",
            search_region="深圳",
            search_industry="外贸",
            persona_id=None,
            send_limit=20,
        )
        assert campaign_id > 0

        campaign = await db.get_campaign(campaign_id)
        assert campaign["platform"] == "facebook"
        assert campaign["search_keywords"] == "深圳外贸"
        assert campaign["status"] == "draft"

    asyncio.get_event_loop().run_until_complete(_test())

def test_create_and_get_lead(db):
    async def _test():
        cid = await db.create_campaign(
            platform="facebook", search_keywords="test",
            search_region="", search_industry="",
            persona_id=None, send_limit=10,
        )
        lead_id = await db.create_lead(
            campaign_id=cid,
            platform="facebook",
            platform_user_id="user123",
            name="Test User",
            profile_url="https://facebook.com/user123",
        )
        assert lead_id > 0

        lead = await db.get_lead(lead_id)
        assert lead["name"] == "Test User"
        assert lead["status"] == "found"

    asyncio.get_event_loop().run_until_complete(_test())

def test_create_and_list_personas(db):
    async def _test():
        pid = await db.create_persona(
            name="外贸销售",
            company_name="TechBridge",
            company_description="跨境电商",
            tone="friendly",
            system_prompt="你是一位友善的销售",
        )
        personas = await db.list_personas()
        assert len(personas) == 1
        assert personas[0]["name"] == "外贸销售"

    asyncio.get_event_loop().run_until_complete(_test())
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen/sidecar"
source .venv/bin/activate && pip install pytest
python -m pytest tests/test_db.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Write SQLite database layer**

Create `sidecar/db.py`:

```python
"""SQLite database layer using aiosqlite."""

import aiosqlite
import json
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    search_keywords TEXT,
    search_region TEXT,
    search_industry TEXT,
    persona_id INTEGER REFERENCES personas(id) ON DELETE SET NULL,
    send_limit INTEGER NOT NULL DEFAULT 50,
    status TEXT NOT NULL DEFAULT 'draft',
    progress_current INTEGER NOT NULL DEFAULT 0,
    progress_total INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    platform_user_id TEXT,
    name TEXT,
    profile_url TEXT,
    bio TEXT,
    industry TEXT,
    status TEXT NOT NULL DEFAULT 'found',
    intent_score TEXT,
    transfer_contact TEXT,
    profile_data TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    direction TEXT NOT NULL,
    content TEXT NOT NULL,
    ai_generated INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    company_name TEXT,
    company_description TEXT,
    products TEXT,
    salesperson_name TEXT,
    salesperson_title TEXT,
    tone TEXT,
    greeting_rules TEXT,
    conversation_rules TEXT,
    transfer_conditions TEXT,
    system_prompt TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_leads_campaign_id ON leads(campaign_id);
CREATE INDEX IF NOT EXISTS ix_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS ix_leads_platform_user_id ON leads(platform_user_id);
CREATE INDEX IF NOT EXISTS ix_messages_lead_id ON messages(lead_id);
CREATE INDEX IF NOT EXISTS ix_campaigns_status ON campaigns(status);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA_SQL)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    # -- Campaigns --

    async def create_campaign(
        self, platform: str, search_keywords: str,
        search_region: str, search_industry: str,
        persona_id: int | None, send_limit: int,
    ) -> int:
        now = _now()
        cursor = await self._conn.execute(
            "INSERT INTO campaigns (platform, search_keywords, search_region, "
            "search_industry, persona_id, send_limit, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?)",
            (platform, search_keywords, search_region, search_industry,
             persona_id, send_limit, now, now),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_campaign(self, campaign_id: int) -> dict | None:
        cursor = await self._conn.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_campaigns(self, status: str | None = None) -> list[dict]:
        if status:
            cursor = await self._conn.execute(
                "SELECT * FROM campaigns WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        else:
            cursor = await self._conn.execute(
                "SELECT * FROM campaigns ORDER BY created_at DESC"
            )
        return [dict(r) for r in await cursor.fetchall()]

    async def update_campaign(self, campaign_id: int, **fields) -> None:
        fields["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [campaign_id]
        await self._conn.execute(
            f"UPDATE campaigns SET {set_clause} WHERE id = ?", values
        )
        await self._conn.commit()

    # -- Leads --

    async def create_lead(
        self, campaign_id: int, platform: str,
        platform_user_id: str, name: str, profile_url: str,
    ) -> int:
        cursor = await self._conn.execute(
            "INSERT INTO leads (campaign_id, platform, platform_user_id, name, "
            "profile_url, status, created_at) VALUES (?, ?, ?, ?, ?, 'found', ?)",
            (campaign_id, platform, platform_user_id, name, profile_url, _now()),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_lead(self, lead_id: int) -> dict | None:
        cursor = await self._conn.execute(
            "SELECT * FROM leads WHERE id = ?", (lead_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_leads(
        self, campaign_id: int | None = None,
        status: str | None = None,
        intent: str | None = None,
    ) -> list[dict]:
        conditions = []
        params = []
        if campaign_id:
            conditions.append("campaign_id = ?")
            params.append(campaign_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if intent:
            conditions.append("intent_score = ?")
            params.append(intent)
        where = " AND ".join(conditions)
        query = "SELECT * FROM leads"
        if where:
            query += f" WHERE {where}"
        query += " ORDER BY created_at DESC"
        cursor = await self._conn.execute(query, params)
        return [dict(r) for r in await cursor.fetchall()]

    async def update_lead(self, lead_id: int, **fields) -> None:
        if "profile_data" in fields and isinstance(fields["profile_data"], dict):
            fields["profile_data"] = json.dumps(fields["profile_data"], ensure_ascii=False)
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [lead_id]
        await self._conn.execute(
            f"UPDATE leads SET {set_clause} WHERE id = ?", values
        )
        await self._conn.commit()

    async def lead_already_messaged(self, platform_user_id: str) -> bool:
        cursor = await self._conn.execute(
            "SELECT id FROM leads WHERE platform_user_id = ? AND status IN ('messaged', 'in_conversation', 'high_intent', 'transferred')",
            (platform_user_id,),
        )
        return (await cursor.fetchone()) is not None

    # -- Messages --

    async def create_message(
        self, lead_id: int, direction: str, content: str,
        ai_generated: bool = False,
    ) -> int:
        cursor = await self._conn.execute(
            "INSERT INTO messages (lead_id, direction, content, ai_generated, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (lead_id, direction, content, int(ai_generated), _now()),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_conversation(self, lead_id: int) -> list[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM messages WHERE lead_id = ? ORDER BY created_at ASC",
            (lead_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    # -- Personas --

    async def create_persona(self, name: str, **fields) -> int:
        now = _now()
        all_fields = {"name": name, "created_at": now, "updated_at": now, **fields}
        columns = ", ".join(all_fields.keys())
        placeholders = ", ".join("?" for _ in all_fields)
        cursor = await self._conn.execute(
            f"INSERT INTO personas ({columns}) VALUES ({placeholders})",
            list(all_fields.values()),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_persona(self, persona_id: int) -> dict | None:
        cursor = await self._conn.execute(
            "SELECT * FROM personas WHERE id = ?", (persona_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_personas(self) -> list[dict]:
        cursor = await self._conn.execute(
            "SELECT * FROM personas ORDER BY created_at DESC"
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def update_persona(self, persona_id: int, **fields) -> None:
        fields["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [persona_id]
        await self._conn.execute(
            f"UPDATE personas SET {set_clause} WHERE id = ?", values
        )
        await self._conn.commit()

    # -- Settings --

    async def get_setting(self, key: str) -> str | None:
        cursor = await self._conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        await self._conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = ?",
            (key, value, value),
        )
        await self._conn.commit()

    # -- Stats --

    async def count_messages_today(self) -> int:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cursor = await self._conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE direction = 'outbound' AND created_at LIKE ?",
            (f"{today}%",),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen/sidecar"
source .venv/bin/activate && PYTHONPATH=. python -m pytest tests/test_db.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
git add sidecar/db.py sidecar/models.py sidecar/tests/
git commit -m "feat: add SQLite database layer with campaigns, leads, messages, personas"
```

---

### Task 4: Migrate Frontend from Next.js to Vite + React

**Files:**
- Modify: `tauri/package.json` (add dependencies)
- Create: `tauri/src/main.tsx`
- Create: `tauri/src/App.tsx`
- Create: `tauri/src/lib/ipc.ts`
- Move/adapt: existing React components from `frontend/src/`

- [ ] **Step 1: Install frontend dependencies in Tauri project**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen/tauri"
npm install react react-dom recharts lucide-react
npm install -D typescript @types/react @types/react-dom tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

- [ ] **Step 2: Create IPC client (replaces axios HTTP calls)**

Create `tauri/src/lib/ipc.ts`:

```typescript
import { invoke } from '@tauri-apps/api/core';

/**
 * Call a method on the Python sidecar via JSON-RPC through Tauri IPC.
 */
export async function callSidecar<T = unknown>(
  method: string,
  params: Record<string, unknown> = {},
): Promise<T> {
  const result = await invoke('call_sidecar', { method, params });
  return result as T;
}

// Campaign APIs
export const campaignApi = {
  list: (status?: string) =>
    callSidecar<Campaign[]>('list_campaigns', status ? { status } : {}),
  get: (id: number) =>
    callSidecar<Campaign>('get_campaign', { campaign_id: id }),
  create: (data: CreateCampaignParams) =>
    callSidecar<{ id: number }>('create_campaign', data),
  start: (id: number) =>
    callSidecar<{ message: string }>('start_campaign', { campaign_id: id }),
  pause: (id: number) =>
    callSidecar<{ message: string }>('pause_campaign', { campaign_id: id }),
};

// Lead APIs
export const leadApi = {
  list: (params?: { campaign_id?: number; status?: string; intent?: string }) =>
    callSidecar<Lead[]>('list_leads', params ?? {}),
  get: (id: number) =>
    callSidecar<Lead>('get_lead', { lead_id: id }),
  getConversation: (id: number) =>
    callSidecar<Message[]>('get_conversation', { lead_id: id }),
};

// Persona APIs
export const personaApi = {
  list: () => callSidecar<Persona[]>('list_personas'),
  get: (id: number) => callSidecar<Persona>('get_persona', { persona_id: id }),
  create: (data: CreatePersonaParams) =>
    callSidecar<{ id: number }>('create_persona', data),
  update: (id: number, data: Record<string, unknown>) =>
    callSidecar<void>('update_persona', { persona_id: id, ...data }),
};

// Settings APIs
export const settingsApi = {
  get: (key: string) => callSidecar<string | null>('get_setting', { key }),
  set: (key: string, value: string) =>
    callSidecar<void>('set_setting', { key, value }),
};

// System APIs
export const systemApi = {
  status: () => callSidecar<SystemStatus>('get_status'),
  ping: () => callSidecar<string>('ping'),
};

// Types
export interface Campaign {
  id: number;
  platform: string;
  search_keywords: string;
  search_region: string;
  search_industry: string;
  persona_id: number | null;
  send_limit: number;
  status: string;
  progress_current: number;
  progress_total: number;
  created_at: string;
  updated_at: string;
}

export interface Lead {
  id: number;
  campaign_id: number;
  platform: string;
  platform_user_id: string;
  name: string;
  profile_url: string;
  bio: string | null;
  industry: string | null;
  status: string;
  intent_score: string | null;
  transfer_contact: string | null;
  created_at: string;
}

export interface Message {
  id: number;
  lead_id: number;
  direction: string;
  content: string;
  ai_generated: boolean;
  created_at: string;
}

export interface Persona {
  id: number;
  name: string;
  company_name: string | null;
  company_description: string | null;
  tone: string | null;
  system_prompt: string | null;
  created_at: string;
}

export interface SystemStatus {
  version: string;
  database: string;
  browser_sessions: Record<string, string>;
}

export interface CreateCampaignParams {
  platform: string;
  search_keywords: string;
  search_region?: string;
  search_industry?: string;
  persona_id?: number;
  send_limit?: number;
}

export interface CreatePersonaParams {
  description: string;
}
```

- [ ] **Step 3: Copy and adapt existing React components**

```bash
# Copy components that can be reused
cp -r "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen/frontend/src/components" \
      "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen/tauri/src/components"
```

Then adapt each component: replace `import { ... } from '@/lib/api'` with `import { ... } from '../lib/ipc'`, remove Next.js-specific imports (`'use client'`, `next/navigation`, etc.), replace `api.get()/api.post()` calls with `callSidecar()` calls.

- [ ] **Step 4: Create App.tsx with router**

Create `tauri/src/App.tsx`:

```tsx
import { useState } from 'react';
import Sidebar from './components/Sidebar';
import DashboardPage from './pages/Dashboard';
import CampaignsPage from './pages/Campaigns';
import LeadsPage from './pages/Leads';
import PersonasPage from './pages/Personas';
import SettingsPage from './pages/Settings';

type Page = 'dashboard' | 'campaigns' | 'leads' | 'personas' | 'settings';

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard': return <DashboardPage />;
      case 'campaigns': return <CampaignsPage />;
      case 'leads': return <LeadsPage />;
      case 'personas': return <PersonasPage />;
      case 'settings': return <SettingsPage />;
    }
  };

  return (
    <div className="flex h-screen bg-[#f5f5f7]">
      <Sidebar currentPage={currentPage} onNavigate={setCurrentPage} />
      <main className="flex-1 overflow-auto p-8">
        {renderPage()}
      </main>
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
git add tauri/src/
git commit -m "feat: migrate frontend from Next.js to Vite+React with Tauri IPC"
```

---

### Task 5: Wire Sidecar RPC Handlers to Database

**Files:**
- Modify: `sidecar/main.py`
- Create: `sidecar/tests/test_rpc.py`

- [ ] **Step 1: Write the failing test**

Create `sidecar/tests/test_rpc.py`:

```python
import asyncio
import json
import pytest

async def send_rpc(server_task, method, params=None):
    """Helper: simulates a JSON-RPC call to the server."""
    # We'll test the handler functions directly instead
    pass

def test_rpc_ping():
    """Test that ping handler returns pong."""
    from main import ping
    result = asyncio.get_event_loop().run_until_complete(ping())
    assert result == "pong"

def test_rpc_create_campaign(tmp_path):
    """Test create_campaign via RPC handler."""
    import main
    # Override DB path for test
    from db import Database
    db = Database(str(tmp_path / "test.db"))
    asyncio.get_event_loop().run_until_complete(db.initialize())
    main._db = db

    from main import rpc_create_campaign
    result = asyncio.get_event_loop().run_until_complete(
        rpc_create_campaign(
            platform="facebook",
            search_keywords="test",
            search_region="",
            search_industry="",
            send_limit=10,
        )
    )
    assert "id" in result
    assert result["id"] > 0

    asyncio.get_event_loop().run_until_complete(db.close())
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen/sidecar"
source .venv/bin/activate && PYTHONPATH=. python -m pytest tests/test_rpc.py -v
```

Expected: FAIL — `ImportError: cannot import name 'rpc_create_campaign' from 'main'`

- [ ] **Step 3: Wire all RPC handlers in main.py**

Replace `sidecar/main.py`:

```python
"""LeadFlow Python sidecar — JSON-RPC server for Tauri IPC."""

import asyncio
import logging
import os
import sys

from jsonrpc import JsonRpcServer
from db import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("leadflow")

# Database instance (set during startup, overridden in tests)
_db: Database | None = None

DATA_DIR = os.path.expanduser("~/Library/Application Support/LeadFlow")
DB_PATH = os.path.join(DATA_DIR, "leadflow.db")

server = JsonRpcServer()


def _get_db() -> Database:
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


# -- System --

@server.method("ping")
async def ping() -> str:
    return "pong"


@server.method("get_status")
async def get_status() -> dict:
    db = _get_db()
    msg_count = await db.count_messages_today()
    return {
        "version": "0.1.0",
        "database": "ok",
        "messages_sent_today": msg_count,
        "browser_sessions": {},
    }


# -- Campaigns --

@server.method("create_campaign")
async def rpc_create_campaign(
    platform: str,
    search_keywords: str,
    search_region: str = "",
    search_industry: str = "",
    persona_id: int | None = None,
    send_limit: int = 20,
) -> dict:
    db = _get_db()
    campaign_id = await db.create_campaign(
        platform=platform,
        search_keywords=search_keywords,
        search_region=search_region,
        search_industry=search_industry,
        persona_id=persona_id,
        send_limit=send_limit,
    )
    return await db.get_campaign(campaign_id)


@server.method("list_campaigns")
async def rpc_list_campaigns(status: str | None = None) -> list:
    db = _get_db()
    return await db.list_campaigns(status=status)


@server.method("get_campaign")
async def rpc_get_campaign(campaign_id: int) -> dict:
    db = _get_db()
    campaign = await db.get_campaign(campaign_id)
    if campaign is None:
        raise ValueError(f"Campaign {campaign_id} not found")
    # Include leads
    leads = await db.list_leads(campaign_id=campaign_id)
    campaign["leads"] = leads
    return campaign


# -- Leads --

@server.method("list_leads")
async def rpc_list_leads(
    campaign_id: int | None = None,
    status: str | None = None,
    intent: str | None = None,
) -> list:
    db = _get_db()
    return await db.list_leads(campaign_id=campaign_id, status=status, intent=intent)


@server.method("get_lead")
async def rpc_get_lead(lead_id: int) -> dict:
    db = _get_db()
    lead = await db.get_lead(lead_id)
    if lead is None:
        raise ValueError(f"Lead {lead_id} not found")
    return lead


@server.method("get_conversation")
async def rpc_get_conversation(lead_id: int) -> list:
    db = _get_db()
    return await db.get_conversation(lead_id)


# -- Personas --

@server.method("list_personas")
async def rpc_list_personas() -> list:
    db = _get_db()
    return await db.list_personas()


@server.method("get_persona")
async def rpc_get_persona(persona_id: int) -> dict:
    db = _get_db()
    persona = await db.get_persona(persona_id)
    if persona is None:
        raise ValueError(f"Persona {persona_id} not found")
    return persona


@server.method("create_persona")
async def rpc_create_persona(
    name: str = "",
    description: str = "",
    company_name: str = "",
    company_description: str = "",
    tone: str = "friendly",
    system_prompt: str = "",
    **kwargs,
) -> dict:
    db = _get_db()
    pid = await db.create_persona(
        name=name or "New Persona",
        company_name=company_name,
        company_description=company_description,
        tone=tone,
        system_prompt=system_prompt,
        **{k: v for k, v in kwargs.items() if v},
    )
    return await db.get_persona(pid)


@server.method("update_persona")
async def rpc_update_persona(persona_id: int, **fields) -> dict:
    db = _get_db()
    await db.update_persona(persona_id, **{k: v for k, v in fields.items() if k != "persona_id"})
    return await db.get_persona(persona_id)


# -- Settings --

@server.method("get_setting")
async def rpc_get_setting(key: str) -> str | None:
    db = _get_db()
    return await db.get_setting(key)


@server.method("set_setting")
async def rpc_set_setting(key: str, value: str) -> None:
    db = _get_db()
    await db.set_setting(key, value)


# -- Entry point --

async def _main():
    global _db
    _db = Database(DB_PATH)
    await _db.initialize()
    logger.info("Sidecar started. DB: %s", DB_PATH)
    try:
        await server.run()
    finally:
        await _db.close()


if __name__ == "__main__":
    asyncio.run(_main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen/sidecar"
source .venv/bin/activate && PYTHONPATH=. python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
git add sidecar/
git commit -m "feat: wire sidecar RPC handlers to SQLite database"
```

---

## Phase 2: Browser Automation — Campaign Runner

Port the existing Facebook adapter and campaign runner to work in the sidecar, add Instagram adapter, add retry logic.

---

### Task 6: Port Facebook Adapter to Sidecar

**Files:**
- Create: `sidecar/adapters/__init__.py`
- Create: `sidecar/adapters/facebook.py`
- Create: `sidecar/adapters/base.py`

- [ ] **Step 1: Create base adapter**

Create `sidecar/adapters/__init__.py` (empty) and `sidecar/adapters/base.py`:

```python
"""Base class for platform adapters."""

from abc import ABC, abstractmethod


class PlatformAdapter(ABC):

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def search_people(self, keywords: str, region: str = "", industry: str = "") -> list[dict]: ...

    @abstractmethod
    async def get_profile(self, profile_url: str) -> dict: ...

    @abstractmethod
    async def send_message(self, profile_url: str, message: str) -> bool: ...

    @abstractmethod
    async def read_new_messages(self) -> list[dict]: ...

    @abstractmethod
    async def close(self) -> None: ...
```

- [ ] **Step 2: Port Facebook adapter**

Create `sidecar/adapters/facebook.py` by copying from `backend/app/adapters/platforms/facebook.py` with these changes:

1. Change data dir paths to use `~/Library/Application Support/LeadFlow/`:
```python
import os

DATA_DIR = os.path.expanduser("~/Library/Application Support/LeadFlow")
BROWSER_DATA_DIR = os.path.join(DATA_DIR, "browser", "facebook")
COOKIES_FILE = os.path.join(DATA_DIR, "cookies", "facebook.json")
SCREENSHOT_DIR = os.path.join(DATA_DIR, "screenshots")
```

2. Remove `from app.config import settings` — read proxy from parameter instead:
```python
class FacebookAdapter(PlatformAdapter):
    def __init__(self, proxy_server: str | None = None) -> None:
        self._proxy_server = proxy_server
        # ... rest same as original
```

3. Add `read_new_messages()` stub (will be implemented in Phase 3):
```python
async def read_new_messages(self) -> list[dict]:
    """Stub — implemented in conversation engine task."""
    return []
```

4. Add retry wrapper for transient failures:
```python
async def _retry(self, coro_fn, retries=3, backoff=(5, 15, 45)):
    """Retry a coroutine with exponential backoff."""
    last_error = None
    for i in range(retries):
        try:
            return await coro_fn()
        except Exception as e:
            last_error = e
            if i < retries - 1:
                wait = backoff[i] if i < len(backoff) else backoff[-1]
                logger.warning("Retry %d/%d after %ds: %s", i+1, retries, wait, e)
                await asyncio.sleep(wait)
    raise last_error
```

5. Wrap `search_people`, `get_profile`, `send_message` in retry:
```python
async def send_message(self, profile_url: str, message: str) -> bool:
    return await self._retry(lambda: self._send_message_impl(profile_url, message))

async def _send_message_impl(self, profile_url: str, message: str) -> bool:
    # ... original send_message code here
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
git add sidecar/adapters/
git commit -m "feat: port Facebook adapter to sidecar with retry logic"
```

---

### Task 7: Port AI Service to Sidecar

**Files:**
- Create: `sidecar/services/__init__.py`
- Create: `sidecar/services/ai_service.py`

- [ ] **Step 1: Copy and adapt AI service**

Create `sidecar/services/__init__.py` (empty).

Create `sidecar/services/ai_service.py` by copying from `backend/app/services/ai_service.py` with these changes:

1. Replace `from app.config import settings` with parameter-based config:
```python
class AIConfig:
    def __init__(self, provider: str, api_key: str, base_url: str | None = None):
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url

def _get_provider_config(config: AIConfig) -> tuple[str, str, str]:
    provider = config.provider.lower()
    if provider == "kimi":
        return "kimi", "https://api.moonshot.cn/v1", config.api_key
    elif provider == "anthropic":
        return "anthropic", "", config.api_key
    else:
        base = config.base_url or "https://api.openai.com/v1"
        return "openai", base, config.api_key
```

2. Update all public functions to accept `config: AIConfig` parameter:
```python
async def generate_greeting(profile_data: dict, persona: dict, config: AIConfig) -> str:
    # ... same logic, use config instead of settings
```

3. Add `evaluate_intent()` function for conversation engine:
```python
async def evaluate_intent(conversation: list[dict], persona: dict, config: AIConfig) -> dict:
    """Evaluate the lead's intent based on conversation history.

    Returns: {"action": "reply"|"transfer"|"stop", "reason": str, "contact": str|None, "reply": str|None}
    """
    system_prompt = (
        "你是一个对话意图分析助手。分析以下对话记录，判断对方的意向和下一步行动。\n"
        "返回 JSON 格式：\n"
        '- action: "reply"（继续对话）、"transfer"（高意向，转人工）、"stop"（对方拒绝或冷淡）\n'
        '- reason: 判断理由\n'
        '- contact: 如果对方给了联系方式（Telegram/WhatsApp/微信号），提取出来，否则为 null\n'
        '- reply: 如果 action 是 "reply"，生成一条回复内容，否则为 null\n'
    )

    transfer_conditions = persona.get("transfer_conditions", "")
    if transfer_conditions:
        system_prompt += f"\n转人工的条件：{transfer_conditions}"

    messages_text = "\n".join(
        f"{'我方' if m['role']=='assistant' else '对方'}: {m['content']}"
        for m in conversation
    )
    user_prompt = f"对话记录：\n{messages_text}\n\n请分析意图并返回 JSON。"

    provider, base_url, api_key = _get_provider_config(config)
    model = _default_model(provider)

    if provider == "anthropic":
        result_text = await _call_anthropic(api_key, model, system_prompt, user_prompt)
    else:
        result_text = await _call_openai_compatible(base_url, api_key, model, system_prompt, user_prompt)

    cleaned = result_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"action": "reply", "reason": "parse_error", "contact": None, "reply": cleaned}
```

- [ ] **Step 2: Commit**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
git add sidecar/services/
git commit -m "feat: port AI service to sidecar with intent evaluation"
```

---

### Task 8: Campaign Runner in Sidecar

**Files:**
- Create: `sidecar/services/campaign_runner.py`
- Modify: `sidecar/main.py` (add start/pause/stop handlers)

- [ ] **Step 1: Write campaign runner**

Create `sidecar/services/campaign_runner.py`:

```python
"""Campaign orchestrator — runs search-analyze-message pipeline."""

import asyncio
import logging
import random

from adapters.facebook import FacebookAdapter
from db import Database
from services.ai_service import AIConfig, analyze_profile, generate_greeting

logger = logging.getLogger(__name__)

# Track running tasks for cancellation
_running_tasks: dict[int, asyncio.Task] = {}

MAX_CONCURRENT_CAMPAIGNS = 2


async def start_campaign(campaign_id: int, db: Database, ai_config: AIConfig) -> str:
    """Start a campaign as a background asyncio task."""
    if len(_running_tasks) >= MAX_CONCURRENT_CAMPAIGNS:
        raise RuntimeError(f"Max {MAX_CONCURRENT_CAMPAIGNS} concurrent campaigns. Please wait.")

    if campaign_id in _running_tasks:
        raise RuntimeError(f"Campaign {campaign_id} is already running.")

    task = asyncio.create_task(_run_campaign(campaign_id, db, ai_config))
    _running_tasks[campaign_id] = task
    task.add_done_callback(lambda _: _running_tasks.pop(campaign_id, None))
    return f"Campaign {campaign_id} started."


async def pause_campaign(campaign_id: int, db: Database) -> str:
    await db.update_campaign(campaign_id, status="paused")
    return f"Campaign {campaign_id} paused."


async def stop_campaign(campaign_id: int, db: Database) -> str:
    await db.update_campaign(campaign_id, status="failed")
    task = _running_tasks.get(campaign_id)
    if task:
        task.cancel()
    return f"Campaign {campaign_id} stopped."


async def _run_campaign(campaign_id: int, db: Database, ai_config: AIConfig) -> None:
    logger.info("Campaign %d: starting", campaign_id)

    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        logger.error("Campaign %d not found", campaign_id)
        return

    persona = None
    if campaign["persona_id"]:
        persona = await db.get_persona(campaign["persona_id"])
    persona_dict = persona or {"system_prompt": "你是一位友善的社交媒体用户。"}

    await db.update_campaign(campaign_id, status="running")

    # Read proxy from settings
    proxy = await db.get_setting("proxy_server")

    adapter = FacebookAdapter(proxy_server=proxy)
    try:
        await adapter.initialize()
    except Exception as e:
        logger.error("Campaign %d: adapter init failed: %s", campaign_id, e)
        await db.update_campaign(campaign_id, status="failed")
        return

    try:
        # Search
        results = await adapter.search_people(
            keywords=campaign["search_keywords"] or "",
            region=campaign["search_region"] or "",
            industry=campaign["search_industry"] or "",
        )

        if not results:
            logger.warning("Campaign %d: no results", campaign_id)
            await db.update_campaign(campaign_id, status="completed", progress_total=0)
            return

        targets = results[:campaign["send_limit"]]
        await db.update_campaign(
            campaign_id,
            progress_total=len(targets),
            progress_current=0,
        )

        # Check daily limit
        send_interval_min = int(await db.get_setting("send_interval_min") or "60")
        send_interval_max = int(await db.get_setting("send_interval_max") or "180")
        max_daily = int(await db.get_setting("max_daily_messages") or "50")

        for idx, target in enumerate(targets):
            # Check pause/stop
            fresh = await db.get_campaign(campaign_id)
            if fresh["status"] in ("paused", "failed"):
                logger.info("Campaign %d: stopped at %d/%d", campaign_id, idx, len(targets))
                break

            # Check daily limit
            sent_today = await db.count_messages_today()
            if sent_today >= max_daily:
                logger.warning("Campaign %d: daily limit %d reached", campaign_id, max_daily)
                await db.update_campaign(campaign_id, status="paused")
                break

            # Check idempotency
            if await db.lead_already_messaged(target.get("platform_user_id", "")):
                logger.info("Campaign %d: skip already-messaged %s", campaign_id, target.get("name"))
                await db.update_campaign(campaign_id, progress_current=idx + 1)
                continue

            profile_url = target.get("profile_url", "")
            target_name = target.get("name", "unknown")
            logger.info("Campaign %d: processing %d/%d — %s", campaign_id, idx+1, len(targets), target_name)

            # Create lead
            lead_id = await db.create_lead(
                campaign_id=campaign_id,
                platform=campaign["platform"],
                platform_user_id=target.get("platform_user_id", ""),
                name=target_name,
                profile_url=profile_url,
            )

            try:
                # Analyze
                await db.update_lead(lead_id, status="analyzing")
                profile_data = await adapter.get_profile(profile_url)

                raw_html = profile_data.pop("raw_html", "")
                ai_analysis = {}
                if raw_html:
                    try:
                        ai_analysis = await analyze_profile(raw_html, ai_config)
                    except Exception as e:
                        logger.warning("Campaign %d: AI analysis failed: %s", campaign_id, e)

                merged = {**profile_data, **ai_analysis}
                await db.update_lead(
                    lead_id,
                    bio=(merged.get("bio") or "")[:500] or None,
                    industry=(merged.get("industry") or "")[:100] or None,
                    profile_data=merged,
                )

                # Generate greeting
                greeting = await generate_greeting(merged, persona_dict, ai_config)

                # Send message
                success = await adapter.send_message(profile_url, greeting)

                if success:
                    await db.update_lead(lead_id, status="messaged")
                    await db.create_message(lead_id, "outbound", greeting, ai_generated=True)
                else:
                    await db.update_lead(lead_id, status="failed")

            except Exception as e:
                logger.error("Campaign %d: error on lead %s: %s", campaign_id, target_name, e)
                await db.update_lead(lead_id, status="failed")

            await db.update_campaign(campaign_id, progress_current=idx + 1)

            # Wait interval
            if idx < len(targets) - 1:
                wait = random.randint(send_interval_min, send_interval_max)
                logger.info("Campaign %d: waiting %ds", campaign_id, wait)
                await asyncio.sleep(wait)

        # Complete
        fresh = await db.get_campaign(campaign_id)
        if fresh["status"] == "running":
            await db.update_campaign(campaign_id, status="completed")

        logger.info("Campaign %d: finished", campaign_id)

    except Exception as e:
        logger.error("Campaign %d: unhandled error: %s", campaign_id, e)
        await db.update_campaign(campaign_id, status="failed")
    finally:
        await adapter.close()
```

- [ ] **Step 2: Add start/pause/stop RPC handlers to main.py**

Add to `sidecar/main.py`:

```python
from services.campaign_runner import start_campaign, pause_campaign, stop_campaign
from services.ai_service import AIConfig

async def _get_ai_config() -> AIConfig:
    db = _get_db()
    provider = await db.get_setting("ai_provider") or "openai"
    api_key = await db.get_setting("ai_api_key") or ""
    base_url = await db.get_setting("ai_base_url")
    return AIConfig(provider=provider, api_key=api_key, base_url=base_url)


@server.method("start_campaign")
async def rpc_start_campaign(campaign_id: int) -> dict:
    db = _get_db()
    ai_config = await _get_ai_config()
    message = await start_campaign(campaign_id, db, ai_config)
    return {"message": message}


@server.method("pause_campaign")
async def rpc_pause_campaign(campaign_id: int) -> dict:
    db = _get_db()
    message = await pause_campaign(campaign_id, db)
    return {"message": message}


@server.method("stop_campaign")
async def rpc_stop_campaign(campaign_id: int) -> dict:
    db = _get_db()
    message = await stop_campaign(campaign_id, db)
    return {"message": message}
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
git add sidecar/services/campaign_runner.py sidecar/main.py
git commit -m "feat: add campaign runner with retry, daily limits, and idempotency"
```

---

## Phase 3: Conversation Engine + Message Monitoring

---

### Task 9: Message Monitor (DOM Observer + Polling)

**Files:**
- Create: `sidecar/services/message_monitor.py`
- Modify: `sidecar/adapters/facebook.py` (implement `read_new_messages`)

- [ ] **Step 1: Implement read_new_messages in Facebook adapter**

Add to `sidecar/adapters/facebook.py`:

```python
async def read_new_messages(self) -> list[dict]:
    """Check Messenger for new unread messages from known leads.

    Returns list of: {"sender_id": str, "sender_name": str, "content": str, "timestamp": str}
    """
    if not self._page:
        return []

    page = self._page
    messages = []

    try:
        # Navigate to Messenger inbox
        await page.goto("https://www.facebook.com/messages/t/", wait_until="domcontentloaded", timeout=30000)
        await _random_delay(3, 5)

        # Look for unread conversation indicators
        unread_convos = await page.query_selector_all(
            'div[role="row"][aria-current="false"] span[data-text="true"],'
            'a[role="link"][aria-current="false"] div[dir="auto"]'
        )

        for convo in unread_convos[:10]:
            try:
                # Check if this conversation has an unread indicator
                parent = await convo.evaluate_handle("el => el.closest('a[role=\"link\"]') || el.closest('div[role=\"row\"]')")
                unread_dot = await parent.query_selector('span[data-visualcompletion="ignore"]')
                if not unread_dot:
                    continue

                # Extract sender name
                name_el = await parent.query_selector('span[dir="auto"]')
                sender_name = (await name_el.inner_text()).strip() if name_el else ""

                # Click to open conversation
                await parent.click()
                await _random_delay(2, 3)

                # Read the last message
                msg_elements = await page.query_selector_all(
                    'div[role="row"] div[dir="auto"][data-text="true"]'
                )
                if msg_elements:
                    last_msg = msg_elements[-1]
                    content = (await last_msg.inner_text()).strip()

                    # Extract sender ID from URL
                    current_url = page.url
                    sender_id = current_url.split("/t/")[-1].rstrip("/") if "/t/" in current_url else ""

                    messages.append({
                        "sender_id": sender_id,
                        "sender_name": sender_name,
                        "content": content,
                        "timestamp": _now_iso(),
                    })

            except Exception as e:
                logger.debug("Error reading conversation: %s", e)
                continue

    except Exception as e:
        logger.error("read_new_messages failed: %s", e)

    return messages
```

- [ ] **Step 2: Write message monitor service**

Create `sidecar/services/message_monitor.py`:

```python
"""Message monitor — watches for new inbound messages and triggers AI replies."""

import asyncio
import logging
from datetime import datetime, timezone

from adapters.facebook import FacebookAdapter
from db import Database
from services.ai_service import AIConfig, evaluate_intent

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 30 * 60  # 30 minutes
POLL_INTERVAL = 5 * 60  # 5 minutes fallback


class MessageMonitor:
    def __init__(self, db: Database, adapter: FacebookAdapter, ai_config: AIConfig) -> None:
        self._db = db
        self._adapter = adapter
        self._ai_config = ai_config
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Message monitor started.")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Message monitor stopped.")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop: poll for new messages, process each."""
        while self._running:
            try:
                new_messages = await self._adapter.read_new_messages()
                for msg in new_messages:
                    await self._process_inbound_message(msg)
            except Exception as e:
                logger.error("Monitor loop error: %s", e)

            await asyncio.sleep(POLL_INTERVAL)

    async def _process_inbound_message(self, msg: dict) -> None:
        """Process a single inbound message: match to lead, evaluate intent, reply or transfer."""
        sender_id = msg.get("sender_id", "")
        content = msg.get("content", "")

        if not sender_id or not content:
            return

        # Match to existing lead
        leads = await self._db.list_leads(status=None)
        matched_lead = None
        for lead in leads:
            if lead["platform_user_id"] == sender_id:
                matched_lead = lead
                break

        if not matched_lead:
            logger.debug("Ignoring message from unknown sender: %s", sender_id)
            return

        lead_id = matched_lead["id"]

        # Skip if already transferred or rejected
        if matched_lead["status"] in ("transferred", "rejected"):
            return

        # Save inbound message
        await self._db.create_message(lead_id, "inbound", content)

        # Update lead status to in_conversation
        if matched_lead["status"] == "messaged":
            await self._db.update_lead(lead_id, status="in_conversation")

        # Build conversation history for AI
        db_messages = await self._db.get_conversation(lead_id)
        conversation = []
        for m in db_messages:
            role = "assistant" if m["direction"] == "outbound" else "user"
            conversation.append({"role": role, "content": m["content"]})

        # Get persona
        campaign = await self._db.get_campaign(matched_lead["campaign_id"])
        persona = {}
        if campaign and campaign.get("persona_id"):
            persona = await self._db.get_persona(campaign["persona_id"]) or {}

        # Evaluate intent
        result = await evaluate_intent(conversation, persona, self._ai_config)
        action = result.get("action", "reply")

        if action == "transfer":
            contact = result.get("contact")
            await self._db.update_lead(
                lead_id,
                status="transferred",
                intent_score="high",
                transfer_contact=contact,
            )
            logger.info("Lead %d transferred. Contact: %s", lead_id, contact)
            # Notification will be handled by the Tauri shell

        elif action == "stop":
            await self._db.update_lead(lead_id, status="rejected", intent_score="none")
            logger.info("Lead %d rejected.", lead_id)

        elif action == "reply":
            reply_text = result.get("reply", "")
            if reply_text:
                profile_url = matched_lead["profile_url"]
                success = await self._adapter.send_message(profile_url, reply_text)
                if success:
                    await self._db.create_message(lead_id, "outbound", reply_text, ai_generated=True)
                    logger.info("Auto-replied to lead %d", lead_id)
                else:
                    logger.error("Failed to send reply to lead %d", lead_id)
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
git add sidecar/services/message_monitor.py sidecar/adapters/facebook.py
git commit -m "feat: add message monitor with AI intent evaluation and auto-reply"
```

---

### Task 10: Mac System Notifications

**Files:**
- Modify: `tauri/src-tauri/src/main.rs` (add notification capability)
- Create: `sidecar/services/notifier.py`
- Modify: `sidecar/main.py` (add notification event emitter)

- [ ] **Step 1: Write notification helper in sidecar**

Create `sidecar/services/notifier.py`:

```python
"""Notification emitter — writes notification events to stderr for Tauri to pick up."""

import json
import sys
import logging

logger = logging.getLogger(__name__)

def emit_notification(title: str, body: str, urgency: str = "normal") -> None:
    """Emit a notification event as a JSON line to stderr.

    Tauri reads stderr and triggers macOS notifications.
    Format: {"type": "notification", "title": "...", "body": "...", "urgency": "normal|high"}
    """
    event = {
        "type": "notification",
        "title": title,
        "body": body,
        "urgency": urgency,
    }
    sys.stderr.write("NOTIFY:" + json.dumps(event, ensure_ascii=False) + "\n")
    sys.stderr.flush()
    logger.info("Notification: %s — %s", title, body)
```

- [ ] **Step 2: Integrate notifications into message monitor**

Add to `sidecar/services/message_monitor.py` in the `_process_inbound_message` method, after the transfer detection block:

```python
from services.notifier import emit_notification

# ... inside the "transfer" action block:
if action == "transfer":
    contact = result.get("contact")
    await self._db.update_lead(
        lead_id,
        status="transferred",
        intent_score="high",
        transfer_contact=contact,
    )
    emit_notification(
        title=f"{matched_lead['name']} - 高意向线索",
        body=f"对方提供了联系方式: {contact}" if contact else "对方表达了合作意向",
        urgency="high",
    )
```

- [ ] **Step 3: Add Tauri stderr reader for notifications**

Add to `tauri/src-tauri/src/main.rs` in the `setup` closure, after spawning sidecar:

```rust
// Read sidecar stderr for notifications
let stderr = sidecar.child.stderr.take().expect("no stderr");
let app_handle = app.handle().clone();
std::thread::spawn(move || {
    use std::io::{BufRead, BufReader};
    let reader = BufReader::new(stderr);
    for line in reader.lines() {
        if let Ok(line) = line {
            if line.starts_with("NOTIFY:") {
                let json_str = &line[7..];
                if let Ok(event) = serde_json::from_str::<serde_json::Value>(json_str) {
                    let title = event["title"].as_str().unwrap_or("LeadFlow");
                    let body = event["body"].as_str().unwrap_or("");
                    // Use Tauri notification plugin
                    let _ = tauri_plugin_notification::NotificationExt::notification(&app_handle)
                        .builder()
                        .title(title)
                        .body(body)
                        .show();
                }
            }
        }
    }
});
```

- [ ] **Step 4: Commit**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
git add sidecar/services/notifier.py sidecar/services/message_monitor.py tauri/src-tauri/src/main.rs
git commit -m "feat: add Mac system notifications for high-intent leads"
```

---

## Phase 4: MCP Server + OpenClaw Remote Control

---

### Task 11: Embedded MCP Server

**Files:**
- Create: `sidecar/mcp_server.py`
- Modify: `sidecar/main.py` (start MCP server alongside JSON-RPC)

- [ ] **Step 1: Write embedded MCP server**

Create `sidecar/mcp_server.py`:

```python
"""Embedded MCP server — exposes all sidecar functions as MCP tools for OpenClaw."""

import logging
from mcp.server.fastmcp import FastMCP

from db import Database
from services.ai_service import AIConfig

logger = logging.getLogger(__name__)

mcp = FastMCP("leadflow")

# These get set by main.py at startup
_db: Database | None = None
_ai_config_fn = None  # callable that returns AIConfig


def configure(db: Database, ai_config_fn) -> None:
    global _db, _ai_config_fn
    _db = db
    _ai_config_fn = ai_config_fn


# -- Campaign Management --

@mcp.tool()
async def create_campaign(
    platform: str,
    keywords: str,
    region: str = "",
    industry: str = "",
    persona_id: int = 0,
    send_limit: int = 20,
) -> str:
    """Create a new lead generation campaign. Platforms: facebook, instagram."""
    campaign_id = await _db.create_campaign(
        platform=platform,
        search_keywords=keywords,
        search_region=region,
        search_industry=industry,
        persona_id=persona_id if persona_id else None,
        send_limit=send_limit,
    )
    campaign = await _db.get_campaign(campaign_id)
    return (
        f"Campaign created!\n"
        f"- ID: {campaign['id']}\n"
        f"- Platform: {campaign['platform']}\n"
        f"- Keywords: {campaign['search_keywords']}\n"
        f"- Status: {campaign['status']}\n"
        f"- Send limit: {campaign['send_limit']}"
    )


@mcp.tool()
async def start_campaign(campaign_id: int) -> str:
    """Start a draft or paused campaign."""
    from services.campaign_runner import start_campaign as _start
    ai_config = await _ai_config_fn()
    msg = await _start(campaign_id, _db, ai_config)
    return msg


@mcp.tool()
async def pause_campaign(campaign_id: int) -> str:
    """Pause a running campaign."""
    from services.campaign_runner import pause_campaign as _pause
    return await _pause(campaign_id, _db)


@mcp.tool()
async def get_campaign_status(campaign_id: int) -> str:
    """Get campaign progress and stats."""
    campaign = await _db.get_campaign(campaign_id)
    if not campaign:
        return f"Campaign {campaign_id} not found."
    leads = await _db.list_leads(campaign_id=campaign_id)
    return (
        f"Campaign #{campaign['id']}\n"
        f"- Platform: {campaign['platform']}\n"
        f"- Keywords: {campaign['search_keywords']}\n"
        f"- Status: {campaign['status']}\n"
        f"- Progress: {campaign['progress_current']} / {campaign['progress_total']}\n"
        f"- Leads: {len(leads)}"
    )


@mcp.tool()
async def list_campaigns(status: str = "") -> str:
    """List all campaigns, optionally filtered by status."""
    campaigns = await _db.list_campaigns(status=status or None)
    if not campaigns:
        return "No campaigns yet."
    lines = ["All campaigns:\n"]
    for c in campaigns:
        lines.append(
            f"  [{c['id']}] {c['platform']} | "
            f"Keywords: {c['search_keywords']} | "
            f"Status: {c['status']} | "
            f"Progress: {c['progress_current']}/{c['send_limit']}"
        )
    return "\n".join(lines)


@mcp.tool()
async def search_and_message(
    platform: str,
    keywords: str,
    region: str = "",
    industry: str = "",
    send_limit: int = 10,
) -> str:
    """One-click: create a campaign and start it immediately."""
    campaign_id = await _db.create_campaign(
        platform=platform,
        search_keywords=keywords,
        search_region=region,
        search_industry=industry,
        persona_id=None,
        send_limit=send_limit,
    )
    from services.campaign_runner import start_campaign as _start
    ai_config = await _ai_config_fn()
    await _start(campaign_id, _db, ai_config)
    return (
        f"Campaign launched!\n"
        f"- ID: {campaign_id}\n"
        f"- Platform: {platform}\n"
        f"- Keywords: {keywords}\n"
        f"- Send limit: {send_limit}\n\n"
        f"Use get_campaign_status({campaign_id}) to check progress."
    )


# -- Persona Management --

@mcp.tool()
async def create_persona(description: str) -> str:
    """Create a persona from a natural language description. AI generates all fields."""
    from services.ai_service import generate_persona_from_description
    ai_config = await _ai_config_fn()
    persona_data = await generate_persona_from_description(description, ai_config)
    pid = await _db.create_persona(**persona_data)
    persona = await _db.get_persona(pid)
    return (
        f"Persona created!\n"
        f"- ID: {persona['id']}\n"
        f"- Name: {persona['name']}\n"
        f"- Company: {persona.get('company_name', 'N/A')}\n"
        f"- Tone: {persona.get('tone', 'N/A')}"
    )


@mcp.tool()
async def list_personas() -> str:
    """List all personas."""
    personas = await _db.list_personas()
    if not personas:
        return "No personas yet."
    lines = ["All personas:\n"]
    for p in personas:
        lines.append(f"  [{p['id']}] {p['name']} | Tone: {p.get('tone', 'N/A')}")
    return "\n".join(lines)


@mcp.tool()
async def update_persona(persona_id: int, field: str, value: str) -> str:
    """Update a specific field of a persona."""
    await _db.update_persona(persona_id, **{field: value})
    persona = await _db.get_persona(persona_id)
    return f"Persona #{persona_id} updated. {field} = {value}"


# -- Leads & Conversations --

@mcp.tool()
async def get_leads(campaign_id: int = 0, status: str = "", intent: str = "") -> str:
    """Query leads with optional filters."""
    leads = await _db.list_leads(
        campaign_id=campaign_id or None,
        status=status or None,
        intent=intent or None,
    )
    if not leads:
        return "No matching leads."
    lines = [f"Found {len(leads)} leads:\n"]
    for lead in leads:
        lines.append(
            f"  - {lead.get('name', 'Unknown')} | "
            f"Platform: {lead['platform']} | "
            f"Status: {lead['status']} | "
            f"Intent: {lead.get('intent_score', 'N/A')}"
        )
    return "\n".join(lines)


@mcp.tool()
async def get_conversation(lead_id: int) -> str:
    """Get full chat history for a lead."""
    messages = await _db.get_conversation(lead_id)
    lead = await _db.get_lead(lead_id)
    if not messages:
        return f"No messages for lead #{lead_id}."
    lines = [f"Conversation with {lead['name'] if lead else 'Unknown'}:\n"]
    for m in messages:
        direction = ">>>" if m["direction"] == "outbound" else "<<<"
        ai_tag = " [AI]" if m["ai_generated"] else ""
        lines.append(f"  {direction} {m['content']}{ai_tag}")
    return "\n".join(lines)


@mcp.tool()
async def get_high_intent_leads() -> str:
    """Get all leads marked as high-intent or transferred."""
    leads = await _db.list_leads(status="transferred")
    high = await _db.list_leads(intent="high")
    all_leads = {l["id"]: l for l in leads + high}
    if not all_leads:
        return "No high-intent leads."
    lines = [f"High-intent leads ({len(all_leads)}):\n"]
    for lead in all_leads.values():
        contact = lead.get("transfer_contact", "N/A")
        lines.append(
            f"  - {lead.get('name', 'Unknown')} | "
            f"Contact: {contact} | "
            f"Status: {lead['status']}"
        )
    return "\n".join(lines)


# -- System --

@mcp.tool()
async def get_daily_stats() -> str:
    """Today's activity summary."""
    sent_today = await _db.count_messages_today()
    return (
        f"Today's stats:\n"
        f"- Messages sent: {sent_today}"
    )
```

- [ ] **Step 2: Add generate_persona_from_description to AI service**

Add to `sidecar/services/ai_service.py`:

```python
async def generate_persona_from_description(description: str, config: AIConfig) -> dict:
    """Generate a complete persona from a natural language description.

    Returns dict with keys: name, company_name, company_description, tone,
    greeting_rules, conversation_rules, transfer_conditions, system_prompt
    """
    system_prompt = (
        "你是一个销售人设设计师。根据用户的描述，生成一个完整的销售人设配置。\n"
        "返回 JSON 格式，包含以下字段：\n"
        "- name: 人设名称\n"
        "- company_name: 公司名称\n"
        "- company_description: 公司简介\n"
        "- salesperson_name: 销售人员名字\n"
        "- salesperson_title: 销售人员职位\n"
        "- tone: 语气风格 (friendly/professional/casual)\n"
        "- greeting_rules: 打招呼规则（字符串）\n"
        "- conversation_rules: 对话规则（字符串）\n"
        "- transfer_conditions: 转人工条件（字符串）\n"
        "- system_prompt: 完整的系统提示词\n"
    )

    provider, base_url, api_key = _get_provider_config(config)
    model = _default_model(provider)

    if provider == "anthropic":
        result_text = await _call_anthropic(api_key, model, system_prompt, description)
    else:
        result_text = await _call_openai_compatible(base_url, api_key, model, system_prompt, description)

    cleaned = result_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "name": "Custom Persona",
            "system_prompt": cleaned,
            "tone": "friendly",
        }
```

- [ ] **Step 3: Wire MCP server into main.py startup**

Add to `sidecar/main.py` `_main()` function:

```python
import threading
import mcp_server

async def _main():
    global _db
    _db = Database(DB_PATH)
    await _db.initialize()
    logger.info("Sidecar started. DB: %s", DB_PATH)

    # Configure MCP server
    mcp_server.configure(_db, _get_ai_config)

    # Start MCP server in a background thread (for OpenClaw connections)
    # MCP uses its own stdio when invoked as `leadflow-mcp`
    # When running as sidecar, MCP listens on a Unix socket instead
    mcp_socket_path = os.path.join(DATA_DIR, "mcp.sock")

    try:
        await server.run()  # JSON-RPC for Tauri IPC
    finally:
        await _db.close()
```

- [ ] **Step 4: Create MCP entry point binary wrapper**

Create `sidecar/mcp_entry.py`:

```python
"""MCP entry point for OpenClaw remote connections.

This is the binary that OpenClaw invokes via stdio.
It connects to the running sidecar's MCP server.
"""

from mcp_server import mcp
from db import Database
import mcp_server as ms
import asyncio
import os

DATA_DIR = os.path.expanduser("~/Library/Application Support/LeadFlow")
DB_PATH = os.path.join(DATA_DIR, "leadflow.db")


async def _get_ai_config():
    from services.ai_service import AIConfig
    db = ms._db
    provider = await db.get_setting("ai_provider") or "openai"
    api_key = await db.get_setting("ai_api_key") or ""
    base_url = await db.get_setting("ai_base_url")
    return AIConfig(provider=provider, api_key=api_key, base_url=base_url)


async def _init():
    db = Database(DB_PATH)
    await db.initialize()
    ms.configure(db, _get_ai_config)


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(_init())
    mcp.run()  # stdio mode for OpenClaw
```

- [ ] **Step 5: Commit**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
git add sidecar/mcp_server.py sidecar/mcp_entry.py sidecar/services/ai_service.py sidecar/main.py
git commit -m "feat: add embedded MCP server with full OpenClaw remote control"
```

---

## Phase 5: Packaging & Distribution

---

### Task 12: PyInstaller Build for Sidecar

**Files:**
- Create: `sidecar/leadflow.spec`
- Create: `scripts/build-sidecar.sh`

- [ ] **Step 1: Create PyInstaller spec**

Create `sidecar/leadflow.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'aiosqlite',
        'httpx',
        'patchright',
        'mcp',
        'pydantic',
        'keyring',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='leadflow-sidecar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    target_arch='universal2',
)

# MCP entry point (separate binary)
b = Analysis(['mcp_entry.py'], pathex=[], hiddenimports=a.hiddenimports)
pyz2 = PYZ(b.pure, b.zipped_data)
exe2 = EXE(pyz2, b.scripts, b.binaries, b.datas, [], name='leadflow-mcp', console=True)
```

- [ ] **Step 2: Create build script**

Create `scripts/build-sidecar.sh`:

```bash
#!/bin/bash
set -e

echo "=== Building LeadFlow sidecar ==="

cd "$(dirname "$0")/../sidecar"

# Ensure venv
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller

# Build
pyinstaller leadflow.spec --distpath ../tauri/src-tauri/binaries/ --clean -y

echo "=== Sidecar built: tauri/src-tauri/binaries/leadflow-sidecar ==="

# Install Playwright browsers
python -m patchright install chromium
echo "=== Chromium browser installed ==="
```

- [ ] **Step 3: Make executable and test build**

```bash
chmod +x "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen/scripts/build-sidecar.sh"
bash "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen/scripts/build-sidecar.sh"
```

Expected: `tauri/src-tauri/binaries/leadflow-sidecar` binary exists.

- [ ] **Step 4: Commit**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
git add sidecar/leadflow.spec scripts/build-sidecar.sh
git commit -m "feat: add PyInstaller build config for sidecar binary"
```

---

### Task 13: Full Tauri Build + DMG

**Files:**
- Create: `scripts/build.sh`
- Modify: `tauri/src-tauri/tauri.conf.json` (finalize bundle config)

- [ ] **Step 1: Create full build script**

Create `scripts/build.sh`:

```bash
#!/bin/bash
set -e

echo "=== LeadFlow Full Build ==="

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Step 1: Build Python sidecar
echo "--- Building Python sidecar ---"
bash "$PROJECT_ROOT/scripts/build-sidecar.sh"

# Step 2: Build frontend + Tauri app
echo "--- Building Tauri app ---"
cd "$PROJECT_ROOT/tauri"
npm install
npm run tauri build

echo "=== Build complete! ==="
echo "DMG: $PROJECT_ROOT/tauri/src-tauri/target/release/bundle/dmg/"
ls -la "$PROJECT_ROOT/tauri/src-tauri/target/release/bundle/dmg/"
```

- [ ] **Step 2: Run full build**

```bash
chmod +x "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen/scripts/build.sh"
bash "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen/scripts/build.sh"
```

Expected: `.dmg` file created in `tauri/src-tauri/target/release/bundle/dmg/`.

- [ ] **Step 3: Test the built .app**

```bash
# Open the DMG and run the app
open "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen/tauri/src-tauri/target/release/bundle/dmg/"*.dmg
```

Expected: App launches, shows the React dashboard, can ping the sidecar.

- [ ] **Step 4: Commit**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
git add scripts/build.sh
git commit -m "feat: add full build script for DMG distribution"
```

---

## Phase 6: Instagram Adapter

---

### Task 14: Instagram Browser Adapter

**Files:**
- Create: `sidecar/adapters/instagram.py`

- [ ] **Step 1: Write Instagram adapter**

Create `sidecar/adapters/instagram.py`, following the same pattern as `facebook.py` but with Instagram-specific selectors:

```python
"""Instagram platform adapter using Patchright for browser automation."""

import asyncio
import logging
import os
import random
from pathlib import Path

from patchright.async_api import async_playwright, Page, BrowserContext

from adapters.base import PlatformAdapter

logger = logging.getLogger(__name__)

DATA_DIR = os.path.expanduser("~/Library/Application Support/LeadFlow")
BROWSER_DATA_DIR = os.path.join(DATA_DIR, "browser", "instagram")
COOKIES_FILE = os.path.join(DATA_DIR, "cookies", "instagram.json")
SCREENSHOT_DIR = os.path.join(DATA_DIR, "screenshots")

# Reuse same helpers from facebook module
from adapters.facebook import (
    _random_delay, _human_scroll, _random_mouse_move,
    _save_screenshot, USER_AGENTS, VIEWPORTS,
)


class InstagramAdapter(PlatformAdapter):
    """Instagram automation adapter."""

    def __init__(self, proxy_server: str | None = None) -> None:
        self._proxy_server = proxy_server
        self._playwright = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    async def initialize(self) -> None:
        os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
        self._playwright = await async_playwright().start()

        viewport = random.choice(VIEWPORTS)
        user_agent = random.choice(USER_AGENTS)

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
        ]
        if self._proxy_server:
            launch_args.append(f"--proxy-server={self._proxy_server}")

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=BROWSER_DATA_DIR,
            headless=False,
            args=launch_args,
            viewport=viewport,
            user_agent=user_agent,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            ignore_https_errors=True,
        )

        if os.path.exists(COOKIES_FILE):
            try:
                import json
                cookies = json.loads(Path(COOKIES_FILE).read_text())
                if cookies:
                    await self._context.add_cookies(cookies)
            except Exception as e:
                logger.warning("Failed to load Instagram cookies: %s", e)

        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        logger.info("Instagram adapter initialized.")

    async def search_people(self, keywords: str, region: str = "", industry: str = "") -> list[dict]:
        if not self._page:
            raise RuntimeError("Adapter not initialized.")

        page = self._page
        results = []

        try:
            query = " ".join(filter(None, [keywords, region, industry]))
            await page.goto(f"https://www.instagram.com/explore/search/keyword/?q={query}", wait_until="domcontentloaded", timeout=30000)
            await _random_delay(3, 5)

            # Instagram search results — click "Accounts" tab
            accounts_tab = await page.query_selector('a[href*="search"][role="tab"]:has-text("Accounts"), button:has-text("Accounts")')
            if accounts_tab:
                await accounts_tab.click()
                await _random_delay(2, 3)

            # Extract account links
            account_links = await page.query_selector_all('a[href^="/"][role="link"]')
            seen = set()
            for link in account_links[:30]:
                try:
                    href = await link.get_attribute("href") or ""
                    if not href or href in seen or href in ("/", "/explore/"):
                        continue
                    if href.count("/") > 2:
                        continue  # Skip non-profile links like /p/xxx/
                    seen.add(href)

                    name_el = await link.query_selector("span")
                    name = (await name_el.inner_text()).strip() if name_el else href.strip("/")

                    username = href.strip("/")
                    results.append({
                        "platform_user_id": username,
                        "name": name,
                        "profile_url": f"https://www.instagram.com/{username}/",
                        "snippet": "",
                    })
                except Exception:
                    continue

            logger.info("Instagram search: found %d results for '%s'", len(results), query)
        except Exception as e:
            logger.error("Instagram search failed: %s", e)

        return results

    async def get_profile(self, profile_url: str) -> dict:
        if not self._page:
            raise RuntimeError("Adapter not initialized.")

        page = self._page
        profile_data = {"profile_url": profile_url, "raw_html": ""}

        try:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await _random_delay(2, 4)

            # Extract name from header
            header = await page.query_selector('header section')
            if header:
                name_el = await header.query_selector('span[dir="auto"]')
                if name_el:
                    profile_data["name"] = (await name_el.inner_text()).strip()

            # Extract bio
            bio_el = await page.query_selector('header section div[dir="auto"] span')
            if bio_el:
                profile_data["bio"] = (await bio_el.inner_text()).strip()[:500]

            profile_data["raw_html"] = await page.content()
        except Exception as e:
            logger.error("Instagram get_profile failed: %s", e)

        return profile_data

    async def send_message(self, profile_url: str, message: str) -> bool:
        if not self._page:
            return False

        page = self._page

        try:
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await _random_delay(2, 4)

            msg_btn = await page.query_selector(
                'div[role="button"]:has-text("Message"),'
                'div[role="button"]:has-text("发消息")'
            )
            if not msg_btn:
                logger.error("Instagram: Message button not found on %s", profile_url)
                return False

            await msg_btn.click()
            await _random_delay(2, 4)

            msg_input = await page.wait_for_selector(
                'div[role="textbox"][contenteditable="true"],'
                'textarea[placeholder*="Message" i],'
                'textarea[placeholder*="消息"]',
                timeout=10000,
            )
            if not msg_input:
                return False

            await msg_input.click()
            for char in message:
                await page.keyboard.type(char)
                await asyncio.sleep(random.uniform(0.05, 0.15))

            await _random_delay(1, 2)
            await page.keyboard.press("Enter")
            await _random_delay(2, 3)

            logger.info("Instagram: message sent to %s", profile_url)
            return True
        except Exception as e:
            logger.error("Instagram send_message failed: %s", e)
            return False

    async def read_new_messages(self) -> list[dict]:
        """Stub — will be expanded when Instagram DM monitoring is needed."""
        return []

    async def close(self) -> None:
        try:
            if self._context:
                await self._context.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.error("Error closing Instagram adapter: %s", e)
```

- [ ] **Step 2: Update campaign runner to support platform selection**

In `sidecar/services/campaign_runner.py`, change the adapter initialization:

```python
from adapters.facebook import FacebookAdapter
from adapters.instagram import InstagramAdapter

# ... inside _run_campaign:
if campaign["platform"] == "instagram":
    adapter = InstagramAdapter(proxy_server=proxy)
else:
    adapter = FacebookAdapter(proxy_server=proxy)
```

- [ ] **Step 3: Commit**

```bash
cd "/Users/yewudao/Desktop/Tech Bridge/02_建造者/fb-lead-gen"
git add sidecar/adapters/instagram.py sidecar/services/campaign_runner.py
git commit -m "feat: add Instagram adapter with search, profile, and messaging"
```

---

## Summary of Deliverables

| Phase | What it delivers | Key files |
|-------|-----------------|-----------|
| 1: Foundation | Tauri app shell + Python sidecar + SQLite + React UI + IPC | `tauri/`, `sidecar/main.py`, `sidecar/db.py`, `sidecar/jsonrpc.py` |
| 2: Browser Automation | Facebook adapter + AI service + campaign runner with retry/limits | `sidecar/adapters/facebook.py`, `sidecar/services/` |
| 3: Conversation Engine | Message monitoring + AI auto-reply + intent detection + Mac notifications | `sidecar/services/message_monitor.py`, `sidecar/services/notifier.py` |
| 4: MCP Remote Control | Embedded MCP server + all tools for OpenClaw | `sidecar/mcp_server.py`, `sidecar/mcp_entry.py` |
| 5: Packaging | PyInstaller build + Tauri DMG build scripts | `scripts/build.sh`, `sidecar/leadflow.spec` |
| 6: Instagram | Instagram platform adapter | `sidecar/adapters/instagram.py` |
