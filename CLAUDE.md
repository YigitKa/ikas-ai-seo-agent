# CLAUDE.md â€” ikas AI SEO Agent

This file provides AI assistants with everything needed to understand, navigate, and contribute to this codebase effectively.

---

## Project Overview

**ikas AI SEO Agent** is a Python tool that connects to ikas e-commerce stores via their GraphQL API, analyzes product listings for SEO quality, and uses AI to rewrite titles, descriptions, and meta fields. It ships as a desktop GUI built with CustomTkinter.

**Key capabilities:**
- Fetches products from ikas via OAuth2 + GraphQL
- Scores each product's SEO on a 100-point rule-based rubric
- Sends content to an AI provider (Claude, GPT, Gemini, Ollama, etc.) for rewrite suggestions
- Shows before/after diffs, allows approval, and applies changes back to ikas
- Supports Turkish and English product content
- Dry-run mode by default (no writes to ikas unless explicitly enabled)

---

## Repository Structure

```text
ikas-ai-seo-agent/
|-- main.py                  # Entry point - launches the desktop UI
|-- requirements.txt         # Python dependencies
|-- .env.example             # All configurable env vars with descriptions
|
|-- config/
|   `-- settings.py          # .env loader, validation, interactive prompts, AppConfig
|
|-- core/                    # Business logic (no UI dependencies)
|   |-- models.py            # Pydantic models: Product, SeoScore, SeoSuggestion, AppConfig
|   |-- ikas_client.py       # Async GraphQL client for ikas API (httpx)
|   |-- ai_client.py         # Multi-provider AI abstraction (factory + adapters)
|   |-- claude_client.py     # Legacy Anthropic-only client (backward compat)
|   |-- product_manager.py   # Orchestrator - coordinates all core operations
|   |-- seo_analyzer.py      # Rule-based SEO scoring engine (100-point scale)
|   |-- csv_handler.py       # CSV import/export for products and suggestions
|   `-- prompt_store.py      # Loads and renders prompt templates from prompts/
|
|-- ui/
|   |-- app.py               # Main CustomTkinter window (product table, toolbar, filters)
|   |-- image_service.py     # Async image loading + TTL cache
|   |-- themes/
|   |   `-- dark.py          # Dark theme color palette constants
|   `-- components/
|       |-- settings_panel.py  # AI provider config, prompt template editing
|       |-- ai_chat_panel.py   # Real-time interactive AI chat
|       |-- diff_viewer.py     # Side-by-side before/after content comparison
|       |-- product_table.py   # Paginated product list with image thumbnails
|       |-- score_card.py      # SEO score visualization
|       `-- dockable_panel.py  # Dockable panel container widget
|
|-- data/
|   |-- db.py                # SQLite schema + helpers (products, scores, suggestions, log)
|   `-- cache.py             # File-based TTL cache keyed by MD5 hash
|
|-- prompts/                 # Editable AI prompt templates ({{variable}} substitution)
|   |-- description_rewrite.system.txt
|   |-- description_rewrite.user.txt
|   |-- translation_en.system.txt
|   |-- translation_en.user.txt
|   `-- README.txt
|
`-- tests/
    |-- fixtures/
    |   `-- sample_products.json    # 4 sample products for unit tests
    |-- test_seo_analyzer.py
    |-- test_ai_client.py
    |-- test_claude_client.py
    |-- test_ikas_client.py
    |-- test_db.py
    `-- test_settings.py
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

# 7. Launch desktop UI
python main.py
```

---

## Running the Application

### Desktop UI (default)
```bash
python main.py
```

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Single test file
python -m pytest tests/test_seo_analyzer.py -v

# Single test function
python -m pytest tests/test_seo_analyzer.py::test_analyze_product_low_score -v
```

No CI/CD pipeline is currently configured. Tests use `pytest` and mock objects â€” no live API calls are made.

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
| `SEO_TARGET_KEYWORDS` | â€” | Comma-separated keywords for scoring |
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

```text
[ UI: CustomTkinter ]
          |
          v
ProductManager (core/product_manager.py)
    |-- IkasClient   -> ikas GraphQL API
    |-- AIClient     -> AI provider (pluggable)
    |-- SEOAnalyzer  -> rule-based scoring
    |-- CSVHandler   -> import/export
    `-- Database     -> SQLite persistence + file cache
```

### Data flow for a typical "analyze + rewrite" operation
1. `ProductManager.fetch_products()` â†’ `IkasClient` fetches products via async GraphQL
2. `SEOAnalyzer.analyze_product()` â†’ scores each product, returns `SeoScore`
3. `AIClient.generate_suggestion()` â†’ sends product content + prompt to AI, returns `SeoSuggestion`
4. Results are stored in SQLite (`data/db.py`)
5. UI displays scores and diffs for user approval
6. On approval: `ProductManager.apply_suggestion()` â†’ `IkasClient` writes back to ikas (if `DRY_RUN=false`)

### Design patterns used
- **Factory** â€” `create_ai_client(config)` in `core/ai_client.py` instantiates the correct provider adapter
- **Adapter** â€” All AI providers implement `BaseAIClient` with a uniform `generate()` interface
- **Orchestrator** â€” `ProductManager` coordinates all core modules; the UI only calls it
- **Singleton** â€” `get_config()` caches a single `AppConfig` instance per process
- **Template** â€” Prompts use `{{variable}}` placeholders, rendered by `PromptStore`
- **Repository** â€” `data/db.py` abstracts all SQLite reads/writes behind plain functions

### Async usage
`IkasClient` uses `httpx.AsyncClient` with `asyncio`. The desktop UI wraps async work in background threads so the main window stays responsive.

