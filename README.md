# ikas AI SEO Agent

ikas e-ticaret magazalari icin AI destekli SEO optimizasyon araci. Urun iceriklerini analiz eder, SEO kalitesini puanlar ve AI ile optimize edilmis yeniden yazim onerileri uretir.

## Giris: Sorun ve Cozum

**Sorun:** ikas magazalarinda urun aciklamalari genellikle zamanla tutarsizlasir; SEO acisindan zayif, eksik anahtar kelimeli veya farkli dillerde dengesiz icerikler organik gorunurlugu dusurur.

**Cozum:** ikas AI SEO Agent, urun iceriklerini otomatik analiz edip puanlar; AI destekli yeniden yazim onerileri ile Turkce/Ingilizce aciklamalari SEO odakli, daha tutarli ve olceklenebilir bir sekilde iyilestirir.

### Temel Yetenekler

- ikas magazasindan urunleri OAuth2 + GraphQL ile ceker
- Her urunu 100 puanlik kural tabanli SEO rubrigine gore puanlar
- AI saglayicisina (Claude, GPT, Gemini, Ollama vb.) icerik gonderip yeniden yazim onerisi alir
- Oncesi/sonrasi diff gosterir, onay sonrasi degisiklikleri ikas'a uygular
- MCP (Model Context Protocol) entegrasyonu ile canli magaza verisi sorgulayan AI sohbet
- Turkce ve Ingilizce urun icerigi destegi
- Varsayilan olarak kuru calistirma modu (DRY_RUN=true) — acikca devre disi birakilmadikca ikas'a yazma yapilmaz

---

## Mimari

```
+---------------------------+     +---------------------------+
|  Web UI (React/TypeScript)|     |  Desktop UI (CustomTkinter)|
|  Vite + SPA               |     |  (legacy)                  |
+-----------+---------------+     +-----------+----------------+
            |                                 |
            v                                 v
+-----------+----------------------------------+
|  FastAPI REST API + WebSocket                |
|  api/main.py                                 |
+-----------+----------------------------------+
            |
+-----------+----------------------------------+
|  ProductManager (Orchestrator)               |
|  core/product_manager.py                     |
+--+--------+--------+--------+--------+------+
   |        |        |        |        |
   v        v        v        v        v
 ikas     SEO      AI       Chat    ikas MCP
 Client   Analyzer Client   Service  Client
 (httpx)  (rules)  (multi)  (multi-  (JSON-RPC)
   |               |        turn)
   v               v
 ikas           Anthropic / OpenAI /
 GraphQL        Gemini / OpenRouter /
 API            Ollama / LM Studio / Custom
            |
      +-----+------+
      |  SQLite DB  |
      |  + Cache    |
      +-------------+
```

---

## Kurulum

```bash
# Repoyu klonla
git clone https://github.com/YigitKa/ikas-ai-seo-agent.git
cd ikas-ai-seo-agent

# Sanal ortam olustur
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Python bagimliklarini yukle
pip install -r requirements.txt

# Frontend bagimliklarini yukle
cd web && npm install && cd ..

# .env dosyasini olustur
cp .env.example .env
# .env dosyasini tercih ettiginiz editor ile duzenleyin

# Testleri calistirarak kurulumu dogrula
python -m pytest tests/ -v
```

---

## Calistirma

### Web UI — gelistirme modu (onerilen)

```bash
python main.py dev          # Backend :8000 + Vite :5173 paralel calisir
```

### Web UI — production modu

```bash
python main.py              # Frontend build eder (gerekirse), FastAPI :8000'de baslar
```

### Desktop UI (legacy CustomTkinter)

```bash
python main.py desktop
```

### start.py ile dogrudan calistirma

```bash
python start.py dev         # Backend :8000 + Vite :5173 paralel
python start.py build       # Sadece frontend build
python start.py backend     # Sadece backend baslat
python start.py prod        # Frontend build + backend baslat
```

> **Not:** Port 8000 mesgulse, `start.py` otomatik olarak sonraki 20 portu dener.

---

## ikas API Kurulumu

1. ikas yonetim paneline gidin
2. **Ayarlar > API Erisimi** bolumine gidin
3. Yeni bir OAuth2 uygulamasi olusturun
4. **Client ID** ve **Client Secret** degerlerini `.env` dosyasina yapistin

---

