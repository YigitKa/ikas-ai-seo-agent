# Claude-Code Esinli Teknik Backlog

Bu dosya, `claude-code` içinden `ikas-ai-seo-agent` projesine uyarlanması önerilen işleri görev ve todo listesi halinde toplar.

## Must

### 1. Tool Runtime v2
- [x] Ortak bir `ToolDefinition` modeli tasarla
- [x] Tool alanlarına `name`, `description`, `input_schema`, `risk_level`, `read_only`, `destructive`, `concurrency_safe`, `ui_meta` ekle
- [x] Mevcut local chat tool'larını yeni kontrata taşı
- [x] `core/agent/tools.py` içindeki tool factory yapısını yeni modele göre sadeleştir
- [x] Tool sonuçları için ortak response formatı belirle
- [x] Tool hata formatını tekilleştir
- [x] Tool kayıt/registry katmanı oluştur
- [x] Tool görünürlüğü ve hangi ajanların hangi tool'ları kullanabileceği için allowlist ekle
- [x] Mevcut SEO/chat tool'ları için regresyon testleri yaz
- [x] Chat/UI tüketicileri için ortak tool result envelope unwrap katmanı ekle

### 2. Permission ve Approval Engine
- [x] `core/permissions/` altında merkezi izin katmanı oluştur
- [x] `allow`, `ask`, `deny` davranışlarını destekleyen kural modeli tasarla
- [x] Riskli işlemleri sınıflandır: `apply`, `rollback`, `bulk apply`, `db reset`, `external write`
- [x] `apply_seo_to_ikas` akışını permission engine üzerinden geçir
- [x] Batch apply akışlarını permission engine üzerinden geçir
- [x] Onay gerektiren işlemler için tek tip audit kaydı üret
- [x] İzin kararını tool çağrısından önce zorunlu kontrol et
- [x] Kural çözümleme sırasını tanımla: global > project > session > runtime override
- [x] İzin sistemi için birim testleri ve entegrasyon testleri ekle
- [x] `suggestions/apply` ve tekil chat apply akışlarını aynı permission guard katmanına bağla
- [x] `rollback` akışlarını permission engine üzerinden geçir
- [x] `products/reset` (db reset) akışına explicit approval override ekle

### 3. Unified Task System
- [x] Genel amaçlı `tasks` tablosu tasarla
- [x] Task alanlarına `type`, `status`, `progress`, `payload`, `result`, `error`, `started_at`, `finished_at` ekle
- [ ] `llms` işçisini unified task modeline tam taşı ve legacy `llms_jobs` durum alanını compatibility layer seviyesine indir
- [ ] `batch` işlerini unified task modeline tam taşı ve retry semantics'ini item-level idempotent hale getir
- [x] Ortak `cancel`, `retry`, `resume`, `stop`, `get status` servislerini ekle
- [x] Task çıktılarını sonradan okunabilir biçimde sakla
- [x] Uzun süren işlerde heartbeat veya progress update standardı ekle
- [x] API tarafında ortak task endpoint'leri oluştur
- [x] Frontend tarafında ortak task durumu bileşeni oluştur
- [x] Task sistemi için migration ve testler yaz
- [x] Readme dosyasını güncelle

### 4. Skill System
#### Temel Sözleşme
- [x] Diskten yüklenen skill yapısı için klasör standardını belirle: `skills/<skill-slug>/`
- [x] Skill dosya sözleşmesini tanımla: `SKILL.md`, `meta.json` veya frontmatter, opsiyonel `prompts/`, `assets/`, `examples/`
- [x] Skill metadata schema v1 tanımla
- [x] Skill alanlarına `schema_version`, `name`, `description`, `when_to_use`, `applies_to`, `allowed_tools`, `prompt_layers`, `tags`, `priority`, `status` ekle
- [x] `allowed_tools` alanını mevcut tool registry isimleriyle doğrulayan validator yaz
- [x] `prompt_layers` için mevcut `prompt_store` anahtarlarına referans + inline layer desteğini tanımla
- [x] Skill klasör taramasında path traversal, beklenmeyen dosya tipi ve bozuk metadata guard'larını ekle

