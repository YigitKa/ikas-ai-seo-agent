# UI Refactor & Reusability Audit

Bu dokuman, `web/src` altindaki UI kodlarinin componentlestirme, refactor ve yeniden kullanilabilirlik acisindan taranmasi sonucu olusturuldu.

## 1) Oncelik: Yuksek

### `web/src/pages/Settings.tsx`
- **Durum:** Tek dosyada hem sayfa state/side-effect yonetimi hem de cok sayida alt UI parca/yardimci fonksiyon bulunuyor.
- **Neden refactor:** Sayfa cok buyuk ve birden fazla sorumluluk tasiyor (provider ayarlari, prompt editoru, MCP/LM Studio durumu, ortak UI primitive'leri).
- **Ayrisma onerisi:**
  - `components/settings/sections/*` (ProviderSettingsSection, PromptEditorSection, ConnectivitySection, LmStudioStatusSection)
  - `components/settings/fields/*` (Field, SelectField, ToggleField)
  - `components/shared/feedback/*` (Banner, StatusPill, StatusRow)
  - `hooks/settings/*` (form state, provider model discovery, prompt reset/save aksiyonlari)

### `web/src/components/ChatPanel.tsx`
- **Durum:** Chat container, header, input, starter prompts, param menu, diff modal davranisi ve performans metrikleri ayni bileşende toplanmis.
- **Neden refactor:** Gorunum + is kurali + durum gecisleri fazla ic ice; testlenebilirlik ve tekrar kullanilabilirlik dusuyor.
- **Ayrisma onerisi:**
  - `components/chat/layout/ChatHeader`, `ChatStatusBar`, `ChatComposer`, `StarterPrompts`
  - `components/chat/param/PromptParamMenu`
  - `hooks/chat/usePromptParamComposer`, `hooks/chat/useLiveTiming`

### `web/src/hooks/useChat.ts`
- **Durum:** WebSocket baglantisi, auto-reconnect, streaming buffer, state makinasi, MCP/pending suggestion mantigi tek hook'ta.
- **Neden refactor:** Tek hook cok fazla domain davranisi yurutuyor; parca bazli test zor.
- **Ayrisma onerisi:**
  - `useChatSocketConnection`
  - `useChatStreamingBuffer`
  - `useChatAutoIntro`
  - `useChatSessionMetrics`

## 2) Oncelik: Orta

### `web/src/components/chat/ChatMessage.tsx`
- **Durum:** Markdown render, oneriler, tool/meta bloklari ve farkli assistant message durumlari bir arada.
- **Neden refactor:** Render varyantlari buyudukce dosya daha da karmaşik hale gelir.
- **Ayrisma onerisi:**
  - `components/chat/message/MarkdownMessage`
  - `components/chat/message/SuggestionCards`
  - `components/chat/message/AssistantMeta`
  - `components/chat/message/ToolResultList`

### `web/src/components/chat/SeoScoreChatMessage.tsx`
- **Durum:** SEO skor ozetleri ve birden cok kart/hesaplama mantigi ayni dosyada.
- **Neden refactor:** Skor kartlari farkli yerlerde tekrar kullanilabilecek gorunuyor.
- **Ayrisma onerisi:**
  - `components/seo-score/ScoreGauge`
  - `components/seo-score/MetricGrid`
  - `components/seo-score/IssueList`

### `web/src/components/ScoreCard.tsx`
- **Durum:** Sunum + domain mapping (issue aciklama regex'leri, skor alan konfigurasyonu) ayni bileşende.
- **Neden refactor:** Domain kurallari UI'dan ayrilmali; farkli ekranlarda yeniden kullanimi kisitli.
- **Ayrisma onerisi:**
  - `lib/seo-score/fieldDefinitions.ts`
  - `lib/seo-score/explainIssue.ts`
  - `components/seo-score/ScoreCard` + alt presentational bileşenler

## 3) Oncelik: Dusuk / Iyilestirme

### `web/src/pages/Dashboard.tsx`
- **Durum:** Sayfa orchestrator rolunde fakat mutation/alert/download akislarinin bir kisimi sayfa icinde.
- **Neden refactor:** Islem aksiyonlari custom hook'a alinip sayfa okunurlugu artirilabilir.
- **Ayrisma onerisi:** `hooks/dashboard/useDashboardActions.ts`.

### `web/src/components/dashboard/DashboardHeader.tsx` ve `web/src/components/dashboard/DashboardSidebar.tsx`
- **Durum:** Ortak action button / filter-tabs / pagination patternleri mevcut.
- **Neden refactor:** Dashboard disinda tekrar kullanilabilecek primitive'lere donusturulebilir.
- **Ayrisma onerisi:** `components/shared/ActionButton`, `components/shared/FilterTabs`, `components/shared/PaginationBar`.

## Reusable Primitive Adaylari (Global)

- **Feedback/UI durum bilesenleri:** `Banner`, `StatusPill`, `StatusRow`
- **Form primitive'leri:** `Field`, `SelectField`, `ToggleField`
- **Liste state UI:** `EmptyState`, `LoadingSkeletonList`
- **Skor gorsellestirme:** dairesel skor/metric badge/puan etiketi

## Kisa Sonuc

Refactor getirisi en yuksek alanlar: **Settings**, **ChatPanel** ve **useChat**. Bu uc dosyanin modulerlesmesi hem gelistirme hizini hem de tekrar kullanilabilirligi belirgin bicimde arttirir.
