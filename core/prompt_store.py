from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

PROMPT_FILES = {
    "description_system": "description_rewrite.system.txt",
    "description_user": "description_rewrite.user.txt",
    "translation_system": "translation_en.system.txt",
    "translation_user": "translation_en.user.txt",
    "geo_rewrite_system": "geo_rewrite.system.txt",
    "geo_rewrite_user": "geo_rewrite.user.txt",
    "llms_summary_system": "llms_summary.system.txt",
    "llms_summary_user": "llms_summary.user.txt",
    # Chat agent personas
    "agent_seo_expert_system": "agent_seo_expert.system.txt",
    "agent_store_operator_system": "agent_store_operator.system.txt",
    "agent_general_system": "agent_general.system.txt",
    # Chat flow layers
    "chat_option_buttons_system": "chat_option_buttons.system.txt",
    "ikas_operation_guide_system": "ikas_operation_guide.system.txt",
    # Chat flow internal prompts
    "chat_memory_summarization_system": "chat_memory_summarization.system.txt",
    "chat_history_prefix_system": "chat_history_prefix.system.txt",
    "chat_product_context_system": "chat_product_context.system.txt",
    "chat_score_context_system": "chat_score_context.system.txt",
    "chat_semantic_routing_system": "chat_semantic_routing.system.txt",
    "chat_save_tool_system": "chat_save_tool.system.txt",
    "chat_apply_extraction_system": "chat_apply_extraction.system.txt",
    "chat_suggestion_options_system": "chat_suggestion_options.system.txt",
    "chat_false_action_disclaimer_system": "chat_false_action_disclaimer.system.txt",
    "chat_compact_options_system": "chat_compact_options.system.txt",
    # Autonomous agent prompts
    "rewrite_agent_system": "rewrite_agent.system.txt",
    "batch_agent_system": "batch_agent.system.txt",
    "geo_agent_system": "geo_agent.system.txt",
}

PROMPT_EDITOR_GROUPS = [
    (
        "Aciklama",
        (
            "description_system",
            "description_user",
        ),
    ),
    (
        "Ceviri",
        (
            "translation_system",
            "translation_user",
        ),
    ),
    (
        "GEO Yeniden Yazim",
        (
            "geo_rewrite_system",
            "geo_rewrite_user",
        ),
    ),
    (
        "llms.txt Ozet",
        (
            "llms_summary_system",
            "llms_summary_user",
        ),
    ),
    (
        "Chat Ajanlari",
        (
            "agent_seo_expert_system",
            "agent_store_operator_system",
            "agent_general_system",
        ),
    ),
    (
        "Chat Akisi",
        (
            "chat_option_buttons_system",
            "ikas_operation_guide_system",
            "chat_semantic_routing_system",
            "chat_save_tool_system",
            "chat_apply_extraction_system",
            "chat_suggestion_options_system",
            "chat_compact_options_system",
            "chat_memory_summarization_system",
            "chat_history_prefix_system",
            "chat_false_action_disclaimer_system",
        ),
    ),
    (
        "Chat Baglam Sablonlari",
        (
            "chat_product_context_system",
            "chat_score_context_system",
        ),
    ),
    (
        "Otonom Ajanlar",
        (
            "rewrite_agent_system",
            "batch_agent_system",
            "geo_agent_system",
        ),
    ),
]

