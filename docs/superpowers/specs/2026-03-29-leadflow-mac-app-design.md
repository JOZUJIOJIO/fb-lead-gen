# LeadFlow Mac App - Design Spec

## 1. Product Definition

A native Mac application (.dmg) for AI-powered social media lead generation. The app controls a browser to search Facebook/Instagram, discover leads, send personalized messages, conduct multi-turn conversations, and classify leads by intent — all driven by the user's own LLM API key. Supports both local use (in-app AI chat) and remote control via OpenClaw MCP.

### Target User

Non-technical business owners who want to automate cold outreach on Facebook and Instagram. Zero command-line, zero Docker, zero config files.

### Success Criteria

- Double-click install, under 3 minutes to first campaign launch
- Multi-turn AI conversations on Facebook Messenger and Instagram DM
- Seamless OpenClaw remote control with full feature parity
- Mac system notifications for high-intent leads

## 2. Architecture

```
┌──────────────────────────────────────────────────────┐
│                    LeadFlow.app                       │
│                                                       │
│  ┌───────────┐    IPC     ┌────────────────────────┐ │
│  │   Tauri   │◄──────────►│    Python Sidecar      │ │
│  │   Shell   │            │    (single process)     │ │
│  │ (WebView) │            │                         │ │
│  └───────────┘            │  ┌──────────────────┐  │ │
│                           │  │   Core Engine     │  │ │
│                           │  │  - CampaignRunner │  │ │
│                           │  │  - ConvoEngine    │  │ │
│                           │  │  - PersonaStudio  │  │ │
│                           │  │  - AIService      │  │ │
│                           │  └────────┬─────────┘  │ │
│                           │           │             │ │
│                           │  ┌────────┴─────────┐  │ │
│                           │  │   MCP Server      │  │ │
│                           │  │  (embedded, stdio) │  │ │
│                           │  └──────────────────┘  │ │
│                           │           │             │ │
│                           │  ┌────────┴─────────┐  │ │
│                           │  │   Playwright      │  │ │
│                           │  │   Browser Pool    │  │ │
│                           │  └────────┬─────────┘  │ │
│                           └───────────┼────────────┘ │
│                                       │              │
│  ┌─────────────────┐                  │              │
│  │ SQLite           │    ┌────────────┴───────────┐  │
│  │ ~/Library/App    │    │  Facebook  │ Instagram  │  │
│  │ Support/LeadFlow │    └────────────────────────┘  │
│  └─────────────────┘                                 │
└──────────────────────────────────────────────────────┘
         ▲
         │ MCP (stdio over SSH tunnel / Tailscale)
         │
    ┌────┴─────┐
    │ OpenClaw │  (remote, when user is away)
    └──────────┘
```

### Component Responsibilities

| Component | Role |
|-----------|------|
| **Tauri Shell** | Native Mac window, renders React UI via system WebView, manages app lifecycle, system notifications |
| **Python Sidecar** | Single Python process bundled via PyInstaller. Hosts all business logic, Playwright browser, and embedded MCP server |
| **Core Engine** | Campaign orchestration, conversation engine, persona management, AI service (OpenAI/Claude/Kimi) |
| **MCP Server** | Embedded FastMCP instance. Exposes all Core Engine functions as MCP tools. Accepts stdio connections from OpenClaw |
| **Playwright Browser Pool** | Manages persistent browser contexts for Facebook and Instagram. Handles login session, cookie persistence, message monitoring |
| **SQLite** | Single-file database at `~/Library/Application Support/LeadFlow/leadflow.db`. Stores campaigns, leads, messages, personas, settings |

### IPC: Tauri <-> Python Sidecar

Tauri spawns the Python sidecar as a child process. Communication via **JSON-RPC over stdin/stdout**:

```
Tauri (Rust) --stdin/stdout JSON-RPC--> Python Sidecar
```

- Tauri frontend calls `invoke("create_campaign", {...})`
- Tauri Rust backend serializes to JSON-RPC, writes to sidecar stdin
- Python sidecar reads, executes, returns JSON-RPC response on stdout
- Tauri Rust backend deserializes, returns to frontend

This avoids HTTP entirely for local use. No ports, no CORS, no auth.

### MCP: OpenClaw <-> LeadFlow

The same Python sidecar process that serves the Tauri UI also hosts the MCP server. OpenClaw connects via stdio:

