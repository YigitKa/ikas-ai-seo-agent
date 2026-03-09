import type { Product, SeoScore } from '../../types';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface PromptParamOption {
  key: string;
  label: string;
  description: string;
  value: string;
  preview: string;
  searchText: string;
}

export interface ParamTriggerState {
  start: number;
  end: number;
  query: string;
}

export interface StarterPrompt {
  label: string;
  template: string;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

export function stripHtml(value: string) {
  return value
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n\n')
    .replace(/<\/li>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/\r/g, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[ \t]{2,}/g, ' ')
    .trim();
}

function compactPreview(value: string, maxLength = 120) {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength - 1)}...`;
}

function createPromptParamOption(
  key: string,
  label: string,
  description: string,
  rawValue: string | null | undefined,
): PromptParamOption {
  const normalizedValue = (rawValue ?? '').trim() || 'Belirtilmemis';
  return {
    key,
    label,
    description,
    value: normalizedValue,
    preview: compactPreview(normalizedValue),
    searchText: `${key} ${label} ${description}`.toLowerCase(),
  };
}

export function buildSeoMetricsSummary(score?: SeoScore | null) {
  if (!score) {
    return 'SEO metrikleri henuz okunmadi.';
  }

  const sections = [
    `Toplam SEO skoru: ${score.total_score}/100`,
    `Baslik skoru: ${score.title_score}/15`,
    `Aciklama skoru: ${score.description_score}/20`,
    `Ingilizce aciklama skoru: ${score.english_description_score}/5`,
    `Meta title skoru: ${score.meta_score}/15`,
    `Meta description skoru: ${score.meta_desc_score}/10`,
    `Anahtar kelime skoru: ${score.keyword_score}/10`,
    `Icerik kalitesi skoru: ${score.content_quality_score}/10`,
    `Teknik SEO skoru: ${score.technical_seo_score}/10`,
    `Okunabilirlik skoru: ${score.readability_score}/5`,
  ];

  if (score.issues.length > 0) {
    sections.push(`Sorunlar:\n- ${score.issues.join('\n- ')}`);
  }
  if (score.suggestions.length > 0) {
    sections.push(`Oneriler:\n- ${score.suggestions.join('\n- ')}`);
  }

  return sections.join('\n');
}

export function buildPromptParamOptions(product?: Product | null, score?: SeoScore | null): PromptParamOption[] {
  const productDescription = stripHtml(product?.description || '');
  const productDescriptionEn = stripHtml(product?.description_translations?.en || '');
  const seoIssues = score?.issues.length ? `- ${score.issues.join('\n- ')}` : 'Belirtilmemis';
  const seoSuggestions = score?.suggestions.length ? `- ${score.suggestions.join('\n- ')}` : 'Belirtilmemis';

  return [
    createPromptParamOption('productName', 'Urun adi', 'Secili urunun basligi', product?.name),
    createPromptParamOption('productCategory', 'Kategori', 'Secili urunun kategorisi', product?.category),
    createPromptParamOption('productDescription', 'Urun aciklamasi', 'Temizlenmis urun aciklama metni', productDescription),
    createPromptParamOption('productDescriptionEn', 'EN aciklama', 'Varsa Ingilizce aciklama', productDescriptionEn),
    createPromptParamOption('productMetaTitle', 'Meta title', 'Mevcut meta title alani', product?.meta_title),
    createPromptParamOption('productMetaDescription', 'Meta description', 'Mevcut meta description alani', product?.meta_description),
    createPromptParamOption('productTags', 'Etiketler', 'Secili urunun etiketleri', product?.tags.join(', ')),
    createPromptParamOption('productSku', 'SKU', 'Secili urunun SKU degeri', product?.sku),
    createPromptParamOption('productStatus', 'Durum', 'Secili urunun yayindaki durumu', product?.status),
    createPromptParamOption(
      'productPrice',
      'Fiyat',
      'Secili urunun kayitli fiyati',
      typeof product?.price === 'number' ? `${product.price.toFixed(2)} TL` : undefined,
    ),
    createPromptParamOption('seoMetricsSummary', 'SEO ozeti', 'Tum mevcut SEO skor kirilimlari', buildSeoMetricsSummary(score)),
    createPromptParamOption(
      'seoTotalScore', 'Toplam SEO skoru', 'Toplam skor',
      typeof score?.total_score === 'number' ? `${score.total_score}/100` : undefined,
    ),
    createPromptParamOption(
      'seoTitleScore', 'Baslik skoru', 'Title skor kirilimi',
      typeof score?.title_score === 'number' ? `${score.title_score}/15` : undefined,
    ),
    createPromptParamOption(
      'seoDescriptionScore', 'Aciklama skoru', 'Description skor kirilimi',
      typeof score?.description_score === 'number' ? `${score.description_score}/20` : undefined,
    ),
    createPromptParamOption(
      'seoEnglishDescriptionScore', 'EN aciklama skoru', 'English description skor kirilimi',
      typeof score?.english_description_score === 'number' ? `${score.english_description_score}/5` : undefined,
    ),
    createPromptParamOption(
      'seoMetaTitleScore', 'Meta title skoru', 'Meta title skor kirilimi',
      typeof score?.meta_score === 'number' ? `${score.meta_score}/15` : undefined,
    ),
    createPromptParamOption(
      'seoMetaDescriptionScore', 'Meta description skoru', 'Meta description skor kirilimi',
      typeof score?.meta_desc_score === 'number' ? `${score.meta_desc_score}/10` : undefined,
    ),
    createPromptParamOption(
      'seoKeywordScore', 'Keyword skoru', 'Anahtar kelime skor kirilimi',
      typeof score?.keyword_score === 'number' ? `${score.keyword_score}/10` : undefined,
    ),
    createPromptParamOption(
      'seoContentQualityScore', 'Icerik kalitesi skoru', 'Content quality skor kirilimi',
      typeof score?.content_quality_score === 'number' ? `${score.content_quality_score}/10` : undefined,
    ),
    createPromptParamOption(
      'seoTechnicalScore', 'Teknik SEO skoru', 'Technical SEO skor kirilimi',
      typeof score?.technical_seo_score === 'number' ? `${score.technical_seo_score}/10` : undefined,
    ),
    createPromptParamOption(
      'seoReadabilityScore', 'Okunabilirlik skoru', 'Readability skor kirilimi',
      typeof score?.readability_score === 'number' ? `${score.readability_score}/5` : undefined,
    ),
    createPromptParamOption('seoIssues', 'SEO sorunlari', 'Mevcut issue listesi', seoIssues),
    createPromptParamOption('seoSuggestions', 'SEO onerileri', 'Mevcut suggestion listesi', seoSuggestions),
  ];
}

export function resolvePromptTemplate(template: string, options: PromptParamOption[]) {
  return options.reduce(
    (resolved, option) => resolved.split(`{${option.key}}`).join(option.value),
    template,
  );
}

export function getParamTriggerState(value: string, caretPosition: number | null): ParamTriggerState | null {
  if (caretPosition === null) {
    return null;
  }

  const textBeforeCaret = value.slice(0, caretPosition);
  const openIndex = textBeforeCaret.lastIndexOf('{');
  if (openIndex === -1) {
    return null;
  }

  if (textBeforeCaret.lastIndexOf('}') > openIndex) {
    return null;
  }

  const query = textBeforeCaret.slice(openIndex + 1);
  if (/\s/.test(query)) {
    return null;
  }

  const closingIndex = value.indexOf('}', openIndex);
  if (closingIndex !== -1 && closingIndex < caretPosition) {
    return null;
  }

  return { start: openIndex, end: caretPosition, query };
}