#### Runtime ve Prompt Entegrasyonu
- [x] Skill loader yaz
- [x] Skill loader için cache ve dosya değişikliği algılama (`modified_at` / hash) ekle
- [x] System, project ve custom skill kaynaklarını birleştiren skill registry katmanı oluştur
- [x] Skill seçim önceliğini tanımla: explicit seçim > chat intent/routing > default fallback
- [x] Birden fazla skill aktifken merge/override kurallarını tanımla
- [x] Skill bazlı prompt birleştirme akışını mevcut `prompt_store` katmanlama sırasına bağla
- [x] Final composed prompt önizleme ve debug payload üret
- [x] Skill bazlı tool setini agent allowlist + permission engine ile intersect et
- [x] Chat, tekil rewrite ve batch akışlarında skill uygulanabilirlik kurallarını ayır
- [x] Skill seçimini chat session state'inde tut
- [x] WebSocket ve REST payload'larına aktif skill bilgisini ekle
- [x] Skill seçimi, kullanılan prompt layer'lar ve tool kapsamı için gözlemlenebilirlik logları ekle

#### API ve Skill Studio
- [x] Skill listeleme/getirme/kaydetme/silme/resetleme servislerini `SettingsService` benzeri bir servis katmanına ekle
- [x] Skill preview/validate endpoint'leri ekle
- [x] Diskten yüklenen skill'ler için import/export akışı ekle
- [x] Chat içinde explicit skill seçimi, değiştirme ve skill temizleme desteği ekle
- [x] Frontend'de Prompt Studio ile uyumlu bir Skill Studio ekranı ekle
- [x] Skill listesi, detay editörü, prompt layer preview ve validation state panellerini ekle
- [x] `allowed_tools` seçici ve skill applicability editörü ekle
- [x] Skill'i chat oturumuna uygulama ve test etme UX'ini ekle

#### Başlangıç Skill'leri
- [x] En az 3 başlangıç skill'i oluştur:
- [x] `category-audit`
- [x] `brand-voice-rewrite`
- [x] `launch-readiness`
- [x] Başlangıç skill'leri için örnek prompt layer kompozisyonlarını tanımla
- [x] Başlangıç skill'leri için allowed tool setlerini ve güvenlik sınırlarını tanımla

#### Test ve Dokümantasyon
- [x] Skill loader, metadata validation, merge ve selection akışları için birim testleri yaz
- [x] Skill bazlı prompt birleştirme akışlarını test et
- [x] Chat, rewrite, batch ve Skill Studio akışları için entegrasyon testleri ekle
- [x] Skill authoring rehberi hazırla
- [x] Readme dosyasını güncelle

### 5. Persistent Store Memory
- [x] Kalıcı mağaza hafızası için veri modeli oluştur
- [x] Hafıza tiplerini ayır: marka tonu, yasak claim'ler, kategori sözlüğü, onaylı tercih, operasyon notu
- [x] Hafızayı chat başlangıç bağlamına kontrollü şekilde ekle
- [x] Hafıza özetleme ve boyut sınırlama mantığı ekle
- [x] Onaylanan suggestion'lardan hafıza çıkarma akışı ekle
- [x] Manuel hafıza ekleme/güncelleme endpoint'i oluştur
- [x] Frontend ayarlar veya prompt ekranından hafıza yönetimi UI'ı ekle
- [x] Hafıza kullanımının suggestion kalitesine etkisini ölçmek için log alanları ekle

## Should

### 8. Command Layer ve Command Palette
- [ ] Backend tarafında command registry oluştur
- [ ] Komut tiplerini belirle: local, async task, prompt-driven
- [ ] En az şu komutları ekle:
- [ ] `sync-products`
- [ ] `run-snapshot`
- [ ] `resume-llms`
- [ ] `reconnect-mcp`
- [ ] `approve-pending`
- [ ] Frontend için command palette bileşeni ekle
- [ ] Komut arama ve klavye ile gezinme desteği ekle
- [ ] Son kullanılan komutlar listesi ekle

