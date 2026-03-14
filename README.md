# ikas AI SEO Agent

**An autonomous AI agent that analyzes, scores, and rewrites e-commerce product content for maximum SEO and AI discoverability.**

Built for [ikas](https://ikas.com) stores. Connects via GraphQL API, scores every product on a 100-point rubric, then deploys an agentic AI pipeline that autonomously identifies weak fields, iteratively rewrites them, validates improvements, and saves suggestions — all without human intervention per product.

Ships as a full-stack web application: **React/TypeScript** frontend, **FastAPI** backend, **async SQLite** storage.

---

## The Problem

E-commerce SEO optimization is repetitive, expensive, and increasingly insufficient. Every product needs a well-crafted title, rich description, proper meta tags, multilingual content, and — in the age of AI search — structured facts that ChatGPT, Perplexity, and Google AI Overviews can cite.

Doing this manually for hundreds of products is impractical. Doing it with a single AI prompt produces mediocre, one-shot results with no quality feedback loop.

## The Solution

This agent doesn't just generate content — it **thinks, scores, rewrites, validates, and iterates**. Like a human SEO specialist would, but across your entire catalog.

```
┌─────────────────────────────────────────────────────┐
│                    Agent Loop                        │
│                                                      │
│   Score product (100-point rubric)                   │
│       ↓                                              │
│   Identify weakest fields                            │
│       ↓                                              │
│   Rewrite field with SEO best practices              │
│       ↓                                              │
│   Validate: did the score actually improve?           │
│       ↓                                              │
│   No improvement → try different strategy             │
│   Improved → move to next weak field                  │
│       ↓                                              │
│   Save suggestion when all fields optimized           │
└─────────────────────────────────────────────────────┘
         (up to 8 autonomous iterations)
```

The result: measurable, validated SEO improvements — not just "AI-generated text."

---

## Key Capabilities

### Agentic SEO Optimization
The AI doesn't fire-and-forget. It uses **tool calling** to autonomously score → rewrite → validate → iterate. Each rewrite is checked against the scoring rubric before being accepted. If a rewrite doesn't improve the score, the agent tries a different approach — up to 2 strategies per field, up to 8 total iterations.

### 100-Point SEO Scoring Engine
Rule-based rubric inspired by Ahrefs, Semrush, Yoast, Moz, and Screaming Frog:

| Category | Points | What it checks |
|---|---|---|
| Title | 15 | Length, capitalization, power words, special chars |
| Description (TR) | 20 | Word count, paragraph structure, HTML elements |
| Description (EN) | 5 | Translation quality, min word count |
| Meta Title | 15 | Length 50-60 chars, brand separator, uniqueness |
| Meta Description | 10 | Length 120-160 chars, CTA presence |
| Keyword Optimization | 10 | Keyword placement, category alignment, consistency |
| Content Quality | 10 | Stuffing detection, vocabulary diversity, coherence |
| Technical SEO | 10 | Images, tags, categories, slug, pricing |
| Readability | 5 | Sentence length, variation, transitions |
| **AI Citability (GEO)** | **10** | Structured facts, clear attributes, AI-readable format |

The last category — **AI Citability** — is what makes this forward-looking. It scores how well your content can be cited by AI search engines.

### GEO Site Audit
A standalone crawler that audits **any website** for Generative Engine Optimization readiness:

- Crawls homepage + sitemap (configurable page limit)
- Runs **5 parallel analysis agents** via `asyncio.gather`:
  - AI Visibility — citability scoring, `robots.txt` crawler policy analysis (tracks 14+ AI bots: GPTBot, ClaudeBot, PerplexityBot...), `llms.txt` detection
  - Platform Readiness — ChatGPT / Perplexity / Google AIO signal scores
  - Technical SEO — HTTPS, mobile viewport, CSP, SSR detection
  - Content Quality — readability, E-E-A-T signals, freshness
  - Schema Markup — JSON-LD detection and type variety
- Synthesizes into a weighted composite **GEO Score (0-100)**
- Generates a prioritized Markdown action plan

### Multi-Agent Chat with Semantic Routing
The chat panel isn't a single chatbot — it's **three specialized agents** with automatic routing:

| Agent | Role | Tools |
|---|---|---|
| **SEO Expert** | Rewrites titles, descriptions, meta tags | SEO scoring, validation, save/apply |
| **Store Operator** | Queries live store data (stock, orders, prices) | 50+ ikas MCP operations |
| **General** | Answers product, SEO, and store management questions | SEO toolkit |

Every user message is semantically classified by the LLM (temp=0.0, max 20 tokens) — no tags or commands needed. Ask about stock levels and you're routed to the Operator. Ask to optimize a title and you're routed to the SEO Expert.

### Structured Option Buttons
AI proposals render as **clickable buttons** in the chat — not free text that users need to type responses to. This eliminates typos, ambiguity, and the need for intent parsing on follow-up messages.

The AI appends a JSON option block to its response:
```json
[{"tone": "Professional", "value": "Apply all changes"}, {"tone": "Cautious", "value": "Let me review first"}]
```
The frontend parses this into styled, clickable cards. When a button has an `action` key, it sends a hidden `[[CHAT_ACTION:action_name]]` message — enabling deterministic multi-step workflows (save → review → apply) without free-text ambiguity.

### Provider Agnostic
One codebase, **8 AI providers**:

| Provider | Type | Default Model |
|---|---|---|
| Anthropic | Cloud API | `claude-haiku-4-5-20251001` |
| OpenAI | Cloud API | `gpt-4o-mini` |
| Gemini | Cloud API | `gemini-1.5-flash` |
| OpenRouter | Cloud API | `openai/gpt-4o-mini` |
| Ollama | Local | `llama3.2` |
| LM Studio | Local | First available |
| Custom | Any OpenAI-compatible | Configurable |
| None | No AI | Scoring only |

All providers (except `none`) support tool calling through a unified OpenAI-compatible interface. Switch providers by changing one environment variable — the entire agentic pipeline, chat system, and streaming work identically.

### Safe by Default
`DRY_RUN=true` is the default. Nothing is written to your ikas store unless you explicitly opt in. Every suggestion goes through a human approval step before it can be applied.

---

## Architecture

```
┌──────────────────────────────────┐
│     React 19 + TypeScript SPA    │
│     TailwindCSS 4 · Vite 7       │
│     TanStack Query · WebSocket    │
└───────────────┬──────────────────┘
                │
                ▼
┌──────────────────────────────────┐
│     FastAPI · REST + WebSocket    │
│     Request-scoped DI · SSE       │
└───────────────┬──────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────┐
│                    ProductManager                         │
│              (fresh instance per request)                  │
│                                                           │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ IkasClient   │  │ SEO Analyzer │  │ AI Client       │  │
│  │ OAuth+GraphQL│  │ 100-pt rubric│  │ 8 providers     │  │
│  └─────────────┘  └──────────────┘  └─────────────────┘  │
│                                                           │
│  ┌──────────────────────┐  ┌───────────────────────────┐  │
│  │ AgentOrchestrator     │  │ ChatService               │  │
│  │ Tool-calling loop     │  │ Multi-agent + MCP + Tools  │  │
│  │ run() / stream()      │  │ Semantic routing           │  │
│  │ AgentToolkit registry │  │ Structured option buttons  │  │
│  └──────────────────────┘  └───────────────────────────┘  │
│                                                           │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │ GeoAuditor   │  │ IkasMCPClient│  │ ProviderService │  │
│  │ Site crawler  │  │ JSON-RPC 2.0 │  │ Health + models │  │
│  └─────────────┘  └──────────────┘  └─────────────────┘  │
└───────────────────────────┬──────────────────────────────┘
                            │
                            ▼
                ┌──────────────────────┐
                │  Async SQLite        │
                │  aiosqlite           │
                │  products · scores   │
                │  suggestions · logs  │
                └──────────────────────┘
```

### Design Decisions Worth Noting

**Request-scoped orchestration.** `ProductManager` is instantiated fresh per HTTP request via FastAPI dependency injection — no global state, no cross-request contamination. Chat state is isolated per WebSocket connection.

**Three-layer tool resolution.** When the chat agent calls a tool, it's resolved through three layers in priority order: (1) Local registry tools (save/apply), (2) AgentToolkit tools (SEO scoring/validation), (3) MCP tools (50+ live ikas operations). This keeps tool dispatch decoupled from implementation.

**Dual-route apply strategy.** When applying suggestions to ikas, the system tries IkasClient (OAuth + GraphQL) first, then falls back to MCP mutation. Two paths to the same destination — resilient by design.

**Layered prompt architecture.** Chat prompts aren't monolithic. They're assembled from 5 layers: base flow prompt → agent-specific persona → operation guide → product context → routing instructions. Each layer is independently maintainable.

**Thinking extraction.** `<think>...</think>` blocks are automatically extracted from model responses and surfaced separately in the UI — users can see the AI's reasoning process without it cluttering the response.

**False-action safety.** If the AI claims it applied changes without actually calling the `apply_seo_to_ikas` tool, the system detects this and appends a warning disclaimer. Trust the tool calls, not the text.

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+

### Setup

```bash
git clone https://github.com/YigitKa/ikas-ai-seo-agent.git
cd ikas-ai-seo-agent

# Python
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd web && npm install && cd ..

# Configuration
cp .env.example .env
# Edit .env with your ikas credentials and AI provider key
```

### Run

```bash
# Development (recommended) — backend :8000 + Vite :5173
python main.py dev

# Production — builds frontend, serves everything from :8000
python main.py
```

### Verify

```bash
python -m pytest tests/ -v
```

---

## Configuration

All configuration lives in `.env`. Three-layer resolution (highest priority first):
1. `.cache/user_settings.json` — runtime overrides from the Settings UI
2. `.env` — initial defaults (read-only at runtime)
3. Hardcoded defaults in `AppConfig`

### Required

| Variable | Description |
|---|---|
| `IKAS_STORE_NAME` | Your ikas store subdomain |
| `IKAS_CLIENT_ID` | OAuth2 client ID from ikas admin |
| `IKAS_CLIENT_SECRET` | OAuth2 client secret |
| `AI_PROVIDER` | `anthropic`, `openai`, `gemini`, `openrouter`, `ollama`, `lm-studio`, `custom`, or `none` |
| `AI_API_KEY` | API key for cloud providers |

### Optional

| Variable | Default | Description |
|---|---|---|
| `AI_MODEL_NAME` | Provider default | Override model selection |
| `AI_TEMPERATURE` | `0.7` | Generation creativity |
| `AI_MAX_TOKENS` | `2000` | Max output tokens |
| `AI_THINKING_MODE` | `false` | Extended thinking (Anthropic) |
| `IKAS_MCP_TOKEN` | — | Enables live store queries in chat |
| `STORE_LANGUAGES` | `tr,en` | Supported content languages |
| `SEO_TARGET_KEYWORDS` | — | Comma-separated target keywords |
| `SEO_LOW_SCORE_THRESHOLD` | `70` | Score below which products need attention |
| `DRY_RUN` | `true` | Set `false` to write changes to ikas |

---

## How It Works

### Dashboard Flow
1. **Sync** your product catalog from ikas
2. **Browse** products with SEO score badges in the sidebar
3. **Select** a product — see its score breakdown and chat panel
4. **Chat** with the AI about the product, or generate an autonomous rewrite
5. **Review** the AI's suggestions with before/after diffs
6. **Approve** and apply changes back to ikas

### Agentic Rewrite Flow
When you click "Generate AI Suggestion," the agent takes over:

1. Scores the product against all 10 rubric categories
2. Identifies the weakest scoring fields
3. Rewrites each field, starting with the lowest-scoring
4. Validates each rewrite against the rubric — **measurable improvement required**
5. If no improvement: tries alternative strategy (max 2 per field)
6. Saves the final suggestion only after validation passes
7. Streams every step in real-time via SSE

### Chat Flow
1. User message enters `ChatService`
2. Semantic routing classifies intent → selects agent persona
3. System prompt assembled from 5 layers + product context
4. Agent responds with tool calls as needed (up to 5 rounds)
5. Tools resolve through 3-layer hierarchy (Registry → Toolkit → MCP)
6. Response includes structured option buttons for next actions
7. User clicks button → deterministic workflow continues

---

## Tech Stack

### Backend
- **Python 3.11+** — async-first with `asyncio`
- **FastAPI** — REST API + WebSocket
- **aiosqlite** — async SQLite for products, scores, suggestions
- **httpx** — async HTTP for ikas GraphQL + MCP
- **Pydantic v2** — data validation and serialization

### Frontend
- **React 19** + **TypeScript 5.9**
- **Vite 7** — dev server + production builds
- **TailwindCSS 4** — utility-first styling
- **TanStack Query 5** — server state management
- **React Router 7** — client-side routing
- **react-markdown** — chat message rendering

### Protocols
- **OAuth2** — ikas API authentication
- **GraphQL** — ikas product CRUD
- **JSON-RPC 2.0** — ikas MCP (Model Context Protocol)
- **OpenAI-compatible** — unified AI provider interface
- **SSE** — real-time agent progress streaming
- **WebSocket** — bidirectional chat

---

## Project Structure

```
ikas-ai-seo-agent/
├── main.py                     # Entry point
├── start.py                    # Backend/frontend coordinator
│
├── config/settings.py          # Three-layer config resolution
│
├── core/                       # Business logic — no UI dependencies
│   ├── models.py               # Pydantic models (Product, SeoScore, AgentEvent, etc.)
│   ├── product_manager.py      # Central orchestrator
│   ├── prompt_store.py         # Template loading + multi-agent prompts
│   │
│   ├── ai/client.py            # Multi-provider AI abstraction (factory + adapters)
│   ├── agent/orchestrator.py   # Generic agent loop (run + stream)
│   ├── agent/tools.py          # Tool definitions + toolkit factories
│   │
│   ├── chat/                   # Multi-turn chat (mixin composition)
│   │   ├── state.py            # Conversation history + product context
│   │   ├── streaming.py        # SSE streaming + multi-agent routing
│   │   ├── suggestions.py      # Draft → review → apply flows
│   │   ├── support.py          # ToolRegistry + helpers
│   │   └── guidance.py         # Operation suggestions + false-action safety
│   │
│   ├── seo/analyzer.py         # 100-point scoring engine
│   ├── seo/geo_audit.py        # Full site GEO audit pipeline
│   │
│   ├── clients/ikas.py         # Async GraphQL client (OAuth2)
│   ├── clients/mcp.py          # ikas MCP JSON-RPC client
│   │
│   ├── services/provider.py    # Provider health + model discovery
│   ├── services/settings.py    # Settings management
│   └── services/suggestion.py  # Suggestion field operations
│
├── api/                        # FastAPI REST + WebSocket
│   ├── main.py                 # App setup, CORS, SPA serving
│   ├── dependencies.py         # Request-scoped DI
│   └── routers/                # products, seo, suggestions, settings, chat
│
├── web/src/                    # React/TypeScript SPA
│   ├── pages/                  # Dashboard, Settings
│   ├── components/             # ChatPanel, ProductTable, ScoreCard
│   ├── api/client.ts           # API client functions
│   └── hooks/useChat.ts        # Chat state management
│
├── data/
│   ├── db.py                   # Async SQLite schema + helpers
│   └── cache.py                # File-based TTL cache
│
├── prompts/                    # Editable AI prompt templates
└── tests/                      # 20+ test files, no live API calls
```

---

## API Surface

### Products
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/products` | List cached products (filterable) |
| `POST` | `/api/products/fetch` | Fetch from ikas |
| `POST` | `/api/products/sync` | Full catalog sync |
| `GET` | `/api/products/{id}` | Single product detail |

### SEO
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/seo/analyze` | Score all products |
| `POST` | `/api/seo/analyze/{id}` | Score single product |
| `GET` | `/api/seo/generate-llms-txt` | Generate `llms.txt` for AI crawlers |
| `POST` | `/api/seo/geo-audit` | Full GEO site audit |

### Suggestions
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/suggestions/generate/{id}` | Generate AI suggestion (agentic) |
| `POST` | `/api/suggestions/generate/{id}/stream` | Generate with SSE streaming |
| `PATCH` | `/api/suggestions/{id}/approve` | Approve suggestion |
| `POST` | `/api/suggestions/apply` | Apply all approved to ikas |

### Real-time
| Protocol | Endpoint | Description |
|---|---|---|
| WebSocket | `/ws/chat` | Multi-agent AI chat |
| WebSocket | `/ws/progress` | Operation progress |

---

## Contributing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_seo_analyzer.py -v
```

Tests use mocks and fixtures — no live API calls. Sample products in `tests/fixtures/sample_products.json`.

---

## License

MIT
