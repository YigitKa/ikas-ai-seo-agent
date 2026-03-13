# CLAUDE.md — ikas AI SEO Agent

This file provides AI assistants with everything needed to understand, navigate, and contribute to this codebase effectively.

---

## Project Overview

**ikas AI SEO Agent** is a Python-based tool that connects to ikas e-commerce stores via their GraphQL API, analyzes product listings for SEO quality, and uses AI to rewrite titles, descriptions, and meta fields. It ships with a **React/TypeScript web UI** backed by a **FastAPI REST API**.

**Key capabilities:**
- Fetches products from ikas via OAuth2 + GraphQL
- Scores each product's SEO on a 100-point rule-based rubric (including GEO/AI citability)
- **Agentic SEO optimisation** — AI autonomously scores products, identifies weak areas, iteratively rewrites fields, validates improvements, and saves suggestions via tool calling
- Sends content to an AI provider (Claude, GPT, Gemini, Ollama, etc.) for rewrite suggestions
- GEO (Generative Engine Optimization) rewrites and `llms.txt` generation for AI citability
- Full **GEO site audit** — crawls a website, runs 5 parallel analysis agents, and produces a composite GEO score with an action plan
- Shows before/after diffs, allows approval, and applies changes back to ikas
- Real-time AI chat with **multi-agent architecture** (SEO Expert, Store Operator, General) and MCP tool integration for live store data queries
- **Structured option buttons** in chat — AI proposals and approval questions render as clickable buttons; no manual typing needed for option selection
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
│   ├── models.py            # Pydantic models: Product, SeoScore, SeoSuggestion, ChatMessage, AgentEvent, AgentResult, etc.
│   ├── ikas_client.py       # Async GraphQL client for ikas API (httpx)
│   ├── ai_client.py         # Multi-provider AI abstraction (factory + adapters)
│   ├── agent_tools.py       # AgentTool, AgentToolkit, built-in tools (score, validate, save), toolkit factories
│   ├── agent_orchestrator.py # Generic agent loop with tool calling (run + stream)
│   ├── claude_client.py     # Legacy Anthropic-only client (backward compat)
│   ├── product_manager.py   # Orchestrator — coordinates all core operations + agentic rewrite
│   ├── seo_analyzer.py      # Rule-based SEO scoring engine (100-point scale + GEO)
│   ├── geo_audit.py         # Full GEO audit pipeline (GeoAuditor class)
│   ├── prompt_store.py      # Loads and renders prompt templates; multi-agent + agentic system prompts
│   ├── chat_service.py      # Multi-turn AI chat with MCP tool integration + AgentToolkit
│   ├── chat_operation_guidance.py # Operation suggestion footer and false-action safety logic
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
│       ├── seo.py           # SEO analysis, scoring, llms.txt, geo-audit endpoints
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
│   ├── geo_rewrite.system.txt   # GEO rewrite system prompt (auto-created if missing)
│   ├── geo_rewrite.user.txt     # GEO rewrite user prompt (auto-created if missing)
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
    ├── test_chat_apply_flow.py
    ├── test_mcp_client.py
    ├── test_product_manager.py
    ├── test_products_api.py
    ├── test_geo_audit.py
    ├── test_agent_tools.py
    └── test_agent_orchestrator.py
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
    ├── IkasClient           -> ikas GraphQL API
    ├── AIClient             -> AI provider (pluggable)
    ├── AgentOrchestrator    -> tool-calling agent loop (iterative rewrite)
    │   └── AgentToolkit     -> built-in tools (score, validate, save, search, guidelines)
    ├── SEOAnalyzer          -> rule-based scoring (incl. GEO/AI citability)
    ├── GeoAuditor           -> full site GEO audit pipeline (standalone, no ProductManager dependency)
    ├── ChatService          -> multi-turn AI chat + multi-agent routing + MCP tools + AgentToolkit
    ├── IkasMCPClient        -> ikas MCP (live store queries)
    ├── ProviderService      -> provider detection & health
    └── Database             -> async SQLite (aiosqlite) + file cache
