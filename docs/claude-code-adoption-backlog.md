# Claude-Code Esinli Teknik Backlog

Bu dosya, `claude-code` iÃ§inden `ikas-ai-seo-agent` projesine uyarlanmasÄ± Ã¶nerilen iÅŸleri gÃ¶rev ve todo listesi halinde toplar.

## Must

### 1. Tool Runtime v2
- [x] Ortak bir `ToolDefinition` modeli tasarla
- [x] Tool alanlarÄ±na `name`, `description`, `input_schema`, `risk_level`, `read_only`, `destructive`, `concurrency_safe`, `ui_meta` ekle
- [x] Mevcut local chat tool'larÄ±nÄ± yeni kontrata taÅŸÄ±
- [x] `core/agent/tools.py` iÃ§indeki tool factory yapÄ±sÄ±nÄ± yeni modele gÃ¶re sadeleÅŸtir
- [x] Tool sonuÃ§larÄ± iÃ§in ortak response formatÄ± belirle
- [x] Tool hata formatÄ±nÄ± tekilleÅŸtir
- [x] Tool kayÄ±t/registry katmanÄ± oluÅŸtur
- [x] Tool gÃ¶rÃ¼nÃ¼rlÃ¼ÄŸÃ¼ ve hangi ajanlarÄ±n hangi tool'larÄ± kullanabileceÄŸi iÃ§in allowlist ekle
- [x] Mevcut SEO/chat tool'larÄ± iÃ§in regresyon testleri yaz
- [x] Chat/UI tÃ¼keticileri iÃ§in ortak tool result envelope unwrap katmanÄ± ekle

### 2. Permission ve Approval Engine
- [x] `core/permissions/` altÄ±nda merkezi izin katmanÄ± oluÅŸtur
- [x] `allow`, `ask`, `deny` davranÄ±ÅŸlarÄ±nÄ± destekleyen kural modeli tasarla
- [x] Riskli iÅŸlemleri sÄ±nÄ±flandÄ±r: `apply`, `rollback`, `bulk apply`, `db reset`, `external write`
- [x] `apply_seo_to_ikas` akÄ±ÅŸÄ±nÄ± permission engine Ã¼zerinden geÃ§ir
- [x] Batch apply akÄ±ÅŸlarÄ±nÄ± permission engine Ã¼zerinden geÃ§ir
- [x] Onay gerektiren iÅŸlemler iÃ§in tek tip audit kaydÄ± Ã¼ret
- [x] Ä°zin kararÄ±nÄ± tool Ã§aÄŸrÄ±sÄ±ndan Ã¶nce zorunlu kontrol et
- [x] Kural Ã§Ã¶zÃ¼mleme sÄ±rasÄ±nÄ± tanÄ±mla: global > project > session > runtime override
- [x] Ä°zin sistemi iÃ§in birim testleri ve entegrasyon testleri ekle
- [x] `suggestions/apply` ve tekil chat apply akÄ±ÅŸlarÄ±nÄ± aynÄ± permission guard katmanÄ±na baÄŸla
- [x] `rollback` akÄ±ÅŸlarÄ±nÄ± permission engine Ã¼zerinden geÃ§ir
- [x] `products/reset` (db reset) akÄ±ÅŸÄ±na explicit approval override ekle

### 3. Unified Task System
- [x] Genel amaÃ§lÄ± `tasks` tablosu tasarla
- [x] Task alanlarÄ±na `type`, `status`, `progress`, `payload`, `result`, `error`, `started_at`, `finished_at` ekle
- [ ] `llms` iÅŸÃ§isini unified task modeline tam taÅŸÄ± ve legacy `llms_jobs` durum alanÄ±nÄ± compatibility layer seviyesine indir
- [ ] `batch` iÅŸlerini unified task modeline tam taÅŸÄ± ve retry semantics'ini item-level idempotent hale getir
- [x] Ortak `cancel`, `retry`, `resume`, `stop`, `get status` servislerini ekle
- [x] Task Ã§Ä±ktÄ±larÄ±nÄ± sonradan okunabilir biÃ§imde sakla
- [x] Uzun sÃ¼ren iÅŸlerde heartbeat veya progress update standardÄ± ekle
- [x] API tarafÄ±nda ortak task endpoint'leri oluÅŸtur
- [x] Frontend tarafÄ±nda ortak task durumu bileÅŸeni oluÅŸtur
- [x] Task sistemi iÃ§in migration ve testler yaz
- [x] Readme dosyasÄ±nÄ± gÃ¼ncelle