### 9. Doctor / Diagnostics ve Operasyon Geri Bildirimi
#### Sistem Sağlığı ve Teknik Tanı
- [x] Tek ekranda provider, MCP, DB, worker ve prompt cache sağlığını gösteren diagnostics endpoint'i oluştur
- [x] `GET /api/diagnostics/summary` response contract'ını tanımla
- [x] Diagnostics payload'ında `providers`, `mcp`, `database`, `workers`, `prompt_cache`, `task_runtime`, `store_context`, `active_jobs` bloklarını standartlaştır
- [x] Her bileşen için sağlık durumunu `healthy`, `degraded`, `down`, `unknown` enum'u ile dön
- [x] Bağlantı testlerini ayrı ayrı raporla
- [x] Her bağlantı testinde `checked_at`, `latency_ms`, `error_code`, `error_summary`, `retryable` alanlarını üret
- [ ] Provider tarafında "config yok", "model erişilemiyor", "ilk token alınamıyor", "rate limit" durumlarını ayrı reason code'larla sınıflandır
- [ ] MCP tarafında "token yok", "init başarısız", "tool listesi boş", "tool çağrısı başarısız" durumlarını ayrı reason code'larla sınıflandır
- [ ] DB tarafında bağlantı, migration uyumu, yazma testi ve lock kaynaklı gecikme kontrollerini ayrı raporla
- [x] Worker sağlığında son heartbeat, çalışan iş sayısı, stuck iş sayısı ve son crash özetini göster
- [ ] Prompt cache için hit/miss, son build zamanı ve bozuk cache reason code'larını göster
- [x] Sık görülen hata durumları için reason code üret
- [x] Stuck worker veya yarım kalmış task tespiti ekle
- [x] Stuck detection için `heartbeat_at`, `updated_at`, `status`, `stage` ve son event zamanını birlikte kullanan heuristik tanımla
- [ ] Her bileşen için son başarılı heartbeat, son başarısız deneme ve son hata özetini göster
- [x] Diagnostics çıktısında global sistem arızası ile tek job/store kaynaklı arızayı ayrı sınıflandır
- [x] Frontend üzerinde diagnostics ekranı oluştur
- [x] Diagnostics ekranında bileşen kartları, reason code listesi ve önerilen aksiyonları göster
- [x] Kopyalanabilir debug raporu üret
- [x] Debug raporunda sistem özeti, aktif job'lar, son hatalar, stuck işler ve reason code'ları tek metinde topla

