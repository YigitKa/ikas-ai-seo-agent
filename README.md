# ikas SEO Optimizer

Python-based SEO optimization tool for ikas e-commerce stores. Analyzes product content, scores SEO quality, and uses Claude AI to generate optimized rewrites.

## TR - Proje Aciklamasi

ikas e-ticaret altyapisi kullanan magazalar icin Python tabanli SEO optimizasyon araci. Urun iceriklerini analiz eder, SEO kalitesini puanlar ve Claude AI ile optimize edilmis icerik uretir.

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
              +--------+  +-----+----+ +-+----------+
              | ikas    |  | SEO      | | Claude     |
              | Client  |  | Analyzer | | Client     |
              | (httpx) |  | (rules)  | | (anthropic)|
              +----+----+  +----------+ +------+-----+
                   |                           |
              +----+----+              +-------+-------+
              | ikas    |              | Anthropic     |
              | GraphQL |              | API           |
              | API     |              |               |
              +---------+              +---------------+
                          |
                    +-----+------+
                    |  SQLite DB |
                    |  + Cache   |
                    +------------+
```

## Yeni: Cift Dil (TR/EN) SEO Destegi

Bu proje artik urun aciklamalarini hem Turkce hem Ingilizce olarak isleyebilir:

- ikas GraphQL sorgularinda `descriptionTranslations` alani okunur.
- Urun modeli icinde tum dil aciklamalari `description_translations` alaninda tutulur.
- SEO skoruna ek olarak Ingilizce aciklama kalitesi icin `english_description_score` hesaplanir.
- Toplam skor hesaplanirken TR + EN kalite sinyalleri birlikte degerlendirilir (ust sinir 100).
- Claude rewrite akisinda hem TR hem EN aciklama baglami modele verilir ve EN onerisi de uretilir.
- Uygulama asamasinda onaylanan onerilerde `tr` ve `en` aciklamalari birlikte guncellenebilir.

### ikas'tan TR/EN aciklamalari okuma/guncelleme notu

`core/ikas_client.py` icindeki akista:

1. Okuma tarafinda `description` + `descriptionTranslations { locale value }` alanlari cekilir.
2. Parse asamasinda liste/dict fark etmeksizin locale->text seklinde normalize edilir.
3. Guncellemede `descriptionTranslations` payload'i gonderilir.
4. Eger store schema'si bu alani kabul etmezse istemci otomatik fallback ile sadece varsayilan `description` guncellemesi yapar.

Bu fallback mekanizmasi farkli ikas store surumleri/schemalari arasinda geriye donuk uyumluluk icin eklendi.

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
# .env dosyasini duzenleyin
```

## ikas API Kurulumu

1. ikas yonetim paneline gidin
2. Ayarlar > API Erisimi bolumine gidin
3. Yeni bir OAuth2 uygulamasi olusturun
4. Client ID ve Client Secret degerlerini `.env` dosyasina yapistin

## .env Parametreleri (Kullanilan Tum Ayarlar)

Uygulama acilisinda `.env` dosyasi okunur. Asagidaki alanlardan **zorunlu** olanlar bos ise uygulama calisirken kullanicidan interaktif olarak istenir (TTY yoksa hata verir).