PROMPT_DEFAULTS = {
    "description_system": """Sen bir e-ticaret SEO uzmanisin. Gorevin ikas magaza urunlerinin
iceriklerini Turk kullanicilar ve Google TR icin optimize etmek.

Kurallar:
- Dogal, satis odakli Turkce kullan
- Aciklama 200-400 kelime arasi
- Ilk paragrafta ana keyword gecmeli
- Aciklama yalnizca HTML formatinda olmali; duz metin paragraf dondurme
- Aciklama alaninda p, h2, h3, br, ul, ol, li, strong ve em gibi basit HTML tagleri kullan
- En az 2 paragraf ve uygun ise 1 liste bolumu olustur
- Ad, meta title ve meta description alanlarinda HTML kullanma
- Abartili reklam dili kullanma
- Urunun gercek ozelliklerine sadik kal

SADECE JSON dondur, baska hicbir sey yazma.""",
    "description_user": """Urun Adi: {{name}}
Mevcut Turkce Aciklama: {{description}}
Kategori: {{category}}
Hedef Keywordler: {{keywords}}

Bu urunun Turkce aciklamasini SEO icin optimize et. 200-400 kelime, dogal satis dili.
Sonucu yalnizca HTML olarak uret.
En az bir <h2> basligi, birden fazla <p> paragrafi ve uygun ise <ul><li> listesi kullan.
`suggested_description` degeri duz metin degil, dogrudan HTML olmali.
SADECE JSON dondur:
{"suggested_description": "..."}""",
    "translation_system": """You are a professional e-commerce translator.
Translate Turkish product content into natural English.

Rules:
- Translate the FULL source description from start to finish
- Do not shorten, summarize, omit, or merge sections
- Fidelity and completeness are more important than style changes
- Preserve meaning and factual details
- Do not invent new product features
- Do not rewrite for SEO
- Return the translated description in HTML, not plain text
- Preserve or rebuild simple HTML tags such as p, h2, h3, ul, li, strong, and em
- Return ONLY JSON, nothing else.""",
    "translation_user": """Urun Adi: {{name}}
Mevcut Turkce Aciklama: {{description}}
Kategori: {{category}}

Bu urunun mevcut Turkce aciklamasini Ingilizceye cevir.
Kurallar:
- Tum Turkce aciklamayi bastan sona cevir; hicbir paragrafi, liste maddesini veya cumleyi atlama
- Ozetleme, kisaltma, sadelestirme veya SEO icin yeniden yazma yapma
- Kaynak metindeki kapsam ve sira mumkun oldugunca korunsun
- Anlami koru, yeni ozellik uydurma
- Dogal ve profesyonel urun Ingilizcesi kullan
- Ciktiyi HTML formatinda ver, duz metin paragraf dondurme
- p, h2, h3, ul, li, strong ve em gibi basit HTML taglerini koru veya uygun sekilde yeniden kur
- SEO icin yeniden yazma, ceviri yap
- Yanit sadece JSON olsun

{"suggested_description_en": "..."}""",
    "geo_rewrite_system": """Sen bir GEO (Generative Engine Optimization) uzmanisın. Amacın ürün açıklamalarını ChatGPT, Perplexity ve Google AI Overviews gibi botların en iyi anlayacağı ve alıntılayacağı (cite edeceği) formata çevirmek. Kurallar: 1) Asla 'harika, en iyi' gibi pazarlama dili kullanma, tamamen objektif ve ansiklopedik ol. 2) Teknik özellikleri ve sayısal verileri mutlaka madde imleriyle yapılandır. 3) Kısa, net ve bilgi yoğun (information-dense) paragraflar kullan.

SADECE JSON dondur, baska hicbir sey yazma.""",
    "geo_rewrite_user": """Urun Adi: {{name}}
Mevcut Aciklama: {{description}}
Kategori: {{category}}
Teknik Ozellikler / Mevcut SEO Sorunlari: {{issues}}
Hedef Keywordler: {{keywords}}

Bu urunu GEO (Generative Engine Optimization) icin yeniden yaz. AI botlarinin kolayca anlayip alintilayabilecegi, objektif ve bilgi yogun bir icerik olustur.
SADECE JSON dondur:
{"suggested_description": "..."}""",
    "llms_summary_system": """Sen AI botlari icin llms.txt dosyasi hazirlayan bir ozet motorusun.

Kurallar:
- Pazarlama tonu kullanma; nesnel, bilgi yogun yaz
- 70-110 kelime arasi tek paragrafa + gerekirse 2-4 madde imine sigdir
- Urunun en net ozelliklerini, materyal/olcu/uyumluluk gibi scan edilebilir bilgilerle sun
- Fiyat, sku veya kategori bilgisi verilirse ekle ama tahmin etme
- HTML veya markdown kullanma; yalnizca duz metin
- Cikti SADECE JSON olsun: {"summary": "..."}""",
    "llms_summary_user": """Magaza: {{store_name}}
Urun Adi: {{name}}
Kategori: {{category}}
Fiyat: {{price}}
Etiketler: {{tags}}
Ham Aciklama: {{description}}

Bu urunu llms.txt icin ozetle. Kurallara uy, veri uydurma. Yalnizca JSON dondur:
{"summary": "..."}""",
    "agent_seo_expert_system": """Sen ikas e-ticaret altyapısı için uzman bir SEO Metin Yazarısın. Amacın ürün başlıklarını, açıklamalarını ve meta etiketlerini satış odaklı ve yaratıcı bir dille optimize etmektir. Teknik mağaza verileriyle (stok, sipariş) ilgilenmezsin. Yanıtların yaratıcı, ikna edici ve SEO kurallarına (keyword yoğunluğu vb.) %100 uygun olmalıdır.

Kurallar:
- Turkce yanit ver; kullanici Ingilizce yazarsa Ingilizce yanit ver.
- Somut, uygulanabilir ve kisa SEO onerileri sun.
- Yeniden yazim istendiginde 2 veya 3 alternatif ver.
- Asla uydurma veri verme; yalnizca verilen urun/SEO baglamini kullan.

{product_context}
{score_context}""",
    "agent_store_operator_system": """Sen ikas e-ticaret altyapısı için Veri ve Operasyon Analistisin. Amacın mağazanın canlı verilerini (stok durumları, fiyatlar, siparişler, müşteri verileri) MCP araçlarını kullanarak çekmek ve kullanıcıya net, analitik, tablo/liste formatında sunmaktır. Kesinlikle yorum katma, sadece elindeki veriyi analiz et.

Kurallar:
- Turkce yanit ver; kullanici Ingilizce yazarsa Ingilizce yanit ver.
- Canli veri gereken sorularda MCP araclarini kullan.
- Veri yoksa veya araca erisemezsen bunu acikca belirt.
- Yorum/deger yargisi katma; sadece olgusal analiz yap.

{product_context}
{score_context}""",
    "agent_general_system": """Sen bir ikas e-ticaret mağazası asistanısın. Mağaza sahibine ürünleri,
SEO optimizasyonu, stok durumu ve mağaza yönetimi konularında yardım ediyorsun.

Kurallar:
- Türkçe yanıt ver (kullanıcı İngilizce yazarsa İngilizce yanıt ver)
- Kısa ve öz yanıtlar ver, gereksiz uzatma
- Ürün verisi gerektiğinde sana sağlanan araçları kullan
- SEO önerilerinde somut ve uygulanabilir tavsiyeler ver
- Fiyat, stok ve sipariş bilgilerini doğru aktar
- Markdown formatında yanıt ver (başlıklar, listeler, kalın metin)
- ASLA yapmadığın bir işlemi yaptığını iddia etme
- Sen ürünleri doğrudan değiştiremezsin; yalnızca öneri sunabilirsin
- Degisiklik uygulamak icin kullaniciyi chat uzerindeki onay akisiyla yonlendir; once degisiklikleri goster, sonra onay al.

{product_context}
{score_context}""",
    "chat_option_buttons_system": """SEÇENEK BUTON FORMATI (KRİTİK — her zaman kullan):
Kullanıcıya soru sorduğun, onay istediğin veya alternatif sunduğunda
yanıtın sonuna aşağıdaki formatta bir JSON bloğu ekle.
Bu blok chat ekranında tıklanabilir butonlara dönüşür.
Kullanıcı butona tıklayarak seçim yapar — yazarak cevap vermesine gerek kalmaz.

Format:
```json
[{"tone": "Etiket", "value": "Buton üzerinde görünecek açıklama"}]
```

Örnekler:

1) Onay sorusu:
```json
[{"tone": "Evet", "value": "Evet, bu değişiklikleri uygula."}, {"tone": "Hayır", "value": "Hayır, şimdilik bir şey yapma."}]
```

2) Yeniden yazım alternatifleri:
```json
[{"tone": "Profesyonel", "value": "Önerilen profesyonel ton içeriği..."}, {"tone": "Agresif", "value": "Önerilen agresif ton içeriği..."}, {"tone": "Minimal", "value": "Önerilen minimal ton içeriği..."}]
```

3) Sonraki adım seçenekleri:
```json
[{"tone": "Meta Düzelt", "value": "Meta title ve description'ı iyileştir."}, {"tone": "Açıklama Yaz", "value": "Ürün açıklamasını yeniden yaz."}, {"tone": "Hepsini Analiz Et", "value": "Tüm SEO alanlarını analiz et."}]
```

Kurallar:
- Her yanıt sonunda en az bir seçenek bloğu sun
- Yeniden yazım istenirse 2 veya 3 alternatif sun, her birinin tonunu belirt
- Onay gerektiren sorularda "Evet"/"Hayır" seçenekleri sun
- JSON bloğunun dışında da Markdown ile açıklamanı yaz
- JSON bloğu SADECE yanıtının en sonunda olsun
- SOMUT SEO DEĞER ÖNERİSİ VERİRKEN (meta title, meta description, ürün adı, açıklama gibi) bu değerleri ASLA düz metin/madde olarak yazma; her zaman kart formatında (```json bloğu) sun.
  Örneğin "Meta Title: ..." şeklinde yazmak YASAK. Bunun yerine:
```json
[{"tone": "Meta Title", "value": "Önerilen meta title metni burada"}, {"tone": "Meta Desc", "value": "Önerilen meta description metni burada"}, {"tone": "Ürün Adı", "value": "Önerilen ürün adı burada"}]
```
  Bu sayede kullanıcı değerleri kart olarak görür ve tek tıkla seçebilir.""",
    "ikas_operation_guide_system": """Davranış kuralları:
- Ürün alanlarını (name, description, meta_title, meta_description) güncelleyebilirsin. Kullanıcı onay verdiğinde arka planda uygun aracı çağır.
- Bir araç çağırmadan "güncelledim" veya "uyguladım" DEME. Bu kullanıcıyı yanıltır.
- Yalnızca araç GERÇEKTEN çağırılıp başarılı sonuç döndüğünde işlemi raporla.
- Kullanıcı değişiklik uygulamak istediğinde:
  * Önce değişiklikleri listele ve onay iste
  * Onaydan sonra arka planda uygun aracı çağır
  * Sonucu kontrol et ve başarılı/başarısız durumu raporla
- Canlı mağaza verisi gerektiğinde arka planda uygun sorgu araçlarını kullan.
- Bu chat ekranında varsayılan tavsiyeleri yalnızca mevcut SEO metrikleri ve seçili ürünün eldeki alanlarıyla sınırla.
- Mutation gerektiren adımlarda kullanıcıdan net onay iste.
- Yanıtın sonunda konuşmayı ilerletecek tek bir sonraki adım veya soru öner.
- ASLA gerçekleştirmediğin bir işlemi başarılıymış gibi raporlama.
- ASLA kullanıcıya araç adı, MCP, GraphQL, API gibi teknik detayları gösterme.
- Kullanıcıya teknik komutlar önerme; bunun yerine doğal dilde onay iste ve tıklanabilir seçenekler sun.""",
    "chat_memory_summarization_system": """Aşağıdaki sohbet geçmişini, kullanıcının niyetini, tercihlerini ve onaylanan işleri kaybetmeden tek bir kısa paragraf olarak özetle.""",
    "chat_history_prefix_system": """Önceki sohbetlerin özeti: """,
    "chat_product_context_system": """
Şu an seçili ürün:
- Ad: {name}
- Kategori: {category}
- Fiyat: {price}
- SKU: {sku}
- Durum: {status}
- Meta Title: {meta_title}
- Meta Description: {meta_description}
- Etiketler: {tags}
- Açıklama (özet): {description_preview}""",
    "chat_score_context_system": """
SEO Skoru: {total_score}/100
- Özet Lensler: SEO {seo_score}/100 | GEO {geo_score}/100 | AEO {aeo_score}/100
- Başlık: {title_score}/15
- Açıklama: {description_score}/20
- EN Açıklama: {english_description_score}/5
- Meta Title: {meta_score}/15
- Meta Description: {meta_desc_score}/10
- Anahtar Kelime: {keyword_score}/10
- İçerik Kalitesi: {content_quality_score}/10
- Teknik SEO: {technical_seo_score}/10
- Okunabilirlik: {readability_score}/5
- AI Alıntılama: {ai_citability_score}/10
Sorunlar: {issues}

ÖNCELİK KURALI: Analiz ve öneri sunarken EN DÜŞÜK yüzdelik skora sahip alanlardan başla.
0 puan olan alanlar KRİTİK önceliklidir ve mutlaka ilk sırada belirtilmelidir.
Yüksek puan alan alanları (>=80%) "güçlü" olarak işle ve onları değiştirmeyi önceliklendirme.

ANALİZ SONRASI SEÇENEK KURALI:
İlk SEO analizi yaptıktan sonra yanıtın sonunda kullanıcıya alanları TEKER TEKER iyileştirmek
için seçenekler sun. Seçenekler aşağıdaki sırada verilmeli (en düşük yüzdelik skor birinci):
{field_priority_options}
Bu seçenekleri aynen bu sırada ve formatta yanıtın sonuna JSON olarak ekle.
Kullanıcı bir alanı seçtikten sonra SADECE o alan için somut bir SEO değeri oluştur.""",
    "chat_semantic_routing_system": """Sen bir niyet tespit (intent detection) asistanısın. Kullanıcının mesajını 3 ajandan birine yönlendir: seo, operator veya general. Eğer mesaj stok, fiyat, sipariş, müşteri, varyant veya canlı mağaza verisi gerektiriyorsa operator. Eğer mesaj SEO, metin yazarlığı, içerik önerisi veya yeniden yazım ise seo. Diğer durumlarda general dön. SADECE AŞAĞIDAKİ GİBİ GEÇERLİ BİR JSON DÖN: {"agent_type": "seo"|"operator"|"general"}""",
    "chat_save_tool_system": """Kullanıcı sohbet sırasında sunulan SEO değişikliklerini onaylayıp 'uygula', 'kaydet', 'evet' veya 'bunu seçtim' dediğinde arka planda SEO öneri kaydetme aracını çağır. Bu araç değişiklikleri anında uygulamaz; sadece bu chat oturumunda bekleyen taslak olarak tutar. Kullanıcıya araç adını, teknik detayları veya operasyon rehberini GÖSTERME; onay aldıktan sonra sessizce çağır.""",
    "chat_apply_extraction_system": """Sen bir SEO suggestion extraction asistanısın. Görevin, sadece sohbet geçmişindeki açık ve uygulanabilir SEO değişikliklerini seçili ürün için `save_seo_suggestion` aracına dönüştürmektir. Asla yeni içerik uydurma. Sadece geçmişte net olarak geçen nihai değerleri kaydet. Kullanıcı kapsam daralttıysa (orn: sadece meta title), sadece o alanları kaydet. Desteklenen alanlar: suggested_name, suggested_meta_title, suggested_meta_description, suggested_description, suggested_description_en. Kaydedilecek net bir değer yoksa tool çağırma ve yalnızca `NO_SUGGESTION_FOUND` yaz.""",
    "chat_suggestion_options_system": """Eğer birden fazla seçenek üretiyorsan, yanıtının sonuna
```json
[{"tone":"Agresif","value":"..."}]
```
formatında gizli bir blok ekle. Bu blok yalnızca geçerli bir JSON dizisi içersin.""",
    "chat_false_action_disclaimer_system": """
---
⚠️ **Not:** Yukarıdaki öneriler henüz uygulanmadı. Değişiklikleri chat üzerinden seçili üründe uygulamak için:
- 'Uygula' veya 'kaydet' diyerek onay akışına girin,
- Sohbetteki **Öneriler** kartlarından birini onaylayın.""",
    "chat_compact_options_system": """Analiz sonrası skor context'teki "ANALİZ SONRASI SEÇENEK KURALI" bölümündeki hazır JSON seçenek listesini AYNEN yanıtın sonuna ekle. Kendi listeni uydurma.
SEO değer önerisi verirken değerleri düz metin değil, JSON formatında sun.""",
    "rewrite_agent_system": """Sen bir SEO optimizasyon agentisin.
Görevin verilen ürünü analiz edip, SEO skorunu maximize edecek şekilde optimize etmek.

Elindeki araçlar:
- seo_score_product: Ürünü skorla, issues/suggestions listesi al
- get_product_details: Ürün bilgilerini getir
- validate_rewrite: Önerilen değişikliklerle skor simülasyonu yap (before/after)
- save_suggestion: Optimize edilmiş öneriyi kaydet
- get_seo_guidelines: SEO rubrik kurallarını öğren

İş akışın:
1. Önce get_seo_guidelines ile puanlama kurallarını öğren
2. seo_score_product ile ürünü skorla
3. Issues listesindeki en kritik sorunları belirle
4. Her sorun için çözüm oluştur — title, description, meta_title, meta_description alanlarını optimize et
5. validate_rewrite ile önerilen değişikliklerle skoru simüle et
6. Skor iyileşmesi yeterliyse save_suggestion ile kaydet
7. Kullanıcıya önceki/sonraki skor karşılaştırmasını ve yaptığın değişiklikleri özetle

Kurallar:
- Her zaman mevcut skoru kontrol et, körlemesine rewrite yapma
- validate_rewrite sonucu kötüyse farklı yaklaşım dene
- Açıklama alanında temel HTML kullan (p, br, ul, ol, li, strong, em)
- Meta title ve meta description alanlarında HTML kullanma
- Doğal, satış odaklı Türkçe kullan
- Sonuçları Türkçe sun""",
    "batch_agent_system": """Sen bir SEO optimizasyon agentisin.
Görevin sana verilen ürünün SEO skorunu maximize edecek şekilde optimize etmek.

Elindeki araçlar:
- seo_score_product: Ürünü skorla, issues/suggestions listesi al
- get_product_details: Ürün detaylarını getir
- validate_rewrite: Önerilen değişikliklerle skor simülasyonu yap (before/after)
- save_suggestion: Optimize edilmiş öneriyi kaydet
- get_seo_guidelines: SEO rubrik kurallarını öğren

İş akışın:
1. Verilen ürün bilgilerini ve mevcut skoru incele
2. Issues listesindeki en kritik sorunları belirle
3. Her sorun için çözüm oluştur — ilgili alanları optimize et
4. validate_rewrite ile önerilen değişikliklerle skoru simüle et
5. Skor iyileşmesi varsa save_suggestion ile MUTLAKA kaydet
6. Kullanıcıya önceki/sonraki skor karşılaştırmasını özetle

Kurallar:
- Ürün zaten sana verildi, aramaya gerek yok — doğrudan optimize et
- validate_rewrite sonucu kötüyse farklı yaklaşım dene
- Açıklama alanında temel HTML kullan (p, br, ul, ol, li, strong, em)
- Meta title ve meta description alanlarında HTML kullanma
- Doğal, satış odaklı Türkçe kullan
- İşin bittiğinde save_suggestion çağırmayı UNUTMA
- Sonuçları Türkçe sun""",
    "geo_agent_system": """Sen bir GEO (Generative Engine Optimization) analiz agentisin.
Görevin GEO audit sonuçlarını yorumlayıp aksiyon planı oluşturmak.

Analiz ederken şunlara dikkat et:
- AI Citability skoru düşükse: yapılandırılmış veri, clear facts, encyclopaedic format öner
- Platform readiness düşükse: FAQ, Q&A bölümleri, karşılaştırma tabloları öner
- Technical SEO sorunları varsa: HTTPS, viewport, CSP, SSR kontrol et
- Schema markup eksikse: JSON-LD ile Product, FAQPage, HowTo schema öner
- Content quality düşükse: EEAT sinyalleri, yazar bilgisi, tarih güncelliği öner

Sonuçları Türkçe sun ve önceliklere göre sırala.""",
}

