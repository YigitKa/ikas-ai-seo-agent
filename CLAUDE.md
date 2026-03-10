# CLAUDE.md — ikas AI SEO Agent

This file provides AI assistants with everything needed to understand, navigate, and contribute to this codebase effectively.

---

## Project Overview

**ikas AI SEO Agent** is a Python-based tool that connects to ikas e-commerce stores via their GraphQL API, analyzes product listings for SEO quality, and uses AI to rewrite titles, descriptions, and meta fields. It ships with a **React/TypeScript web UI** backed by a **FastAPI REST API**.

**Key capabilities:**
- Fetches products from ikas via OAuth2 + GraphQL
- Scores each product's SEO on a 100-point rule-based rubric (including GEO/AI citability)
- Sends content to an AI provider (Claude, GPT, Gemini, Ollama, etc.) for rewrite suggestions
- Shows before/after diffs, allows approval, and applies changes back to ikas
- Real-time AI chat with MCP (Model Context Protocol) tool integration for live store data queries
- GEO (Generative Engine Optimization) rewrites and `llms.txt` generation for AI citability
- Supports Turkish and English product content
- Dry-run mode by default (no writes to ikas unless explicitly enabled)

---

## Repository Structure

```text
ikas-ai-seo-agent/
├── main.py                  # Entry point — web (default) or dev mode
├── start.py                 # Backend/frontend coordinator with Vite dev server
├── requirements.txt         # Python dependencies
├── .env.example             # All configurable env vars with descriptions
│
├── config/
│   └── settings.py          # .env loader + .cache/user_settings.json overrides, AppConfig
│
├── core/                    # Business logic (no UI dependencies)
│   ├── models.py            # Pydantic models: Product, SeoScore, SeoSuggestion, ChatMessage, etc.
│   ├── ikas_client.py       # Async GraphQL client for ikas API (httpx)
│   ├── ai_client.py         # Multi-provider AI abstraction (factory + adapters)
│   ├── claude_client.py     # Legacy Anthropic-only client (backward compat)
│   ├── product_manager.py   # Orchestrator — coordinates all core operations
│   ├── seo_analyzer.py      # Rule-based SEO scoring engine (100-point scale + GEO)
│   ├── csv_handler.py       # CSV import/export for products and suggestions
│   ├── prompt_store.py      # Loads and renders prompt templates from prompts/
│   ├── chat_service.py      # Multi-turn AI chat with MCP tool integration
│   ├── mcp_client.py        # ikas MCP (Model Context Protocol) JSON-RPC client
│   ├── provider_service.py  # Provider detection, health checks, model discovery
│   ├── settings_service.py  # Settings management service
│   ├── suggestion_service.py # Suggestion field operations
│   ├── html_utils.py        # HTML parsing and sanitization utilities
│   └── presentation.py      # Display formatting utilities
│
├── api/                     # FastAPI REST API + WebSocket
│   ├── main.py              # FastAPI app with CORS, lifespan, SPA static file serving
│   ├── dependencies.py      # Request-scoped ProductManager injection (fresh per request)
│   ├── schemas.py           # API request/response Pydantic schemas
│   └── routers/
│       ├── products.py      # Product list, fetch, detail, sync, reset endpoints
│       ├── seo.py           # SEO analysis, scoring, llms.txt generation endpoints
│       ├── suggestions.py   # Suggestion CRUD endpoints
│       ├── settings.py      # Settings management endpoints
│       └── chat.py          # WebSocket chat + MCP endpoints
│
├── web/                     # React/TypeScript frontend (Vite)
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx         # React entry point
│       ├── App.tsx          # Root component
│       ├── api/
│       │   └── client.ts    # API client wrapper functions
│       ├── components/
│       │   ├── ChatPanel.tsx
│       │   ├── ProductTable.tsx
│       │   ├── ScoreCard.tsx
│       │   ├── chat/        # Chat utilities
│       │   │   ├── ChatMessage.tsx
│       │   │   ├── chatUtils.ts
│       │   │   ├── promptParams.ts
│       │   │   └── suggestionUtils.ts
│       │   └── dashboard/   # Dashboard layout components
│       │       ├── DashboardDetail.tsx
│       │       ├── DashboardHeader.tsx
│       │       ├── DashboardSidebar.tsx
│       │       ├── DashboardEmptyState.tsx
│       │       ├── constants.ts
│       │       └── productUrl.ts
│       ├── hooks/
│       │   └── useChat.ts   # Custom React hook for chat state
│       ├── pages/
│       │   ├── Dashboard.tsx
│       │   └── Settings.tsx
│       └── types/
│           └── index.ts     # TypeScript type definitions
│
├── data/
│   ├── db.py                # Async SQLite schema + helpers (aiosqlite)
│   └── cache.py             # File-based TTL cache keyed by MD5 hash
│
├── prompts/                 # Editable AI prompt templates ({{variable}} substitution)
│   ├── description_rewrite.system.txt
│   ├── description_rewrite.user.txt
│   ├── translation_en.system.txt
│   ├── translation_en.user.txt
│   └── README.txt
│
└── tests/
    ├── fixtures/
    │   └── sample_products.json    # 4 sample products for unit tests
    ├── test_seo_analyzer.py
    ├── test_ai_client.py
    ├── test_claude_client.py
    ├── test_ikas_client.py
    ├── test_db.py
    ├── test_settings.py
    ├── test_html_utils.py
    ├── test_presentation.py
    ├── test_provider_service.py
    ├── test_settings_service.py
    ├── test_suggestion_service.py
    ├── test_chat_service.py
    ├── test_mcp_client.py
    ├── test_product_manager.py
    └── test_products_api.py
```