## AI Provider Secimi

Uygulama birden fazla AI saglayicisini desteklemektedir. Ayarlar ekranindan veya `.env` dosyasindan provider secebilirsiniz.

### Desteklenen Provider'lar

| Provider | Aciklama | Gerekli |
|---|---|---|
| `none` | AI yok, yalnizca SEO analizi yapilir | — |
| `anthropic` | Anthropic Claude (haiku / sonnet / opus) | API Key |
| `openai` | OpenAI GPT modelleri | API Key |
| `gemini` | Google Gemini (OpenAI uyumlu endpoint) | API Key |
| `openrouter` | OpenRouter uzerinden herhangi bir model | API Key |
| `ollama` | Yerel Ollama kurulumu, internet gerekmez | — |
| `lm-studio` | Yerel LM Studio kurulumu, internet gerekmez | — |
| `custom` | Herhangi bir OpenAI uyumlu endpoint | Opsiyonel |

### Provider'a Gore API Key ve URL

| Provider | API Key Nereden Alinir | Base URL |
|---|---|---|
| `anthropic` | [console.anthropic.com](https://console.anthropic.com) | (otomatik) |
| `openai` | [platform.openai.com](https://platform.openai.com) | (otomatik) |
| `gemini` | [aistudio.google.com](https://aistudio.google.com) | (otomatik) |
| `openrouter` | [openrouter.ai/keys](https://openrouter.ai/keys) | (otomatik) |
| `ollama` | gereksiz | `http://localhost:11434` |
| `lm-studio` | gereksiz | `http://localhost:1234` |
| `custom` | endpoint sahibinden | sizin URL'iniz |

### Varsayilan Modeller

| Provider | Varsayilan Model |
|---|---|
| `anthropic` | `claude-haiku-4-5-20251001` |
| `openai` | `gpt-4o-mini` |
| `gemini` | `gemini-1.5-flash` |
| `openrouter` | `openai/gpt-4o-mini` |
| `ollama` | `llama3.2` |
| `lm-studio` | ayarlar ekranindan taranir |

---

## .env Parametreleri

Uygulama acilisinda `.env` dosyasi okunur. Zorunlu alanlar bos ise uygulama terminalde interaktif olarak ister (TTY yoksa hata verir).

### ikas API

| Parametre | Zorunlu | Aciklama | Ornek |
|---|---|---|---|
| `IKAS_STORE_NAME` | Evet | Magazanizin alt alani | `my-store` |
| `IKAS_CLIENT_ID` | Evet | OAuth2 Client ID | ikas panelinden |
| `IKAS_CLIENT_SECRET` | Evet | OAuth2 Client Secret | ikas panelinden |
| `IKAS_MCP_TOKEN` | Hayir | ikas MCP token (AI sohbet icin canli magaza verisi) | ikas panelinden |

### AI Provider

| Parametre | Zorunlu | Aciklama | Varsayilan |
|---|---|---|---|
| `AI_PROVIDER` | Hayir | `none` / `anthropic` / `openai` / `gemini` / `openrouter` / `ollama` / `lm-studio` / `custom` | `none` (ANTHROPIC_API_KEY varsa `anthropic`) |
| `AI_API_KEY` | Provider'a gore | Secilen provider'in API anahtari | — |
| `AI_BASE_URL` | Opsiyonel | Ozel endpoint URL'i (ollama veya custom icin) | Provider varsayilani |
| `AI_MODEL_NAME` | Opsiyonel | Kullanilacak model adi | Provider varsayilani |
| `AI_TEMPERATURE` | Hayir | Yaraticilik seviyesi (0.0 - 1.0) | `0.7` |
| `AI_MAX_TOKENS` | Hayir | Maksimum cikti token sayisi | `2000` |
| `ANTHROPIC_API_KEY` | Hayir | Eski Anthropic key (geriye donuk uyumlu) | — |

### Genel

| Parametre | Zorunlu | Aciklama | Varsayilan |
|---|---|---|---|
| `STORE_LANGUAGES` | Hayir | Aktif diller, virgul ayrimli | `tr,en` |
| `SEO_TARGET_KEYWORDS` | Hayir | Hedef anahtar kelimeler, virgul ayrimli | — |
| `DRY_RUN` | Hayir | `true` ise ikas'a gercek yazma yapilmaz | `true` |
| `LOG_LEVEL` | Hayir | `DEBUG` / `INFO` / `WARNING` / `ERROR` | `INFO` |

### Ornek .env

```env
# ikas
IKAS_STORE_NAME=my-store
IKAS_CLIENT_ID=xxx
IKAS_CLIENT_SECRET=yyy
IKAS_MCP_TOKEN=zzz

# AI Provider (birini aktif edin)

## Anthropic
AI_PROVIDER=anthropic
AI_API_KEY=sk-ant-...
AI_MODEL_NAME=claude-haiku-4-5-20251001

## OpenAI
# AI_PROVIDER=openai
# AI_API_KEY=sk-...
# AI_MODEL_NAME=gpt-4o-mini

## Google Gemini
# AI_PROVIDER=gemini
# AI_API_KEY=AIza...
# AI_MODEL_NAME=gemini-1.5-flash

## OpenRouter
# AI_PROVIDER=openrouter
# AI_API_KEY=sk-or-...
# AI_MODEL_NAME=openai/gpt-4o-mini

## Ollama (yerel, internet gerekmez)
# AI_PROVIDER=ollama
# AI_BASE_URL=http://localhost:11434
# AI_MODEL_NAME=llama3.2

## LM Studio (yerel, internet gerekmez)
# AI_PROVIDER=lm-studio
# AI_BASE_URL=http://localhost:1234
# AI_MODEL_NAME=qwen2.5-7b-instruct

## Custom OpenAI-uyumlu endpoint
# AI_PROVIDER=custom
# AI_API_KEY=...
# AI_BASE_URL=https://my-api.example.com/v1
# AI_MODEL_NAME=my-model

AI_TEMPERATURE=0.7
AI_MAX_TOKENS=2000

# Genel
STORE_LANGUAGES=tr,en
SEO_TARGET_KEYWORDS=kadin ayakkabi,spor ayakkabi
DRY_RUN=true
```

---

## API Endpoints

FastAPI backend asagidaki REST endpoint'lerini sunar:

| Route | Method | Aciklama |
|---|---|---|
| `/api/health` | GET | Saglik kontrolu |
| `/api/products/` | GET | Onbellekteki urunleri listele |
| `/api/products/fetch` | POST | ikas'tan urunleri cek |
| `/api/products/{id}` | GET | Tekil urun detayi |
| `/api/products/sync` | POST | Tam urun senkronizasyonu |
| `/api/seo/analyze` | POST | SEO analizi baslat |
| `/api/seo/batch` | POST | Toplu SEO analizi |
| `/api/suggestions/pending` | GET | Bekleyen onerileri listele |
| `/api/suggestions/{id}` | GET | Urun onerilerini getir |
| `/api/suggestions/{id}` | POST | Oneri olustur/guncelle |
| `/api/suggestions/{id}` | PUT | Oneri durumunu guncelle |
| `/api/settings/config` | GET | Mevcut konfigurasyonu getir |
| `/api/settings/save` | POST | Ayarlari kaydet |
| `/api/settings/providers` | GET | AI provider'lari listele |
| `/api/settings/test` | POST | Provider baglantisini test et |
| `/api/settings/prompts` | GET | Prompt sablonlarini getir |
| `/api/settings/prompts` | POST | Prompt sablonlarini kaydet |
| `/api/chat/stream` | WebSocket | AI sohbet (MCP arac entegrasyonu ile) |

---

## AI Sohbet ve MCP Entegrasyonu

Uygulama, ikas MCP (Model Context Protocol) entegrasyonu sayesinde AI sohbet sirasinda canli magaza verilerine erisim saglar:

- **Cok turlu sohbet:** Maks 40 mesajlik konusma gecmisi
- **MCP arac cagirilari:** Urunler, kategoriler, envanter gibi canli magaza verilerini sorgulama
- **Her kullanici mesaji basina maks 5 ardisik arac cagrisi**
- **Turkce/Ingilizce dil tespiti**
- **WebSocket uzerinden gercek zamanli streaming**

MCP'yi etkinlestirmek icin `.env` dosyasina `IKAS_MCP_TOKEN` degerini ekleyin.

---

## Yerel Model Kullanimi

### Ollama

Ollama ile internet baglantisi olmadan yerel bir model kullanabilirsiniz.

```bash
# 1. Ollama'yi yukle
#    Linux / Mac:
curl -fsSL https://ollama.com/install.sh | sh
#    Windows: https://ollama.com/download adresinden yukleyin

# 2. Bir model indir
ollama pull llama3.2        # 2B, hizli
ollama pull llama3.1:8b     # 8B, daha kaliteli
ollama pull mistral         # 7B, cok dilli

# 3. Ollama'nin calistigini dogrula
curl http://localhost:11434/api/tags

# 4. .env dosyasini duzenle
AI_PROVIDER=ollama
AI_BASE_URL=http://localhost:11434
AI_MODEL_NAME=llama3.2
```

### LM Studio

LM Studio ile Qwen, Mistral, Llama gibi modelleri yerel olarak calistirup kullanabilirsiniz.

```bash
# 1. LM Studio'yu yukle
#    https://lmstudio.ai adresinden isletim sisteminize gore indirin

# 2. LM Studio icerisinden bir model indir (ornegin Qwen2.5)

# 3. LM Studio'da Local Server'i baslat (varsayilan port: 1234)

# 4. .env dosyasini duzenle
AI_PROVIDER=lm-studio
AI_BASE_URL=http://localhost:1234
AI_MODEL_NAME=qwen2.5-7b-instruct   # yuklediginiz modelin adi
```

---

## SEO Skor Dagilimi

Skorlama algoritmasi modern SEO araclarindan (Ahrefs, Semrush, Yoast, Moz, Screaming Frog) esinlenerek tasarlanmistir.

| Kategori | Maks Puan | Kontrol Edilen Kriterler |
|---|---|---|
| Baslik Kalitesi | 15 | Uzunluk (30-60 karakter), buyuk harf orani, ozel karakter, power word kullanimi |
| Turkce Aciklama | 20 | Kelime sayisi (150-500 ideal), paragraf yapisi, HTML yapisal ogeler (baslik, liste, bold) |
| Ingilizce Aciklama | 5 | Kelime sayisi, Turkce karakter kontrolu |
| Meta Title | 15 | Uzunluk (50-60 karakter), marka ayirici, urun adindan farklilik |
| Meta Description | 10 | Uzunluk (120-160 karakter), call-to-action varligi |
| Keyword Uyumu | 10 | Hedef keyword kapsami, kategori adi eslesmesi, urun adi-aciklama tutarliligi |
| Icerik Kalitesi | 10 | Keyword stuffing tespiti, kelime cesitliligi (TTR), tekrarlanan n-gram, baslik-icerik uyumu |
| Teknik SEO | 10 | Gorsel sayisi, etiket/tag varligi, kategori atamasi, URL-dostu isim, fiyat bilgisi |
| Okunabilirlik | 5 | Ortalama cumle uzunlugu, cumle uzunluk varyasyonu, gecis kelimeleri |
| **Toplam** | **100** | |

Skor < 70 ise urun "optimizasyon gerekiyor" olarak isaretlenir.

---

## Cift Dil (TR/EN) Destegi

- ikas GraphQL sorgularinda `translations { locale name description }` alani okunur
- SEO skoruna ek olarak Ingilizce aciklama kalitesi icin `english_description_score` hesaplanir
- AI rewrite akisinda hem TR hem EN baglami modele verilir; EN onerisi de uretilir
- Uygulama asamasinda `tr` ve `en` aciklamalari birlikte guncellenebilir

---

## Prompt Sablonlari

Prompt dosyalari `prompts/` klasorunde bulunur ve `core/prompt_store.py` tarafindan yuklenir. `{{degisken}}` sozdizimini kullanir. Kullanicilar prompt'lari Ayarlar ekranindan duzenleyebilir.

Mevcut sablonlar:
- `description_rewrite.system.txt` / `.user.txt` — urun aciklamasi yeniden yazimi
- `translation_en.system.txt` / `.user.txt` — Turkce icerigin Ingilizce'ye cevirisi

---

## Testler

```bash
# Tum testler
python -m pytest tests/ -v

# Tekil test dosyasi
python -m pytest tests/test_seo_analyzer.py -v

# Tekil test fonksiyonu
python -m pytest tests/test_seo_analyzer.py::test_analyze_product_low_score -v
```

Testler `pytest` ve mock nesneler kullanir — canli API cagrisi yapilmaz.

---

## Proje Yapisi

```text
ikas-ai-seo-agent/
|-- main.py                  # Entry point — web (varsayilan), desktop veya dev modu
|-- start.py                 # Backend/frontend koordinatoru, Vite dev server
|-- requirements.txt         # Python bagimliliklari
|-- .env.example             # Tum konfigurasyonlar ve aciklamalari
|
|-- config/
|   `-- settings.py          # .env yukleyici, dogrulama, AppConfig
|
|-- core/                    # Is mantigi (UI bagimliligi yok)
|   |-- models.py            # Pydantic modeller: Product, SeoScore, SeoSuggestion, ChatMessage vb.
|   |-- ikas_client.py       # Async GraphQL client (httpx)
|   |-- ai_client.py         # Coklu AI provider soyutlamasi (factory + adapter)
|   |-- claude_client.py     # Eski Anthropic client (geriye donuk uyumlu)
|   |-- product_manager.py   # Orkestrator — tum core modulleri koordine eder
|   |-- seo_analyzer.py      # Kural tabanli SEO skorlama motoru
|   |-- csv_handler.py       # CSV import/export
|   |-- prompt_store.py      # Prompt sablonlarini yukler ve render eder
|   |-- chat_service.py      # Cok turlu AI sohbet + MCP arac entegrasyonu
|   |-- mcp_client.py        # ikas MCP JSON-RPC client
|   |-- provider_service.py  # Provider tespiti, saglik kontrolu, model kesfetme
|   |-- settings_service.py  # Ayar yonetim servisi
|   |-- suggestion_service.py # Oneri alan islemleri
|   |-- html_utils.py        # HTML ayristirma ve temizleme
|   `-- presentation.py      # Gorunum formatlama yardimcilari
|
|-- api/                     # FastAPI REST API + WebSocket
|   |-- main.py              # FastAPI app, CORS, router'lar, SPA static dosya sunumu
|   |-- dependencies.py      # Singleton ProductManager injection
|   |-- schemas.py           # API istek/yanit Pydantic semalari
|   `-- routers/
|       |-- products.py      # Urun listele, cek, detay, senkronize
|       |-- seo.py           # SEO analiz endpoint'leri
|       |-- suggestions.py   # Oneri CRUD endpoint'leri
|       |-- settings.py      # Ayar yonetimi endpoint'leri
|       `-- chat.py          # WebSocket sohbet endpoint'i
|
|-- web/                     # React/TypeScript frontend (Vite)
|   |-- package.json
|   |-- tsconfig.json
|   |-- vite.config.ts
|   `-- src/
|       |-- main.tsx         # React entry point
|       |-- App.tsx          # Root component
|       |-- api/             # API client fonksiyonlari
|       |-- components/      # React bilesenler
|       |-- hooks/           # Custom React hook'lar
|       |-- pages/           # Sayfa bilesenler
|       `-- types/           # TypeScript tip tanimlari
|
|-- ui/                      # Legacy CustomTkinter masaustu UI
|   |-- app.py               # Ana pencere
|   |-- image_service.py     # Async gorsel yukleme + TTL cache
|   `-- components/
|       |-- settings_panel.py
|       |-- ai_chat_panel.py
|       |-- diff_viewer.py
|       |-- product_table.py
|       |-- score_card.py
|       `-- dockable_panel.py
|
|-- data/
|   |-- db.py                # SQLite sema + yardimcilar
|   `-- cache.py             # Dosya tabanli TTL cache
|
|-- prompts/                 # Duzenlenebilir AI prompt sablonlari
|   |-- description_rewrite.system.txt
|   |-- description_rewrite.user.txt
|   |-- translation_en.system.txt
|   |-- translation_en.user.txt
|   `-- README.txt
|
`-- tests/
    |-- fixtures/
    |   `-- sample_products.json
    |-- test_seo_analyzer.py
    |-- test_ai_client.py
    |-- test_claude_client.py
    |-- test_ikas_client.py
    |-- test_db.py
    |-- test_settings.py
    |-- test_html_utils.py
    |-- test_presentation.py
    |-- test_provider_service.py
    |-- test_settings_service.py
    |-- test_suggestion_service.py
    |-- test_chat_service.py
    `-- test_mcp_client.py
```

---

## Lisans

MIT License — detaylar icin [LICENSE](LICENSE) dosyasina bakin.