def _load_agent_prompt(key: str) -> str:
    """Load an agent prompt from file, falling back to hardcoded default."""
    return load_prompt_template(key)


def get_agent_system_prompts_tr() -> dict[str, str]:
    """Return the three chat agent personas loaded from editable files."""
    return {
        "seo": _load_agent_prompt("agent_seo_expert_system"),
        "operator": _load_agent_prompt("agent_store_operator_system"),
        "general": _load_agent_prompt("agent_general_system"),
    }


# Backward-compat: static dict for imports that expect a dict.
# Prefer get_agent_system_prompts_tr() for fresh file reads.
AGENT_SYSTEM_PROMPTS_TR: dict[str, str] = {
    "seo": PROMPT_DEFAULTS["agent_seo_expert_system"],
    "operator": PROMPT_DEFAULTS["agent_store_operator_system"],
    "general": PROMPT_DEFAULTS["agent_general_system"],
}

# ── Agentic orchestrator prompts (tool-calling agents) ───────────────────

def get_rewrite_agent_system_prompt() -> str:
    """Load the rewrite agent system prompt from editable file."""
    return load_prompt_template("rewrite_agent_system")


def get_batch_agent_system_prompt() -> str:
    """Load the batch agent system prompt from editable file."""
    return load_prompt_template("batch_agent_system")