---

## Development Environment Setup

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd ikas-ai-seo-agent

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install frontend dependencies
cd web && npm install && cd ..

# 5. Configure environment
cp .env.example .env
# Edit .env with your ikas credentials and AI provider key

# 6. Run tests to verify setup
python -m pytest tests/ -v

# 7. Launch in dev mode (backend + frontend hot-reload)
python main.py dev
```

---

## Running the Application

### Web UI — development mode (default workflow)
```bash
python main.py dev          # Backend :8000 + Vite :5173 in parallel
```

### Web UI — production mode
```bash
python main.py              # Builds frontend if needed, starts FastAPI on :8000
```

### Using start.py directly
```bash
python start.py dev         # Backend :8000 + Vite :5173 in parallel
python start.py build       # Build frontend only
python start.py backend     # Start backend only
python start.py prod        # Build frontend + start backend
```

Port fallback: if port 8000 is busy, `start.py` automatically tries the next 20 ports.

---

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Single test file
python -m pytest tests/test_seo_analyzer.py -v

# Single test function
python -m pytest tests/test_seo_analyzer.py::test_analyze_product_low_score -v
```

No CI/CD pipeline is currently configured. Tests use `pytest` and mock objects — no live API calls are made.

---

## Configuration (.env)

All configuration is loaded from `.env` via `config/settings.py`. The `AppConfig` Pydantic model is the single source of truth. See `.env.example` for the full list of variables.

### Required variables
| Variable | Description |
|---|---|
| `IKAS_STORE_NAME` | Your ikas store subdomain (e.g., `mystore`) |
| `IKAS_CLIENT_ID` | OAuth2 client ID from ikas admin panel |
| `IKAS_CLIENT_SECRET` | OAuth2 client secret |
| `AI_PROVIDER` | One of: `anthropic`, `openai`, `gemini`, `openrouter`, `ollama`, `lm-studio`, `custom`, `none` |
| `AI_API_KEY` | API key for the selected provider (not needed for `ollama`, `lm-studio`, `none`) |