#### Operasyon Şeffaflığı ve Kullanıcı Feedback'i
- [ ] Uzun süren işlemler için ortak bir `OperationFeedbackEnvelope` sözleşmesi tanımla; task, batch, bulk apply ve rollback aynı dili konuşsun
- [ ] Ortak feedback alanlarını netleştir: `stage`, `stage_label`, `stage_order`, `current_step`, `current_item`, `last_completed_item`, `summary_counts`, `warning_count`, `eta_seconds`, `last_event_at`, `stalled_since`, `next_action_hints`
- [x] Task/job payload'una batch feedback için `stage`, `stage_label`, `current_item`, `last_completed_item`, `summary_counts`, `warning_count`, `eta_seconds`, `last_event_at`, `next_action_hints` alanlarını ekle
- [x] `summary_counts` içinde en az `total`, `processed`, `succeeded`, `skipped`, `failed`, `retried`, `remaining` sayaçlarını zorunlu kıl
- [ ] Ortak event tiplerini standardize et: `operation_started`, `stage_changed`, `item_started`, `item_completed`, `item_skipped`, `item_failed`, `heartbeat`, `operation_waiting`, `operation_completed`
- [ ] Yalnızca yüzde ilerleme değil, faz geçişlerini de event olarak yayınla: `queued`, `preparing`, `analyzing`, `awaiting_review`, `awaiting_approval`, `applying`, `rolling_back`, `completed`, `completed_with_errors`
- [ ] Permission bekleyen durumları normal çalışma ile karıştırma; `awaiting_approval` ve `awaiting_user_action` için ayrı event ve UI copy üret
- [x] Batch akışlarında ürün bazlı olay akışını görünür kıl: hangi ürün işlendi, hangisi atlandı, hangisi hata verdi, neden
- [ ] Ürün bazlı event'lerde `product_id`, `product_name`, `item_status`, `duration_ms`, `reason_code` alanlarını zorunlu kıl
- [x] `skipped` ve `failed` item'lar için kullanıcıya gösterilebilir kısa açıklama ile teknik `reason_code` alanını birlikte üret
- [ ] Backend tarafında `reason_code`, `user_message`, `retryable`, `suggested_action` alanlarını aynı event içinde döndür
- [x] Toplu işlemlerde toplam, işlenen, başarılı, atlanan, hatalı, yeniden denenen ve kalan sayaçlarını ayrı ayrı göster
- [x] Tek bir aktif yüzde yerine "şu an ne yapıyor" metni üret: ör. "ürünler okunuyor", "AI öneri üretiyor", "IKAS'a yazılıyor", "rollback hazırlanıyor"
- [x] Stage bazlı kullanıcı metinlerini backend kaynaklı sabit bir kopya kataloğundan üret; frontend bu metinleri tahmin etmesin
- [ ] Uzun süre sessiz kalan işlemler için "çalışıyor ama yanıt bekleniyor" ve "muhtemelen stuck" ayrımını yapan timeout/heartbeat UX'i ekle
- [ ] Toplu onay, toplu apply ve rollback başlatıldığında anlık başlangıç geri bildirimi, canlı ilerleme ve tamamlanma özeti göster
- [ ] İşlem tamamlandığında başarı özeti, hata özeti, atlananlar özeti ve önerilen sonraki adımı tek kapanış kartında göster
- [x] İşlem sırasında oluşan son N olayı tutan zaman akışı / event log bileşeni ekle
- [x] Hata veya durdurma sonrası bir sonraki önerilen aksiyonu göster: retry, resume, failed-only rerun, debug raporu kopyala
- [ ] SSE, WebSocket ve polling fallback katmanlarında aynı feedback alanlarını taşıyan ortak event envelope tasarla
- [x] Polling fallback'te event history kaybını azaltmak için `sequence` veya `last_event_id` alanı ekle

#### Batch UX Odaklı İyileştirmeler
- [ ] Analiz aşaması ile apply aşamasını tek bir progress bar içinde eritmeyi bırak; faz bazlı ayrı ilerleme göstergeleri ekle
- [x] Batch header'ında mevcut faz, canlı durum metni, son event zamanı ve tahmini kalan süreyi birlikte göster
- [x] `processed_count` değişmediğinde bile durum değişikliği event'i yayınla; kullanıcı sadece sayaç artınca değil, faz değişince de bilgilendirilsin
- [x] Job detayında "son işlenen ürün", "en son hata" ve "en son atlama nedeni" alanlarını göster
- [x] Job detayında "kalan tahmini süre" alanını göster
- [x] Job detayında item listesi için `all`, `processing`, `failed`, `skipped`, `approved`, `applied` filtreleri ekle
- [ ] Analiz tamamlandığında apply öncesi özet ver; kaç ürün öneri üretti, kaçı atlandı, kaçı review bekliyor açıkça göster
- [ ] Apply aşamasında analiz sayaçları ile yazma sayaçlarını ayır; "kaç ürün IKAS'a yazıldı / kaç ürün kaldı" metnini ayrı göster
- [ ] Büyük batch'lerde hata dağılımını reason code bazında gruplayıp özetle
- [x] Büyük batch'lerde son N olayın canlı akışını ve ayrı bir "hata özeti" panelini aynı ekranda sun
- [ ] Tek tıkla "yalnızca hatalıları tekrar çalıştır" ve "yalnızca atlananları incele" gibi takip aksiyonlarını backlog'a ekle
- [ ] İş durdurulursa veya hata ile biterse "en son başarılı ürün", "kaldığı faz", "devam ettirilebilir mi" bilgisini açıkça göster
- [ ] Toplu apply başlamadan önce kullanıcıya "kaç ürün yazılacak, kaç ürün atlanacak, riskli alanlar neler" özetini göster
- [x] Tamamlanma kartında sadece yüzde değil, uygulanan ürün sayısı, atlanan ürün sayısı ve ortalama skor değişimini de göster