```json
{
  "mcpServers": {
    "leadflow": {
      "command": "ssh",
      "args": ["user@mac-ip", "/Applications/LeadFlow.app/Contents/Resources/leadflow-mcp"]
    }
  }
}
```

Or via Tailscale/local network. The `leadflow-mcp` binary is a thin wrapper that connects to the running sidecar's MCP socket.

Key principle: **MCP tools and Tauri IPC handlers call the same Core Engine functions.** Zero code duplication between local and remote paths.

## 3. Data Model (SQLite)

### campaigns
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| platform | TEXT | "facebook" or "instagram" |
| search_keywords | TEXT | Search query |
| search_region | TEXT | Optional region filter |
| search_industry | TEXT | Optional industry filter |
| persona_id | INTEGER FK | Links to personas table |
| send_limit | INTEGER | Max targets per campaign |
| status | TEXT | draft/running/paused/completed/failed |
| progress_current | INTEGER | Leads processed so far |
| progress_total | INTEGER | Total leads discovered |
| created_at | DATETIME | |
| updated_at | DATETIME | |

### leads
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | |
| campaign_id | INTEGER FK | |
| platform | TEXT | |
| platform_user_id | TEXT | Unique ID on platform |
| name | TEXT | |
| profile_url | TEXT | |
| bio | TEXT | Extracted bio |
| industry | TEXT | AI-inferred industry |
| status | TEXT | found/analyzing/messaged/in_conversation/high_intent/transferred/rejected/cold |
| intent_score | TEXT | high/medium/low/none |
| transfer_contact | TEXT | Telegram/WhatsApp number if provided |
| profile_data | JSON | Full extracted profile |
| created_at | DATETIME | |

### messages
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | |
| lead_id | INTEGER FK | |
| direction | TEXT | outbound/inbound |
| content | TEXT | Message text |
| ai_generated | BOOLEAN | |
| created_at | DATETIME | |

### personas
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | |
| name | TEXT | Persona display name |
| company_name | TEXT | |
| company_description | TEXT | |
| products | TEXT | |
| salesperson_name | TEXT | |
| salesperson_title | TEXT | |
| tone | TEXT | e.g. "friendly", "professional" |
| greeting_rules | TEXT | Rules for first message |
| conversation_rules | TEXT | Rules for follow-up replies |
| transfer_conditions | TEXT | When to stop and mark as high-intent |
| system_prompt | TEXT | Full AI system prompt |
| created_at | DATETIME | |

### settings
| Column | Type | Description |
|--------|------|-------------|
| key | TEXT PK | Setting name |
| value | TEXT | JSON-encoded value |

Settings include: ai_provider, api_keys (encrypted), send_interval_min/max, max_daily_messages, proxy_server.

## 4. Core Modules

### 4.1 Browser Engine

**Login Flow:**
1. User clicks "Login to Facebook" in the app
2. Tauri opens a visible Playwright browser window (not headless)
3. User manually logs in to Facebook
4. App saves cookies to `~/Library/Application Support/LeadFlow/cookies/facebook.json`
5. Subsequent automation reuses these cookies
6. Same flow for Instagram

**Browser Pool:**
- One persistent browser context per platform (Facebook, Instagram)
- Contexts share a single Chromium instance to save memory
- Cookie files loaded on context creation
- If cookies expire, app prompts user to re-login

**Anti-Detection:**
- Patchright (Playwright fork with anti-detection patches)
- Random viewport from pool of 5 sizes
- Random user-agent from pool of 5 strings
- Human-like typing: 50-150ms per character
- Random delays between actions: 2-6 seconds
- Random mouse movements before clicks
- Message send interval: configurable, default 60-180 seconds

### 4.2 Campaign Runner

Same pipeline as current project, but simplified:

```
search_people(keywords, region, industry, platform)
  → for each target (up to send_limit):
      → get_profile(profile_url)
      → analyze_profile(raw_html)  [AI call]
      → generate_greeting(profile, persona)  [AI call]
      → send_message(profile_url, greeting)
      → save lead + message to SQLite
      → wait random interval
```

Improvements over current:
- **Retry logic:** 3 attempts with exponential backoff (5s, 15s, 45s) for transient failures
- **Daily limit enforcement:** Check `messages_sent_today` count before each send
- **Concurrent campaign limit:** Max 2 campaigns running simultaneously
- **Idempotency:** Check if lead already messaged (by platform_user_id) before sending

### 4.3 Conversation Engine

Monitors incoming messages and generates AI replies.