### Optional variables
| Variable | Default | Description |
|---|---|---|
| `AI_MODEL_NAME` | Provider default | Override the default model |
| `AI_BASE_URL` | Provider default | For custom/local endpoints |
| `AI_TEMPERATURE` | `0.7` | AI generation temperature |
| `AI_MAX_TOKENS` | `2000` | Max tokens per AI response |
| `AI_THINKING_MODE` | `false` | Enable extended thinking (Anthropic only) |
| `IKAS_MCP_TOKEN` | — | ikas MCP token for AI chat with live store data |
| `STORE_LANGUAGES` | `tr,en` | Comma-separated language codes |
| `SEO_TARGET_KEYWORDS` | — | Comma-separated keywords for scoring |
| `SEO_LOW_SCORE_THRESHOLD` | `70` | Threshold below which products need optimization |
| `DRY_RUN` | `true` | Set to `false` to write changes to ikas |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### Config loading behavior
- `get_config()` in `config/settings.py` returns a cached singleton `AppConfig`
- **Three-layer config resolution** (highest priority first):
  1. `.cache/user_settings.json` — runtime overrides persisted via the Settings UI
  2. `.env` file — initial defaults (treated as read-only; never modified by the app)
  3. Hardcoded defaults in `AppConfig`
- Missing required vars trigger an interactive prompt when running in a TTY
- Legacy `ANTHROPIC_API_KEY` is auto-mapped to `AI_API_KEY` for backward compatibility
- `save_config_to_db()` persists runtime changes to `.cache/user_settings.json`, never to `.env`
- `save_config_to_env` is a backward-compat alias for `save_config_to_db`

---

## Architecture & Key Patterns

### Layered architecture

```text
[ Web: React/TypeScript SPA ]
          |
          v
[ FastAPI REST API + WebSocket ]
          |
          v
ProductManager (core/product_manager.py)  [request-scoped — fresh per HTTP request]
    ├── IkasClient      -> ikas GraphQL API
    ├── AIClient         -> AI provider (pluggable)
    ├── SEOAnalyzer      -> rule-based scoring (incl. GEO/AI citability)
    ├── ChatService      -> multi-turn AI chat + MCP tools
    ├── IkasMCPClient    -> ikas MCP (live store queries)
    ├── ProviderService  -> provider detection & health
    ├── CSVHandler       -> import/export
    └── Database         -> async SQLite (aiosqlite) + file cache
```

### Data flow for a typical "analyze + rewrite" operation
1. `ProductManager.fetch_products()` → `IkasClient` fetches products via async GraphQL
2. `SEOAnalyzer.analyze_product()` → scores each product, returns `SeoScore`
3. `AIClient.generate_suggestion()` → sends product content + prompt to AI, returns `SeoSuggestion`
4. Results are stored in SQLite via async `aiosqlite`
5. UI displays scores and diffs for user approval
6. On approval: `ProductManager.apply_suggestion()` → `IkasClient` writes back to ikas (if `DRY_RUN=false`)

### Design patterns used
- **Factory** — `create_ai_client(config)` in `core/ai_client.py` instantiates the correct provider adapter
- **Adapter** — All AI providers implement `BaseAIClient` with a uniform `generate()` interface
- **Orchestrator** — `ProductManager` coordinates all core modules; the UI/API only calls it
- **Singleton** — `get_config()` caches a single `AppConfig` instance per process
- **Template** — Prompts use `{{variable}}` placeholders, rendered by `PromptStore`
- **Repository** — `data/db.py` abstracts all async SQLite reads/writes behind plain functions
- **Dependency Injection** — `api/dependencies.py` yields a fresh `ProductManager` per FastAPI request (request-scoped, not a global singleton)

### Async usage
`IkasClient`, `IkasMCPClient`, and `data/db.py` use async I/O (`httpx.AsyncClient`, `aiosqlite`). The FastAPI backend handles async natively. All database access is async — do not call `db.*` functions from synchronous code.

---

## Core Modules Reference

### `core/models.py`
Key Pydantic models:
- `Product` — id, name, slug, description (TR), `description_translations` dict (keyed by lang code), meta title/description, tags, category, price, sku, image_urls
- `SeoScore` — `total_score` (0–100), per-field breakdown including `ai_citability_score` (0–10, GEO), issues list, suggestions list
- `SeoSuggestion` — all original/suggested field pairs, `thinking_text`, status (pending/approved/rejected)
- `ChatMessage` — role, content, tool calls, timestamps for multi-turn conversations
- `ChatResponse` — AI chat response with thinking text, tool results, `suggestion_saved` dict
- `AppConfig` — mirrors all `.env` variables including `ai_thinking_mode` and `seo_low_score_threshold`

