# ikas AI SEO Agent

`ikas AI SEO Agent`, ikas magazalari icin gelistirilmis web tabanli bir SEO analiz ve AI destekli icerik iyilestirme aracidir. Urunleri ikas API'sinden senkronize eder, yerel SQLite cache icinde saklar, 100 puanlik bir rubric ile skorlar ve secilen AI provider uzerinden rewrite veya TR -> EN ceviri onerileri uretir.

`2026-03-10` itibariyla proje yalnizca web uygulamasi olarak devam eder. Legacy masaustu UI repo'dan kaldirilmistir.

## Son Guncellemeler (2026-03-11)

- **Agentic tool mimarisi:** AI artik tek seferlik istek/cevap yerine iteratif tool-calling agent olarak calisir. Urun SEO'sunu otomatik skorlar, zayif alanlari tespit eder, tek tek yeniden yazar, dogrular ve kaydeder.
- Yeni modüller: `core/agent_tools.py` (AgentTool, AgentToolkit, built-in tool'lar), `core/agent_orchestrator.py` (generic agent loop)
- SSE streaming endpoint: `POST /api/suggestions/generate/{id}/stream` — agent adimlari gercek zamanli izlenebilir
- Tool-calling tum aktif provider'larda desteklenir (Ollama, LM Studio, OpenAI, Anthropic, Gemini, OpenRouter, custom). Yalnizca `none` provider tek-seferlik (fallback) modda kalir.
- Chat akisi `seo`, `operator` ve `general` ajanlari arasinda niyet tabanli yonlendirme ile calisir; operasyon rehberi ayri modulde (`core/chat_operation_guidance.py`) tutulur.
- Sohbet guvenilirligi guclendirildi: modelin gercekte yapilmayan degisiklikleri yapildi gibi raporlamasini engelleyen ek dogrulama kontrolleri bulunur.
- GEO denetimi icin tam website tarama endpoint'i eklendi: `POST /api/seo/geo-audit`.
- Dokumantasyon ve kod yapisi Claude/Codex agent akislariyla uyumlu hale getirildi.

## Guncel Durum

- React 19 + TypeScript frontend (`web/`)
- FastAPI backend + WebSocket chat (`api/`)
- SQLite tabanli yerel cache, skor ve suggestion kaydi (`data/`)
- ikas urun senkronizasyonu ve tekil urun fetch destegi
- **Agentic SEO optimizasyonu**: AI otonom olarak skorlar, zayif alanlari belirler, iteratif yeniden yazar, dogrular ve kaydeder (tool-calling ile)
- Urun filtreleri: `all`, `low_score`, `missing_english`, `pending`, `approved`
- SEO score breakdown: title, description, EN description, meta, keyword, content quality, technical SEO, readability, AI citability (GEO)
- GEO (Generative Engine Optimization): AI citability skorlama ve `llms.txt` uretimi
- Chat-first AI akisi: urun baglami, SEO metrikleri, prompt parametre ekleme, istek iptali, oturum token/context gostergeleri
- Otomatik urun giris mesaji: urun secildiginde chat paneli SEO analizi ile baslar
- Gecmis ozetleme: uzun sohbet gecmisi AI ile otomatik olarak ozetlenir
- Semantik yonlendirme: `@ikas` / `@local` etiketleri olmadan kullanici mesaji MCP mi yerel mi cozumlenir
- LM Studio native streaming: `/api/v1/chat` uzerinden gercek zamanli akis
- Ayar merkezi: provider secimi, model kesfi, prompt editoru, MCP durumu, LM Studio canli durum ekrani
- Suggestion durumlari: `pending`, `approved`, `rejected`, `applied`
- Guvenli varsayilan: `DRY_RUN=true`

## Mimari

```text
+------------------------------+
| React SPA (Vite)             |
| /            -> Dashboard    |
| /settings    -> Settings     |
+---------------+--------------+
                |
                v
+-----------------------------------+
| FastAPI                           |
| REST + WebSocket                  |
| api/main.py                       |
+---+---+---+-----------+-----------+
    |   |   |
    v   v   v
+---------------+--------------+
| ProductManager                 |
| core/product_manager.py        |
+---+-----------+-----------+---+
    |           |           |
    v           v           v
  ikas API    SEO        AI / Chat / Agent
  GraphQL     Rules      Providers + MCP
    |                      |
    v                      v
 SQLite cache          AgentOrchestrator
 scores, suggestions   + AgentToolkit
 logs                  (iteratif tool-calling)
```

Production modunda FastAPI, build edilmis SPA'yi `web/dist` altindan servis eder.

## Baslangic

### Gereksinimler

- Python 3.11+
- Node.js 20+
- npm

### Kurulum

```bash
git clone https://github.com/YigitKa/ikas-ai-seo-agent.git
cd ikas-ai-seo-agent

python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt

cd web
npm install
cd ..

copy .env.example .env   # Windows
# cp .env.example .env   # Linux / macOS
```

`.env` dosyasini doldurmadan ikas baglantili akislar calismaz.

## Calistirma

### Onerilen gelistirme modu

```bash
python start.py dev
```

Bu komut:

- FastAPI backend'i baslatir
- Vite dev server'i `:5173` uzerinden calistirir
- Backend portu mesgulse sonraki 20 portu dener

### Production benzeri calisma

```bash
python start.py
```

Varsayilan mod `prod`'dur. `web/dist` yoksa frontend build edilir, sonra FastAPI tek proses olarak kalkar.

### Diger launcher modlari

```bash
python start.py build
python start.py backend
python start.py prod
```

`main.py`, geriye donuk uyumluluk icin `start.py` alias'i olarak birakilmistir. Su komutlar da ayni sekilde calisir:

```bash
python main.py dev
python main.py
```

### Manuel calistirma

Frontend ve backend'i ayri proseslerde acmak isterseniz:

```bash
# terminal 1
python -m uvicorn api.main:app --reload

# terminal 2
cd web
npm run dev
```

## Uygulama Akisi

### Dashboard

Dashboard ekraninda:

- Tum katalog senkronize edilir
- Yerel veritabani sifirlanabilir
- Onayli suggestion'lar tek seferde uygulanabilir
- Sol panelde urun listesi ve skor rozetleri gorulur
- Secilen urun icin chat paneli ve SEO skor karti acilir

### Chat Panel

Chat paneli mevcut urun baglamini ve skor metriklerini modele verir. Urun secildiginde panel otomatik olarak bir SEO analizi intro mesaji gonderir. Arayuzde:

- Urun seciminde otomatik giris mesaji (auto intro)
- `@local` ile yalnizca mevcut baglam, `@ikas` ile canli magaza verisi uzerinden analiz isteme
- Etiket kullanilmadan da semantik yonlendirme ile dogru kaynak secilir
- `{productDescription}`, `{productMetaTitle}`, `{seoMetricsSummary}` gibi hazir alanlari mesaja ekleme
- Aktif istegi `Stop` ile iptal etme
- MCP arac cagri sonucunu mesaja gomulu gorme
- Uzun sohbet gecmisi otomatik olarak ozetlenir (gecmis sıkıştırma)
- LM Studio kullanirken context uzunlugu ve token kullanimini izleme

### Settings

Settings ekraninda:

- ikas kimlik bilgileri
- MCP token
- AI provider / model / base URL
- `AI_THINKING_MODE`
- Prompt editoru
- Provider health check
- Ollama ve LM Studio icin model discovery
- LM Studio secili model ve download job durumu

tek yerden yonetilir.

## Konfigurasyon

### Zorunlu `.env` alanlari

| Key | Aciklama |
| --- | --- |
| `IKAS_STORE_NAME` | Magaza alt alani veya host bilgisi |
| `IKAS_CLIENT_ID` | ikas OAuth client id |
| `IKAS_CLIENT_SECRET` | ikas OAuth client secret |

TTY ortaminda zorunlu alanlar eksikse uygulama bunlari terminalden isteyebilir. TTY yoksa hata verir.

### Opsiyonel `.env` alanlari

| Key | Varsayilan | Not |
| --- | --- | --- |
| `IKAS_MCP_TOKEN` | bos | AI sohbeti icin ikas MCP baglantisi |
| `AI_PROVIDER` | `none` | `none`, `anthropic`, `openai`, `gemini`, `openrouter`, `ollama`, `lm-studio`, `custom` |
| `AI_API_KEY` | bos | Secilen provider API key'i |
| `AI_BASE_URL` | provider default | OpenAI-compatible endpoint |
| `AI_MODEL_NAME` | provider default | Model adi |
| `AI_TEMPERATURE` | `0.7` | Rewrite yaraticiligi |
| `AI_MAX_TOKENS` | `2000` | Max output token |
| `AI_THINKING_MODE` | `false` | Destekleyen providerlarda reasoning isteyen mod |
| `STORE_LANGUAGES` | `tr,en` | Virgulle ayrilmis dil listesi |
| `STORE_LANGUAGE` | `tr` | Geriye donuk desteklenir |
| `SEO_TARGET_KEYWORDS` | bos | Virgulle ayrilmis keyword listesi |
| `SEO_LOW_SCORE_THRESHOLD` | `70` | `low_score` filtresi icin alt esik |
| `DRY_RUN` | `true` | Aciksa ikas'a yazma yapilmaz |
| `LOG_LEVEL` | `INFO` | Log seviyesi |
| `ANTHROPIC_API_KEY` | bos | Legacy geriye donuk uyumluluk |

### Provider varsayilanlari

| Provider | Varsayilan model | Varsayilan base URL |
| --- | --- | --- |
| `anthropic` | `claude-haiku-4-5-20251001` | SDK icinden |
| `openai` | `gpt-4o-mini` | `https://api.openai.com/v1` |
| `gemini` | `gemini-1.5-flash` | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| `openrouter` | `openai/gpt-4o-mini` | `https://openrouter.ai/api/v1` |
| `ollama` | `llama3.2` | `http://localhost:11434/v1` |
| `lm-studio` | `local-model` | `http://localhost:1234/v1` |
| `custom` | `gpt-3.5-turbo` | kullanici tanimlar |

## API Yuzeyi

### Genel

| Method | Path | Aciklama |
| --- | --- | --- |
| `GET` | `/api/health` | Saglik kontrolu |

### Products

| Method | Path | Aciklama |
| --- | --- | --- |
| `GET` | `/api/products?page=1&limit=50&filter=all` | Cache'deki urunleri listeler |
| `POST` | `/api/products/fetch` | ikas'tan sayfali urun ceker |
| `POST` | `/api/products/sync` | Tum katalogu ceker, cache ve skorlar guncellenir |
| `POST` | `/api/products/reset` | Urun, skor, suggestion ve log verisini temizler |
| `GET` | `/api/products/{product_id}` | Tekil urun ve son skoru |

`filter` parametresi su degerleri kabul eder: `all`, `low_score`, `missing_english`, `pending`, `approved`.

### SEO

| Method | Path | Aciklama |
| --- | --- | --- |
| `POST` | `/api/seo/analyze` | Cache'deki tum urunleri skorlar |
| `POST` | `/api/seo/analyze/{product_id}` | Tek urun skoru uretir |
| `GET` | `/api/seo/scores/{product_id}` | Son kaydedilen skoru doner |
| `GET` | `/api/seo/generate-llms-txt` | AI tarayicilari icin `llms.txt` uretir (GEO) |
| `POST` | `/api/seo/geo-audit` | Verilen URL icin tam GEO audit calistirir |

### Suggestions

| Method | Path | Aciklama |
| --- | --- | --- |
| `POST` | `/api/suggestions/generate/{product_id}` | Tam rewrite suggestion uretir (agentic mod) |
| `POST` | `/api/suggestions/generate/{product_id}/stream` | SSE streaming ile agent adimlarini gercek zamanli izler |
| `POST` | `/api/suggestions/generate-field/{product_id}` | Tek alan rewrite veya EN ceviri uretir |
| `GET` | `/api/suggestions/{product_id}` | Urunun suggestion gecmisi |
| `PATCH` | `/api/suggestions/{product_id}/approve` | Son pending suggestion'i onaylar |
| `PATCH` | `/api/suggestions/{product_id}/reject` | Son pending suggestion'i reddeder |
| `PATCH` | `/api/suggestions/{product_id}/update` | Son pending suggestion alanlarini gunceller |
| `POST` | `/api/suggestions/apply` | Tum approved suggestion'lari uygular |

### Settings ve MCP

| Method | Path | Aciklama |
| --- | --- | --- |
| `GET` | `/api/settings` | Aktif ayarlar |
| `PUT` | `/api/settings` | Ayarlari `.cache/user_settings.json`'a kaydet ve yeniden yukle |
| `GET` | `/api/settings/prompts` | Prompt editor metadata + icerik |
| `PUT` | `/api/settings/prompts` | Promptlari kaydet |
| `POST` | `/api/settings/prompts/reset` | Promptlari varsayilana dondur |
| `GET` | `/api/settings/providers` | Provider listesi |
| `GET` | `/api/settings/health` | Provider baglanti durumu |
| `GET` | `/api/settings/models/{provider}` | Model discovery |
| `GET` | `/api/settings/lm-studio/status` | LM Studio canli durum |
| `POST` | `/api/settings/test-connection` | ikas + provider baglanti testi |
| `GET` | `/api/mcp/status` | MCP durum ozeti |
| `POST` | `/api/mcp/initialize` | MCP baglantisini baslat |
| `POST` | `/api/chat/clear` | Sohbet gecmisini temizle |

### WebSocket

| Path | Aciklama |
| --- | --- |
| `/ws/chat` | AI sohbet, MCP arac cagirilari ve streaming response |
| `/ws/progress` | Uzun sureli operasyonlar icin keep-alive / progress kanali |

## SEO Skorlama

Toplam skor `100` puandir:

| Alan | Maks puan |
| --- | --- |
| Title | 15 |
| Description | 20 |
| English description | 5 |
| Meta title | 15 |
| Meta description | 10 |
| Keyword usage | 10 |
| Content quality | 10 |
| Technical SEO | 10 |
| Readability | 5 |
| AI Citability (GEO) | 10 |

Toplam 100 puan. Varsayilan olarak `70` alti urunler dusuk skor kabul edilir.

GEO skoru; yapilandirilmis urun bilgisi, net urun ozellikleri ve AI-okunabilir formatlama gibi sinyaller uzerinden hesaplanir.

Kontroller arasinda su sinyaller bulunur:

- title uzunlugu, buyuk harf ve ozel karakter yogunlugu
- TR ve EN description uzunlugu ve yapisi
- meta alan uzunluklari
- hedef keyword kapsami
- tekrar / stuffing sinyalleri
- gorsel, etiket, kategori, fiyat, slug gibi teknik alanlar
- cumle uzunlugu ve okunabilirlik

## Prompt Sistemi

Prompt dosyalari `prompts/` klasorunde tutulur ve her AI isteginde yeniden okunur.

Aktif prompt dosyalari:

- `description_rewrite.system.txt`
- `description_rewrite.user.txt`
- `translation_en.system.txt`
- `translation_en.user.txt`
- `geo_rewrite.system.txt`
- `geo_rewrite.user.txt`

Promptlar Settings ekranindan duzenlenebilir. Gecerli degiskenler:

- `{{name}}`
- `{{description}}`
- `{{category}}`
- `{{keywords}}`

Translation prompt'larinda `{{keywords}}` yoktur; yalnizca ilgili ceviri degiskenleri kullanilir.

## Agentic Tool Mimarisi

AI rewrite pipeline artik iteratif, tool-calling tabanli bir agent olarak calisir. Provider tool calling destekliyorsa (Ollama, LM Studio, OpenAI, Anthropic, Gemini, OpenRouter, custom) otomatik olarak agentic moda gecer. `none` provider tek-seferlik (fallback) modda kalir.

### Is akisi

1. `ProductManager.rewrite_product()` provider'in tool-calling destegini kontrol eder
2. Agentic mod: `AgentOrchestrator` + `AgentToolkit` olusturulur
3. Agent otonom olarak:
   - `seo_score_product` ile urunu skorlar
   - En dusuk alandan baslayarak `rewrite_field` ile optimize eder
   - `validate_rewrite` ile iyilesmeyi dogrular
   - Skor iyileşmediyse farkli strateji dener (max 2 retry/alan)
   - `save_suggestion` ile oneriyi kaydeder
4. Maks 8 iterasyon guvenligi vardir
5. SSE streaming: `POST /api/suggestions/generate/{id}/stream` ile agent adimlari gercek zamanli izlenebilir

### Built-in tool'lar

| Tool | Aciklama |
| --- | --- |
| `seo_score_product` | Urunu skorla, issues/suggestions JSON dondur |
| `get_product_details` | Urun bilgilerini getir |
| `search_products` | Urunleri filtrele (dusuk skorlular vb.) |
| `validate_rewrite` | Yeni degerle skoru hesapla, iyilesme goster |
| `save_suggestion` | Oneriyi DB'ye kaydet |
| `get_seo_guidelines` | SEO rubrik kurallarini dondur |

### Toolkit fabrikalar

- `create_seo_rewrite_toolkit()` — Rewrite pipeline (5 tool)
- `create_chat_toolkit()` — Chat (6 tool, MCP tool'lari dinamik eklenir)
- `create_batch_toolkit()` — Toplu operasyonlar (5 tool)

## MCP ve AI Chat

`IKAS_MCP_TOKEN` tanimliysa backend acilista veya Settings ekranindan MCP baglantisini kurabilir. Chat akisi:

- secili urun baglamini modele aktarir
- kullanici mesajina gore MCP arac cagrisi yapabilir
- `@ikas` / `@local` etiketleri ile ya da semantik yonlendirme ile dogru kaynak secilir
- arac sonucunu assistant cevabina baglar
- uzun sohbet gecmisini AI ozetleme ile sıkıştırır
- aktif istegi iptal edebilir
- oturum bazli token ve context kullanim metriklerini saklar

## Testler

```bash
python -m pytest tests -v
```

Sik kullanilan testler:

```bash
python -m pytest tests/test_products_api.py -v
python -m pytest tests/test_product_manager.py -v
python -m pytest tests/test_chat_service.py -v
python -m pytest tests/test_settings_service.py -v
python -m pytest tests/test_provider_service.py -v
```

## Gelistirme Notlari

- `seo_optimizer.db` yerel veritabani dosyasidir.
- Frontend build ciktilari `web/dist` altina uretilir.
- FastAPI, build alinmis SPA varsa root path'te onu servis eder.
- `web/package.json` icinde `dev`, `build`, `lint`, `preview` script'leri bulunur.
- Legacy masaustu UI (`ui/`) repo'dan kaldirilmistir; `ui/` dizini artik mevcut degil.
- LM Studio entegrasyonu native SSE streaming (`/api/v1/chat`) ile calisir; OpenAI-compat endpoint'i de desteklenir.

## Proje Yapisi

```text
ikas-ai-seo-agent/
|-- api/
|   |-- dependencies.py
|   |-- main.py
|   |-- schemas.py
|   `-- routers/
|       |-- chat.py
|       |-- products.py
|       |-- seo.py
|       |-- settings.py
|       `-- suggestions.py
|-- config/
|   `-- settings.py
|-- core/
|   |-- agent_orchestrator.py  # Generic agent loop (run + stream)
|   |-- agent_tools.py         # AgentTool, AgentToolkit, built-in tool'lar, toolkit fabrikalar
|   |-- ai_client.py
|   |-- chat_service.py
|   |-- claude_client.py       # legacy, geriye donuk uyumluluk
|   |-- csv_handler.py
|   |-- html_utils.py
|   |-- ikas_client.py
|   |-- mcp_client.py
|   |-- models.py
|   |-- presentation.py
|   |-- product_manager.py
|   |-- prompt_store.py
|   |-- provider_service.py
|   |-- seo_analyzer.py
|   |-- settings_service.py
|   `-- suggestion_service.py
|-- data/
|   |-- cache.py
|   `-- db.py
|-- prompts/
|   |-- description_rewrite.system.txt
|   |-- description_rewrite.user.txt
|   |-- translation_en.system.txt
|   |-- translation_en.user.txt
|   `-- README.txt
|-- tests/
|   |-- fixtures/
|   |   `-- sample_products.json
|   |-- test_ai_client.py
|   |-- test_chat_service.py
|   |-- test_claude_client.py
|   |-- test_db.py
|   |-- test_html_utils.py
|   |-- test_ikas_client.py
|   |-- test_mcp_client.py
|   |-- test_presentation.py
|   |-- test_product_manager.py
|   |-- test_products_api.py
|   |-- test_provider_service.py
|   |-- test_seo_analyzer.py
|   |-- test_settings.py
|   |-- test_settings_service.py
|   |-- test_suggestion_service.py
|   |-- test_agent_tools.py
|   `-- test_agent_orchestrator.py
|-- web/
|   |-- package.json
|   |-- vite.config.ts
|   `-- src/
|       |-- api/
|       |   `-- client.ts
|       |-- components/
|       |   |-- ChatPanel.tsx
|       |   |-- ProductTable.tsx
|       |   |-- ScoreCard.tsx
|       |   |-- chat/
|       |   |   |-- ChatMessage.tsx
|       |   |   |-- chatUtils.ts
|       |   |   |-- promptParams.ts
|       |   |   `-- suggestionUtils.ts
|       |   `-- dashboard/
|       |       |-- DashboardDetail.tsx
|       |       |-- DashboardEmptyState.tsx
|       |       |-- DashboardHeader.tsx
|       |       |-- DashboardSidebar.tsx
|       |       |-- constants.ts
|       |       `-- productUrl.ts
|       |-- hooks/
|       |   `-- useChat.ts
|       |-- pages/
|       |   |-- Dashboard.tsx
|       |   `-- Settings.tsx
|       `-- types/
|           `-- index.ts
|-- .env.example
|-- main.py
|-- requirements.txt
`-- start.py
```

## Lisans

MIT. Detaylar icin `LICENSE` dosyasina bakin.