```

### Data flow for a typical "analyze + rewrite" operation

**Agentic mode** (tool-calling providers — Ollama, OpenAI, Anthropic, Gemini, OpenRouter, LM Studio, custom):
1. `ProductManager.rewrite_product()` detects tool-calling support → creates `AgentOrchestrator` with `AgentToolkit`
2. Agent autonomously: scores product → identifies weak fields → proposes rewrites → validates with `validate_rewrite` → saves via `save_suggestion`
3. Multiple iterations possible (max 8) — agent retries if validation shows no improvement
4. Result stored in SQLite; UI displays scores and diffs for user approval
5. SSE streaming available via `POST /api/suggestions/generate/{id}/stream`

**Fallback mode** (`none` provider):
1. `ProductManager.fetch_products()` → `IkasClient` fetches products via async GraphQL
2. `SEOAnalyzer.analyze_product()` → scores each product, returns `SeoScore`
3. `AIClient.rewrite_product()` → single-shot prompt to AI, returns `SeoSuggestion`
4. Results are stored in SQLite via async `aiosqlite`
5. UI displays scores and diffs for user approval
6. On approval: `ProductManager.apply_suggestion()` → `IkasClient` writes back to ikas (if `DRY_RUN=false`)

### Data flow for a GEO site audit
1. Client posts `{ url, max_pages }` to `POST /api/seo/geo-audit`
2. `GeoAuditor.run_full_audit()` crawls the homepage + sitemap (up to `max_pages`)
3. 5 analysis agents run in parallel via `asyncio.gather`:
   - AI visibility (citability score, robots.txt crawler policy, llms.txt check, brand mentions)
   - Platform readiness (ChatGPT / Perplexity / Google AIO signal scores)
   - Technical SEO (HTTPS, mobile viewport, CSP, render-blocking, SSR)
   - Content quality (readability, EEAT signals, freshness)
   - Schema markup (JSON-LD detection, type variety)
4. `_synthesize()` combines the five dimensions into a composite GEO score using fixed weights
5. `_build_report()` returns a prioritized Markdown action plan
6. Full `GeoAuditResponse` (JSON) is returned to the client

### Design patterns used
- **Factory** — `create_ai_client(config)` in `core/ai_client.py` instantiates the correct provider adapter
- **Adapter** — All AI providers implement `BaseAIClient` with a uniform `generate()` interface
- **Orchestrator** — `ProductManager` coordinates all core modules; the UI/API only calls it
- **Agent Loop** — `AgentOrchestrator` in `core/agent_orchestrator.py` runs an iterative tool-calling loop: LLM call → tool execution → result injection → repeat until done or max iterations
- **Toolkit** — `AgentToolkit` in `core/agent_tools.py` groups related tools; toolkit factories (`create_seo_rewrite_toolkit`, `create_chat_toolkit`, `create_batch_toolkit`) assemble curated subsets for different use cases
- **Singleton** — `get_config()` caches a single `AppConfig` instance per process
- **Template** — Prompts use `{{variable}}` placeholders, rendered by `PromptStore`
- **Repository** — `data/db.py` abstracts all async SQLite reads/writes behind plain functions
- **Dependency Injection** — `api/dependencies.py` yields a fresh `ProductManager` per FastAPI request (request-scoped, not a global singleton)
- **Multi-agent routing** — `chat_service.py` selects one of three agent personas (SEO Expert, Store Operator, General) based on the conversation context; prompts are defined in `prompt_store.py` as `AGENT_SYSTEM_PROMPTS_TR`
- **Registry** — `ToolRegistry` in `chat_service.py` decouples tool dispatch from implementation; tools register without modifying the dispatcher
- **Strategy** — `apply_seo_to_ikas` uses IkasClient (OAuth/GraphQL) first, with MCP mutation as fallback
- **Structured Options** — AI responses and programmatic builders (e.g. `_build_suggestion_saved_response`) embed JSON option arrays that the frontend parses into clickable buttons, ensuring deterministic user input without free-text ambiguity

### Async usage
`IkasClient`, `IkasMCPClient`, `GeoAuditor`, and `data/db.py` use async I/O (`httpx.AsyncClient`, `aiosqlite`). The FastAPI backend handles async natively. All database access is async — do not call `db.*` functions from synchronous code.

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
- `AgentToolCall` — record of a single tool invocation (name, args, result, duration)
- `AgentEvent` — streaming event from `AgentOrchestrator` (types: thinking, tool_call, tool_result, response_chunk, completed, error)
- `AgentResult` — final result of an agent run (content, thinking, tool_calls_made, iterations, suggestion_saved)

### `core/agent_tools.py` — Agent tool definitions and toolkits
- `AgentTool` dataclass — name, description, JSON Schema parameters, async handler
- `AgentToolkit` — registry class with `register()`, `get_openai_functions()`, `execute()`
- Built-in tools: `seo_score_product`, `get_product_details`, `search_products`, `validate_rewrite`, `save_suggestion`, `get_seo_guidelines`
- Toolkit factories: `create_seo_rewrite_toolkit()` (5 tools for rewrite pipeline), `create_chat_toolkit()` (6 tools for chat), `create_batch_toolkit()` (5 tools for batch operations)

### `core/agent_orchestrator.py` — Generic agent loop
- `supports_tool_calling(config)` — returns `True` for all providers except `none`
- `AgentOrchestrator` — provider-agnostic agent loop using OpenAI-compatible `/chat/completions` endpoint
- `run()` — blocking execution, returns `AgentResult`
- `stream()` — async iterator yielding `AgentEvent` (thinking, tool_call, tool_result, response_chunk, completed, error)
- `cancel()` — cancels the active request
- Extracts `<think>...</think>` blocks from model responses as thinking text
- Max iterations safety limit (default 10)

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

### `core/geo_audit.py` — Full GEO audit pipeline

`GeoAuditor` performs a standalone, provider-agnostic crawl-and-score of any public website URL. It does not require an ikas connection or AI provider.

**Pipeline stages:**

| Stage | Method | What it does |
|---|---|---|
| Discovery | `_discover()` | Fetches homepage HTML; parses `sitemap.xml` for additional URLs; crawls up to `max_pages` same-domain pages |
| AI Visibility | `_analyze_ai_visibility()` | Scores passage citability (134–167 word "optimal" blocks), analyzes `robots.txt` for AI crawler policies, checks for `llms.txt`, scans for brand-platform mentions |
| Platform Analysis | `_analyze_platforms()` | Estimates ChatGPT / Perplexity / Google AIO readiness from FAQ, Q&A, source, and comparison signals |
| Technical SEO | `_analyze_technical_seo()` | Checks HTTPS, mobile viewport, CSP, asset deferral/preload, and SSR markup presence |
| Content Quality | `_analyze_content_quality()` | Measures avg sentence length, EEAT signals (author/about/contact/review mentions), date freshness |
| Schema Markup | `_analyze_schema()` | Detects `application/ld+json` blocks and enumerates `@type` values |
| Synthesis | `_synthesize()` | Combines the six category scores with fixed weights into a composite GEO score (0–100) |
| Report | `_build_report()` | Renders a prioritized Markdown action plan |

**Synthesis weights:**

| Category | Weight |
|---|---|
| AI Citability / Visibility | 25% |
| Brand Authority Signals | 20% |
| Content Quality (EEAT) | 20% |
| Technical Foundations | 15% |
| Structured Data | 10% |
| Platform Optimization | 10% |

**Known AI crawlers tracked in `robots.txt` analysis:** GPTBot, ChatGPT-User, CCBot, ClaudeBot, Claude-Web, anthropic-ai, PerplexityBot, Google-Extended, GoogleOther, Bytespider, Amazonbot, Applebot-Extended, Meta-ExternalAgent, OAI-SearchBot.

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
- `build_geo_rewrite_request()` — Helper that loads `geo_rewrite` prompt templates and builds the LLM request for GEO rewrites
- All providers implement `rewrite_product_for_geo()` — generates AI-bot-optimised, encyclopaedic product descriptions

### `core/prompt_store.py` — prompt templates and multi-agent system prompts

**Editable prompt files** (stored in `prompts/`, auto-created from defaults if missing):
| Key | File | Variables |
|---|---|---|
| `description_system` | `description_rewrite.system.txt` | — |
| `description_user` | `description_rewrite.user.txt` | `name`, `description`, `category`, `keywords` |
| `translation_system` | `translation_en.system.txt` | — |
| `translation_user` | `translation_en.user.txt` | `name`, `description`, `category` |
| `geo_rewrite_system` | `geo_rewrite.system.txt` | — |
| `geo_rewrite_user` | `geo_rewrite.user.txt` | `name`, `description`, `category`, `issues`, `keywords` |

**Multi-agent system prompts** (not user-editable; defined in `AGENT_SYSTEM_PROMPTS_TR`):
| Key | Persona | Role |
|---|---|---|
| `"seo"` | `AGENT_SEO_EXPERT_PROMPT_TR` | Creative SEO copywriter — rewrites titles, descriptions, meta tags |
| `"operator"` | `AGENT_STORE_OPERATOR_PROMPT_TR` | Data/operations analyst — uses MCP tools for live store data (stock, orders, prices) |
| `"general"` | `AGENT_GENERAL_PROMPT_TR` | General assistant — answers product, SEO, inventory, and store management questions |

`ChatService` selects the appropriate agent prompt based on routing logic. Both TR and EN conversations are supported (language is auto-detected).

**Agentic system prompts** (not user-editable; defined in `prompt_store.py`):
| Constant | Used by | Purpose |
|---|---|---|
| `REWRITE_AGENT_SYSTEM_PROMPT` | `AgentOrchestrator` via `ProductManager` | Instructs agent to score → rewrite → validate → save iteratively |
| `BATCH_AGENT_SYSTEM_PROMPT` | Batch optimize pipeline | Instructs agent to find low-score products and optimize in bulk |
| `GEO_AGENT_SYSTEM_PROMPT` | GEO audit AI enhancement | Instructs agent to interpret GEO audit results and create action plans |

### `core/ikas_client.py`
- OAuth2 token fetch via form-encoded POST to ikas auth endpoint
- All product reads/writes use GraphQL queries/mutations
- Async methods: `fetch_products()`, `update_product()`, `test_connection()`
- Token is cached in-memory and refreshed on expiry
- ikas API URL: `https://api.myikas.com/api/v1/admin/graphql`