| Parametre | Zorunlu | Aciklama | Olasi Deger/Format | Varsayilan |
|---|---|---|---|---|
| `IKAS_STORE_NAME` | Evet | ikas magaza alt alani; API URL bu degerden olusturulur. | `my-store` (sadece subdomain, `https://` olmadan) | Yok |
| `IKAS_CLIENT_ID` | Evet | ikas OAuth2 istemci kimligi. | ikas panelinden alinan metin degeri | Yok |
| `IKAS_CLIENT_SECRET` | Evet | ikas OAuth2 istemci gizli anahtari. | ikas panelinden alinan gizli deger | Yok |
| `ANTHROPIC_API_KEY` | Evet | Claude API anahtari. | `sk-ant-...` formatinda anahtar | Yok |
| `STORE_LANGUAGES` | Hayir (onerilen) | Magazada aktif diller; birden fazla dil virgul ile verilir. | `tr,en,de,fr,es` gibi ISO kod listesi | `tr` |
| `STORE_LANGUAGE` | Hayir (geri uyumlu) | Eski tekil dil anahtari. Tek deger veya virgul ayrimli liste de alabilir. | `tr` veya `tr,en` | `tr` |
| `SEO_TARGET_KEYWORDS` | Hayir | Anahtar kelime listesi; virgul ile ayrilir. | `kadin ayakkabi,spor ayakkabi,deri` | Bos liste |
| `DRY_RUN` | Hayir | `apply` asamasinda gercek guncelleme yapilsin mi. | `true/false`, `1/0`, `yes/no`, `on/off` | `true` |
| `LOG_LEVEL` | Hayir | Uygulama log seviyesi. | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` |

### Eksik ayarlari calisma aninda isteme davranisi

- Zorunlu alanlardan biri eksikse uygulama terminalde sizden degeri ister.
- `IKAS_CLIENT_SECRET` ve `ANTHROPIC_API_KEY` girisleri guvenlik icin maskeli alinir.
- Uygulama TTY olmayan bir ortamda (or. non-interactive pipeline) calisiyorsa, eksik zorunlu alanlar icin acik hata verir ve durur.
- Cok dilli magazalar icin `STORE_LANGUAGES` kullanin (ornek: `tr,en,de`). Sistem prompt seciminde su an `tr` varsa Turkce, yoksa Ingilizce prompt kullanilir.

## CLI Kullanim

```bash
# Tum urunleri analiz et
python main.py --cli analyze

# Dusuk skorlu urunleri analiz et
python main.py --cli analyze --threshold 60

# CSV'den urun import et
python main.py --cli analyze --source csv --file products.csv

# Tek urun analiz
python main.py --cli analyze --product-id abc123

# Claude ile rewrite uret
python main.py --cli rewrite --dry-run

# Onaylanan degisiklikleri uygula
python main.py --cli apply

# Gecmis raporu goster
python main.py --cli history

# Baglanti testi
python main.py --cli test-connection

# Onerileri CSV olarak disari aktar
python main.py --cli export --output report.csv
```

## Desktop UI

```bash
# UI modunda baslat (varsayilan)
python main.py

# veya acikca belirt
python main.py --ui
```

UI 3 panelden olusur:
- **Sol:** Urun listesi (arama + filtre + skor renk kodlamasi)
- **Orta:** Secili urun detayi + SEO skor karti
- **Sag:** Claude onerisi + diff gorunumu

## SEO Skor Dagilimi

Mevcut skor dagilimi:

- Baslik: 25
- Turkce aciklama: 30
- Ingilizce aciklama: 10
- Meta title: 20
- Meta description: 15
- Keyword uyumu: 10

Toplam skor 100'e cap edilir.

## Testler

```bash
# Testleri calistir
python -m pytest tests/ -v
```

## Proje Yapisi

```
ikas-seo-optimizer/
├── core/                    # Core is mantigi
│   ├── models.py            # Pydantic veri modelleri
│   ├── ikas_client.py       # ikas GraphQL API client
│   ├── csv_handler.py       # CSV import/export
│   ├── seo_analyzer.py      # Kural tabanli SEO skorlama
│   ├── claude_client.py     # Anthropic SDK entegrasyonu
│   └── product_manager.py   # Orkestrator
├── cli/main.py              # CLI arayuzu (typer + rich)
├── ui/                      # Desktop UI (CustomTkinter)
│   ├── app.py               # Ana pencere
│   └── components/          # UI bilesenleri
├── data/                    # Veritabani ve cache
├── config/settings.py       # Uygulama ayarlari
└── tests/                   # Unit testler
```

## Lisans

MIT License - detaylar icin [LICENSE](LICENSE) dosyasina bakin.
