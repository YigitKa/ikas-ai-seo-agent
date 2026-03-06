# ikas SEO Optimizer

Python-based SEO optimization tool for ikas e-commerce stores. Analyzes product content, scores SEO quality, and uses AI to generate optimized rewrites.

## Giris: Sorun ve Cozum

**Sorun:** ikas magazalarinda urun aciklamalari genellikle zamanla tutarsizlasir; SEO acisindan zayif, eksik anahtar kelimeli veya farkli dillerde dengesiz icerikler organik gorunurlugu dusurur.

**Cozum:** ikas SEO Optimizer, urun iceriklerini otomatik analiz edip puanlar; AI destekli yeniden yazim onerileri ile Turkce/Ingilizce aciklamalari SEO odakli, daha tutarli ve olceklenebilir bir sekilde iyilestirir.

---

## Mimari

```
+------------------+     +------------------+     +------------------+
|   CLI (typer)    |     |  Desktop UI      |     |  CSV Import      |
|   cli/main.py    |     |  (CustomTkinter) |     |  csv_handler.py  |
+--------+---------+     +--------+---------+     +--------+---------+
         |                        |                        |
         +------------------------+------------------------+
                                  |
                    +-------------+-------------+
                    |   Product Manager         |
                    |   (Orchestrator)          |
                    +--+--------+--------+-----+
                       |        |        |
              +--------+  +-----+----+ +-+------------+
              | ikas    |  | SEO      | | AI Client    |
              | Client  |  | Analyzer | | (multi-prov) |
              | (httpx) |  | (rules)  | +-+------------+
              +----+----+  +----------+   |
                   |         Anthropic / OpenAI /
              +----+----+    Gemini / OpenRouter /
              | ikas    |    Ollama / Custom
              | GraphQL |
              | API     |
              +---------+
                          |
                    +-----+------+
                    |  SQLite DB |
                    |  + Cache   |
                    +------------+
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

# Bagimliliklari yukle
pip install -r requirements.txt

# .env dosyasini olustur
cp .env.example .env
# .env dosyasini tercih ettiginiz editor ile duzenleyin
```

---

## ikas API Kurulumu

1. ikas yonetim paneline gidin
2. **Ayarlar > API Erisimi** bolumine gidin
3. Yeni bir OAuth2 uygulamasi olusturun
4. **Client ID** ve **Client Secret** degerlerini `.env` dosyasina yapistin

---

## AI Provider Secimi

Uygulama artik birden fazla AI saglayicisini desteklemektedir. Ayarlar ekranindan veya `.env` dosyasindan provider secebilirsiniz.

### Desteklenen Provider'lar

| Provider | Aciklama | Gerekli |
|---|---|---|
| `none` | AI yok, yalnizca SEO analizi yapilir | — |
| `anthropic` | Anthropic Claude (haiku / sonnet / opus) | API Key |
| `openai` | OpenAI GPT modelleri | API Key |
| `gemini` | Google Gemini (OpenAI uyumlu endpoint) | API Key |
| `openrouter` | OpenRouter uzerinden herhangi bir model | API Key |
| `ollama` | Yerel Ollama kurulumu, internet gerekmez | — |
| `custom` | Herhangi bir OpenAI uyumlu endpoint | Opsiyonel |

### Provider'a Gore API Key ve URL