### `core/chat_service.py` — AI chat with live store data
- Multi-turn conversation history (max 40 messages)
- Multi-agent routing via `_route_to_agent()`: selects `"seo"`, `"operator"`, or `"general"` agent per message using semantic LLM routing (no explicit tags needed)
- **Structured option buttons** — AI responses that contain a trailing JSON block (`[{"tone":"...","value":"..."}]`) are parsed by the frontend into clickable buttons; users select options by clicking instead of typing
- `_build_single_apply_confirmation_response()` — builds field-level apply options (Meta / Icerik / Hepsi / Iptal) as structured buttons
- `_build_suggestion_saved_response()` — after saving a draft, shows Uygula / Detayli Sec / Iptal action buttons
- `CHAT_ACTION` protocol — buttons with an `action` key send `[[CHAT_ACTION:<action>]]` hidden messages; handled by `_maybe_handle_single_product_apply_flow()`
- `_extract_message_directives()` returns 4-tuple: `(cleaned_message, instruction, agent_type, allow_tools)`
- `ToolRegistry` — lightweight tool name→handler map; currently registers `save_seo_suggestion` and `apply_seo_to_ikas`
- `_build_chat_tools()` assembles 3-layer tool list: Registry tools → AgentToolkit tools → MCP tools (MCP only for `operator` agent)
- `apply_seo_to_ikas` tool: dual-route strategy (IkasClient OAuth/GraphQL first, MCP mutation fallback)
- `save_seo_suggestion` tool: saves to in-memory session store (`_session_pending_suggestions`), not to DB
- `_build_auth_headers()` handles Anthropic (`x-api-key`) vs all other providers (`Authorization: Bearer`)
- Max 5 sequential tool-call rounds per user message
- Integrates with `IkasMCPClient` for real-time store queries (products, categories, inventory)
- System prompt layers: `CHAT_FLOW_SYSTEM_PROMPT_TR` + agent persona + `IKAS_OPERATION_GUIDE_TR` + product context
- Per-WebSocket-connection isolation of chat history and MCP state