**Message Detection (hybrid approach):**

1. **Primary: DOM monitoring**
   - Keep Messenger / Instagram DM page open in a background browser tab
   - Inject MutationObserver script to detect new message DOM nodes
   - On new message detected: extract sender, content, timestamp
   - Heartbeat refresh every 30 minutes to prevent session expiry

2. **Fallback: Polling**
   - If DOM monitoring fails (page crash, session expired), fall back to polling
   - Every 5 minutes: navigate to DM inbox, scan for unread indicators
   - Extract new messages from conversations with known leads

**Reply Flow:**
```
New inbound message detected
  → Match to existing lead (by platform_user_id)
  → If no match: ignore (not our lead)
  → Load conversation history from SQLite
  → Load persona rules
  → AI decides:
      a) Generate reply → send it → save to messages table
      b) Mark as high-intent → stop auto-reply → push Mac notification
      c) Mark as rejected → stop auto-reply
      d) Mark as cold (no response 48h) → stop auto-reply
```

**Transfer Detection (AI-judged):**
The AI receives the full conversation + persona's `transfer_conditions` field. Default transfer conditions:
- Lead provides a Telegram/WhatsApp/WeChat number or username
- Lead explicitly asks about pricing, cooperation, or partnership
- Lead asks to move conversation to another platform

When transfer is detected:
- `lead.status = "transferred"`
- `lead.transfer_contact = <extracted contact info>`
- Mac system notification: "Lead [Name] shared WhatsApp: +86xxx. Ready for handoff."
- Auto-reply stops for this lead

### 4.4 Persona Studio

**AI-assisted persona creation:**
User describes their business in natural language in the app's chat interface:
> "I sell home furniture to Southeast Asian markets, targeting small retailers"

AI generates a complete persona:
- Company name, description, products
- Salesperson name and title
- Tone (friendly/professional/casual)
- Greeting rules (first message template guidance)
- Conversation rules (follow-up strategy)
- Transfer conditions (when to flag as high-intent)
- Full system prompt

User can edit any field manually. Multiple personas supported.

**This same flow works via OpenClaw MCP** — the `create_persona` tool accepts a natural language description and returns the generated persona for confirmation.

### 4.5 AI Service

Supports three providers, user selects one during setup:

| Provider | Model | Use |
|----------|-------|-----|
| OpenAI | gpt-4o-mini | Profile analysis, greeting generation, conversation replies |
| Anthropic | claude-sonnet-4-20250514 | Same |
| Kimi/Moonshot | moonshot-v1-8k | Same (budget option) |

All AI calls go through a unified `ai_call(system_prompt, user_prompt) -> str` function. Provider is selected at runtime based on settings.

API keys stored encrypted in SQLite settings table using macOS Keychain via `keyring` library.

## 5. MCP Tools (OpenClaw Remote Control)

All tools call the same Core Engine functions used by the Tauri UI.

### Campaign Management
| Tool | Description |
|------|-------------|
| `create_campaign(platform, keywords, region?, industry?, persona_id?, send_limit?)` | Create a new campaign |
| `start_campaign(campaign_id)` | Start a draft/paused campaign |
| `pause_campaign(campaign_id)` | Pause a running campaign |
| `get_campaign_status(campaign_id)` | Get campaign progress and stats |
| `list_campaigns(status?)` | List all campaigns, optionally filtered |
| `search_and_message(platform, keywords, region?, industry?, send_limit?)` | One-click: create + start |

### Persona Management
| Tool | Description |
|------|-------------|
| `create_persona(description)` | AI generates persona from natural language description |
| `update_persona(persona_id, field, value)` | Update a specific persona field |
| `list_personas()` | List all personas |
| `get_persona(persona_id)` | Get full persona details |

### Lead & Conversation
| Tool | Description |
|------|-------------|
| `get_leads(campaign_id?, status?, intent?)` | Query leads with filters |
| `get_conversation(lead_id)` | Get full chat history for a lead |
| `get_high_intent_leads()` | Get all leads marked as high-intent/transferred |
| `get_lead_summary(campaign_id)` | Stats: total, messaged, replied, high-intent, rejected |

### System
| Tool | Description |
|------|-------------|
| `get_status()` | App health: browser sessions active, campaigns running, today's message count |
| `get_daily_stats()` | Today's activity: messages sent, replies received, new high-intent leads |

## 6. Frontend Pages (Tauri WebView)