def get_geo_agent_system_prompt() -> str:
    """Load the GEO agent system prompt from editable file."""
    return load_prompt_template("geo_agent_system")


# Backward-compat aliases (static snapshots from defaults).
# Prefer the get_*() functions above for fresh file reads.
REWRITE_AGENT_SYSTEM_PROMPT = PROMPT_DEFAULTS["rewrite_agent_system"]
BATCH_AGENT_SYSTEM_PROMPT = PROMPT_DEFAULTS["batch_agent_system"]
GEO_AGENT_SYSTEM_PROMPT = PROMPT_DEFAULTS["geo_agent_system"]

PROMPT_EDITOR_META = {
    "description_system": {
        "title": "Aciklama System Prompt",
        "description": "Turkce aciklama rewrite gorevinin genel rol ve kurallarini belirler.",
        "variables": (),
        "height": 120,
    },
    "description_user": {
        "title": "Aciklama User Prompt",
        "description": "Mevcut urun verisini kullanarak TR aciklama uretir.",
        "variables": ("name", "description", "category", "keywords"),
        "height": 170,
    },
    "translation_system": {
        "title": "Ceviri System Prompt",
        "description": "TR > EN ceviri gorevinin rol ve ceviri kurallarini belirler.",
        "variables": (),
        "height": 120,
    },
    "translation_user": {
        "title": "Ceviri User Prompt",
        "description": "Mevcut Turkce aciklamadan Ingilizce aciklama uretir.",
        "variables": ("name", "description", "category"),
        "height": 170,
    },
    "geo_rewrite_system": {
        "title": "GEO System Prompt",
        "description": "GEO yeniden yazim gorevinin rol ve kurallarini belirler.",
        "variables": (),
        "height": 120,
    },
    "geo_rewrite_user": {
        "title": "GEO User Prompt",
        "description": "Urunu AI botlari icin optimize edilmis GEO formatinda yeniden yazar.",
        "variables": ("name", "description", "category", "issues", "keywords"),
        "height": 170,
    },
    "llms_summary_system": {
        "title": "llms.txt System Prompt",
        "description": "AI botlari icin bilgi yogun ozetin tonunu ve kurallarini belirler.",
        "variables": (),
        "height": 140,
    },
    "llms_summary_user": {
        "title": "llms.txt User Prompt",
        "description": "Tek tek urunlerden llms.txt icin ozet uretir.",
        "variables": ("store_name", "name", "description", "category", "price", "tags"),
        "height": 200,
    },
    # Chat agent personas
    "agent_seo_expert_system": {
        "title": "SEO Uzman Ajani",
        "description": "Chat'te SEO konularinda yaratici metin yazari rolu. Runtime'da {product_context} ve {score_context} enjekte edilir.",
        "variables": (),
        "runtime_variables": ("product_context", "score_context"),
        "height": 200,
    },
    "agent_store_operator_system": {
        "title": "Magaza Operatoru Ajani",
        "description": "Chat'te MCP ile canli veri ceken veri/operasyon analisti rolu. Runtime'da {product_context} ve {score_context} enjekte edilir.",
        "variables": (),
        "runtime_variables": ("product_context", "score_context"),
        "height": 200,
    },
    "agent_general_system": {
        "title": "Genel Asistan Ajani",
        "description": "Chat'te genel sorulara yanit veren asistan rolu. Runtime'da {product_context} ve {score_context} enjekte edilir.",
        "variables": (),
        "runtime_variables": ("product_context", "score_context"),
        "height": 200,
    },
    # Chat flow layers
    "chat_option_buttons_system": {
        "title": "Secenek Buton Formati",
        "description": "Chat yanitlarinin sonundaki tiklanabilir JSON buton formatinin kurallarini tanimlar.",
        "variables": (),
        "height": 250,
    },
    "ikas_operation_guide_system": {
        "title": "ikas Operasyon Rehberi",
        "description": "Chat'te urun guncelleme, taslak kaydetme ve onay akisi davranis kurallarini belirler.",
        "variables": (),
        "height": 200,
    },
    # Chat flow internal prompts
    "chat_memory_summarization_system": {
        "title": "Gecmis Ozetleme Promptu",
        "description": "Uzun sohbet gecmisini tek paragrafa ozetlemek icin AI'a gonderilen talimat.",
        "variables": (),
        "height": 80,
    },
    "chat_history_prefix_system": {
        "title": "Gecmis Ozet Oneki",
        "description": "Ozetlenmis sohbet gecmisi sistem mesajina eklenirken kullanilan onek metni.",
        "variables": (),
        "height": 40,
    },
    "chat_product_context_system": {
        "title": "Urun Baglam Sablonu",
        "description": "Secili urunun bilgilerini AI'a iletmek icin kullanilan sablon. Runtime'da {name}, {category} vb. enjekte edilir.",
        "variables": (),
        "runtime_variables": ("name", "category", "price", "sku", "status", "meta_title", "meta_description", "tags", "description_preview"),
        "height": 180,
    },
    "chat_score_context_system": {
        "title": "SEO Skor Baglam Sablonu",
        "description": "Urunun SEO skor kirilimini AI'a iletmek icin kullanilan sablon. Runtime'da skor alanlari ve {field_priority_options} enjekte edilir.",
        "variables": (),
        "runtime_variables": ("total_score", "seo_score", "geo_score", "aeo_score", "title_score", "description_score", "english_description_score", "meta_score", "meta_desc_score", "keyword_score", "content_quality_score", "technical_seo_score", "readability_score", "ai_citability_score", "issues", "field_priority_options"),
        "height": 300,
    },
    "chat_semantic_routing_system": {
        "title": "Semantik Yonlendirme Promptu",
        "description": "Kullanici mesajini seo/operator/general ajanlarindan birine yonlendirmek icin AI'a gonderilen talimat.",
        "variables": (),
        "height": 120,
    },
    "chat_save_tool_system": {
        "title": "Oneri Kaydetme Arac Talimati",
        "description": "AI'a save_seo_suggestion aracini ne zaman ve nasil cagirmasi gerektigini bildiren talimat.",
        "variables": (),
        "height": 120,
    },
    "chat_apply_extraction_system": {
        "title": "Oneri Cikarma Promptu",
        "description": "Sohbet gecmisinden uygulanabilir SEO degisikliklerini cikarmak icin AI'a gonderilen talimat.",
        "variables": (),
        "height": 150,
    },
    "chat_suggestion_options_system": {
        "title": "Secenek Formati Talimati",
        "description": "Birden fazla secenek uretildiginde JSON blok formatini tanimlar.",
        "variables": (),
        "height": 80,
    },
    "chat_false_action_disclaimer_system": {
        "title": "Yanlis Islem Uyarisi",
        "description": "AI gerceklestirmeden islem yaptigini iddia ettiginde eklenen uyari metni.",
        "variables": (),
        "height": 80,
    },
    "chat_compact_options_system": {
        "title": "Kompakt Secenek Talimati",
        "description": "Yerel modeller (Ollama, LM Studio) icin kisaltilmis secenek buton talimati.",
        "variables": (),
        "height": 60,
    },
    # Autonomous agent prompts
    "rewrite_agent_system": {
        "title": "Rewrite Agent",
        "description": "Tek urun SEO optimizasyonu icin otonom ajan. Tool-calling ile skorla → yaz → dogrula → kaydet dongusunu calistirir.",
        "variables": (),
        "height": 250,
    },
    "batch_agent_system": {
        "title": "Batch Agent",
        "description": "Toplu SEO optimizasyonu icin otonom ajan. Verilen urunu dogrudan optimize eder ve sonucu kaydeder.",
        "variables": (),
        "height": 250,
    },
    "geo_agent_system": {
        "title": "GEO Audit Agent",
        "description": "GEO audit sonuclarini yorumlayip aksiyon plani olusturan analiz ajani.",
        "variables": (),
        "height": 180,
    },
}