### `core/chat_operation_guidance.py` — Operation guidance helpers
- `select_product_operation_suggestion()` — context-aware footer suggesting next ikas operation
- `append_operation_suggestion()` — appends operation footer to assistant response
- `append_false_action_disclaimer()` — safety net: if LLM falsely claims it applied changes without a tool call, appends a warning disclaimer
- All pattern matching uses Turkish-normalized text (`MATCH_NORMALIZATION_TABLE`)

### `core/mcp_client.py` — ikas MCP integration
- JSON-RPC 2.0 over Streamable HTTP transport
- Endpoint: `https://api.myikas.com/api/v2/admin/mcp`
- Tool discovery via `tools/list` and execution via `call_tool()`
- `introspect_operation(name)` — fetches GraphQL schema for an operation; results cached in `_introspect_cache`
- `execute_mutation(name, query, vars)` — runs a mutation using introspect→execute chain
- `get_tools_as_openai_functions()` — converts 50+ ikas operations to OpenAI function calling format
- Session ID tracking via `mcp-session-id` header
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
| `/api/seo/geo-audit` | POST | Run full GEO audit for a website URL |
| `/api/suggestions/generate/{id}` | POST | Generate AI suggestion for a product |
| `/api/suggestions/generate/{id}/stream` | POST | Generate AI suggestion with SSE streaming (agentic mode) |
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