Reuse existing React codebase with modifications:

### 6.1 Onboarding (first launch only)
1. Welcome screen
2. Select AI provider + enter API key
3. Login to Facebook (opens browser window)
4. (Optional) Login to Instagram
5. Done — enter dashboard

### 6.2 Dashboard
- Today's stats cards: messages sent, replies received, high-intent leads, active campaigns
- Active campaigns with progress bars
- Recent high-intent leads (quick action: view conversation, copy contact)

### 6.3 Campaigns
- List view: all campaigns with status, progress, platform icon
- New campaign form: platform, keywords, region, industry, persona selector, send limit
- Campaign detail: lead pipeline (found → analyzing → messaged → in_conversation → high_intent → transferred), conversation viewer per lead

### 6.4 Leads
- Filterable table: by campaign, status, intent, platform
- Lead detail: profile info, full conversation history, intent classification, transfer contact

### 6.5 Persona Studio
- List of personas with preview cards
- New persona: AI chat interface (describe your business → AI generates persona) + manual editor
- Edit persona: form with all fields editable

### 6.6 Settings
- AI provider and API key
- Browser sessions status (Facebook: logged in / expired, Instagram: same)
- Re-login buttons
- Send interval config
- Daily message limit
- Proxy config (optional)

## 7. Notifications

Mac native notifications via Tauri's notification API:

| Event | Notification |
|-------|-------------|
| Lead gives contact info | "[Name] shared WhatsApp: +86xxx. Ready for handoff." |
| Lead expresses strong intent | "[Name] asked about pricing. High-intent lead." |
| Campaign completed | "Campaign 'keyword' finished. 15 messaged, 3 replied." |
| Browser session expired | "Facebook session expired. Please re-login." |

## 8. Packaging & Distribution

### Build Pipeline
```
React frontend → npm run build → static files
Python sidecar → PyInstaller → single binary (~50MB)
Playwright Chromium → bundled (~150MB) or first-launch download
Tauri → tauri build → .dmg (~200MB total)
```

### File Layout in .app Bundle
```
LeadFlow.app/
  Contents/
    MacOS/
      LeadFlow          (Tauri binary, ~5MB)
    Resources/
      leadflow-sidecar  (Python PyInstaller binary, ~50MB)
      leadflow-mcp      (MCP entry point, thin wrapper)
      chromium/          (Playwright browser, ~150MB)
      frontend/          (React static files)
    Info.plist
```

### User Data Location
```
~/Library/Application Support/LeadFlow/
  leadflow.db           (SQLite database)
  cookies/
    facebook.json       (Facebook cookies)
    instagram.json      (Instagram cookies)
  logs/
    leadflow.log        (rotating log, max 10MB x 3)
```

### Code Signing
- Requires Apple Developer account ($99/year) for notarization
- Without signing: users see "unidentified developer" warning, can bypass via System Preferences
- Signing recommended for distribution but not blocking for MVP

## 9. Migration from Current Codebase

### What to Keep
- `backend/app/adapters/platforms/facebook.py` — Facebook browser automation (adapt for Instagram too)
- `backend/app/services/ai_service.py` — AI provider abstraction
- `backend/app/services/campaign_runner.py` — Campaign orchestration loop (add retry + conversation)
- `frontend/src/` — React components (adapt from Next.js to plain React/Vite)
- `mcp-server/server.py` — MCP tool definitions (expand with persona/conversation tools)

### What to Remove
- Docker: `docker-compose.yml`, all `Dockerfile`s
- PostgreSQL: async driver, connection pool config
- Redis: all references
- Auth: JWT, login endpoint, password hashing (local app, no auth needed)
- CORS middleware (no HTTP server)
- Xvfb virtual display (Mac has native display)

### What to Add
- Tauri shell (Rust project)
- JSON-RPC IPC layer
- SQLite database layer (replace SQLAlchemy async PostgreSQL with aiosqlite)
- Conversation Engine (new module)
- Message monitoring (DOM observer + polling)
- Instagram adapter (based on Facebook adapter pattern)
- Persona AI generation
- Mac notifications
- PyInstaller build config
- Onboarding flow

## 10. Out of Scope (for MVP)

- Twitter/X support
- Mobile app
- Cloud sync between devices
- Team/multi-user support
- Webhook-based message detection (requires Facebook app review)
- Auto-update mechanism (can add post-MVP via Tauri updater)
- End-to-end encryption for stored data
