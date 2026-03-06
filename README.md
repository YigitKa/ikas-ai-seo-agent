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
