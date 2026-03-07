# CLAUDE.md — ikas AI SEO Agent

This file provides AI assistants with everything needed to understand, navigate, and contribute to this codebase effectively.

---

## Project Overview

**ikas AI SEO Agent** is a Python tool that connects to ikas e-commerce stores via their GraphQL API, analyzes product listings for SEO quality, and uses AI to rewrite titles, descriptions, and meta fields. It ships as both a desktop GUI (CustomTkinter) and a CLI (Typer + Rich).

**Key capabilities:**
- Fetches products from ikas via OAuth2 + GraphQL
- Scores each product's SEO on a 100-point rule-based rubric
- Sends content to an AI provider (Claude, GPT, Gemini, Ollama, etc.) for rewrite suggestions
- Shows before/after diffs, allows approval, and applies changes back to ikas
- Supports Turkish and English product content
- Dry-run mode by default (no writes to ikas unless explicitly enabled)

---

## Repository Structure

```
ikas-ai-seo-agent/
├── main.py                     # Entry point — routes to CLI or desktop UI
├── requirements.txt            # Python dependencies
├── .env.example                # All configurable env vars with descriptions
│
├── config/
│   └── settings.py             # .env loader, validation, interactive prompts, AppConfig
│
├── core/                       # Business logic (no UI dependencies)
│   ├── models.py               # Pydantic models: Product, SeoScore, SeoSuggestion, AppConfig
│   ├── ikas_client.py          # Async GraphQL client for ikas API (httpx)
│   ├── ai_client.py            # Multi-provider AI abstraction (factory + adapters)
│   ├── claude_client.py        # Legacy Anthropic-only client (backward compat)
│   ├── product_manager.py      # Orchestrator — coordinates all core operations
│   ├── seo_analyzer.py         # Rule-based SEO scoring engine (100-point scale)
│   ├── csv_handler.py          # CSV import/export for products and suggestions
│   └── prompt_store.py         # Loads and renders prompt templates from prompts/
│
├── cli/
│   └── main.py                 # Typer CLI: analyze, rewrite, apply, history, export, test-connection
│
├── ui/
│   ├── app.py                  # Main CustomTkinter window (product table, toolbar, filters)
│   ├── image_service.py        # Async image loading + TTL cache
│   └── components/
│       ├── settings_panel.py   # AI provider config, prompt template editing
│       ├── ai_chat_panel.py    # Real-time interactive AI chat
│       ├── diff_viewer.py      # Side-by-side before/after content comparison
│       ├── product_table.py    # Paginated product list with image thumbnails
│       ├── score_card.py       # SEO score visualization
│       └── dockable_panel.py   # Dockable panel container widget
│   └── themes/
│       └── dark.py             # Dark theme color palette constants
│
├── data/
│   ├── db.py                   # SQLite schema + helpers (products, scores, suggestions, log)
│   └── cache.py                # File-based TTL cache keyed by MD5 hash
│
├── prompts/                    # Editable AI prompt templates ({{variable}} substitution)
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
    └── test_settings.py
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

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your ikas credentials and AI provider key

# 5. Run tests to verify setup
python -m pytest tests/ -v

# 6. Launch desktop UI
python main.py

# 7. Or use CLI
python main.py --cli analyze
```

---

## Running the Application

### Desktop UI (default)
```bash
python main.py
```

### CLI mode
```bash
python main.py --cli <command> [options]

# Available commands:
python main.py --cli analyze          # Fetch products + compute SEO scores
python main.py --cli rewrite          # Generate AI rewrite suggestions
python main.py --cli apply            # Apply approved suggestions to ikas
python main.py --cli history          # View operation history
python main.py --cli export           # Export products/suggestions to CSV
python main.py --cli test-connection  # Verify ikas API connectivity
```

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
| `STORE_LANGUAGES` | `tr` | Comma-separated language codes |
| `SEO_TARGET_KEYWORDS` | — | Comma-separated keywords for scoring |
| `DRY_RUN` | `true` | Set to `false` to write changes to ikas |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### Config loading behavior
- `get_config()` in `config/settings.py` returns a cached singleton `AppConfig`
- Missing required vars trigger an interactive prompt when running in a TTY
- Legacy `ANTHROPIC_API_KEY` is auto-mapped to `AI_API_KEY` for backward compatibility
- `save_config_to_env()` persists any runtime changes back to `.env`