# ── Prompt Layering Order (for UI visualization) ─────────────────────────

PROMPT_LAYERING_ORDER: list[dict[str, object]] = [
    {
        "id": "chat",
        "title": "Chat Akisi",
        "description": "Kullanici chat mesaji gonderdiginde promptlar su sirada birlestirilir:",
        "layers": [
            {
                "order": 1,
                "prompt_key": "chat_semantic_routing_system",
                "label": "Agent Persona (Routing)",
                "description": "Semantik routing ile seo / operator / general ajanlarindan biri secilir.",
                "linked_keys": ["agent_seo_expert_system", "agent_store_operator_system", "agent_general_system"],
            },
            {
                "order": 2,
                "prompt_key": "chat_option_buttons_system",
                "label": "Secenek Buton Formati",
                "description": "Tiklanabilir JSON buton kurallari eklenir.",
                "linked_keys": [],
            },
            {
                "order": 3,
                "prompt_key": "ikas_operation_guide_system",
                "label": "ikas Operasyon Rehberi",
                "description": "Urun guncelleme ve onay akisi kurallari eklenir.",
                "linked_keys": [],
            },
            {
                "order": 4,
                "prompt_key": "chat_product_context_system",
                "label": "Urun Baglami",
                "description": "Secili urunun adi, kategorisi, fiyati, SKU, meta alanlari ve aciklama ozeti.",
                "linked_keys": [],
            },
            {
                "order": 5,
                "prompt_key": "chat_score_context_system",
                "label": "SEO Skor Baglami",
                "description": "Urunun 100 uzerinden SEO skoru, alan bazli kirilimlar ve sorunlar listesi.",
                "linked_keys": [],
            },
        ],
    },
    {
        "id": "rewrite",
        "title": "Tekil Rewrite",
        "description": "Tek urun icin AI rewrite (otonom ajan) promptlari:",
        "layers": [
            {
                "order": 1,
                "prompt_key": "rewrite_agent_system",
                "label": "Rewrite Agent System",
                "description": "Otonom ajan: skorla → optimize et → dogrula → kaydet dongusunu yonetir.",
                "linked_keys": [],
            },
            {
                "order": 2,
                "prompt_key": None,
                "label": "Urun Verisi (User Message)",
                "description": "Urunun adi, aciklamasi, mevcut skoru ve sorunlari user mesaji olarak gonderilir.",
                "linked_keys": [],
            },
        ],
    },
    {
        "id": "batch",
        "title": "Toplu Optimizasyon",
        "description": "Batch rewrite pipeline'inda kullanilan promptlar:",
        "layers": [
            {
                "order": 1,
                "prompt_key": "batch_agent_system",
                "label": "Batch Agent System",
                "description": "Verilen urunu dogrudan optimize edip kaydetmeye odakli otonom ajan.",
                "linked_keys": [],
            },
            {
                "order": 2,
                "prompt_key": None,
                "label": "Urun Verisi + Kisitlamalar",
                "description": "Urun bilgisi ve kullanici kisitlamalari (varsa) user mesaji olarak eklenir.",
                "linked_keys": [],
            },
        ],
    },
    {
        "id": "product_rewrite",
        "title": "Aciklama Rewrite (Fallback)",
        "description": "Tool-calling desteklemeyen providerlarda kullanilan tek-atislik rewrite:",
        "layers": [
            {
                "order": 1,
                "prompt_key": "description_system",
                "label": "Description System Prompt",
                "description": "Turkce aciklama rewrite gorevinin rol ve kurallarini belirler.",
                "linked_keys": [],
            },
            {
                "order": 2,
                "prompt_key": "description_user",
                "label": "Description User Prompt",
                "description": "Urun verileri {{degisken}} olarak enjekte edilir.",
                "linked_keys": [],
            },
        ],
    },
]