### 4. Skill System
#### Temel SÃ¶zleÅŸme
- [x] Diskten yÃ¼klenen skill yapÄ±sÄ± iÃ§in klasÃ¶r standardÄ±nÄ± belirle: `skills/<skill-slug>/`
- [x] Skill dosya sÃ¶zleÅŸmesini tanÄ±mla: `SKILL.md`, `meta.json` veya frontmatter, opsiyonel `prompts/`, `assets/`, `examples/`
- [x] Skill metadata schema v1 tanÄ±mla
- [x] Skill alanlarÄ±na `schema_version`, `name`, `description`, `when_to_use`, `applies_to`, `allowed_tools`, `prompt_layers`, `tags`, `priority`, `status` ekle
- [x] `allowed_tools` alanÄ±nÄ± mevcut tool registry isimleriyle doÄŸrulayan validator yaz
- [x] `prompt_layers` iÃ§in mevcut `prompt_store` anahtarlarÄ±na referans + inline layer desteÄŸini tanÄ±mla
- [x] Skill klasÃ¶r taramasÄ±nda path traversal, beklenmeyen dosya tipi ve bozuk metadata guard'larÄ±nÄ± ekle

#### Runtime ve Prompt Entegrasyonu
- [x] Skill loader yaz
- [x] Skill loader iÃ§in cache ve dosya deÄŸiÅŸikliÄŸi algÄ±lama (`modified_at` / hash) ekle
- [x] System, project ve custom skill kaynaklar??n?? birle??tiren skill registry katman?? olu??tur
- [x] Skill se??im ??nceli??ini tan??mla: explicit se??im > chat intent/routing > default fallback
- [x] Birden fazla skill aktifken merge/override kurallar??n?? tan??mla
- [x] Skill bazl?? prompt birle??tirme ak??????n?? mevcut `prompt_store` katmanlama s??ras??na ba??la
- [x] Final composed prompt Ã¶nizleme ve debug payload Ã¼ret
- [x] Skill bazl?? tool setini agent allowlist + permission engine ile intersect et
- [x] Chat, tekil rewrite ve batch akÄ±ÅŸlarÄ±nda skill uygulanabilirlik kurallarÄ±nÄ± ayÄ±r
- [x] Skill seÃ§imini chat session state'inde tut
- [x] WebSocket ve REST payload'larÄ±na aktif skill bilgisini ekle
- [x] Skill se??imi, kullan??lan prompt layer'lar ve tool kapsam?? i??in g??zlemlenebilirlik loglar?? ekle

#### API ve Skill Studio
- [x] Skill listeleme/getirme/kaydetme/silme/resetleme servislerini `SettingsService` benzeri bir servis katmanÄ±na ekle
- [x] Skill preview/validate endpoint'leri ekle
- [x] Diskten yÃ¼klenen skill'ler iÃ§in import/export akÄ±ÅŸÄ± ekle
- [x] Chat iÃ§inde explicit skill seÃ§imi, deÄŸiÅŸtirme ve skill temizleme desteÄŸi ekle
- [x] Frontend'de Prompt Studio ile uyumlu bir Skill Studio ekranÄ± ekle
- [x] Skill listesi, detay editÃ¶rÃ¼, prompt layer preview ve validation state panellerini ekle
- [x] `allowed_tools` seÃ§ici ve skill applicability editÃ¶rÃ¼ ekle
- [x] Skill'i chat oturumuna uygulama ve test etme UX'ini ekle