---

## Architecture & Key Patterns

### Layered architecture

```
[ UI: CustomTkinter ]   [ CLI: Typer + Rich ]
            ↓                    ↓
        ProductManager (core/product_manager.py)
            ├── IkasClient      → ikas GraphQL API
            ├── AIClient        → AI provider (pluggable)
            ├── SEOAnalyzer     → rule-based scoring
            ├── CSVHandler      → import/export
            └── Database        → SQLite persistence + file cache
```

### Data flow for a typical "analyze + rewrite" operation
1. `ProductManager.fetch_products()` → `IkasClient` fetches products via async GraphQL
2. `SEOAnalyzer.analyze_product()` → scores each product, returns `SeoScore`
3. `AIClient.generate_suggestion()` → sends product content + prompt to AI, returns `SeoSuggestion`
4. Results are stored in SQLite (`data/db.py`)
5. UI/CLI displays scores and diffs for user approval
6. On approval: `ProductManager.apply_suggestion()` → `IkasClient` writes back to ikas (if `DRY_RUN=false`)

### Design patterns used
- **Factory** — `create_ai_client(config)` in `core/ai_client.py` instantiates the correct provider adapter
- **Adapter** — All AI providers implement `BaseAIClient` with a uniform `generate()` interface
- **Orchestrator** — `ProductManager` coordinates all core modules; UI/CLI only call it
- **Singleton** — `get_config()` caches a single `AppConfig` instance per process
- **Template** — Prompts use `{{variable}}` placeholders, rendered by `PromptStore`
- **Repository** — `data/db.py` abstracts all SQLite reads/writes behind plain functions

### Async usage
`IkasClient` uses `httpx.AsyncClient` with `asyncio`. When calling from synchronous contexts (CLI, UI), wrap with `asyncio.run()`. The UI uses threading to avoid blocking the main thread.

---

## Core Modules Reference

### `core/models.py`
Key Pydantic models:
- `Product` — id, name, description (TR/EN), meta title/description, images, variants
- `SeoScore` — total_score (0–100), per-field breakdown, issues list, suggestions list
- `SeoSuggestion` — field, original_value, suggested_value, ai_provider, status (pending/approved/rejected)
- `AppConfig` — mirrors all `.env` variables

### `core/seo_analyzer.py` — SEO scoring rubric
| Field | Max Points | Key checks |
|---|---|---|
| Title (TR) | 25 | Length 30–60 chars, keyword presence, no excessive caps |
| Description (TR) | 30 | Min 150 chars, structured content, keyword density |
| Description (EN) | 10 | Min 100 chars |
| Meta Title | 20 | Length 50–60 chars, keyword presence |
| Meta Description | 15 | Length 120–160 chars |
| Keyword coverage | — | Bonus/penalty based on `SEO_TARGET_KEYWORDS` |

### `core/ai_client.py` — supported providers
| `AI_PROVIDER` value | SDK / Endpoint | Default model |
|---|---|---|
| `anthropic` | Anthropic Python SDK | `claude-opus-4-6` |
| `openai` | OpenAI Python SDK | `gpt-4o` |
| `gemini` | OpenAI-compat endpoint | `gemini-1.5-pro` |
| `openrouter` | OpenAI-compat endpoint | `openai/gpt-4o` |
| `ollama` | Local OpenAI-compat | `llama3` |
| `lm-studio` | Local OpenAI-compat | first available |
| `custom` | Custom `AI_BASE_URL` | set `AI_MODEL_NAME` |
| `none` | No AI — scoring only | — |