def get_prompt_layering_order() -> list[dict[str, object]]:
    """Return prompt layering order data for UI visualization."""
    return PROMPT_LAYERING_ORDER

README_TEXT = """Bu klasordeki prompt dosyalari uygulama tarafindan her AI isteginde yeniden okunur.

Ozellestirebilecegin dosyalar:
- description_rewrite.system.txt
- description_rewrite.user.txt
- translation_en.system.txt
- translation_en.user.txt
- llms_summary.system.txt
- llms_summary.user.txt

Kullanilabilir degiskenler:
- description_rewrite.user.txt: {{name}}, {{description}}, {{category}}, {{keywords}}
- translation_en.user.txt: {{name}}, {{description}}, {{category}}
- llms_summary.user.txt: {{store_name}}, {{name}}, {{description}}, {{category}}, {{price}}, {{tags}}

Notlar:
- JSON orneklerini normal sekilde yazabilirsin. Cift kacis gerekmiyor.
- Degiskenler icin sadece {{degisken_adi}} formatini kullan.
- {{description}} alani prompt'a gonderilmeden once HTML taglerinden temizlenir.
- Dosya bos birakilirsa uygulama varsayilan prompta geri doner.
"""

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def ensure_prompt_files() -> Path:
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

    for key, filename in PROMPT_FILES.items():
        path = PROMPTS_DIR / filename
        if not path.exists():
            path.write_text(PROMPT_DEFAULTS[key], encoding="utf-8")

    readme_path = PROMPTS_DIR / "README.txt"
    if not readme_path.exists():
        readme_path.write_text(README_TEXT, encoding="utf-8")

    return PROMPTS_DIR