### GEO Audit endpoint details
`POST /api/seo/geo-audit`

Request body (`GeoAuditRequest`):
```json
{ "url": "https://example.com", "max_pages": 8 }
```

Response (`GeoAuditResponse`):
```json
{
  "url": "https://example.com",
  "timestamp": "2026-03-10T12:00:00Z",
  "discovery": { "business_type": "ecommerce", "sitemap_count": 45, "crawled_pages": [...] },
  "analysis": {
    "ai_visibility": { "citability_score": 62, "llms_txt": {...}, "ai_crawler_analysis": {...}, "brand_mentions": {...} },
    "platform_analysis": { "readiness": { "chatgpt": 67, "perplexity": 55, "google_aio": 72 }, "recommendations": [...] },
    "technical_seo": { "score": 75, "issues": [...] },
    "content_quality": { "score": 60, "readability": 18.3, "eeat_signals": 3, "freshness_signal": true },
    "schema_markup": { "score": 30, "detected": 0, "types": [], "recommendation": "..." }
  },
  "synthesis": { "geo_score": 61, "category_scores": {...}, "weights": {...} },
  "report_markdown": "# GEO Audit Report — ..."
}
```

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
- `components/chat/` — Chat utilities: message rendering, prompt parameters, suggestion option parsing (JSON→buttons)
- `components/ChatPanel.tsx` — Full chat UI with WebSocket connection, multi-agent awareness, and **interaction panel** (renders structured options from the latest assistant message as clickable buttons above the input area)
- `components/ProductTable.tsx` — Product list with pagination and score badges
- `components/ScoreCard.tsx` — SEO score breakdown display

---

## Prompt Templates

Prompt files live in `prompts/` and are loaded by `core/prompt_store.py`. They use `{{variable}}` syntax. Users can edit them at runtime via the Settings page in the UI, and changes are saved to disk. Missing files are auto-created from in-code defaults on first access.

Available editable templates:
- `description_rewrite.system.txt` / `.user.txt` — rewrites product descriptions for SEO
- `translation_en.system.txt` / `.user.txt` — translates Turkish content to English
- `geo_rewrite.system.txt` / `.user.txt` — rewrites product descriptions in encyclopaedic GEO format for AI bot citability

The prompt system includes:
- Per-prompt metadata (title, description, variables, height) in `PROMPT_EDITOR_META`
- Three editor groups shown in the Settings UI: "Aciklama", "Ceviri", "GEO Yeniden Yazim"
- Agent template support for chat system prompts (`AGENT_SYSTEM_PROMPTS_TR`)
- Validation of placeholder names before saving
- Fallback to hardcoded defaults (`PROMPT_DEFAULTS`) if files are missing or empty

