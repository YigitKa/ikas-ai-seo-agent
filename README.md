# ikas AI SEO Agent

**E-ticaret ürün içeriklerini otonom olarak analiz eden, skorlayan ve yeniden yazan AI ajan sistemi — maksimum SEO ve AI keşfedilebilirliği için.**

[ikas](https://ikas.com) mağazaları için geliştirildi. GraphQL API üzerinden bağlanır, her ürünü 100 puanlık bir rubrikle skorlar, ardından otonom bir AI pipeline ile zayıf alanları tespit eder, iteratif olarak yeniden yazar, iyileşmeleri doğrular ve önerileri kaydeder — ürün başına insan müdahalesi gerekmeden.

Full-stack web uygulaması: **React/TypeScript** frontend, **FastAPI** backend, **async SQLite** depolama.

---

## Problem

E-ticarette SEO optimizasyonu tekrarlayan, pahalı ve giderek yetersiz kalıyor. Her ürün için iyi bir başlık, zengin açıklama, doğru meta etiketleri, çok dilli içerik ve — AI arama çağında — ChatGPT, Perplexity ve Google AI Overviews'un alıntılayabileceği yapılandırılmış bilgiler gerekiyor.

Bunu yüzlerce ürün için manuel yapmak pratik değil. Tek bir AI prompt'u ile yapmak ise ölçülebilir kalite kontrolü olmayan, sıradan sonuçlar üretiyor.

## Çözüm

Bu ajan sadece içerik üretmiyor — **düşünüyor, skorluyor, yeniden yazıyor, doğruluyor ve iterasyon yapıyor**. Tıpkı bir insan SEO uzmanının yapacağı gibi, ama tüm kataloğunuz genelinde.

```mermaid
graph TD
    A["🔍 Ürünü skorla<br/><i>100 puanlık rubrik</i>"] --> B["📊 En zayıf alanları tespit et"]
    B --> C["✍️ Alanı SEO best practice'lere göre yeniden yaz"]
    C --> D{"✅ Skor iyileşti mi?"}
    D -->|Evet| E{"Başka zayıf alan var mı?"}
    D -->|Hayır| F["🔄 Farklı strateji dene<br/><i>alan başına maks 2 deneme</i>"]
    F --> D
    E -->|Evet| C
    E -->|Hayır| G["💾 Oneriyi kaydet"]

    style A fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style B fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style C fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style D fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style E fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style F fill:#1e293b,stroke:#ef4444,color:#e2e8f0
    style G fill:#1e293b,stroke:#10b981,color:#e2e8f0
```

<p align="center"><i>Maks 8 otonom iterasyon — her yeniden yazım kabul edilmeden önce doğrulanır</i></p>

Sonuç: ölçülebilir, doğrulanmış SEO iyileştirmeleri — "AI üretimi metin" değil.

---

## Temel Yetenekler

### Otonom SEO Optimizasyonu

AI tek seferlik istek/cevap yapmıyor. **Tool calling** ile otonom olarak skorla → yeniden yaz → doğrula → tekrarla döngüsü çalıştırıyor. Her yeniden yazım, kabul edilmeden önce skorlama rubriğine karşı kontrol ediliyor. İyileşme yoksa ajan farklı bir yaklaşım deniyor — alan başına 2, toplamda 8 iterasyona kadar.

```mermaid
sequenceDiagram
    participant U as Kullanıcı
    participant API as FastAPI
    participant PM as ProductManager
    participant AO as AgentOrchestrator
    participant LLM as AI Provider
    participant T as AgentToolkit

    U->>API: "AI Önerisi Oluştur"
    API->>PM: rewrite_product()
    PM->>AO: run(system_prompt, tools)

    loop Maks 8 İterasyon
        AO->>LLM: Mesaj + Tool tanımları
        LLM-->>AO: tool_call: seo_score_product
        AO->>T: execute("seo_score_product")
        T-->>AO: {score: 42, issues: [...]}
        AO->>LLM: Tool sonucu inject et

        LLM-->>AO: tool_call: validate_rewrite
        AO->>T: execute("validate_rewrite")
        T-->>AO: {old: 42, new: 68, improved: true}
        AO->>LLM: Tool sonucu inject et

        LLM-->>AO: tool_call: save_suggestion
        AO->>T: execute("save_suggestion")
        T-->>AO: {ok: true}
    end

    AO-->>PM: AgentResult
    PM-->>API: Öneri kaydedildi
    API-->>U: SSE stream ile gerçek zamanlı takip
```

### 100 Puanlık SEO Skorlama Motoru

Ahrefs, Semrush, Yoast, Moz ve Screaming Frog'dan ilham alan kural tabanlı rubrik:

```mermaid
pie title SEO Skor Dağılımı (100 Puan)
    "Başlık" : 15
    "Açıklama (TR)" : 20
    "Açıklama (EN)" : 5
    "Meta Başlık" : 15
    "Meta Açıklama" : 10
    "Anahtar Kelime" : 10
    "İçerik Kalitesi" : 10
    "Teknik SEO" : 10
    "Okunabilirlik" : 5
    "AI Alıntılanabilirlik (GEO)" : 10
```

| Kategori | Puan | Kontrol ettikleri |
|---|---|---|
| Başlık | 15 | Uzunluk, büyük harf, güçlü kelimeler, özel karakterler |
| Açıklama (TR) | 20 | Kelime sayısı, paragraf yapısı, HTML öğeleri |
| Açıklama (EN) | 5 | Çeviri kalitesi, min kelime sayısı |
| Meta Başlık | 15 | 50-60 karakter, marka ayırıcı, benzersizlik |
| Meta Açıklama | 10 | 120-160 karakter, CTA varlığı |
| Anahtar Kelime | 10 | Kelime yerleşimi, kategori uyumu, tutarlılık |
| İçerik Kalitesi | 10 | Stuffing tespiti, kelime çeşitliliği, tutarlılık |
| Teknik SEO | 10 | Görseller, etiketler, kategoriler, slug, fiyat |
| Okunabilirlik | 5 | Cümle uzunluğu, varyasyon, geçiş kelimeleri |
| **AI Alıntılanabilirlik (GEO)** | **10** | Yapılandırılmış bilgiler, net özellikler, AI okunabilir format |

Son kategori — **AI Alıntılanabilirlik** — bu projeyi geleceğe taşıyan şey. İçeriğinizin AI arama motorları tarafından ne kadar iyi alıntılanabileceğini skorluyor.

### GEO Site Denetimi

**Herhangi bir web sitesini** Generative Engine Optimization hazırlığı için denetleyen bağımsız tarayıcı:

```mermaid
graph LR
    URL["🌐 Hedef URL"] --> CRAWL["🕷️ Tarama<br/>Homepage + Sitemap"]

    CRAWL --> A1["🤖 AI Görünürlük<br/><i>Alıntılanabilirlik, robots.txt<br/>llms.txt, 14+ AI bot</i>"]
    CRAWL --> A2["📱 Platform Hazırlık<br/><i>ChatGPT / Perplexity<br/>Google AIO</i>"]
    CRAWL --> A3["⚙️ Teknik SEO<br/><i>HTTPS, mobile, CSP<br/>SSR tespiti</i>"]
    CRAWL --> A4["📝 İçerik Kalitesi<br/><i>Okunabilirlik, E-E-A-T<br/>Tazelik</i>"]
    CRAWL --> A5["🏷️ Schema Markup<br/><i>JSON-LD tespiti<br/>tip çeşitliliği</i>"]

    A1 --> SYN["📊 Sentez<br/><i>Ağırlıklı GEO Skoru</i>"]
    A2 --> SYN
    A3 --> SYN
    A4 --> SYN
    A5 --> SYN

    SYN --> REPORT["📋 Aksiyon Planı<br/><i>Öncelikli Markdown rapor</i>"]

    style URL fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style CRAWL fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style A1 fill:#0f172a,stroke:#f59e0b,color:#e2e8f0
    style A2 fill:#0f172a,stroke:#f59e0b,color:#e2e8f0
    style A3 fill:#0f172a,stroke:#f59e0b,color:#e2e8f0
    style A4 fill:#0f172a,stroke:#f59e0b,color:#e2e8f0
    style A5 fill:#0f172a,stroke:#f59e0b,color:#e2e8f0
    style SYN fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style REPORT fill:#1e293b,stroke:#10b981,color:#e2e8f0
```

5 analiz ajanı `asyncio.gather` ile **paralel** çalışır. Sentez ağırlıkları:

| Kategori | Ağırlık |
|---|---|
| AI Alıntılanabilirlik / Görünürlük | %25 |
| Marka Otorite Sinyalleri | %20 |
| İçerik Kalitesi (E-E-A-T) | %20 |
| Teknik Altyapı | %15 |
| Yapılandırılmış Veri | %10 |
| Platform Optimizasyonu | %10 |

### llms.txt Studio

AI arama motorları ve asistanlar için daha okunabilir içerik blokları üretmek üzere `llms.txt` akışı ayrı bir stüdyo ekranında yönetilir. Sistem yeni veya güncellenen ürünleri kuyruklar, özetleri batch halinde üretir ve indirilebilir bir `llms.txt` çıktısına dönüştürür.

<p align="center">
  <img src="./assets/llmstxt.png" alt="llms.txt Studio ekranı" width="1100" />
</p>

<p align="center"><i>Özet kuyrukları, son üretilen bloklar ve indirilebilir `llms.txt` çıktısı tek ekranda yönetilir</i></p>

### Semantik Yönlendirmeli Multi-Agent Chat

Chat paneli tek bir chatbot değil — **üç uzman ajan** ve otomatik yönlendirme:

```mermaid
graph TD
    MSG["💬 Kullanıcı Mesajı"] --> ROUTE{"🧠 Semantik Yönlendirme<br/><i>LLM, temp=0.0, maks 20 token</i>"}

    ROUTE -->|"stok, sipariş, fiyat"| OP["📦 Mağaza Operatörü<br/><i>Canlı mağaza verisi<br/>50+ MCP operasyonu</i>"]
    ROUTE -->|"SEO, başlık, açıklama"| SEO["✍️ SEO Uzmanı<br/><i>Yeniden yazım, skorlama<br/>kaydet / uygula</i>"]
    ROUTE -->|"diğer"| GEN["💡 Genel Asistan<br/><i>Ürün, SEO, envanter<br/>mağaza yönetimi</i>"]

    OP --> TOOLS_OP["🔧 Registry + Toolkit + MCP"]
    SEO --> TOOLS_SEO["🔧 Registry + Toolkit"]
    GEN --> TOOLS_GEN["🔧 Registry + Toolkit"]

    TOOLS_OP --> RESP["📨 Yapısal Butonlu Yanıt"]
    TOOLS_SEO --> RESP
    TOOLS_GEN --> RESP

    style MSG fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style ROUTE fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style OP fill:#0f172a,stroke:#8b5cf6,color:#e2e8f0
    style SEO fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style GEN fill:#0f172a,stroke:#6366f1,color:#e2e8f0
    style TOOLS_OP fill:#1e293b,stroke:#64748b,color:#e2e8f0
    style TOOLS_SEO fill:#1e293b,stroke:#64748b,color:#e2e8f0
    style TOOLS_GEN fill:#1e293b,stroke:#64748b,color:#e2e8f0
    style RESP fill:#1e293b,stroke:#10b981,color:#e2e8f0
```

Her kullanıcı mesajı LLM tarafından semantik olarak sınıflandırılır — etiket veya komut gerekmez. Stok sorguladığınızda Operatör'e, başlık optimize etmek istediğinizde SEO Uzmanı'na yönlendirilirsiniz.

<p align="center">
  <video src="./assets/ikasseo1.mp4" controls muted playsinline width="1100"></video>
</p>

<p align="center"><i>Chat kullanım videosu README önizlemesinde gömülü görünmezse <a href="./assets/ikasseo1.mp4">buradan açabilirsiniz</a></i></p>

### Uygulama Sonrası Doğrulama ve Skor Karşılaştırması

Değişiklikler ikas'a uygulandıktan sonra sistem otomatik olarak:
1. Ürünü ikas'tan tekrar çeker (güncel veriyi doğrular)
2. Lokal ürün verisini ve veritabanını günceller
3. SEO analizini yeniden çalıştırır
4. Eski/yeni skor farkını alan bazlı gösterir (ör: 📈 65/100 → 74/100, +9 puan)

<p align="center">
  <img src="./assets/batch1.png" alt="Karar ve uygulama masası ekranı" width="1100" />
</p>

<p align="center"><i>İnceleme masasında alan bazlı farklar görülür, öneriler tek tek veya toplu olarak onaylanabilir</i></p>

### Yapısal Seçenek Butonları

AI önerileri chat'te **tıklanabilir butonlar** olarak gösterilir — kullanıcının serbest metin yazıp cevap vermesi gerekmez. Typo, belirsizlik ve niyet ayrıştırma ihtiyacını ortadan kaldırır.

```mermaid
graph LR
    AI["🤖 AI Yanıtı"] --> JSON["JSON bloku ekle<br/><code>[{tone, value, action}]</code>"]
    JSON --> FE["⚛️ Frontend parse"]
    FE --> CARDS["🎴 Mesaj içi kartlar"]
    FE --> PANEL["📋 Input üstü<br/>etkileşim paneli"]

    CARDS --> CLICK{"Kullanıcı tıklar"}
    PANEL --> CLICK

    CLICK -->|action var| HIDDEN["[[CHAT_ACTION:x]]<br/>gizli mesaj"]
    CLICK -->|action yok| TEXT["Seçenek metni<br/>olarak gönder"]

    style AI fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style JSON fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style FE fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style CARDS fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style PANEL fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style CLICK fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style HIDDEN fill:#0f172a,stroke:#ef4444,color:#e2e8f0
    style TEXT fill:#0f172a,stroke:#6366f1,color:#e2e8f0
```

`action` anahtarı olan butonlar `[[CHAT_ACTION:action_name]]` gizli mesajı gönderir — serbest metin belirsizliği olmadan deterministik çok adımlı iş akışları (kaydet → incele → uygula) sağlar.

### Provider Agnostik

Tek kod tabanı, **8 AI sağlayıcı**:

```mermaid
graph TD
    APP["🏗️ ikas AI SEO Agent"] --> UNIFIED["🔌 Birleşik AI Arayüzü"]

    UNIFIED --> NATIVE["🎯 Native SDK"]
    UNIFIED --> COMPAT["🔌 OpenAI-Compatible"]
    UNIFIED --> OTHER["⚡ Diğer"]

    NATIVE --> C1["Anthropic Claude<br/><i>Native Messages API<br/>Extended Thinking + Streaming</i>"]
    COMPAT --> C2["OpenAI<br/><i>gpt-4o-mini</i>"]
    COMPAT --> C3["Gemini<br/><i>gemini-1.5-flash</i>"]
    COMPAT --> C4["OpenRouter<br/><i>openai/gpt-4o-mini</i>"]
    COMPAT --> L1["Ollama<br/><i>llama3.2</i>"]
    COMPAT --> L2["LM Studio<br/><i>ilk mevcut model</i>"]

    OTHER --> O1["Custom<br/><i>herhangi bir endpoint</i>"]
    OTHER --> O2["None<br/><i>yalnızca skorlama</i>"]

    style APP fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style UNIFIED fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style NATIVE fill:#0f172a,stroke:#8b5cf6,color:#e2e8f0
    style COMPAT fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style OTHER fill:#0f172a,stroke:#64748b,color:#e2e8f0
    style C1 fill:#1e293b,stroke:#d97706,color:#e2e8f0
    style C2 fill:#1e293b,stroke:#d97706,color:#e2e8f0
    style C3 fill:#1e293b,stroke:#d97706,color:#e2e8f0
    style C4 fill:#1e293b,stroke:#d97706,color:#e2e8f0
    style L1 fill:#1e293b,stroke:#059669,color:#e2e8f0
    style L2 fill:#1e293b,stroke:#059669,color:#e2e8f0
    style O1 fill:#1e293b,stroke:#475569,color:#e2e8f0
    style O2 fill:#1e293b,stroke:#475569,color:#e2e8f0
```

**Anthropic Claude**, native Messages API ile tam entegre: extended thinking (derin akıl yürütme), streaming yanıtlar, istek iptali ve model bazlı maliyet takibi. Diğer sağlayıcılar birleşik OpenAI-compatible arayüz üzerinden tool calling destekler. Bir ortam değişkeni değiştirin — tüm agentic pipeline, chat sistemi ve streaming aynı şekilde çalışır.

### Ürün Başına Chat Geçmişi

Her ürünün sohbet geçmişi tarayıcının `localStorage` alanına ayrı ayrı kaydedilir. Farklı bir ürüne geçip geri döndüğünüzde konuşmadan kaldığınız yerden devam edersiniz. Sayfa yenilemelerinde geçmiş korunur; son 50 mesaj saklanır.

```mermaid
graph LR
    PROD_A["Ürün A"] -->|seç| LOAD_A["localStorage'dan yükle<br/><i>chatHistory.ts</i>"]
    LOAD_A --> CHAT_A["Chat paneliyle devam et"]

    PROD_B["Ürün B"] -->|seç| GUARD{"AI analiz<br/>devam ediyor mu?"}
    GUARD -->|Hayır| LOAD_B["localStorage'dan yükle"]
    GUARD -->|Evet| MODAL["Modal: ne yapmak istersiniz?"]
    MODAL -->|"Durdur ve Geç"| LOAD_B
    MODAL -->|"Analiz Bitince Geç"| WAIT["Analiz tamamlansın<br/>sonra geç"]
    MODAL -->|İptal| STAY["Mevcut üründe kal"]

    style PROD_A fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style PROD_B fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style GUARD fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style MODAL fill:#1e293b,stroke:#ef4444,color:#e2e8f0
    style LOAD_A fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style LOAD_B fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style WAIT fill:#0f172a,stroke:#8b5cf6,color:#e2e8f0
    style STAY fill:#0f172a,stroke:#64748b,color:#e2e8f0
```

Bir AI analizi devam ederken başka bir ürüne tıklanırsa **ürün-geçiş koruma modali** açılır: analizi durdurup geç, bitmesini bekle veya iptal et seçenekleri sunulur.

### Toplu SEO Optimizasyonu

Yüzlerce ürünü tek tıklamayla optimize eden **5 aşamalı batch iş akışı**:

```mermaid
graph LR
    S1["1. 🎯 Seç<br/><i>Skor eşiği, kategori<br/>stok durumu filtresi</i>"] --> S2["2. 🔍 Analiz<br/><i>AI paralel skorlama<br/>ve öneri üretimi</i>"]
    S2 --> S3["3. 📋 İncele<br/><i>Alan bazlı onay/ret<br/>Yeniden üretim</i>"]
    S3 --> S4["4. ⚙️ Uygula<br/><i>Gerçek zamanlı ilerleme<br/>ikas'a yazım</i>"]
    S4 --> S5["5. ✅ Tamamlandı<br/><i>İş geçmişi + geri alma<br/>Skor karşılaştırması</i>"]

    style S1 fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style S2 fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style S3 fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style S4 fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style S5 fill:#1e293b,stroke:#10b981,color:#e2e8f0
```

- **Threshold tabanlı filtreleme** — skor eşiği, kategori ve stok durumuna göre ürün seçimi
- **Toplu onay/ret** — tüm önerileri tek seferde ya da alan bazında onaylayın
- **Alan bazlı yeniden üretim** — beğenmediğiniz tek bir alanı yeniden oluşturun
- **Tam geri alma desteği** — tekil ürün veya tüm batch geri alınabilir

### llms.txt Studio

**Tüm ürün kataloğunu** `ChatGPT`, `Perplexity` ve `Claude` gibi AI motorlarının alıntılayabileceği ansiklopedik özetlere dönüştüren, yönetilen iş kuyruğu. Çıktı, standart `llms.txt` formatında export edilir.

```mermaid
graph LR
    START["▶️ Görevi Başlat"] --> QUEUE["📋 Tüm ürünler\nkuyruğa alındı"]
    QUEUE --> WORKER["🤖 Arka Plan Worker\nSıradaki ürünü al"]
    WORKER --> AI["✍️ AI Özeti Üret\nAnsiklopedik format"]
    AI --> SAVE["💾 Kaydet ve\nilerlemeyi güncelle"]
    SAVE --> MORE{"Kuyruk\nboş mu?"}
    MORE -->|Hayır| WORKER
    MORE -->|Evet| DONE["✅ Tamamlandı\nllms.txt indir"]
    WORKER -->|Kullanıcı| CTRL["⏸️ Duraklat / ⏹️ Durdur"]
    CTRL -->|Devam et| WORKER

    style START fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style QUEUE fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style WORKER fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style AI fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style SAVE fill:#1e293b,stroke:#64748b,color:#e2e8f0
    style MORE fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style DONE fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style CTRL fill:#0f172a,stroke:#ef4444,color:#e2e8f0
```

- **Yönetilen iş kuyruğu** — Start / Pause / Resume / Stop kontrolleriyle çalışan async arka plan worker
- **Gerçek zamanlı sayaçlar** — toplam / işlendi / bekliyor / başarısız canlı takibi; tıklanabilir stat kartları listeyi filtreler
- **Tekil yeniden üretim** — beğenmediğiniz tek bir ürün özetini anında yeniden oluşturma
- **Kesintiden devam** — backend yeniden başlatılsa bile yarıda kalan iş otomatik sürdürülür
- **Tek tıkla indirme** — tüm özetler standart `llms.txt` formatında dışa aktarılır

### Prompts Studio

Sistemdeki **tüm AI prompt şablonlarını** düzenleyip yönetebileceğiniz tam özellikli editör. Hiçbir Python dosyasına dokunmadan, Settings sayfasından canlı olarak her prompt'u güncelleyebilirsiniz.

```mermaid
graph TD
    EDITOR["📝 Prompts Studio"] --> G1["📄 Açıklama Yeniden Yazım\nsystem + user"]
    EDITOR --> G2["🌐 İngilizce Çeviri\nsystem + user"]
    EDITOR --> G3["🤖 GEO Yeniden Yazım\nsystem + user"]
    EDITOR --> G4["📋 llms.txt Özet\nsystem + user"]
    EDITOR --> G5["🎭 Chat Ajanları\nSEO · Operatör · Genel"]
    EDITOR --> G6["💬 Chat Akışı + Bağlam\nrouting · buttons · context"]
    EDITOR --> G7["⚙️ Otonom Ajanlar\nrewrite · batch · GEO"]

    style EDITOR fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style G1 fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style G2 fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style G3 fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style G4 fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style G5 fill:#0f172a,stroke:#8b5cf6,color:#e2e8f0
    style G6 fill:#0f172a,stroke:#8b5cf6,color:#e2e8f0
    style G7 fill:#0f172a,stroke:#f59e0b,color:#e2e8f0
```

- **7 grup, 20+ şablon** — ürün yeniden yazımı, çeviri, GEO, llms.txt özeti, chat ajanı personaları, akış bağlamı ve otonom ajan prompt'ları
- **`{{değişken}}` doğrulama** — tanımsız placeholder kullanımında kayıt öncesi uyarı; her prompt için kullanılabilir değişkenler listelidir
- **Değişiklik takibi** — kaydedilmemiş prompt'lar görsel olarak işaretlenir; tek seferde toplu kayıt
- **Varsayılana sıfırlama** — tekil prompt veya tüm grubu tek tıkla kod içi varsayılana döndürme
- **Anlık arama** — tüm prompt başlık ve içeriklerinde canlı filtreleme
- **Prompt katman görselleştirmesi** — hangi prompt'un hangi pipeline'da nasıl birleştiğini gösteren diyagram; akışı anlamak için Settings sayfasında "Katmanlama" sekmesi

### SEO/GEO Raporlama

Skor geçmişini izleyen ve iyileşmeleri görselleştiren **analitik dashboard**:

- **Trend grafikleri** — 7/30/90/365 günlük dönemlerde mağaza geneli skor eğrisi
- **Alt-skor karşılaştırması** — ilk ve son anlık görüntü arasında 10+ boyutta bar grafiği (başlık, açıklama, meta alanlar, içerik kalitesi, okunabilirlik vb.)
- **En çok gelişenler** — skor artışına göre sıralı ürün listesi
- **Ürün bazlı drilldown** — her ürünün kendi trend grafiği
- **Sorun trendi** — zaman içinde ortalama sorun sayısı takibi
- **Anlık görüntü** — karşılaştırma için mevcut durumu elle kaydedin

### Varsayılan Olarak Güvenli

`DRY_RUN=true` varsayılandır. Siz açıkça izin vermeden ikas mağazanıza hiçbir şey yazılmaz. Her öneri, uygulanmadan önce bir insan onay adımından geçer.

---

## Mimari

```mermaid
graph TB
    subgraph FRONTEND ["⚛️ Frontend"]
        FE["React 19 + TypeScript SPA<br/>TailwindCSS 4 · Vite 7<br/>TanStack Query · WebSocket"]
    end

    subgraph BACKEND ["⚡ Backend"]
        API["FastAPI<br/>REST + WebSocket + SSE<br/>Request-scoped DI"]
    end

    subgraph CORE ["🧠 Core — ProductManager <i>(istek başına yeni instance)</i>"]
        direction TB
        subgraph ROW1 [" "]
            IKAS_C["IkasClient<br/><i>OAuth + GraphQL</i>"]
            SEO_A["SEO Analyzer<br/><i>100 puan rubrik</i>"]
            AI_C["AI Client<br/><i>8 sağlayıcı</i>"]
        end
        subgraph ROW2 [" "]
            AGENT["AgentOrchestrator<br/><i>Tool-calling döngüsü<br/>run() / stream()</i>"]
            CHAT["ChatService<br/><i>Multi-agent + MCP<br/>Semantik yönlendirme</i>"]
        end
        subgraph ROW3 [" "]
            GEO["GeoAuditor<br/><i>Site tarayıcı</i>"]
            MCP["IkasMCPClient<br/><i>JSON-RPC 2.0</i>"]
            PROV["ProviderService<br/><i>Sağlık + modeller</i>"]
        end
    end

    subgraph DATA ["💾 Veri Katmanı"]
        DB["Async SQLite — aiosqlite<br/>ürünler · skorlar · öneriler · loglar"]
    end

    FE <-->|REST + WS| API
    API --> CORE
    CORE --> DATA

    style FRONTEND fill:#0f172a,stroke:#3b82f6,color:#e2e8f0
    style BACKEND fill:#0f172a,stroke:#8b5cf6,color:#e2e8f0
    style CORE fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style DATA fill:#0f172a,stroke:#f59e0b,color:#e2e8f0
    style ROW1 fill:transparent,stroke:transparent
    style ROW2 fill:transparent,stroke:transparent
    style ROW3 fill:transparent,stroke:transparent
```

### Dikkat Çeken Tasarım Kararları

```mermaid
mindmap
  root(("🏗️ Tasarım<br/>Kararları"))
    ("🔒 Request-Scoped DI")
      ("ProductManager istek başına yeni")
      ("Chat state WebSocket başına izole")
      ("Cross-request kontaminasyonu yok")
    ("🔧 3 Katmanlı Tool Çözümleme")
      ("1 — Registry: kaydet/uygula")
      ("2 — Toolkit: SEO skorlama")
      ("3 — MCP: 50+ ikas operasyonu")
    ("🛡️ Çift Yollu Uygulama + Doğrulama")
      ("Birincil: IkasClient OAuth+GraphQL")
      ("Fallback: MCP mutation")
      ("Uygulama sonrası re-fetch + re-score")
    ("📝 Katmanlı Prompt Mimarisi")
      ("5 katman → tek system mesajı")
      ("Compact mode: yerel modeller için sadeleştirme")
    ("🧠 Düşünce Çıkarımı")
      ("think bloğu otomatik ayrıştırma")
      ("UI'da ayrı gösterim")
    ("⚠️ Sahte-Eylem Güvenliği")
      ("Tool çağırmadan uyguladım derse")
      ("Sistem tespit edip uyarı ekler")
```

---

## Chat Mesaj İşleme Akışı

```mermaid
graph TD
    INPUT["💬 Kullanıcı Mesajı"] --> GEN_CHECK{"[[GENERATE_SUGGESTION]]<br/>marker var mı?"}

    GEN_CHECK -->|Evet| GEN_STRIP["Marker'ı sıyır<br/>agent_type → seo"]
    GEN_STRIP --> GEN_BUILD["Minimal prompt oluştur<br/><i>sadece ürün alanları +<br/>save_seo_suggestion tool</i>"]
    GEN_BUILD --> LLM_CALL

    GEN_CHECK -->|Hayır| EXTRACT["1. Direktif çıkarma<br/><i>_extract_message_directives()</i>"]
    EXTRACT --> HISTORY["2. Geçmişe ekle<br/><i>maks 40 mesaj</i>"]
    HISTORY --> SAVE{"3. Kaydetme<br/>niyeti var mı?"}

    SAVE -->|Evet| DRAFT["Pending suggestion çıkar<br/>erken dön"]
    SAVE -->|Hayır| APPLY{"4. Uygulama<br/>niyeti var mı?"}

    APPLY -->|Evet| WRITE["Kaydedilmiş öneriyi uygula<br/>erken dön"]
    APPLY -->|Hayır| PREFETCH["5. MCP data prefetch<br/><i>operator ise snapshot çek</i>"]

    PREFETCH --> BUILD["6. Completion mesajları<br/>+ tool listesi oluştur<br/><i>local model → compact mode</i>"]
    BUILD --> LLM_CALL["7. LLM'e gönder<br/><i>streaming veya blocking</i>"]

    LLM_CALL --> TOOL_LOOP{"Tool call<br/>var mı?"}
    TOOL_LOOP -->|Evet| EXEC["Tool çalıştır<br/><i>maks 5 tur</i>"]
    EXEC --> RESOLVE["Registry → Toolkit → MCP"]
    RESOLVE --> INJECT["Sonucu inject et"]
    INJECT --> TOOL_LOOP

    TOOL_LOOP -->|Hayır| RESPONSE["8. Yanıtı geçmişe ekle"]
    RESPONSE --> RETURN["9. ChatResponse dön<br/><i>+ yapısal butonlar</i>"]

    style INPUT fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style GEN_CHECK fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style GEN_STRIP fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style GEN_BUILD fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style EXTRACT fill:#1e293b,stroke:#64748b,color:#e2e8f0
    style HISTORY fill:#1e293b,stroke:#64748b,color:#e2e8f0
    style SAVE fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style APPLY fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style DRAFT fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style WRITE fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style PREFETCH fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style BUILD fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style LLM_CALL fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style TOOL_LOOP fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style EXEC fill:#0f172a,stroke:#ef4444,color:#e2e8f0
    style RESOLVE fill:#0f172a,stroke:#64748b,color:#e2e8f0
    style INJECT fill:#0f172a,stroke:#64748b,color:#e2e8f0
    style RESPONSE fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style RETURN fill:#1e293b,stroke:#10b981,color:#e2e8f0
```

> **Compact Mode:** LM Studio ve Ollama gibi yerel modeller için sistem prompt'u otomatik olarak sadeleştirilir — verbose örnekler, operasyon rehberi ve routing talimatları kaldırılır. `[[GENERATE_SUGGESTION]]` isteklerinde ise yalnızca ürün alanları ve `save_seo_suggestion` tool'u gönderilir (~500 token vs ~10K).

---

## Tool Çözümleme Hiyerarşisi

```mermaid
graph TD
    CALL["🔧 _execute_chat_tool(name, args)"] --> L1{"1. ToolRegistry<br/><i>Yerel araçlar</i>"}

    L1 -->|Bulundu| R1["save_seo_suggestion<br/><i>session'a kaydet</i>"]
    L1 -->|Bulundu| R2["apply_seo_to_ikas<br/><i>mağazaya yaz</i>"]

    L1 -->|Bulunamadı| L2{"2. AgentToolkit<br/><i>SEO araçları</i>"}

    L2 -->|Bulundu| T1["seo_score_product"]
    L2 -->|Bulundu| T2["validate_rewrite"]
    L2 -->|Bulundu| T3["get_product_details"]
    L2 -->|Bulundu| T4["get_seo_guidelines"]
    L2 -->|Bulundu| T5["search_products"]

    L2 -->|Bulunamadı| L3{"3. MCP<br/><i>Canlı ikas operasyonları</i>"}

    L3 --> M1["listProduct, getProduct<br/>updateProduct, listOrder<br/><i>50+ GraphQL operasyonu</i>"]

    style CALL fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style L1 fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style L2 fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style L3 fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style R1 fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style R2 fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style T1 fill:#0f172a,stroke:#8b5cf6,color:#e2e8f0
    style T2 fill:#0f172a,stroke:#8b5cf6,color:#e2e8f0
    style T3 fill:#0f172a,stroke:#8b5cf6,color:#e2e8f0
    style T4 fill:#0f172a,stroke:#8b5cf6,color:#e2e8f0
    style T5 fill:#0f172a,stroke:#8b5cf6,color:#e2e8f0
    style M1 fill:#0f172a,stroke:#f59e0b,color:#e2e8f0
```

---

## Çift Yollu Uygulama Stratejisi

```mermaid
graph TD
    TRIGGER["apply_seo_to_ikas tetiklendi"] --> TRY["IkasClient ile dene<br/><i>OAuth + GraphQL</i>"]
    TRY --> CHECK{Başarılı mı?}

    CHECK -->|Evet| VERIFY
    CHECK -->|Hayır| INTROSPECT["MCP Fallback:<br/>introspect_operation('updateProduct')"]
    INTROSPECT --> CACHE["GraphQL şema +<br/>input type'lar cache'le"]
    CACHE --> MUTATION["execute_mutation()<br/><i>JSON-RPC execute çağrısı</i>"]
    MUTATION --> VERIFY

    VERIFY["🔍 Doğrulama:<br/>ikas'tan tekrar çek"] --> UPDATE["💾 Lokal veriyi güncelle<br/><i>product + DB</i>"]
    UPDATE --> RESCORE["📊 SEO yeniden skorla"]
    RESCORE --> DELTA["📈 Skor farkını göster<br/><i>eski → yeni + alan bazlı</i>"]

    style TRIGGER fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style TRY fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style CHECK fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style INTROSPECT fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style CACHE fill:#1e293b,stroke:#64748b,color:#e2e8f0
    style MUTATION fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style VERIFY fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style UPDATE fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style RESCORE fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style DELTA fill:#0f172a,stroke:#10b981,color:#e2e8f0
```

---

## Konfigürasyon Çözümleme

```mermaid
graph TD
    REQ["Ayar değeri istendi"] --> L1{"1. .cache/user_settings.json<br/><i>UI'dan kaydedilen overrides</i>"}

    L1 -->|Bulundu| USE1["✅ Bu değeri kullan"]
    L1 -->|Bulunamadı| L2{{"2. .env dosyası<br/><i>İlk kurulum varsayılanları</i>"}}

    L2 -->|Bulundu| USE2["✅ Bu değeri kullan"]
    L2 -->|Bulunamadı| L3{{"3. AppConfig varsayılanları<br/><i>Kod içi sabit değerler</i>"}}

    L3 --> USE3["✅ Varsayılan değeri kullan"]

    style REQ fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style L1 fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style L2 fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style L3 fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style USE1 fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style USE2 fill:#0f172a,stroke:#10b981,color:#e2e8f0
    style USE3 fill:#0f172a,stroke:#10b981,color:#e2e8f0
```

---

## Hızlı Başlangıç

### Gereksinimler
- Python 3.11+
- Node.js 20+

### Kurulum

```bash
git clone https://github.com/YigitKa/ikas-ai-seo-agent.git
cd ikas-ai-seo-agent

# Python
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd web && npm install && cd ..

# Konfigürasyon
cp .env.example .env
# .env dosyasını ikas kimlik bilgileri ve AI provider anahtarıyla düzenleyin
```

### Çalıştırma

```bash
# Geliştirme (önerilen) — backend :8000 + Vite :5173
python main.py dev

# Production — frontend build eder, her şeyi :8000'den sunar
python main.py
```

### Doğrulama

```bash
python -m pytest tests/ -v
```

---

## Konfigürasyon

### Zorunlu

| Değişken | Açıklama |
|---|---|
| `IKAS_STORE_NAME` | ikas mağaza alt alan adı |
| `IKAS_CLIENT_ID` | ikas admin panelinden OAuth2 client ID |
| `IKAS_CLIENT_SECRET` | OAuth2 client secret |
| `AI_PROVIDER` | `anthropic`, `openai`, `gemini`, `openrouter`, `ollama`, `lm-studio`, `custom` veya `none` |
| `AI_API_KEY` | Bulut sağlayıcılar için API anahtarı |

### Opsiyonel

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `AI_MODEL_NAME` | Provider varsayılanı | Model seçimini geçersiz kıl |
| `AI_TEMPERATURE` | `0.7` | Üretim yaratıcılığı |
| `AI_MAX_TOKENS` | `2000` | Maks çıktı token |
| `AI_THINKING_MODE_CHAT` | `false` | Native extended thinking for chat (Anthropic Claude — `temperature=1` zorunlu, budget otomatik ayarlanır) |
| `AI_THINKING_MODE_BATCH` | `false` | Native extended thinking for batch/agentic rewrites (Anthropic Claude — `temperature=1` zorunlu, budget otomatik ayarlanır) |
| `IKAS_MCP_TOKEN` | — | Chat'te canlı mağaza sorgularını etkinleştirir |
| `STORE_LANGUAGES` | `tr,en` | Desteklenen içerik dilleri |
| `SEO_TARGET_KEYWORDS` | — | Virgülle ayrılmış hedef anahtar kelimeler |
| `SEO_LOW_SCORE_THRESHOLD` | `70` | Ürünlerin dikkat gerektirdiği skor eşiği |
| `DRY_RUN` | `true` | ikas'a yazmak için `false` yapın |

---

## Nasıl Çalışır

### Dashboard Akışı

```mermaid
graph LR
    SYNC["1. 🔄 Senkronize Et<br/><i>ikas'tan ürünleri çek</i>"] --> BROWSE["2. 📋 Listele<br/><i>Skor rozetleri ile</i>"]
    BROWSE --> SELECT["3. 🎯 Seç<br/><i>Skor kırılımı + chat</i>"]
    SELECT --> HIST["3b. 📂 Geçmiş Yükle<br/><i>localStorage — ürün başına</i>"]
    HIST --> CHAT["4. 💬 Chat / AI Öner<br/><i>Otonom yeniden yazım</i>"]
    CHAT --> REVIEW["5. 🔍 İncele<br/><i>Önce/sonra diff</i>"]
    REVIEW --> APPLY["6. ✅ Onayla<br/><i>ikas'a uygula</i>"]
    APPLY --> VERIFY["7. 📊 Doğrula<br/><i>Skor karşılaştırması</i>"]

    style SYNC fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style BROWSE fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style SELECT fill:#1e293b,stroke:#6366f1,color:#e2e8f0
    style HIST fill:#1e293b,stroke:#64748b,color:#e2e8f0
    style CHAT fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style REVIEW fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style APPLY fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style VERIFY fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
```

<p align="center">
  <img src="./assets/dashboard.png" alt="ikas AI SEO Agent dashboard ekranı" width="1200" />
</p>

<p align="center"><i>Ürün listesi, SEO/GEO/AEO skorları ve çalışan ajan durumu aynı dashboard üzerinde izlenir</i></p>

### Katmanlı Prompt Mimarisi

Tüm katmanlar **tek bir `system` mesajında** birleştirilir (qwen, llama gibi modellerin jinja template'leri birden fazla system mesajını desteklemez).

```mermaid
graph TB
    subgraph LAYERS ["Prompt Katmanları (tek system mesajında birleştirilir)"]
        P1["1. 📜 Ana Sistem Prompt'u<br/><i>CHAT_FLOW_SYSTEM_PROMPT_TR<br/>Rol, hedefler, doğruluk kuralları, tool rehberi</i>"]
        P2["2. 🎭 Agent Persona<br/><i>AGENT_SYSTEM_PROMPTS_TR[seo|operator|general]<br/>Semantik routing ile seçilir</i>"]
        P3["3. 📋 Operasyon Rehberi<br/><i>IKAS_OPERATION_GUIDE_TR<br/>apply_seo_to_ikas kullanım talimatları</i>"]
        P4["4. 📦 Ürün Bağlamı<br/><i>Seçili ürün adı, skoru, mevcut alanları</i>"]
        P5["5. 🧭 Yönlendirme Talimatı<br/><i>_extract_message_directives() çıktısı</i>"]
    end

    P1 --> P2 --> P3 --> P4 --> P5
    P5 --> MERGE["📨 Tek system mesajı<br/><i>join('\\n\\n')</i>"]

    style LAYERS fill:#0f172a,stroke:#3b82f6,color:#e2e8f0
    style P1 fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style P2 fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style P3 fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style P4 fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style P5 fill:#1e293b,stroke:#ef4444,color:#e2e8f0
    style MERGE fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
```

> **Compact Mode (Yerel Modeller):** LM Studio ve Ollama kullanılırken 3. katman (Operasyon Rehberi), 5. katman (Yönlendirme Talimatı) ve verbose tool talimatları otomatik olarak atlanır. Bunların yerine kısa bir JSON buton formatı talimatı eklenir. Bu sayede ~10K token'lık tam prompt yerine ~2-3K token'lık minimal prompt gönderilir.

<p align="center">
  <img src="./assets/promptsstudio.png" alt="Prompt Studio ekranı" width="900" />
</p>

<p align="center"><i>Prompt Studio ile sistem ve kullanıcı prompt'ları tek yerden düzenlenip katmanlı yapı korunur</i></p>

---

## Teknoloji Yığını

### Backend
- **Python 3.11+** — async-first, `asyncio`
- **FastAPI** — REST API + WebSocket
- **aiosqlite** — async SQLite
- **httpx** — async HTTP (ikas GraphQL + MCP)
- **Pydantic v2** — veri doğrulama ve serileştirme

### Frontend
- **React 19** + **TypeScript 5.9**
- **Vite 7** — dev server + production build
- **TailwindCSS 4** — utility-first stil
- **TanStack Query 5** — sunucu durum yönetimi
- **React Router 7** — istemci tarafı routing
- **react-markdown** — chat mesaj renderlama

### Protokoller
- **OAuth2** — ikas API kimlik doğrulama
- **GraphQL** — ikas ürün CRUD
- **JSON-RPC 2.0** — ikas MCP (Model Context Protocol)
- **OpenAI-compatible** — birleşik AI sağlayıcı arayüzü
- **SSE** — gerçek zamanlı agent progress streaming
- **WebSocket** — çift yönlü chat

---

## Proje Yapısı

```
ikas-ai-seo-agent/
├── main.py                     # Giriş noktası
├── start.py                    # Backend/frontend koordinatörü
│
├── config/settings.py          # 3 katmanlı konfigürasyon çözümleme
│
├── core/                       # İş mantığı — UI bağımlılığı yok
│   ├── models.py               # Pydantic modeller (Product, SeoScore, AgentEvent, vb.)
│   ├── product_manager.py      # Merkezi orkestratör
│   ├── prompt_store.py         # Template yükleme + multi-agent prompt'lar
│   │
│   ├── ai/client.py            # Multi-provider AI soyutlaması (fabrika + adaptörler)
│   ├── agent/orchestrator.py   # Jenerik agent döngüsü (run + stream)
│   ├── agent/tools.py          # Tool tanımları + toolkit fabrikaları
│   │
│   ├── chat/                   # Çok turlu chat (mixin composition)
│   │   ├── state.py            # Konuşma geçmişi + ürün bağlamı
│   │   ├── streaming.py        # SSE streaming + multi-agent routing
│   │   ├── suggestions.py      # Taslak → inceleme → uygulama akışları
│   │   ├── support.py          # ToolRegistry + yardımcılar
│   │   └── guidance.py         # Operasyon önerileri + sahte-eylem güvenliği
│   │
│   ├── seo/analyzer.py         # 100 puanlık skorlama motoru
│   ├── seo/geo_audit.py        # Tam site GEO denetim pipeline'ı
│   │
│   ├── clients/ikas.py         # Async GraphQL istemcisi (OAuth2)
│   ├── clients/mcp.py          # ikas MCP JSON-RPC istemcisi
│   │
│   ├── services/provider.py    # Sağlayıcı sağlık + model keşfi
│   ├── services/settings.py    # Ayar yönetimi
│   └── services/suggestion.py  # Öneri alan operasyonları
│
├── api/                        # FastAPI REST + WebSocket
│   ├── main.py                 # Uygulama kurulumu, CORS, SPA sunumu
│   ├── dependencies.py         # Request-scoped DI
│   └── routers/                # products, seo, suggestions, settings, chat
│
├── web/src/                    # React/TypeScript SPA
│   ├── pages/                  # Dashboard, Settings, LlmsLab, BatchOperations, Reports
│   ├── components/             # ChatPanel, ProductTable, ScoreCard (Quick Wins)
│   │   ├── chat/messages/      # MessageBubble, ToolResultCard (SEO agent + MCP), ThinkingBlock, CostCard
│   │   └── dashboard/          # DashboardHeader (sync butonu), DashboardSidebar (boş arama durumu)
│   ├── shared/
│   │   ├── score/scoreUtils.ts # SCORE_FIELDS, getScoreColor, explainIssue
│   │   └── ui/                 # Toast (bildirim sistemi), ConfirmDialog
│   ├── api/client.ts           # API istemci fonksiyonları
│   └── hooks/
│       ├── useChat.ts          # Chat durum yönetimi
│       └── chat/chatHistory.ts # localStorage chat geçmişi (ürün başına, son 50 mesaj)
│
├── data/
│   ├── db.py                   # Async SQLite şema + yardımcılar
│   └── cache.py                # Dosya tabanlı TTL cache
│
├── prompts/                    # Düzenlenebilir AI prompt şablonları
└── tests/                      # 20+ test dosyası, canlı API çağrısı yok
```

---

## API Yüzeyi

### Ürünler
| Metod | Endpoint | Açıklama |
|---|---|---|
| `GET` | `/api/products` | Cache'deki ürünleri listele (filtrelenebilir) |
| `POST` | `/api/products/fetch` | ikas'tan çek |
| `POST` | `/api/products/sync` | Tam katalog senkronizasyonu |
| `GET` | `/api/products/{id}` | Tekil ürün detayı |

### SEO
| Metod | Endpoint | Açıklama |
|---|---|---|
| `POST` | `/api/seo/analyze` | Tüm ürünleri skorla |
| `POST` | `/api/seo/analyze/{id}` | Tekil ürün skorla |
| `GET` | `/api/seo/generate-llms-txt` | AI tarayıcılar için `llms.txt` üret ve indir |
| `POST` | `/api/seo/geo-audit` | Tam GEO site denetimi |

### llms.txt Studio
| Metod | Endpoint | Açıklama |
|---|---|---|
| `GET` | `/api/llms/status` | İş durumu, sayaçlar, aktif ürün, son özetler |
| `POST` | `/api/llms/start` | Yeni özetleme işi oluştur ve başlat |
| `POST` | `/api/llms/pause` | Aktif işi duraklat (kuyruk konumu korunur) |
| `POST` | `/api/llms/resume` | Duraklatılmış işi kaldığı yerden sürdür |
| `POST` | `/api/llms/stop` | İşi tamamen durdur |
| `GET` | `/api/llms/processed` | İşlenmiş özetleri listele (sayfalandırılmış) |
| `GET` | `/api/llms/pending` | İşlenmemiş ürünleri listele |
| `POST` | `/api/llms/regenerate/{productId}` | Tek ürün özetini yeniden üret |

### Öneriler
| Metod | Endpoint | Açıklama |
|---|---|---|
| `POST` | `/api/suggestions/generate/{id}` | AI önerisi oluştur (agentic) |
| `POST` | `/api/suggestions/generate/{id}/stream` | SSE streaming ile oluştur |
| `PATCH` | `/api/suggestions/{id}/approve` | Öneriyi onayla |
| `POST` | `/api/suggestions/apply` | Onaylananları ikas'a uygula |

### Toplu İşlemler
| Metod | Endpoint | Açıklama |
|---|---|---|
| `GET` | `/api/batch/stats` | Batch dashboard istatistikleri |
| `GET` | `/api/batch/jobs` | Tüm batch işleri listele |
| `POST` | `/api/batch/jobs` | Yeni batch iş oluştur ve analizi başlat |
| `GET` | `/api/batch/jobs/{id}` | Batch iş detayı (öğelerle birlikte) |
| `GET` | `/api/batch/jobs/{id}/stream` | SSE ile gerçek zamanlı ilerleme |
| `POST` | `/api/batch/jobs/{id}/apply` | Onaylı önerileri ikas'a uygula |
| `POST` | `/api/batch/jobs/{id}/stop` | Çalışan işi durdur |
| `DELETE` | `/api/batch/jobs/{id}` | Batch işi sil |
| `POST` | `/api/batch/jobs/{id}/rollback` | Tüm batch'i geri al |
| `POST` | `/api/batch/items/{id}/rollback` | Tekil öğeyi geri al |
| `POST` | `/api/batch/items/{id}/regenerate` | Öğeyi yeniden üret |
| `POST` | `/api/batch/items/{id}/fields/{field}/regenerate` | Tek alanı yeniden üret |
| `PATCH` | `/api/batch/items/{id}` | Öğeyi onayla / reddet |
| `POST` | `/api/batch/items/bulk-decision` | Toplu onayla / reddet |

### Raporlar
| Metod | Endpoint | Açıklama |
|---|---|---|
| `GET` | `/api/reports/store-trends` | Mağaza geneli günlük skor ortalamaları |
| `GET` | `/api/reports/product-trends/{id}` | Ürün bazlı skor geçmişi |
| `GET` | `/api/reports/summary` | İlk / son anlık görüntü karşılaştırması |
| `GET` | `/api/reports/top-improvers` | En çok gelişen ürünler |
| `GET` | `/api/reports/snapshot-dates` | Tüm anlık görüntü tarihleri |
| `GET` | `/api/reports/snapshot/{date}` | Belirli bir tarihin tüm skor verileri |
| `POST` | `/api/reports/take-snapshot` | Anlık görüntü al (idempotent) |

### Gerçek Zamanlı
| Protokol | Endpoint | Açıklama |
|---|---|---|
| WebSocket | `/ws/chat` | Multi-agent AI chat |
| WebSocket | `/ws/progress` | Operasyon ilerleme durumu |

### Ayarlar & Prompts
| Metod | Endpoint | Açıklama |
|---|---|---|
| `GET` | `/api/settings` | Mevcut konfigürasyonu getir |
| `PUT` | `/api/settings` | Ayarları kaydet (`.cache/user_settings.json`'a yazar) |
| `GET` | `/api/settings/prompts` | Tüm prompt şablonlarını grup metadata'sıyla getir |
| `PUT` | `/api/settings/prompts` | Prompt şablonlarını kaydet (diske yazar) |
| `POST` | `/api/settings/prompts/reset` | Seçili veya tüm prompt'ları hardcoded varsayılana sıfırla |
| `GET` | `/api/settings/providers` | AI sağlayıcılarını etiket + model bilgisiyle listele |
| `GET` | `/api/settings/health` | Seçili sağlayıcı sağlık kontrolü |
| `GET` | `/api/settings/models/{provider}` | Sağlayıcıya ait kullanılabilir modelleri getir |
| `POST` | `/api/settings/test-connection` | Sağlayıcı bağlantısını test et |

### MCP
| Metod | Endpoint | Açıklama |
|---|---|---|
| `GET` | `/api/mcp/status` | MCP bağlantı durumu |
| `POST` | `/api/mcp/initialize` | MCP oturumu başlat |
| `POST` | `/api/chat/clear` | Sohbet geçmişini temizle |

---

## Katkıda Bulunma

```bash
# Tüm testler
python -m pytest tests/ -v

# Belirli bir test
python -m pytest tests/test_seo_analyzer.py -v
```

Testler mock ve fixture kullanır — canlı API çağrısı yapılmaz. Örnek ürünler: `tests/fixtures/sample_products.json`.

---

## Anthropic Claude Entegrasyonu

Bu proje **Anthropic Claude** ile en iyi deneyim icin optimize edilmistir. `AI_PROVIDER=anthropic` sectigenizde:

### Native Messages API
Diger saglayicilar OpenAI-compatible endpoint kullanirken, Claude **native Anthropic SDK** (`anthropic` Python paketi) ile entegre olur. Bu sayede:
- **Extended Thinking**: `AI_THINKING_MODE=true` ile Claude'un derin akil yurutme yetenegi aktive olur. Otomatik olarak `temperature=1` ayarlanir ve thinking budget hesaplanir
- **Streaming**: Gercek zamanli yanitlar — hem dusunme bloklari hem metin parcalari anlik iletilir
- **Istek Iptali**: Uzun suren istekler `cancel_active_request()` ile aninda iptal edilebilir
- **Token Takibi**: Her API cagrisi icin input/output token sayimi ve model bazli maliyet tahmini

### Desteklenen Modeller
| Model | Kullanim | Maliyet (1M token) |
|---|---|---|
| `claude-haiku-4-5-20251001` | Varsayilan — hizli ve ekonomik | $0.80 input / $4.0 output |
| `claude-sonnet-4-20250514` | Dengeli performans | $3.0 input / $15.0 output |
| `claude-opus-4-20250514` | Maksimum kalite | $15.0 input / $75.0 output |

### Hizli Baslangic
```bash
# .env dosyaniza ekleyin:
AI_PROVIDER=anthropic
AI_API_KEY=sk-ant-api03-...  # Anthropic Console'dan alin
AI_MODEL_NAME=claude-haiku-4-5-20251001  # Opsiyonel, varsayilan zaten bu
AI_THINKING_MODE_CHAT=false   # Chat icin derin dusunme, true yapin
AI_THINKING_MODE_BATCH=false  # Batch/agentic rewrite icin derin dusunme, true yapin
```

### Agentic Pipeline ile Claude
Claude'un tool calling yetenegi sayesinde **otonom SEO optimizasyonu** calisir:
1. `seo_score_product` — urunu skorlar
2. `validate_rewrite` — yeniden yazimlari dogrular
3. `save_suggestion` — oneriyi kaydeder
4. Maks 8 iterasyon ile iyilestirme dongusu

Chat modunda uc uzman ajan (SEO Uzmani, Magaza Operatoru, Genel Asistan) Claude uzerinden calisir ve semantik yonlendirme ile otomatik secilir.

---

## Lisans

MIT