### `core/seo_analyzer.py` — SEO scoring rubric

Scoring inspired by Ahrefs, Semrush, Yoast, Moz, and Screaming Frog.

| Field | Max Points | Key checks |
|---|---|---|
| Title | 15 | Length 30–60 chars, no excessive caps, no special chars, power words |
| Description (TR) | 20 | Min 150 words, paragraph structure, HTML elements (headings, lists, bold) |
| Description (EN) | 5 | Min 100 words, no Turkish chars |
| Meta Title | 15 | Length 50–60 chars, brand separator, differs from product title |
| Meta Description | 10 | Length 120–160 chars, CTA presence |
| Keyword Optimization | 10 | Target keywords in description/meta, category alignment, title-desc consistency |
| Content Quality | 10 | Keyword stuffing detection (>5%), TTR vocabulary diversity, repeated n-grams, title-content coherence |
| Technical SEO | 10 | Image count (ideal 3-5), tags (3-5), category, URL-friendly slug, price |
| Readability | 5 | Avg sentence length (15-25 words), sentence length variation, transition words |
| AI Citability (GEO) | 10 | Structured facts, clear product attributes, AI-readable formatting |

### `core/ai_client.py` — supported providers
| `AI_PROVIDER` value | SDK / Endpoint | Default model |
|---|---|---|
| `anthropic` | Anthropic Python SDK | `claude-haiku-4-5-20251001` |
| `openai` | OpenAI Python SDK | `gpt-4o-mini` |
| `gemini` | OpenAI-compat endpoint | `gemini-1.5-flash` |
| `openrouter` | OpenAI-compat endpoint | `openai/gpt-4o-mini` |
| `ollama` | Local OpenAI-compat | `llama3.2` |
| `lm-studio` | Local REST API (native + OpenAI-compat) | first available |
| `custom` | Custom `AI_BASE_URL` | set `AI_MODEL_NAME` |
| `none` | No AI — scoring only | — |

Key implementations:
- `AnthropicAIClient` — Direct Anthropic SDK with extended thinking support and token/cost tracking
- `OpenAICompatibleClient` — Unified handler for all OpenAI-compatible providers
- `NoneAIClient` — Placeholder that raises errors if rewrite is attempted

### `core/ikas_client.py`
- OAuth2 token fetch via form-encoded POST to ikas auth endpoint
- All product reads/writes use GraphQL queries/mutations
- Async methods: `fetch_products()`, `update_product()`, `test_connection()`
- Token is cached in-memory and refreshed on expiry
- ikas API URL: `https://api.myikas.com/api/v1/admin/graphql`

### `core/chat_service.py` — AI chat with live store data
- Multi-turn conversation history (max 40 messages)
- Integrates with `IkasMCPClient` for real-time store queries (products, categories, inventory)
- Max 5 sequential tool-call rounds per user message
- Turkish/English language detection
- System prompt with product and score context; uses configurable agent prompt templates
- Per-WebSocket-connection isolation of chat history and MCP state

### `core/mcp_client.py` — ikas MCP integration
- JSON-RPC 2.0 over HTTP client
- Endpoint: `https://api.myikas.com/api/v2/admin/mcp`
- Tool discovery and execution for live store data access
- Session ID tracking via headers
- Async context manager pattern

### `core/provider_service.py` — provider management
- Provider labels, model options, and metadata
- Base URL resolution (auto-appends `/v1` for OpenAI-compatible)
- Provider health checking via API test requests
- Model discovery via provider's model list endpoints

### `core/html_utils.py` — HTML processing
- `html_to_plain_text()` — Strip HTML with break preservation
- `sanitize_html_for_prompt()` — Clean HTML for AI prompts
- `has_html_markup()` — Detect HTML content

### `data/db.py` — async SQLite tables (aiosqlite)
| Table | Purpose |
|---|---|
| `products` | Cached product snapshots |
| `seo_scores` | Computed scores per product per run |
| `suggestions` | AI-generated rewrites with status |
| `operation_log` | Audit log of all apply operations |
| `settings` | Persisted key-value settings |

Database file is created at `./seo_optimizer.db` in the working directory. All functions are `async` — always `await` them.