#### Test ve Gözlemlenebilirlik
- [ ] Operation feedback sözleşmesi için REST, SSE ve WebSocket entegrasyon testleri ekle
- [ ] Stage değişse de sayaç değişmediğinde event yayınlandığını doğrulayan regresyon testi ekle
- [ ] Batch/apply/rollback akışlarında stage transition loglarını structured logging ile kaydet
- [ ] Her `reason_code` için kullanıcı mesajı üretildiğini doğrulayan sözleşme testi ekle
- [ ] Kullanıcıya gösterilen durum metni ile backend event tiplerinin birebir eşleştiğini doğrulayan UI testleri ekle
- [x] Stuck detection heuristikleri için zaman tabanlı test senaryoları ekle
- [ ] Telemetry tarafında event yayın gecikmesi, son heartbeat yaşı ve stuck job sayısı için metrik ekle

### 10. Rich Export ve Audit Trail
- [ ] Mevcut chat export'unu genişlet
- [ ] `txt`, `json`, `markdown`, `html` export formatlarını destekle
- [ ] Tool çağrılarını export içine dahil et
- [ ] Task geçmişi ve approval kayıtlarını export edilebilir yap
- [ ] Batch ve apply operasyonları için audit trail görünümü ekle
- [ ] Export ayarları UI'ı ekle

### 11. Multi-Agent Delegation
- [ ] Paralel ajan rolleri tanımla
- [ ] Başlangıç rolleri oluştur:
- [ ] `rewriter`
- [ ] `verifier`
- [ ] `compliance-checker`
- [ ] `publisher`
- [ ] Ana ajan ile alt ajanlar arasında görev kontratı belirle
- [ ] Alt ajan çıktılarının birleştirilme mantığını yaz
- [ ] Tek ürün ve batch akışında deneysel parallel mode ekle
- [ ] Multi-agent gözlemlenebilirlik loglarını ekle

## Nice-to-have

### 12. Virtualized Chat UI
- [x] Uzun sohbetlerde sanallaştırılmış mesaj listesi kullan
- [x] Tool çıktıları için lazy render ekle
- [x] Otomatik scroll davranışını streaming sırasında iyileştir
- [x] Büyük sohbet geçmişlerinde performans testi yap (`npm run bench:chat`)

### 13. Collaboration / Presence
- [ ] Çok kullanıcılı session modeli tasarla
- [ ] Presence, typing ve approval paylaşımı ekle
- [ ] Ortak review notları ve annotation sistemi ekle
- [ ] Rol bazlı erişim modeli tasarla

### 14. Voice Mode
- [ ] Sesli komut kullanım senaryolarını tanımla
- [ ] STT katmanı ekle
- [ ] Chat input ile voice input'u birleştir
- [ ] Temel sesli komutlar için prototype çıkar

### 15. IDE Bridge / Worktree Isolation
- [ ] IDE bridge ihtiyacını ürün bağlamında netleştir
- [ ] İzole çalışma alanı gerektiren senaryoları çıkar
- [ ] Worktree tabanlı güvenli agent execution için tasarım notu hazırla
- [ ] Ancak temel platform işleri bitmeden implementasyona başlama

## Genel Teknik Borç ve Destekleyici İşler

### 16. Test ve Gözlemlenebilirlik
- [ ] Yeni katmanlar için test stratejisi dokümanı yaz
- [ ] Tool, permission, task ve MCP server için entegrasyon testleri ekle
- [ ] Kritik akışlara structured logging ekle
- [ ] Hata sınıfları ve error code standardı belirle

### 17. Dokümantasyon
- [ ] Yeni platform katmanları için mimari doküman yaz
- [ ] Skill ve plugin geliştirme rehberi hazırla
- [ ] Permission kuralları için kullanım örnekleri ekle
- [ ] Task sistemi ve command katmanı için geliştirici notları yaz