---

## Core Modules Reference

### `core/models.py`
Key Pydantic models:
- `Product` â€” id, name, description (TR/EN), meta title/description, images, variants
- `SeoScore` â€” total_score (0â€“100), per-field breakdown, issues list, suggestions list
- `SeoSuggestion` â€” field, original_value, suggested_value, ai_provider, status (pending/approved/rejected)
- `AppConfig` â€” mirrors all `.env` variables

### `core/seo_analyzer.py` â€” SEO scoring rubric (modern algorithm)

Scoring inspired by Ahrefs, Semrush, Yoast, Moz, and Screaming Frog.

| Field | Max Points | Key checks |
|---|---|---|
| Title | 15 | Length 30â€“60 chars, no excessive caps, no special chars, power words |
| Description (TR) | 20 | Min 150 words, paragraph structure, HTML elements (headings, lists, bold) |
| Description (EN) | 5 | Min 100 words, no Turkish chars |
| Meta Title | 15 | Length 50â€“60 chars, brand separator, differs from product title |
| Meta Description | 10 | Length 120â€“160 chars, CTA presence |
| Keyword Optimization | 10 | Target keywords in description/meta, category alignment, title-desc consistency |
| Content Quality | 10 | Keyword stuffing detection (>5%), TTR vocabulary diversity, repeated n-grams, title-content coherence |
| Technical SEO | 10 | Image count (ideal 3-5), tags (3-5), category, URL-friendly name, price |
| Readability | 5 | Avg sentence length (15-25 words), sentence length variation, transition words |

### `core/ai_client.py` â€” supported providers
| `AI_PROVIDER` value | SDK / Endpoint | Default model |
|---|---|---|
| `anthropic` | Anthropic Python SDK | `claude-opus-4-6` |
| `openai` | OpenAI Python SDK | `gpt-4o` |
| `gemini` | OpenAI-compat endpoint | `gemini-1.5-pro` |
| `openrouter` | OpenAI-compat endpoint | `openai/gpt-4o` |
| `ollama` | Local OpenAI-compat | `llama3` |
| `lm-studio` | Local OpenAI-compat | first available |
| `custom` | Custom `AI_BASE_URL` | set `AI_MODEL_NAME` |
| `none` | No AI â€” scoring only | â€” |

### `core/ikas_client.py`
- OAuth2 token fetch via form-encoded POST to ikas auth endpoint
- All product reads/writes use GraphQL queries/mutations
- Async methods: `fetch_products()`, `update_product()`, `test_connection()`
- Token is cached in-memory and refreshed on expiry

### `data/db.py` â€” SQLite tables
| Table | Purpose |
|---|---|
| `products` | Cached product snapshots |
| `seo_scores` | Computed scores per product per run |
| `suggestions` | AI-generated rewrites with status |
| `operation_log` | Audit log of all apply operations |

---

## UI Components

The desktop UI (`ui/app.py`) is a 3-column CustomTkinter layout:
1. **Left panel** â€” Product table with pagination, image thumbnails, SEO score badges, filter tabs (All / Low Score / Pending / Approved)
2. **Center panel** â€” Diff viewer showing original vs. suggested content, field-level rewrite buttons
3. **Right panel** â€” Settings (provider, API keys, model, prompt editor) or AI chat (real-time conversation)

Panel visibility and layout can be toggled. All UI operations that call the core are run in background threads to keep the GUI responsive.

---

## Prompt Templates

Prompt files live in `prompts/` and are loaded by `core/prompt_store.py`. They use `{{variable}}` syntax. Users can edit them at runtime via the Settings panel in the UI, and changes are saved to disk.

Available templates:
- `description_rewrite.system.txt` / `.user.txt` â€” rewrites product descriptions
- `translation_en.system.txt` / `.user.txt` â€” translates Turkish content to English

To add a new prompt type, add `.system.txt` + `.user.txt` files and reference them in `PromptStore`.

---

## Coding Conventions

- **Python 3.10+** required (uses `match`/`case`, `|` union types)
- **Pydantic v2** for all data models â€” use `model_validate()`, not `parse_obj()`
- **Type hints** on all public function signatures
- **Async** for all ikas API calls; keep sync wrappers at the desktop UI boundary
- **No wildcard imports** â€” always import explicitly
- **`DRY_RUN=true` is the safe default** â€” never change this without explicit user intent
- All user-visible strings are plain strings; formatting belongs in the UI layer
- Prompts are never hardcoded in Python â€” always loaded from `prompts/`
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

### Add a new SEO scoring rule
1. Edit `core/seo_analyzer.py` â€” add your rule to the relevant field scorer
2. Update the max points constant if the rule changes the total weight
3. Add a test case to `tests/test_seo_analyzer.py`

### Add a new database table
1. Add `CREATE TABLE IF NOT EXISTS` to the schema in `data/db.py`
2. Add helper functions (insert, fetch, update) in the same file
3. Call the schema init from the existing `init_db()` function

---

## Gotchas & Known Issues

- **ikas GraphQL field names** differ from REST conventions â€” verify against the ikas API docs; several fixes have been made for this (see git log)
- **OAuth token** is not persisted across restarts â€” re-fetched automatically on each run
- **Image loading** in the UI is async and may show placeholders briefly on first load
- **`DRY_RUN=true`** is the default â€” changes will NOT be written to ikas unless explicitly set to `false`
- The `claude_client.py` legacy module is kept for backward compatibility but new code should use `ai_client.py`
- When running in a non-TTY environment (e.g., CI), missing env vars will raise an error instead of prompting
- SQLite database file is created at `./seo_agent.db` in the working directory (not configurable via env yet)