| Provider | API Key Nereden Alinir | Base URL |
|---|---|---|
| `anthropic` | [console.anthropic.com](https://console.anthropic.com) | (otomatik) |
| `openai` | [platform.openai.com](https://platform.openai.com) | (otomatik) |
| `gemini` | [aistudio.google.com](https://aistudio.google.com) | (otomatik) |
| `openrouter` | [openrouter.ai/keys](https://openrouter.ai/keys) | (otomatik) |
| `ollama` | gereksiz | `http://localhost:11434` |
| `custom` | endpoint sahibinden | sizin URL'iniz |

### Varsayilan Modeller

| Provider | Varsayilan Model |
|---|---|
| `anthropic` | `claude-haiku-4-5-20251001` |
| `openai` | `gpt-4o-mini` |
| `gemini` | `gemini-1.5-flash` |
| `openrouter` | `openai/gpt-4o-mini` |
| `ollama` | `llama3.2` |

---

## .env Parametreleri

Uygulama acilisinda `.env` dosyasi okunur. Zorunlu alanlar bos ise uygulama terminalde sizden interaktif olarak ister (TTY yoksa hata verir).

### ikas API

| Parametre | Zorunlu | Aciklama | Ornek |
|---|---|---|---|
| `IKAS_STORE_NAME` | Evet | Magazanizin alt alani | `my-store` |
| `IKAS_CLIENT_ID` | Evet | OAuth2 Client ID | ikas panelinden |
| `IKAS_CLIENT_SECRET` | Evet | OAuth2 Client Secret | ikas panelinden |

### AI Provider

| Parametre | Zorunlu | Aciklama | Varsayilan |
|---|---|---|---|
| `AI_PROVIDER` | Hayir | `none` / `anthropic` / `openai` / `gemini` / `openrouter` / `ollama` / `custom` | `none` (ANTHROPIC_API_KEY varsa `anthropic`) |
| `AI_API_KEY` | Provider'a gore | Secilen provider'in API anahtari | — |
| `AI_BASE_URL` | Opsiyonel | Ozel endpoint URL'i (ollama veya custom icin) | Provider varsayilani |
| `AI_MODEL_NAME` | Opsiyonel | Kullanilacak model adi | Provider varsayilani |
| `AI_TEMPERATURE` | Hayir | Yaraticilik seviyesi (0.0 - 1.0) | `0.7` |
| `AI_MAX_TOKENS` | Hayir | Maksimum cikti token sayisi | `2000` |
| `ANTHROPIC_API_KEY` | Hayir | Eski Anthropic key (geriye donuk uyumlu) | — |

### Genel

| Parametre | Zorunlu | Aciklama | Varsayilan |
|---|---|---|---|
| `STORE_LANGUAGES` | Hayir | Aktif diller, virgul ayrimli | `tr` |
| `SEO_TARGET_KEYWORDS` | Hayir | Hedef anahtar kelimeler, virgul ayrimli | — |
| `DRY_RUN` | Hayir | `true` ise ikas'a gercek yazma yapilmaz | `true` |
| `LOG_LEVEL` | Hayir | `DEBUG` / `INFO` / `WARNING` / `ERROR` | `INFO` |

### Ornek .env

```env
# ikas
IKAS_STORE_NAME=my-store
IKAS_CLIENT_ID=xxx
IKAS_CLIENT_SECRET=yyy

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

## Ollama Kurulumu (Yerel Model)

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

Uygulama icerisinde **Ayarlar > AI Provider > Ollama** secip **"Ollama Bulundu mu?"** butonuna basarak kurulu modelleri otomatik kesfedebilirsiniz.

---

## Desktop UI Kullanimi

```bash
python main.py        # varsayilan: UI modu
python main.py --ui   # acikca UI modu
```

### Toolbar

| Buton | Aciklama |
|---|---|
| Urunleri Cek | ikas API'den urunleri ceker ve SEO puanlarini hesaplar |
| Secilileri Analiz Et | Secili urunu kural tabanli analiz eder |
| AI ile Yeniden Yaz | Secili urun icin AI'a yeniden yazim onerisi urettirir |
| Onayla ve Uygula | Onaylanan onerileri ikas'a gonderir (DRY_RUN=false gerekli) |
| Ayarlar | Provider ve API ayarlarini acar |

### Filtreler

`Tumu` / `Dusuk Skor` / `Bekleyen` / `Onayli`

### Ayarlar Ekrani

1. **Ayarlar** butonuna basin
2. **AI Provider** alaninda istediginiz saglayiciy secin
3. Provider'a ozgu alanlari doldurun (API Key, Model, vb.)
4. Ollama icin **"Ollama Bulundu mu?"** butonuyla kurulu modelleri listeleyin
5. **Kaydet**'e basin — ayarlar `.env` dosyasina yazilir ve uygulama yeniden baslatma gerekmeksizin guncellenir

---

## CLI Kullanim

```bash
python main.py --cli analyze                          # Tum urunleri analiz et
python main.py --cli analyze --threshold 60           # Dusuk skorlu urunler
python main.py --cli analyze --source csv --file products.csv  # CSV'den
python main.py --cli analyze --product-id abc123      # Tek urun

python main.py --cli rewrite --dry-run                # AI onerisi uret
python main.py --cli apply                            # Onaylari uygula

python main.py --cli history                          # Gecmis raporu
python main.py --cli test-connection                  # Baglanti testi
python main.py --cli export --output report.csv       # CSV'ye aktar
```

---

## SEO Skor Dagilimi

| Alan | Puan |
|---|---|
| Baslik kalitesi | 25 |
| Turkce aciklama | 30 |
| Ingilizce aciklama | 10 |
| Meta title | 20 |
| Meta description | 15 |
| Keyword uyumu | 10 |
| **Toplam** | **100** |

Skor < 70 ise urun "optimizasyon gerekiyor" olarak isaretlenir.

---

## Cift Dil (TR/EN) Destegi

- ikas GraphQL sorgularinda `descriptionTranslations { locale value }` alani okunur
- SEO skoruna ek olarak Ingilizce aciklama kalitesi icin `english_description_score` hesaplanir
- AI rewrite akisinda hem TR hem EN baglami modele verilir; EN onerisi de uretilir
- Uygulama asamasinda `tr` ve `en` aciklamalari birlikte guncellenebilir
- Eger store schema'si `descriptionTranslations` alanini desteklemiyorsa istemci fallback olarak sadece varsayilan `description` gunceller

---

## Testler

```bash
python -m pytest tests/ -v
```

---

## Proje Yapisi

```
ikas-ai-seo-agent/
├── core/
│   ├── models.py            # Pydantic veri modelleri
│   ├── ikas_client.py       # ikas GraphQL API client
│   ├── csv_handler.py       # CSV import/export
│   ├── seo_analyzer.py      # Kural tabanli SEO skorlama
│   ├── ai_client.py         # Unified AI client (tum provider'lar)
│   ├── claude_client.py     # (eski, geriye donuk)
│   └── product_manager.py   # Orkestrator
├── cli/main.py              # CLI arayuzu (typer + rich)
├── ui/
│   ├── app.py               # Ana pencere
│   └── components/
│       ├── settings_panel.py  # Provider secimi + ayarlar
│       ├── diff_viewer.py
│       ├── product_table.py
│       └── score_card.py
├── data/                    # SQLite + cache
├── config/settings.py       # Ayar yukleme + .env yazma
├── .env.example             # Ornek konfigürasyon
└── tests/
```

---

## Lisans

MIT License — detaylar icin [LICENSE](LICENSE) dosyasina bakin.