#### BaÅŸlangÄ±Ã§ Skill'leri
- [x] En az 3 baÅŸlangÄ±Ã§ skill'i oluÅŸtur:
- [x] `category-audit`
- [x] `brand-voice-rewrite`
- [x] `launch-readiness`
- [x] BaÅŸlangÄ±Ã§ skill'leri iÃ§in Ã¶rnek prompt layer kompozisyonlarÄ±nÄ± tanÄ±mla
- [x] BaÅŸlangÄ±Ã§ skill'leri iÃ§in allowed tool setlerini ve gÃ¼venlik sÄ±nÄ±rlarÄ±nÄ± tanÄ±mla

#### Test ve DokÃ¼mantasyon
- [x] Skill loader, metadata validation, merge ve selection akÄ±ÅŸlarÄ± iÃ§in birim testleri yaz
- [x] Skill bazlÄ± prompt birleÅŸtirme akÄ±ÅŸlarÄ±nÄ± test et
- [x] Chat, rewrite, batch ve Skill Studio akÄ±ÅŸlarÄ± iÃ§in entegrasyon testleri ekle
- [x] Skill authoring rehberi hazÄ±rla
- [x] Readme dosyasÄ±nÄ± gÃ¼ncelle

### 5. Persistent Store Memory
- [x] KalÄ±cÄ± maÄŸaza hafÄ±zasÄ± iÃ§in veri modeli oluÅŸtur
- [x] HafÄ±za tiplerini ayÄ±r: marka tonu, yasak claim'ler, kategori sÃ¶zlÃ¼ÄŸÃ¼, onaylÄ± tercih, operasyon notu
- [x] HafÄ±zayÄ± chat baÅŸlangÄ±Ã§ baÄŸlamÄ±na kontrollÃ¼ ÅŸekilde ekle
- [x] HafÄ±za Ã¶zetleme ve boyut sÄ±nÄ±rlama mantÄ±ÄŸÄ± ekle
- [x] Onaylanan suggestion'lardan hafÄ±za Ã§Ä±karma akÄ±ÅŸÄ± ekle
- [x] Manuel hafÄ±za ekleme/gÃ¼ncelleme endpoint'i oluÅŸtur
- [x] Frontend ayarlar veya prompt ekranÄ±ndan hafÄ±za yÃ¶netimi UI'Ä± ekle
- [x] HafÄ±za kullanÄ±mÄ±nÄ±n suggestion kalitesine etkisini Ã¶lÃ§mek iÃ§in log alanlarÄ± ekle

## Should

### 8. Command Layer ve Command Palette
- [ ] Backend tarafÄ±nda command registry oluÅŸtur
- [ ] Komut tiplerini belirle: local, async task, prompt-driven
- [ ] En az ÅŸu komutlarÄ± ekle:
- [ ] `sync-products`
- [ ] `run-snapshot`
- [ ] `resume-llms`
- [ ] `reconnect-mcp`
- [ ] `approve-pending`
- [ ] Frontend iÃ§in command palette bileÅŸeni ekle
- [ ] Komut arama ve klavye ile gezinme desteÄŸi ekle
- [ ] Son kullanÄ±lan komutlar listesi ekle

### 9. Doctor / Diagnostics
- [ ] Tek ekranda provider, MCP, DB, worker ve prompt cache saÄŸlÄ±ÄŸÄ±nÄ± gÃ¶steren endpoint oluÅŸtur
- [ ] BaÄŸlantÄ± testlerini ayrÄ± ayrÄ± raporla
- [ ] SÄ±k gÃ¶rÃ¼len hata durumlarÄ± iÃ§in reason code Ã¼ret
- [ ] Stuck worker veya yarÄ±m kalmÄ±ÅŸ task tespiti ekle
- [ ] Frontend Ã¼zerinde diagnostics ekranÄ± oluÅŸtur
- [ ] Kopyalanabilir debug raporu Ã¼ret