To add a new prompt type: add `.system.txt` + `.user.txt` entries to `PROMPT_FILES`, `PROMPT_DEFAULTS`, `PROMPT_EDITOR_GROUPS`, and `PROMPT_EDITOR_META` in `prompt_store.py`.

---

## Coding Conventions

- **Python 3.10+** required (uses `match`/`case`, `|` union types)
- **Pydantic v2** for all data models — use `model_validate()`, not `parse_obj()`
- **Type hints** on all public function signatures
- **Async** for all ikas API calls, MCP operations, GEO audit crawling, and database access (aiosqlite); keep sync wrappers at UI boundary only
- **No wildcard imports** — always import explicitly
- **`DRY_RUN=true` is the safe default** — never change this without explicit user intent
- All user-visible strings are plain strings; formatting belongs in the UI layer
- Prompts are never hardcoded in Python — always loaded from `prompts/` (with fallback defaults in `prompt_store.py`)
- New AI providers must subclass `BaseAIClient` and implement `rewrite_product()`, `rewrite_field()`, `translate_description_to_en()`, and `rewrite_product_for_geo()`
- New API endpoints go in `api/routers/` and are registered in `api/main.py`
- Frontend API client functions go in `web/src/api/client.ts`
- **`.env` is read-only at runtime** — never write to it; use `save_config_to_db()` to persist settings to `.cache/user_settings.json`
- `ProductManager` is request-scoped in FastAPI — never store it as a module-level global
- `GeoAuditor` is stateless and instantiated directly in the route handler — it does not go through `ProductManager`

---

## Common Tasks

### Add a new AI provider
1. Create a subclass of `BaseAIClient` in `core/ai_client.py`
2. Implement `rewrite_product()`, `rewrite_field()`, `translate_description_to_en()`, and `rewrite_product_for_geo()`
3. Register it in the `create_ai_client()` factory function
4. Add the provider name to the enum in `core/models.py` (`AppConfig.ai_provider`)
5. Add provider metadata in `core/provider_service.py`
6. Document it in `README.md` and `.env.example`

### Add a new SEO scoring rule
1. Edit `core/seo_analyzer.py` — add your rule to the relevant field scorer
2. Update the max points constant if the rule changes the total weight
3. Add a test case to `tests/test_seo_analyzer.py`

### Add a new GEO audit analysis dimension
1. Add an `async _analyze_<dimension>()` method to `GeoAuditor` in `core/geo_audit.py`
2. Add it to the `asyncio.gather()` call in `run_full_audit()`
3. Add a weight entry to `WEIGHTS` (ensure all weights still sum to 1.0)
4. Update `_synthesize()` and `_build_report()` to include the new dimension
5. Add a test case to `tests/test_geo_audit.py`

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

### Add a new agent tool
1. Create a builder function `build_<tool_name>_tool()` in `core/agent_tools.py` that returns an `AgentTool`
2. Define the tool's JSON Schema parameters and async handler
3. Add the tool to the appropriate toolkit factory (`create_seo_rewrite_toolkit`, `create_chat_toolkit`, etc.)
4. Add test cases in `tests/test_agent_tools.py`

### Add a new chat agent persona
1. Add a new prompt constant (e.g., `AGENT_MYAGENT_PROMPT_TR`) in `core/prompt_store.py`
2. Register it in `AGENT_SYSTEM_PROMPTS_TR` under a new key
3. Update `ChatService` routing logic to select the new key when appropriate

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
- `GeoAuditor` makes real outbound HTTP requests to the target website — tests must mock `httpx.AsyncClient` or the `_fetch()` method
- GEO audit `geo_rewrite.system.txt` / `geo_rewrite.user.txt` prompt files are auto-created on first use; they will not appear in `prompts/` until the app runs at least once or `ensure_prompt_files()` is called
- `AGENT_SYSTEM_PROMPTS_TR` agent prompts in `prompt_store.py` are not user-editable via the Settings UI (only the product rewrite and translation prompts are exposed for editing)