---

## API Endpoints

The FastAPI app (`api/main.py`) exposes the following REST endpoints:

| Route | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/products/` | GET | List cached products |
| `/api/products/fetch` | POST | Fetch products from ikas |
| `/api/products/sync` | POST | Full product sync |
| `/api/products/reset` | POST | Clear all cached products |
| `/api/products/{id}` | GET | Get single product |
| `/api/seo/analyze` | POST | Analyze all products for SEO |
| `/api/seo/analyze/{id}` | POST | Analyze single product |
| `/api/seo/scores/{id}` | GET | Get SEO scores for a product |
| `/api/seo/generate-llms-txt` | GET | Generate `llms.txt` for AI crawlers (GEO) |
| `/api/suggestions/generate/{id}` | POST | Generate AI suggestion for a product |
| `/api/suggestions/generate-field/{id}` | POST | Generate AI suggestion for a single field |
| `/api/suggestions/{id}` | GET | Get suggestions for a product |
| `/api/suggestions/{id}/approve` | PATCH | Approve a suggestion |
| `/api/suggestions/{id}/reject` | PATCH | Reject a suggestion |
| `/api/suggestions/{id}/update` | PATCH | Update suggestion content |
| `/api/suggestions/apply` | POST | Apply approved suggestions to ikas |
| `/api/settings` | GET | Get current config |
| `/api/settings` | PUT | Save settings |
| `/api/settings/prompts` | GET | Get prompt templates |
| `/api/settings/prompts` | PUT | Save prompt templates |
| `/api/settings/prompts/reset` | POST | Reset prompts to defaults |
| `/api/settings/providers` | GET | List AI providers |
| `/api/settings/health` | GET | Provider health check |
| `/api/settings/models/{provider}` | GET | List models for a provider |
| `/api/settings/lm-studio/status` | GET | LM Studio connection status |
| `/api/settings/test-connection` | POST | Test provider connection |
| `/ws/chat` | WebSocket | Multi-turn AI chat with MCP tools |
| `/ws/progress` | WebSocket | Progress notifications |
| `/api/mcp/status` | GET | MCP connection status |
| `/api/mcp/initialize` | POST | Initialize MCP session |
| `/api/chat/clear` | POST | Clear chat history |

Production builds of the React frontend are served as SPA static files from `web/dist/`.

---

## Web UI Components (`web/src/`)

React/TypeScript SPA built with Vite. Communicates with the FastAPI backend via REST and WebSocket.

### Tech stack
- **React 19** + TypeScript ~5.9
- **TailwindCSS 4** (via `@tailwindcss/vite` plugin)
- **Vite 7** (dev server + build)
- **@tanstack/react-query 5** (server state management)
- **React Router 7** (client-side routing)
- **react-markdown** + **remark-gfm** (markdown rendering in chat)

### Page structure
- `pages/Dashboard.tsx` — Main dashboard: product list, SEO scores, AI suggestions, diff viewer
- `pages/Settings.tsx` — Provider config, API keys, model selection, prompt editing

### Component groups
- `components/dashboard/` — Dashboard layout: header, sidebar, detail panel, empty state
- `components/chat/` — Chat utilities: message rendering, prompt parameters, suggestion creation from chat
- `components/ChatPanel.tsx` — Full chat UI with WebSocket connection
- `components/ProductTable.tsx` — Product list with pagination and score badges
- `components/ScoreCard.tsx` — SEO score breakdown display

---

## Prompt Templates

Prompt files live in `prompts/` and are loaded by `core/prompt_store.py`. They use `{{variable}}` syntax. Users can edit them at runtime via the Settings page in the UI, and changes are saved to disk.

Available templates:
- `description_rewrite.system.txt` / `.user.txt` — rewrites product descriptions
- `translation_en.system.txt` / `.user.txt` — translates Turkish content to English

The prompt system includes:
- Per-prompt metadata (title, description, variables, height)
- Agent template support for chat system prompts
- Validation of placeholder names
- Fallback to hardcoded defaults if files are missing or empty

To add a new prompt type, add `.system.txt` + `.user.txt` files and reference them in `PromptStore`.

---

## Coding Conventions

- **Python 3.10+** required (uses `match`/`case`, `|` union types)
- **Pydantic v2** for all data models — use `model_validate()`, not `parse_obj()`
- **Type hints** on all public function signatures
- **Async** for all ikas API calls, MCP operations, and database access (aiosqlite); keep sync wrappers at UI boundary only
- **No wildcard imports** — always import explicitly
- **`DRY_RUN=true` is the safe default** — never change this without explicit user intent
- All user-visible strings are plain strings; formatting belongs in the UI layer
- Prompts are never hardcoded in Python — always loaded from `prompts/` (with fallback defaults in `prompt_store.py`)
- New AI providers must subclass `BaseAIClient` and be registered in `create_ai_client()`
- New API endpoints go in `api/routers/` and are registered in `api/main.py`
- Frontend API client functions go in `web/src/api/client.ts`
- **`.env` is read-only at runtime** — never write to it; use `save_config_to_db()` to persist settings to `.cache/user_settings.json`
- `ProductManager` is request-scoped in FastAPI — never store it as a module-level global

---

## Common Tasks

### Add a new AI provider
1. Create a subclass of `BaseAIClient` in `core/ai_client.py`
2. Implement `rewrite_product()`, `rewrite_field()`, and `translate_description_to_en()`
3. Register it in the `create_ai_client()` factory function
4. Add the provider name to the enum in `core/models.py` (`AppConfig.ai_provider`)
5. Add provider metadata in `core/provider_service.py`
6. Document it in `README.md` and `.env.example`

### Add a new SEO scoring rule
1. Edit `core/seo_analyzer.py` — add your rule to the relevant field scorer
2. Update the max points constant if the rule changes the total weight
3. Add a test case to `tests/test_seo_analyzer.py`

### Add a new API endpoint
1. Add the route function in the appropriate router in `api/routers/`
2. Add request/response schemas in `api/schemas.py` if needed
3. Register the router in `api/main.py` if it's a new router file

### Add a new database table
1. Add `CREATE TABLE IF NOT EXISTS` to the schema in `data/db.py`
2. Add async helper functions (insert, fetch, update) in the same file
3. Call the schema init from the existing `init_db()` function

### Persist a new config setting at runtime
1. Add the field to `AppConfig` in `core/models.py`
2. Add the env-var mapping to `KEY_MAP` in `config/settings.py`
3. Load it in `get_config()` using `_getenv()`
4. The Settings API router will automatically include it in save/load via the key map

---

## Dependencies

### Python (`requirements.txt`)
```
anthropic>=0.40.0
openai>=1.0.0
httpx>=0.27.0
pydantic>=2.0.0
pandas>=2.0.0
python-dotenv>=1.0.0
aiofiles>=23.0.0
aiosqlite>=0.20.0
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
websockets>=12.0
```

### Frontend (`web/package.json`)
- React 19, TypeScript ~5.9, Vite 7
- TailwindCSS 4 (via `@tailwindcss/vite`)
- `@tanstack/react-query` 5 (server state)
- `react-router-dom` 7
- `react-markdown` + `remark-gfm`

---

## Gotchas & Known Issues

- **ikas GraphQL field names** differ from REST conventions — verify against the ikas API docs
- **OAuth token** is not persisted across restarts — re-fetched automatically on each run
- **`DRY_RUN=true`** is the default — changes will NOT be written to ikas unless explicitly set to `false`
- The `claude_client.py` legacy module is kept for backward compatibility; new code should use `ai_client.py`
- `save_config_to_env` is a backward-compat alias for `save_config_to_db` — both write to `.cache/user_settings.json`, never to `.env`
- When running in a non-TTY environment (e.g., CI), missing env vars will raise an error instead of prompting
- SQLite database file is created at `./seo_optimizer.db` in the working directory
- All `data/db.py` functions are async — calling them without `await` will silently return a coroutine object
- Port 8000 is used by default for the backend; `start.py` auto-falls back to next available port if busy
- `ProductManager` is request-scoped — do not cache it across requests or store it as a module-level global
- The desktop UI (`ui/` directory) has been removed; the project is now web-only