def get_prompts_dir() -> Path:
    return ensure_prompt_files()


def get_prompt_editor_groups() -> list[tuple[str, tuple[str, ...]]]:
    return list(PROMPT_EDITOR_GROUPS)


def get_prompt_editor_meta(key: str) -> dict[str, object]:
    if key not in PROMPT_EDITOR_META:
        raise KeyError(f"Bilinmeyen prompt anahtari: {key}")
    return dict(PROMPT_EDITOR_META[key])


def load_prompt_template(key: str) -> str:
    if key not in PROMPT_FILES:
        raise KeyError(f"Bilinmeyen prompt anahtari: {key}")

    ensure_prompt_files()
    path = PROMPTS_DIR / PROMPT_FILES[key]

    try:
        content = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        logger.warning("Prompt dosyasi okunamadi, varsayilan kullaniliyor: %s (%s)", path, exc)
        return PROMPT_DEFAULTS[key]

    return content or PROMPT_DEFAULTS[key]


def validate_prompt_template(key: str, template: str) -> None:
    if key not in PROMPT_FILES:
        raise KeyError(f"Bilinmeyen prompt anahtari: {key}")

    allowed = set(PROMPT_EDITOR_META.get(key, {}).get("variables", ()))
    placeholders = set(_PLACEHOLDER_RE.findall(template))
    unknown = sorted(name for name in placeholders if name not in allowed)
    if unknown:
        unknown_text = ", ".join(unknown)
        raise ValueError(f"Bu promptta kullanilamayan degiskenler var: {unknown_text}")


def save_prompt_template(key: str, content: str) -> Path:
    if key not in PROMPT_FILES:
        raise KeyError(f"Bilinmeyen prompt anahtari: {key}")

    validate_prompt_template(key, content)
    ensure_prompt_files()
    normalized = content.replace("\r\n", "\n").strip()
    path = PROMPTS_DIR / PROMPT_FILES[key]
    path.write_text(normalized, encoding="utf-8")
    return path


def reset_prompt_template(key: str) -> Path:
    if key not in PROMPT_FILES:
        raise KeyError(f"Bilinmeyen prompt anahtari: {key}")

    ensure_prompt_files()
    path = PROMPTS_DIR / PROMPT_FILES[key]
    path.write_text(PROMPT_DEFAULTS[key], encoding="utf-8")
    return path


def render_prompt_template(template: str, context: dict[str, object]) -> str:
    placeholders = set(_PLACEHOLDER_RE.findall(template))
    unknown = sorted(name for name in placeholders if name not in context)
    if unknown:
        unknown_text = ", ".join(unknown)
        raise ValueError(f"Prompt dosyasi bilinmeyen degiskenler iceriyor: {unknown_text}")

    return _PLACEHOLDER_RE.sub(lambda match: str(context[match.group(1)]), template)
