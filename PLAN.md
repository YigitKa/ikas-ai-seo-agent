# Web UI Migration Plan

## Phase 1: Backend API (FastAPI)

### 1.1 Proje yapısı
```
ikas-ai-seo-agent/
├── core/                    # Mevcut - değişmez
├── config/                  # Mevcut - değişmez
├── data/                    # Mevcut - değişmez
├── prompts/                 # Mevcut - değişmez
├── api/                     # YENİ - FastAPI backend
│   ├── __init__.py
│   ├── main.py              # FastAPI app, CORS, lifespan
│   ├── dependencies.py      # Shared dependencies (ProductManager, config)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── products.py      # GET /products, GET /products/{id}
│   │   ├── seo.py           # POST /seo/analyze, GET /seo/scores/{product_id}
│   │   ├── suggestions.py   # POST /suggestions/generate, PATCH /suggestions/{id}
│   │   ├── settings.py      # GET/PUT /settings, GET /providers, POST /test-connection
│   │   └── chat.py          # WebSocket /ws/chat
│   └── schemas.py           # API request/response Pydantic models (core models'i wrap eder)
├── web/                     # YENİ - React frontend
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/             # API client (fetch wrapper)
│   │   ├── components/      # React components
│   │   ├── hooks/           # Custom hooks
│   │   ├── pages/           # Page-level components
│   │   └── types/           # TypeScript types (API response mirrors)
│   └── public/
├── tests/                   # Mevcut + yeni API testleri
├── ui/                      # ESKİ - CustomTkinter (silinecek, Phase sonunda)
└── main.py                  # Güncellenir: web server launcher
```

### 1.2 API Endpoints

#### Products
```
GET    /api/products                    # Liste (paginated, filterable)
GET    /api/products/{id}               # Tekil ürün detay
POST   /api/products/fetch              # ikas'tan çek (trigger)
```

#### SEO Analysis
```
POST   /api/seo/analyze                 # Tüm ürünleri analiz et
GET    /api/seo/scores/{product_id}     # Ürün SEO skoru
POST   /api/seo/analyze/{product_id}    # Tek ürün analiz
```

#### AI Suggestions
```
POST   /api/suggestions/generate/{product_id}         # AI rewrite tetikle
POST   /api/suggestions/generate-field/{product_id}   # Tek alan rewrite
POST   /api/suggestions/translate/{product_id}         # EN çeviri
PATCH  /api/suggestions/{product_id}/approve           # Onayla
PATCH  /api/suggestions/{product_id}/reject            # Reddet
POST   /api/suggestions/apply                          # ikas'a uygula
GET    /api/suggestions/{product_id}                   # Mevcut suggestion'lar
```

#### Settings
```
GET    /api/settings                    # Mevcut ayarlar
PUT    /api/settings                    # Ayar güncelle
GET    /api/settings/providers          # Provider listesi + durumları
POST   /api/settings/test-connection    # ikas bağlantı testi
GET    /api/settings/models/{provider}  # Provider model listesi
```

#### Real-time (WebSocket)
```
WS     /ws/chat                         # AI chat stream
WS     /ws/progress                     # Uzun işlem progress
```

### 1.3 Backend implementasyon adımları

1. `pip install fastapi uvicorn websockets` → requirements.txt güncelle
2. `api/main.py` → FastAPI app oluştur, CORS middleware ekle
3. `api/dependencies.py` → ProductManager singleton, config injection
4. Router'ları sırayla implement et:
   - products.py: `ProductManager.fetch_products()` wrap
   - seo.py: `ProductManager.score_products()` wrap
   - suggestions.py: `ProductManager.rewrite_product()` wrap
   - settings.py: `SettingsService` wrap
   - chat.py: WebSocket + AI streaming
5. `api/schemas.py` → Request/Response modelleri (core models extend)
6. Background tasks: uzun süren işlemler (batch rewrite) için FastAPI BackgroundTasks veya asyncio.Task

---

## Phase 2: Frontend (React + TypeScript)

### 2.1 Sayfa yapısı

```
/ (Dashboard)
├── Sidebar: Navigation + Settings özet
├── Main Content:
│   ├── Product Table (filterable, paginated, sortable)
│   ├── Product Detail → SEO Score Card + Diff Viewer
│   └── AI Chat Panel (slide-over)
└── Settings Page (/settings)
```

### 2.2 Temel componentler

| Component | Karşılığı (CustomTkinter) | Kütüphane |
|-----------|--------------------------|-----------|
| ProductTable | product_table.py | TanStack Table |
| DiffViewer | diff_viewer.py | react-diff-viewer-continued |
| ScoreCard | score_card.py | Recharts (radar chart) |
| SettingsForm | settings_panel.py | React Hook Form + Zod |
| AIChatPanel | ai_chat_panel.py | Custom + WebSocket |
| HTMLPreview | diff_viewer._HtmlPreviewParser | DOMPurify + iframe sandbox |

### 2.3 Frontend implementasyon adımları

1. `npm create vite@latest web -- --template react-ts`
2. Tailwind CSS + shadcn/ui kurulumu
3. API client layer (`web/src/api/client.ts`)
4. Type definitions (`web/src/types/`)
5. Pages sırayla:
   - Dashboard: Product table + filters
   - Product detail: Score card + diff viewer + rewrite buttons
   - Settings: Form + connection test
   - AI Chat: WebSocket panel
6. WebSocket hooks: progress tracking, chat streaming

---

## Phase 3: Entegrasyon & Temizlik

1. `main.py` güncelle → `uvicorn api.main:app` başlat
2. Static file serving: FastAPI React build dosyalarını serve etsin
3. CustomTkinter UI kodunu (`ui/` dizini) sil
4. Desktop-only dependency'leri kaldır (`customtkinter`, `Pillow`)
5. Testleri güncelle (API endpoint testleri ekle)
6. Docker desteği (opsiyonel)

---

## Küçük Düzeltmeler (Phase 1 öncesi)

1. **Hardcoded skor eşiği** → `AppConfig`'e `seo_low_score_threshold: int = 70` ekle
2. **Image URL fallback** → `core/presentation.py`'ye `get_product_image_urls()` ekle
3. Bu iki düzeltme hem mevcut UI'ı hem gelecek web UI'ı temizler

---

## Öncelik Sırası

```
[1] Küçük düzeltmeler (core temizlik)          ~30 dk
[2] FastAPI backend + products/seo router       ~2-3 saat
[3] Suggestions + settings router               ~2 saat
[4] WebSocket (chat + progress)                 ~1-2 saat
[5] React proje kurulumu + API client           ~1 saat
[6] Product table + score card sayfası          ~2-3 saat
[7] Diff viewer + rewrite UI                    ~3-4 saat
[8] Settings sayfası                            ~1-2 saat
[9] AI Chat panel                               ~2 saat
[10] Entegrasyon, test, temizlik                ~2 saat
```