### `core/ikas_client.py`
- OAuth2 token fetch via form-encoded POST to ikas auth endpoint
- All product reads/writes use GraphQL queries/mutations
- Async methods: `fetch_products()`, `update_product()`, `test_connection()`
- Token is cached in-memory and refreshed on expiry

### `data/db.py` — SQLite tables
| Table | Purpose |
|---|---|
| `products` | Cached product snapshots |
| `seo_scores` | Computed scores per product per run |
| `suggestions` | AI-generated rewrites with status |
| `operation_log` | Audit log of all apply operations |

---

## UI Components

The desktop UI (`ui/app.py`) is a 3-column CustomTkinter layout:
1. **Left panel** — Product table with pagination, image thumbnails, SEO score badges, filter tabs (All / Low Score / Pending / Approved)
2. **Center panel** — Diff viewer showing original vs. suggested content, field-level rewrite buttons
3. **Right panel** — Settings (provider, API keys, model, prompt editor) or AI chat (real-time conversation)

Panel visibility and layout can be toggled. All UI operations that call the core are run in background threads to keep the GUI responsive.

---

## Prompt Templates

Prompt files live in `prompts/` and are loaded by `core/prompt_store.py`. They use `{{variable}}` syntax. Users can edit them at runtime via the Settings panel in the UI, and changes are saved to disk.

Available templates:
- `description_rewrite.system.txt` / `.user.txt` — rewrites product descriptions
- `translation_en.system.txt` / `.user.txt` — translates Turkish content to English

To add a new prompt type, add `.system.txt` + `.user.txt` files and reference them in `PromptStore`.

---

## Coding Conventions

- **Python 3.10+** required (uses `match`/`case`, `|` union types)
- **Pydantic v2** for all data models — use `model_validate()`, not `parse_obj()`
- **Type hints** on all public function signatures
- **Async** for all ikas API calls; sync wrappers at the UI/CLI boundary
- **No wildcard imports** — always import explicitly
- **`DRY_RUN=true` is the safe default** — never change this without explicit user intent
- All user-visible strings use Rich markup (`[bold]`, `[green]`, etc.) in CLI; plain strings in core
- Prompts are never hardcoded in Python — always loaded from `prompts/`
- New AI providers must subclass `BaseAIClient` and be registered in `create_ai_client()`

---

## Common Tasks

### Add a new AI provider
1. Create a subclass of `BaseAIClient` in `core/ai_client.py`
2. Implement `generate(system_prompt, user_prompt) -> str`
3. Register it in the `create_ai_client()` factory function
4. Add the provider name to the enum in `core/models.py` (`AppConfig.ai_provider`)
5. Add it to the provider dropdown in `ui/components/settings_panel.py`
6. Document it in `README.md` and `.env.example`

### Add a new CLI command
1. Add a new `@app.command()` function in `cli/main.py`
2. Call `ProductManager` methods — do not add business logic to the CLI layer
3. Use `rich.console.Console` for output formatting

### Add a new SEO scoring rule
1. Edit `core/seo_analyzer.py` — add your rule to the relevant field scorer
2. Update the max points constant if the rule changes the total weight
3. Add a test case to `tests/test_seo_analyzer.py`

### Add a new database table
1. Add `CREATE TABLE IF NOT EXISTS` to the schema in `data/db.py`
2. Add helper functions (insert, fetch, update) in the same file
3. Call the schema init from the existing `init_db()` function

---

## Gotchas & Known Issues

- **ikas GraphQL field names** differ from REST conventions — verify against the ikas API docs; several fixes have been made for this (see git log)
- **OAuth token** is not persisted across restarts — re-fetched automatically on each run
- **Image loading** in the UI is async and may show placeholders briefly on first load
- **`DRY_RUN=true`** is the default — changes will NOT be written to ikas unless explicitly set to `false`
- The `claude_client.py` legacy module is kept for backward compatibility but new code should use `ai_client.py`
- When running in a non-TTY environment (e.g., CI), missing env vars will raise an error instead of prompting
- SQLite database file is created at `./seo_agent.db` in the working directory (not configurable via env yet)