### 10. Rich Export ve Audit Trail
- [ ] Mevcut chat export'unu geniÅŸlet
- [ ] `txt`, `json`, `markdown`, `html` export formatlarÄ±nÄ± destekle
- [ ] Tool Ã§aÄŸrÄ±larÄ±nÄ± export iÃ§ine dahil et
- [ ] Task geÃ§miÅŸi ve approval kayÄ±tlarÄ±nÄ± export edilebilir yap
- [ ] Batch ve apply operasyonlarÄ± iÃ§in audit trail gÃ¶rÃ¼nÃ¼mÃ¼ ekle
- [ ] Export ayarlarÄ± UI'Ä± ekle

### 11. Multi-Agent Delegation
- [ ] Paralel ajan rolleri tanÄ±mla
- [ ] BaÅŸlangÄ±Ã§ rolleri oluÅŸtur:
- [ ] `rewriter`
- [ ] `verifier`
- [ ] `compliance-checker`
- [ ] `publisher`
- [ ] Ana ajan ile alt ajanlar arasÄ±nda gÃ¶rev kontratÄ± belirle
- [ ] Alt ajan Ã§Ä±ktÄ±larÄ±nÄ±n birleÅŸtirilme mantÄ±ÄŸÄ±nÄ± yaz
- [ ] Tek Ã¼rÃ¼n ve batch akÄ±ÅŸÄ±nda deneysel parallel mode ekle
- [ ] Multi-agent gÃ¶zlemlenebilirlik loglarÄ±nÄ± ekle

## Nice-to-have

### 12. Virtualized Chat UI
- [x] Uzun sohbetlerde sanallaÅŸtÄ±rÄ±lmÄ±ÅŸ mesaj listesi kullan
- [x] Tool Ã§Ä±ktÄ±larÄ± iÃ§in lazy render ekle
- [x] Otomatik scroll davranÄ±ÅŸÄ±nÄ± streaming sÄ±rasÄ±nda iyileÅŸtir
- [x] BÃ¼yÃ¼k sohbet geÃ§miÅŸlerinde performans testi yap (`npm run bench:chat`)

### 13. Collaboration / Presence
- [ ] Ã‡ok kullanÄ±cÄ±lÄ± session modeli tasarla
- [ ] Presence, typing ve approval paylaÅŸÄ±mÄ± ekle
- [ ] Ortak review notlarÄ± ve annotation sistemi ekle
- [ ] Rol bazlÄ± eriÅŸim modeli tasarla

### 14. Voice Mode
- [ ] Sesli komut kullanÄ±m senaryolarÄ±nÄ± tanÄ±mla
- [ ] STT katmanÄ± ekle
- [ ] Chat input ile voice input'u birleÅŸtir
- [ ] Temel sesli komutlar iÃ§in prototype Ã§Ä±kar

### 15. IDE Bridge / Worktree Isolation
- [ ] IDE bridge ihtiyacÄ±nÄ± Ã¼rÃ¼n baÄŸlamÄ±nda netleÅŸtir
- [ ] Ä°zole Ã§alÄ±ÅŸma alanÄ± gerektiren senaryolarÄ± Ã§Ä±kar
- [ ] Worktree tabanlÄ± gÃ¼venli agent execution iÃ§in tasarÄ±m notu hazÄ±rla
- [ ] Ancak temel platform iÅŸleri bitmeden implementasyona baÅŸlama

## Genel Teknik BorÃ§ ve Destekleyici Ä°ÅŸler

### 16. Test ve GÃ¶zlemlenebilirlik
- [ ] Yeni katmanlar iÃ§in test stratejisi dokÃ¼manÄ± yaz
- [ ] Tool, permission, task ve MCP server iÃ§in entegrasyon testleri ekle
- [ ] Kritik akÄ±ÅŸlara structured logging ekle
- [ ] Hata sÄ±nÄ±flarÄ± ve error code standardÄ± belirle

### 17. DokÃ¼mantasyon
- [ ] Yeni platform katmanlarÄ± iÃ§in mimari dokÃ¼man yaz
- [ ] Skill ve plugin geliÅŸtirme rehberi hazÄ±rla
- [ ] Permission kurallarÄ± iÃ§in kullanÄ±m Ã¶rnekleri ekle
- [ ] Task sistemi ve command katmanÄ± iÃ§in geliÅŸtirici notlarÄ± yaz


