import { memo, type ReactNode } from 'react';
import type { Product, SeoScore } from '../../types';
import {
  explainIssue,
  getFieldStatusText,
  getScoreColor,
  getStatusBadgeStyle,
} from '../../shared/score/scoreUtils';
import CircularScore, { useCountUp } from '../../shared/ui/CircularScore';
import ProgressBar from '../../shared/ui/ProgressBar';

type SectionKey = 'seo' | 'geo' | 'aeo';
type CategoryScoreKey = 'seo_score' | 'geo_score' | 'aeo_score';
type FieldScoreKey =
  | 'title_score'
  | 'description_score'
  | 'english_description_score'
  | 'meta_score'
  | 'meta_desc_score'
  | 'keyword_score'
  | 'content_quality_score'
  | 'technical_seo_score'
  | 'readability_score'
  | 'ai_citability_score';

interface CategoryDefinition {
  key: CategoryScoreKey;
  label: string;
  section: SectionKey;
  accent: string;
  focus: string;
  description: string;
  icon: ReactNode;
}

interface FieldDefinition {
  key: FieldScoreKey;
  label: string;
  max: number;
  section: SectionKey;
  description: string;
  previewLabel: string;
  issueMatcher: RegExp;
  suggestionMatcher: RegExp;
}

interface FieldCardData {
  field: FieldDefinition;
  value: number;
  pct: number;
  color: string;
  badgeStyle: { background: string; color: string };
  statusText: string;
  accent: string;
  preview: {
    label: string;
    value: string;
    metrics: string[];
  };
  issues: string[];
  suggestions: string[];
}

const PREVIEW_CLAMP_STYLE = {
  display: '-webkit-box',
  WebkitLineClamp: 4,
  WebkitBoxOrient: 'vertical',
  overflow: 'hidden',
} as const;

const CTA_PATTERNS = ['hemen', 'simdi', 'incele', 'kesfet', 'buy', 'discover', 'shop now'];

const FIELD_SECTION_ACCENTS: Record<SectionKey, string> = {
  seo: '#8b5cf6',
  geo: '#06b6d4',
  aeo: '#34d399',
};

const CATEGORIES: readonly CategoryDefinition[] = [
  {
    key: 'seo_score',
    label: 'SEO',
    section: 'seo',
    accent: FIELD_SECTION_ACCENTS.seo,
    focus: 'Baslik, meta alanlari, keyword ve teknik sinyaller.',
    description: 'Google gorunurlugu ve arama sonucundaki ilk izlenim gucu.',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
  },
  {
    key: 'geo_score',
    label: 'GEO',
    section: 'geo',
    accent: FIELD_SECTION_ACCENTS.geo,
    focus: 'Somut veri, objektif dil ve alintilanabilir yapilar.',
    description: 'AI motorlarinin urunu anlamasi ve kaynak gostermeye uygunlugu.',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
      </svg>
    ),
  },
  {
    key: 'aeo_score',
    label: 'AEO',
    section: 'aeo',
    accent: FIELD_SECTION_ACCENTS.aeo,
    focus: 'Acilabilir aciklama akisi, net cevaplar ve okunurluk.',
    description: 'Kullaniciya ve answer engine yapilarina net cevap verebilme seviyesi.',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
      </svg>
    ),
  },
] as const;

const FIELDS: readonly FieldDefinition[] = [
  {
    key: 'title_score',
    label: 'Baslik',
    max: 15,
    section: 'seo',
    description: 'Urun adinin uzunlugu, okunabilirligi ve arama niyetiyle uyumu.',
    previewLabel: 'Mevcut urun adi',
    issueMatcher: /Urun adi bos|Urun adi cok kisa|Urun adi biraz kisa|Urun adi cok uzun|Urun adi biraz uzun|Urun adinda/i,
    suggestionMatcher: /Urun adini|Basliga/i,
  },
  {
    key: 'description_score',
    label: 'Aciklama',
    max: 20,
    section: 'aeo',
    description: 'Aciklamanin uzunlugu, paragraflari ve yapisal HTML kullanimi.',
    previewLabel: 'Mevcut aciklama',
    issueMatcher: /Urun aciklamasi bos|Aciklama cok kisa|Aciklama kisa|Aciklama yeterli ama ideal degil|Aciklamada paragraf yapisi yok|Aciklamada yapisal HTML ogeleri eksik/i,
    suggestionMatcher: /Aciklamayi|<h2>|<h3>|<ul>|<ol>|<strong>/i,
  },
  {
    key: 'english_description_score',
    label: 'EN Aciklama',
    max: 5,
    section: 'aeo',
    description: 'Ingilizce aciklamanin varligi ve temel kalite seviyesi.',
    previewLabel: 'Mevcut EN aciklama',
    issueMatcher: /Ingilizce aciklama/i,
    suggestionMatcher: /Ingilizce aciklam/i,
  },
  {
    key: 'meta_score',
    label: 'Meta Title',
    max: 15,
    section: 'seo',
    description: 'Arama sonucunda gorunen basligin uzunlugu ve farklilastirici gucu.',
    previewLabel: 'Mevcut meta title',
    issueMatcher: /Meta title/i,
    suggestionMatcher: /Meta title/i,
  },
  {
    key: 'meta_desc_score',
    label: 'Meta Description',
    max: 10,
    section: 'seo',
    description: 'Arama sonucundaki aciklamanin netligi, uzunlugu ve tiklama istegi.',
    previewLabel: 'Mevcut meta description',
    issueMatcher: /Meta description/i,
    suggestionMatcher: /Meta description/i,
  },
  {
    key: 'keyword_score',
    label: 'Keyword',
    max: 10,
    section: 'seo',
    description: 'Kategori, hedef kelimeler ve urun sinyallerinin alana dagilimi.',
    previewLabel: 'Keyword sinyalleri',
    issueMatcher: /Kategori adi|Urun adi kelimeleri aciklamada|Hedef keyword/i,
    suggestionMatcher: /kategori adini|keyword|anahtar kelime|meta title'a ekleyin/i,
  },
  {
    key: 'content_quality_score',
    label: 'Icerik Kalitesi',
    max: 10,
    section: 'aeo',
    description: 'Kelime cesitliligi, tekrar kontrolu ve icerik tutarliligi.',
    previewLabel: 'Icerik ornegi',
    issueMatcher: /kelimesi cok sik tekrarlaniyor|Kelime cesitliligi|Tekrarlanan ifadeler|icerik uyumsuzlugu/i,
    suggestionMatcher: /Kelime cesitliligini|Farkli kelimeler|Tekrarlanan ifadeleri|Aciklama icinde urun adinin anahtar/i,
  },
  {
    key: 'technical_seo_score',
    label: 'Teknik SEO',
    max: 10,
    section: 'seo',
    description: 'Gorsel, etiket, kategori, fiyat ve slug gibi sinyallerin tamligi.',
    previewLabel: 'Teknik sinyaller',
    issueMatcher: /Urun gorseli yok|Urun etiketleri|Etiket sayisi az|Urun kategorisi tanimlanmamis|Urun slug'i|Urun fiyati tanimlanmamis/i,
    suggestionMatcher: /gorseli|etiket|kategori|Slug|fiyat/i,
  },
  {
    key: 'readability_score',
    label: 'Okunabilirlik',
    max: 5,
    section: 'aeo',
    description: 'Cumle yapisi, ritim ve gecis kelimeleriyle okuma akisi.',
    previewLabel: 'Okunabilirlik ozeti',
    issueMatcher: /Aciklamada yeterli cumle yapisi yok|Cumleler|Cumle uzunluklari|Gecis kelimeleri eksik/i,
    suggestionMatcher: /cumle|ritim|gecis kelimeleri/i,
  },
  {
    key: 'ai_citability_score',
    label: 'AI Alintilanabilirlik',
    max: 10,
    section: 'geo',
    description: 'Somut veri, objektif dil ve madde yapisinin AI icin okunabilirligi.',
    previewLabel: 'AI icin somut veri',
    issueMatcher: /AI|istatistik veya teknik veri yok|subjektif ifadeler|pazarlama dili|liste\/madde imi yapisi yok/i,
    suggestionMatcher: /AI kaynak|objektif|olcumler|madde imleri|yapilandirin/i,
  },
] as const;

function getCategoryCardStyle(accent: string): {
  background: string;
  border: string;
  boxShadow: string;
} {
  return {
    background: `radial-gradient(circle at top right, ${accent}1f, transparent 36%), linear-gradient(180deg, rgba(15,23,42,0.96), rgba(15,23,42,0.84))`,
    border: `1px solid ${accent}30`,
    boxShadow: `0 16px 30px ${accent}14`,
  };
}

function getSoftCardStyle(accent: string): {
  background: string;
  border: string;
  boxShadow: string;
} {
  return {
    background: 'linear-gradient(180deg, rgba(15,23,42,0.86), rgba(15,23,42,0.72))',
    border: `1px solid ${accent}24`,
    boxShadow: `0 12px 28px ${accent}10`,
  };
}

function getCategoryHintStyle(accent: string): {
  background: string;
  border: string;
  color: string;
} {
  return {
    background: `${accent}16`,
    border: `1px solid ${accent}24`,
    color: accent,
  };
}

function toPlainText(value?: string | null): string {
  if (!value) {
    return '';
  }

  if (typeof DOMParser !== 'undefined') {
    const parser = new DOMParser();
    const doc = parser.parseFromString(value, 'text/html');
    return doc.body.textContent?.replace(/\s+/g, ' ').trim() ?? '';
  }

  return value.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

function countWords(text: string): number {
  if (!text.trim()) {
    return 0;
  }
  return text.trim().split(/\s+/).length;
}

function countParagraphs(raw?: string | null): number {
  if (!raw?.trim()) {
    return 0;
  }

  const blocks = raw
    .split(/\n\s*\n|<br\s*\/?>|<\/p>/i)
    .map((part) => part.replace(/<[^>]+>/g, ' ').trim())
    .filter(Boolean);

  return blocks.length || (toPlainText(raw) ? 1 : 0);
}

function countSentences(text: string): number {
  const matches = text.match(/[^.!?]+[.!?]+/g);
  if (!matches) {
    return text.trim() ? 1 : 0;
  }
  return matches.length;
}

function countNumbers(text: string): number {
  return text.match(/\b\d+[.,]?\d*\b/g)?.length ?? 0;
}

function hasUnits(text: string): boolean {
  return /\d+[.,]?\d*\s*(%|cm|mm|m2|m²|kg|g|l|ml|watt|w|hz|gb|mb|tb|adet|pcs?|piece)/i.test(text);
}

function hasList(raw?: string | null): boolean {
  if (!raw) {
    return false;
  }
  return /<[uo]l[^>]*>/i.test(raw) || /(^|\n)\s*[-*•]\s+\w/i.test(toPlainText(raw));
}

function hasHeading(raw?: string | null): boolean {
  return raw ? /<h[1-6][^>]*>/i.test(raw) : false;
}

function hasSeparator(text?: string | null): boolean {
  return text ? text.includes('|') || text.includes(' - ') || text.includes(' -') : false;
}

function hasCallToAction(text?: string | null): boolean {
  if (!text) {
    return false;
  }
  const normalized = text.toLowerCase();
  return CTA_PATTERNS.some((pattern) => normalized.includes(pattern));
}

function hasTurkishCharacters(text?: string | null): boolean {
  return /[ğüşöçıİĞÜŞÖÇ]/.test(text ?? '');
}

function getUniqueImageCount(product?: Product | null): number {
  const imageUrls = [product?.image_url, ...(product?.image_urls ?? [])]
    .filter((value): value is string => Boolean(value?.trim()))
    .map((value) => value.trim());

  return new Set(imageUrls).size;
}

function getPrimaryImage(product?: Product | null): string | null {
  const imageUrls = [product?.image_url, ...(product?.image_urls ?? [])]
    .filter((value): value is string => Boolean(value?.trim()));

  return imageUrls[0] ?? null;
}

function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1).trimEnd()}...`;
}

function formatPrice(price: number | null | undefined): string {
  if (typeof price !== 'number' || Number.isNaN(price) || price <= 0) {
    return 'Fiyat yok';
  }

  return `${new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 0 }).format(price)} birim`;
}

function joinHumanList(values: string[]): string {
  if (values.length === 0) {
    return '';
  }
  if (values.length === 1) {
    return values[0];
  }
  if (values.length === 2) {
    return `${values[0]} ve ${values[1]}`;
  }
  return `${values.slice(0, -1).join(', ')} ve ${values[values.length - 1]}`;
}

function estimateRangeHealth(value: number, idealMin: number, idealMax: number, hardMax: number): number {
  if (value <= 0) {
    return 0;
  }

  if (value >= idealMin && value <= idealMax) {
    return 100;
  }

  if (value < idealMin) {
    return Math.max(0, Math.round((value / idealMin) * 70));
  }

  if (value > hardMax) {
    return 20;
  }

  const overflow = value - idealMax;
  const distance = Math.max(hardMax - idealMax, 1);
  return Math.max(25, 100 - Math.round((overflow / distance) * 70));
}

function buildHeroSummary(
  score: SeoScore,
  product: Product | null | undefined,
  weakestCategory: CategoryDefinition & { value: number },
  prioritizedFields: FieldCardData[],
): string {
  const missingFields: string[] = [];

  if (!product?.meta_title?.trim()) {
    missingFields.push('meta title');
  }
  if (!product?.meta_description?.trim()) {
    missingFields.push('meta description');
  }
  if (!(product?.description_translations?.en ?? '').trim()) {
    missingFields.push('EN aciklama');
  }

  const weakestFieldSummary = prioritizedFields
    .slice(0, 3)
    .map((item) => `${item.field.label} ${item.value}/${item.field.max}`);

  const parts: string[] = [];

  if (missingFields.length > 0) {
    parts.push(`${joinHumanList(missingFields)} eksik.`);
  }

  parts.push(`En zayif kategori ${weakestCategory.label} ${weakestCategory.value}/100.`);

  if (weakestFieldSummary.length > 0) {
    parts.push(`En cok puan kaybi ${joinHumanList(weakestFieldSummary)} alanlarinda.`);
  }

  if (score.issues.length > 0) {
    parts.push(`${score.issues.length} sorun tespit edildi.`);
  }

  return parts.join(' ');
}

function getHeroMetrics(product?: Product | null): Array<{
  label: string;
  value: string;
  helper: string;
  accent: string;
}> {
  const titleLength = product?.name?.trim().length ?? 0;
  const descriptionWords = countWords(toPlainText(product?.description));
  const metaTitleLength = product?.meta_title?.trim().length ?? 0;
  const metaDescLength = product?.meta_description?.trim().length ?? 0;

  return [
    {
      label: 'Urun adi',
      value: titleLength ? `${titleLength} karakter` : 'Alan bos',
      helper: 'Ideal aralik 30-60 karakter',
      accent: getScoreColor(estimateRangeHealth(titleLength, 30, 60, 80)),
    },
    {
      label: 'Aciklama',
      value: descriptionWords ? `${descriptionWords} kelime` : 'Alan bos',
      helper: '150+ kelime ve paragraflar beklenir',
      accent: getScoreColor(estimateRangeHealth(descriptionWords, 150, 320, 650)),
    },
    {
      label: 'Meta title',
      value: metaTitleLength ? `${metaTitleLength} karakter` : 'Alan bos',
      helper: 'Ideal aralik 50-60 karakter',
      accent: getScoreColor(estimateRangeHealth(metaTitleLength, 50, 60, 80)),
    },
    {
      label: 'Meta desc',
      value: metaDescLength ? `${metaDescLength} karakter` : 'Alan bos',
      helper: 'Ideal aralik 120-160 karakter',
      accent: getScoreColor(estimateRangeHealth(metaDescLength, 120, 160, 200)),
    },
  ];
}

function getFieldPreview(fieldKey: FieldScoreKey, product?: Product | null): {
  label: string;
  value: string;
  metrics: string[];
} {
  const rawDescription = product?.description ?? '';
  const descriptionText = toPlainText(rawDescription);
  const englishRaw = product?.description_translations?.en ?? '';
  const englishText = toPlainText(englishRaw);
  const metaTitle = product?.meta_title?.trim() ?? '';
  const metaDescription = product?.meta_description?.trim() ?? '';
  const tagCount = product?.tags?.length ?? 0;
  const imageCount = getUniqueImageCount(product);

  switch (fieldKey) {
    case 'title_score':
      return {
        label: 'Mevcut urun adi',
        value: product?.name?.trim() || 'Urun adi girilmemis.',
        metrics: [
          product?.name?.trim() ? `${product.name.trim().length} karakter` : 'Deger yok',
          product?.category ? `Kategori: ${product.category}` : 'Kategori yok',
          product?.slug ? `Slug: /${product.slug}` : 'Slug yok',
        ],
      };
    case 'description_score':
      return {
        label: 'Mevcut aciklama',
        value: descriptionText || 'Aciklama girilmemis.',
        metrics: [
          `${countWords(descriptionText)} kelime`,
          `${countParagraphs(rawDescription)} blok`,
          hasList(rawDescription) || hasHeading(rawDescription) ? 'Yapisal ogeler var' : 'Yapisal ogeler zayif',
        ],
      };
    case 'english_description_score':
      return {
        label: 'Mevcut EN aciklama',
        value: englishText || 'Ingilizce aciklama girilmemis.',
        metrics: [
          `${countWords(englishText)} kelime`,
          hasTurkishCharacters(englishRaw) ? 'TR karakter var' : 'Dil temiz',
          englishText ? 'Alan mevcut' : 'Alan eksik',
        ],
      };
    case 'meta_score':
      return {
        label: 'Mevcut meta title',
        value: metaTitle || 'Meta title girilmemis.',
        metrics: [
          `${metaTitle.length} karakter`,
          metaTitle && product?.name
            ? metaTitle.toLowerCase() === product.name.trim().toLowerCase()
              ? 'Urun adi ile ayni'
              : 'Urun adindan ayrisiyor'
            : 'Karsilastirma yok',
          hasSeparator(metaTitle) ? 'Marka ayirici var' : 'Marka ayirici yok',
        ],
      };
    case 'meta_desc_score':
      return {
        label: 'Mevcut meta description',
        value: metaDescription || 'Meta description girilmemis.',
        metrics: [
          `${metaDescription.length} karakter`,
          hasCallToAction(metaDescription) ? 'CTA var' : 'CTA yok',
          `${countWords(metaDescription)} kelime`,
        ],
      };
    case 'keyword_score':
      return {
        label: 'Keyword sinyalleri',
        value: [
          product?.category ? `Kategori: ${product.category}` : 'Kategori atanmis degil',
          tagCount ? `Etiketler: ${product?.tags.slice(0, 5).join(', ')}` : 'Etiket girilmemis',
          metaTitle ? `Meta title: ${metaTitle}` : 'Meta title girilmemis',
        ].join(' / '),
        metrics: [
          product?.category ? 'Kategori var' : 'Kategori yok',
          `${tagCount} etiket`,
          metaTitle ? 'Meta title mevcut' : 'Meta title eksik',
        ],
      };
    case 'content_quality_score': {
      const uniqueWords = new Set(
        descriptionText
          .toLowerCase()
          .split(/\s+/)
          .filter((word) => word.length > 3),
      ).size;

      return {
        label: 'Icerik ornegi',
        value: descriptionText || 'Icerik bulunamadi.',
        metrics: [
          `${countWords(descriptionText)} kelime`,
          `${uniqueWords} benzersiz kelime`,
          hasList(rawDescription) ? 'Liste var' : 'Liste yok',
        ],
      };
    }
    case 'technical_seo_score':
      return {
        label: 'Teknik sinyaller',
        value: [
          product?.slug ? `Slug: /${product.slug}` : 'Slug girilmemis',
          product?.category ? `Kategori: ${product.category}` : 'Kategori yok',
          formatPrice(product?.price),
        ].join(' / '),
        metrics: [
          `${imageCount} gorsel`,
          `${tagCount} etiket`,
          typeof product?.price === 'number' && product.price > 0 ? 'Fiyat var' : 'Fiyat eksik',
        ],
      };
    case 'readability_score': {
      const sentenceCount = countSentences(descriptionText);
      const wordCount = countWords(descriptionText);
      const avgSentenceLength = sentenceCount ? Math.round(wordCount / sentenceCount) : 0;

      return {
        label: 'Okunabilirlik ozeti',
        value: descriptionText || 'Aciklama girilmemis.',
        metrics: [
          `${sentenceCount} cumle`,
          avgSentenceLength ? `Ort. ${avgSentenceLength} kelime/cumle` : 'Cumle yok',
          wordCount >= 80 ? 'Uzun metin' : 'Kisa metin',
        ],
      };
    }
    case 'ai_citability_score':
      return {
        label: 'AI icin somut veri',
        value: descriptionText || 'Aciklama girilmemis.',
        metrics: [
          `${countNumbers(descriptionText)} sayisal ifade`,
          hasUnits(descriptionText) ? 'Olcu/birim var' : 'Olcu yok',
          hasList(rawDescription) ? 'Liste var' : 'Liste yok',
        ],
      };
    default:
      return {
        label: 'Alan',
        value: 'Veri yok.',
        metrics: [],
      };
  }
}

function resolveFieldForIssue(issue: string): FieldDefinition | undefined {
  return FIELDS.find((field) => field.issueMatcher.test(issue));
}

function resolveIssueTone(issue: string): string {
  if (/bos|yok|eksik|tanimlanmamis|cok kisa|cok uzun/i.test(issue)) {
    return '#f87171';
  }
  if (/biraz|orta|az/i.test(issue)) {
    return '#fbbf24';
  }
  return '#fb923c';
}

function CategoryCard({
  cat,
  value,
  index,
}: {
  cat: CategoryDefinition;
  value: number;
  index: number;
}) {
  const color = getScoreColor(value);
  const displayValue = useCountUp(value, 900, 240 + index * 140);
  const statusText = getFieldStatusText(value);
  const statusBadge = getStatusBadgeStyle(value);

  return (
    <div
      className="score-section-enter relative overflow-hidden rounded-[24px] px-4 py-4 transition-transform duration-200 hover:-translate-y-0.5"
      style={{
        animationDelay: `${220 + index * 120}ms`,
        ...getCategoryCardStyle(cat.accent),
      }}
    >
      <div
        className="score-glow-drift absolute -right-8 -top-8 h-28 w-28 rounded-full blur-3xl"
        style={{ background: `${cat.accent}28` }}
      />
      <div className="relative flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-2xl"
            style={{ background: `${cat.accent}20`, color: cat.accent }}
          >
            {cat.icon}
          </div>
          <div>
            <div
              className="text-[10px] font-semibold uppercase tracking-[0.18em]"
              style={{ color: 'var(--color-text-muted)' }}
            >
              Kategori
            </div>
            <div className="text-[15px] font-semibold" style={{ color: cat.accent }}>
              {cat.label}
            </div>
          </div>
        </div>
        <span className="rounded-full px-2.5 py-1 text-[10px] font-semibold" style={statusBadge}>
          {statusText}
        </span>
      </div>

      <div className="relative mt-4 flex items-end gap-1.5">
        <span className="text-[32px] font-bold leading-none" style={{ color }}>
          {displayValue}
        </span>
        <span className="text-[12px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
          /100
        </span>
      </div>

      <p className="relative mt-2 text-[12px] leading-5" style={{ color: 'var(--color-text-secondary)' }}>
        {cat.description}
      </p>

      <div className="relative mt-3">
        <ProgressBar pct={value} animated delay={520 + index * 120} />
      </div>

      <div
        className="relative mt-3 rounded-2xl px-3 py-2 text-[11px] leading-5"
        style={{ background: 'rgba(15,23,42,0.52)', border: `1px solid ${cat.accent}1f`, color: '#dbeafe' }}
      >
        <span className="font-semibold" style={{ color: cat.accent }}>
          Odak:
        </span>{' '}
        {cat.focus}
      </div>
    </div>
  );
}

function HeroMetricCard({
  label,
  value,
  helper,
  accent,
  index,
}: {
  label: string;
  value: string;
  helper: string;
  accent: string;
  index: number;
}) {
  return (
    <div
      className="score-field-enter rounded-2xl px-3.5 py-3"
      style={{
        animationDelay: `${260 + index * 60}ms`,
        background: `linear-gradient(180deg, ${accent}14, rgba(15,23,42,0.68))`,
        border: `1px solid ${accent}26`,
      }}
    >
      <div className="flex items-center gap-2">
        <span className="animate-pulse-dot h-2 w-2 rounded-full" style={{ background: accent }} />
        <span className="text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: 'var(--color-text-muted)' }}>
          {label}
        </span>
      </div>
      <div className="mt-2 text-[15px] font-semibold" style={{ color: accent }}>
        {value}
      </div>
      <div className="mt-1 text-[11px] leading-5" style={{ color: 'var(--color-text-secondary)' }}>
        {helper}
      </div>
    </div>
  );
}

function ProductSnapshotCard({ product }: { product?: Product | null }) {
  const primaryImage = getPrimaryImage(product);
  const title = product?.name?.trim() || 'Urun bilgisi bulunamadi';
  const metaTitle = product?.meta_title?.trim() || 'Meta title girilmemis';
  const metaDescription = product?.meta_description?.trim() || 'Meta description girilmemis';

  return (
    <div
      className="score-section-enter relative overflow-hidden rounded-[28px] p-4"
      style={{
        animationDelay: '140ms',
        background: 'linear-gradient(180deg, rgba(15,23,42,0.96), rgba(15,23,42,0.82))',
        border: '1px solid rgba(148,163,184,0.16)',
        boxShadow: '0 16px 38px rgba(2, 6, 23, 0.32)',
      }}
    >
      <div className="score-glow-drift absolute right-2 top-0 h-24 w-24 rounded-full bg-cyan-400/10 blur-3xl" />

      <div className="relative flex items-start gap-3">
        {primaryImage ? (
          <img
            src={primaryImage}
            alt={title}
            className="rounded-2xl object-cover"
            style={{ height: 72, width: 72, border: '1px solid rgba(255,255,255,0.08)' }}
          />
        ) : (
          <div
            className="flex items-center justify-center rounded-2xl"
            style={{
              height: 72,
              width: 72,
              background: 'linear-gradient(135deg, rgba(99,102,241,0.18), rgba(6,182,212,0.14))',
              border: '1px solid rgba(148,163,184,0.16)',
              color: '#93c5fd',
            }}
          >
            <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5v10.5H3.75V6.75z" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 15l2.25-2.25a1.5 1.5 0 012.121 0L14.25 15l1.629-1.629a1.5 1.5 0 012.121 0L20.25 15" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 10.125a1.125 1.125 0 100-2.25 1.125 1.125 0 000 2.25z" />
            </svg>
          </div>
        )}

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className="rounded-full px-2.5 py-1 text-[10px] font-semibold"
              style={{ background: 'rgba(99,102,241,0.16)', color: '#a5b4fc' }}
            >
              Canli gorunum
            </span>
            {product?.category ? (
              <span
                className="rounded-full px-2.5 py-1 text-[10px] font-semibold"
                style={{ background: 'rgba(6,182,212,0.14)', color: '#67e8f9' }}
              >
                {product.category}
              </span>
            ) : null}
          </div>
          <div className="mt-2 text-[15px] font-semibold leading-6 text-white" style={PREVIEW_CLAMP_STYLE}>
            {title}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <span className="rounded-full px-2 py-1 text-[10px] font-medium" style={{ background: 'rgba(52,211,153,0.12)', color: '#6ee7b7' }}>
              {(product?.tags?.length ?? 0)} etiket
            </span>
            <span className="rounded-full px-2 py-1 text-[10px] font-medium" style={{ background: 'rgba(148,163,184,0.12)', color: '#cbd5e1' }}>
              {formatPrice(product?.price)}
            </span>
          </div>
        </div>
      </div>

      <div className="relative mt-4 space-y-2.5">
        {[
          { label: 'Urun adi', value: title, accent: FIELD_SECTION_ACCENTS.seo },
          { label: 'Meta title', value: metaTitle, accent: '#f59e0b' },
          { label: 'Meta desc', value: metaDescription, accent: metaDescription === 'Meta description girilmemis' ? '#f87171' : '#34d399' },
        ].map((item) => (
          <div
            key={item.label}
            className="rounded-2xl px-3.5 py-3"
            style={{
              background: 'rgba(15,23,42,0.54)',
              border: `1px solid ${item.accent}24`,
            }}
          >
            <div className="text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: item.accent }}>
              {item.label}
            </div>
            <div className="mt-1 text-[12px] leading-5" style={{ color: 'var(--color-text-primary)', ...PREVIEW_CLAMP_STYLE }}>
              {item.value}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PriorityCard({ item, index }: { item: FieldCardData; index: number }) {
  const leadIssue = item.issues[0];
  const leadSuggestion = item.suggestions[0];

  return (
    <div
      className="score-section-enter relative overflow-hidden rounded-[24px] px-4 py-4"
      style={{
        animationDelay: `${520 + index * 90}ms`,
        ...getSoftCardStyle(item.accent),
      }}
    >
      <div className="absolute -right-6 top-0 h-20 w-20 rounded-full blur-2xl" style={{ background: `${item.accent}1e` }} />

      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className="rounded-full px-2 py-1 text-[10px] font-semibold"
              style={{ background: `${item.accent}18`, color: item.accent }}
            >
              {item.field.label}
            </span>
            <span className="rounded-full px-2 py-1 text-[10px] font-semibold" style={item.badgeStyle}>
              {item.statusText}
            </span>
          </div>
          <div className="mt-3 flex items-end gap-1">
            <span className="text-[28px] font-bold leading-none" style={{ color: item.color }}>
              {item.value}
            </span>
            <span className="text-[12px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
              /{item.field.max}
            </span>
          </div>
        </div>
        <div
          className="rounded-2xl px-3 py-2 text-right"
          style={{ background: 'rgba(15,23,42,0.54)', border: `1px solid ${item.accent}1e` }}
        >
          <div className="text-[10px] uppercase tracking-[0.14em]" style={{ color: 'var(--color-text-muted)' }}>
            Oncelik
          </div>
          <div className="mt-1 text-[12px] font-semibold" style={{ color: item.accent }}>
            Hemen ele al
          </div>
        </div>
      </div>

      <p className="relative mt-3 text-[12px] leading-5" style={{ color: 'var(--color-text-secondary)' }}>
        {leadIssue || item.field.description}
      </p>

      <div className="relative mt-3">
        <ProgressBar pct={item.pct} animated delay={840 + index * 90} />
      </div>

      <div
        className="relative mt-3 rounded-2xl px-3 py-2.5 text-[12px] leading-5"
        style={{
          background: 'rgba(15,23,42,0.5)',
          border: `1px solid ${item.accent}18`,
          color: '#dbeafe',
        }}
      >
        <span className="font-semibold" style={{ color: item.accent }}>
          Sonraki adim:
        </span>{' '}
        {leadSuggestion || 'Bu alani guclendirmek icin ilgili icerik ve meta sinyallerini guncelle.'}
      </div>
    </div>
  );
}

function FieldDetailCard({ item, index }: { item: FieldCardData; index: number }) {
  return (
    <article
      className="score-section-enter relative overflow-hidden rounded-[26px] p-4 transition-transform duration-200 hover:-translate-y-0.5"
      style={{
        animationDelay: `${680 + index * 55}ms`,
        ...getSoftCardStyle(item.accent),
      }}
    >
      <div className="score-glow-drift absolute -right-6 -top-6 h-24 w-24 rounded-full blur-3xl" style={{ background: `${item.accent}18` }} />

      <div className="relative flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className="rounded-full px-2.5 py-1 text-[10px] font-semibold"
              style={{ background: `${item.accent}18`, color: item.accent }}
            >
              {item.field.label}
            </span>
            <span className="rounded-full px-2.5 py-1 text-[10px] font-semibold" style={item.badgeStyle}>
              {item.statusText}
            </span>
          </div>
          <p className="mt-2 text-[12px] leading-5" style={{ color: 'var(--color-text-secondary)' }}>
            {item.field.description}
          </p>
        </div>

        <div
          className="min-w-[112px] rounded-2xl px-3 py-2"
          style={{ background: 'rgba(15,23,42,0.56)', border: `1px solid ${item.accent}24` }}
        >
          <div className="text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: 'var(--color-text-muted)' }}>
            Skor
          </div>
          <div className="mt-1 flex items-end gap-1">
            <span className="text-[26px] font-bold leading-none" style={{ color: item.color }}>
              {item.value}
            </span>
            <span className="text-[12px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
              /{item.field.max}
            </span>
          </div>
        </div>
      </div>

      <div className="relative mt-3">
        <ProgressBar pct={item.pct} animated delay={920 + index * 55} height="h-1.5" />
      </div>

      <div
        className="relative mt-4 rounded-[22px] px-3.5 py-3.5"
        style={{
          background: 'rgba(15,23,42,0.56)',
          border: `1px solid ${item.accent}1e`,
        }}
      >
        <div className="text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: item.accent }}>
          {item.preview.label}
        </div>
        <p className="mt-2 text-[13px] leading-6" style={{ color: 'var(--color-text-primary)', ...PREVIEW_CLAMP_STYLE }}>
          {truncateText(item.preview.value, 260)}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {item.preview.metrics.map((metric) => (
            <span
              key={`${item.field.key}-${metric}`}
              className="rounded-full px-2.5 py-1 text-[10px] font-medium"
              style={{ background: 'rgba(148,163,184,0.12)', color: '#cbd5e1' }}
            >
              {metric}
            </span>
          ))}
        </div>
      </div>

      <div className="relative mt-4 grid gap-3 xl:grid-cols-[1.08fr_0.92fr]">
        <div
          className="rounded-[22px] px-3.5 py-3.5"
          style={{ background: 'rgba(15,23,42,0.54)', border: '1px solid rgba(148,163,184,0.12)' }}
        >
          <div className="text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: 'var(--color-text-muted)' }}>
            Neden bu skor?
          </div>
          <div className="mt-2 space-y-2.5">
            {item.issues.length > 0 ? (
              item.issues.slice(0, 2).map((issue) => (
                <div key={`${item.field.key}-${issue}`} className="rounded-2xl px-3 py-2.5" style={{ background: 'rgba(255,255,255,0.02)' }}>
                  <div className="text-[12px] font-semibold leading-5 text-white">{issue}</div>
                  <div className="mt-1 text-[11px] leading-5" style={{ color: 'var(--color-text-secondary)' }}>
                    {explainIssue(issue)}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-[12px] leading-6" style={{ color: 'var(--color-text-secondary)' }}>
                Bu alanda belirgin bir kritik issue gorunmuyor. Mevcut yapiyi koruyup ince ayarlarla gucu sabitleyebilirsin.
              </p>
            )}
          </div>
        </div>

        <div
          className="rounded-[22px] px-3.5 py-3.5"
          style={{ background: 'rgba(15,23,42,0.54)', border: '1px solid rgba(148,163,184,0.12)' }}
        >
          <div className="text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: 'var(--color-text-muted)' }}>
            Siradaki aksiyon
          </div>
          <div className="mt-2 space-y-2">
            {item.suggestions.length > 0 ? (
              item.suggestions.slice(0, 2).map((suggestion) => (
                <div
                  key={`${item.field.key}-${suggestion}`}
                  className="rounded-2xl px-3 py-2.5 text-[12px] leading-5"
                  style={{ background: `${item.accent}12`, border: `1px solid ${item.accent}20`, color: '#e2e8f0' }}
                >
                  {suggestion}
                </div>
              ))
            ) : (
              <p className="text-[12px] leading-6" style={{ color: 'var(--color-text-secondary)' }}>
                Alan dengeli gorunuyor. Yeni icerik eklerken bu kalite cizgisini korumak yeterli.
              </p>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

function IssueCard({
  issue,
  index,
  field,
  suggestion,
}: {
  issue: string;
  index: number;
  field?: FieldDefinition;
  suggestion?: string;
}) {
  const accent = field ? FIELD_SECTION_ACCENTS[field.section] : resolveIssueTone(issue);

  return (
    <article
      className="score-field-enter rounded-[24px] px-4 py-4"
      style={{
        animationDelay: `${index * 45}ms`,
        background: 'linear-gradient(180deg, rgba(15,23,42,0.84), rgba(15,23,42,0.74))',
        border: `1px solid ${accent}24`,
      }}
    >
      <div className="flex items-start gap-3">
        <div
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-2xl text-[12px] font-semibold"
          style={{ background: `${accent}18`, color: accent }}
        >
          {index + 1}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {field ? (
              <span
                className="rounded-full px-2.5 py-1 text-[10px] font-semibold"
                style={{ background: `${accent}18`, color: accent }}
              >
                {field.label}
              </span>
            ) : null}
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
              Sorun
            </span>
          </div>

          <p className="mt-2 text-[13px] font-semibold leading-6 text-white">
            {issue}
          </p>
          <p className="mt-2 text-[12px] leading-6" style={{ color: 'var(--color-text-secondary)' }}>
            {explainIssue(issue)}
          </p>

          {suggestion ? (
            <div
              className="mt-3 rounded-2xl px-3 py-2.5"
              style={{ background: `${accent}10`, border: `1px solid ${accent}1c` }}
            >
              <div className="text-[10px] font-semibold uppercase tracking-[0.14em]" style={{ color: accent }}>
                Onerilen aksiyon
              </div>
              <div className="mt-1 text-[12px] leading-5" style={{ color: '#e2e8f0' }}>
                {suggestion}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function SeoScoreChatMessage({
  score,
  product,
}: {
  score: SeoScore;
  product?: Product | null;
}) {
  const totalPct = score.total_score;
  const totalColor = getScoreColor(totalPct);
  const totalStatusText = getFieldStatusText(totalPct);
  const totalStatusBadge = getStatusBadgeStyle(totalPct);

  const categoryScores = CATEGORIES.map((cat) => ({
    ...cat,
    value: score[cat.key],
  }));
  const strongestCategory = categoryScores.reduce((best, current) =>
    current.value > best.value ? current : best,
  );
  const weakestCategory = categoryScores.reduce((worst, current) =>
    current.value < worst.value ? current : worst,
  );

  const heroMetrics = getHeroMetrics(product);

  const fieldCards: FieldCardData[] = FIELDS.map((field) => {
    const value = score[field.key];
    const pct = (value / field.max) * 100;

    return {
      field,
      value,
      pct,
      color: getScoreColor(pct),
      badgeStyle: getStatusBadgeStyle(pct),
      statusText: getFieldStatusText(pct),
      accent: FIELD_SECTION_ACCENTS[field.section],
      preview: getFieldPreview(field.key, product),
      issues: score.issues.filter((issue) => field.issueMatcher.test(issue)),
      suggestions: score.suggestions.filter((suggestion) => field.suggestionMatcher.test(suggestion)),
    };
  });

  const prioritizedFields = [...fieldCards]
    .sort((left, right) => left.pct - right.pct)
    .slice(0, 3);
  const heroSummary = buildHeroSummary(score, product, weakestCategory, prioritizedFields);

  return (
    <div className="score-chat-message mr-6 space-y-0">
      <div
        className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-[0.16em]"
        style={{ color: 'var(--color-text-muted)' }}
      >
        SEO Analiz
      </div>

      <div
        className="relative overflow-hidden rounded-[28px]"
        style={{
          background: 'linear-gradient(180deg, rgba(17,24,39,0.98), rgba(15,23,42,0.92))',
          border: '1px solid rgba(148,163,184,0.16)',
          boxShadow: '0 22px 48px rgba(2, 6, 23, 0.38)',
        }}
      >
        <div className="score-glow-drift absolute -left-12 top-10 h-40 w-40 rounded-full bg-violet-500/10 blur-3xl" />
        <div className="score-glow-drift absolute right-0 top-0 h-40 w-40 rounded-full bg-cyan-400/10 blur-3xl" />

        <div
          className="px-4 py-4 sm:px-5 sm:py-5"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}
        >
          <div className="grid gap-4 xl:grid-cols-[1.25fr_0.95fr]">
            <div
              className="score-section-enter relative overflow-hidden rounded-[28px] px-4 py-4 sm:px-5"
              style={{
                animationDelay: '0ms',
                background: 'linear-gradient(135deg, rgba(30,41,59,0.74), rgba(15,23,42,0.92))',
                border: '1px solid rgba(148,163,184,0.16)',
              }}
            >
              <div className="score-glow-drift absolute -right-6 -top-10 h-28 w-28 rounded-full bg-violet-500/15 blur-3xl" />
              <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center">
                <CircularScore score={totalPct} size={86} strokeWidth={6} animated delay={120} />

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full px-2.5 py-1 text-[10px] font-semibold" style={totalStatusBadge}>
                      {totalStatusText}
                    </span>
                    <span className="text-[28px] font-bold leading-none" style={{ color: totalColor }}>
                      {score.total_score}
                    </span>
                    <span className="text-[12px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
                      /100
                    </span>
                  </div>

                  <p className="mt-2 text-[13px] leading-6" style={{ color: 'var(--color-text-secondary)' }}>
                    {heroSummary}
                  </p>

                  <div className="mt-3 flex flex-wrap gap-2">
                    <span className="rounded-full px-2.5 py-1 text-[10px] font-semibold" style={getCategoryHintStyle(strongestCategory.accent)}>
                      En guclu: {strongestCategory.label} {strongestCategory.value}/100
                    </span>
                    <span className="rounded-full px-2.5 py-1 text-[10px] font-semibold" style={getCategoryHintStyle(weakestCategory.accent)}>
                      Ilk odak: {weakestCategory.label} {weakestCategory.value}/100
                    </span>
                    <span className="rounded-full px-2.5 py-1 text-[10px] font-semibold" style={{ background: 'rgba(239,68,68,0.14)', border: '1px solid rgba(239,68,68,0.22)', color: '#f87171' }}>
                      {score.issues.length} acik issue
                    </span>
                    <span className="rounded-full px-2.5 py-1 text-[10px] font-semibold" style={{ background: 'rgba(59,130,246,0.14)', border: '1px solid rgba(59,130,246,0.22)', color: '#93c5fd' }}>
                      {score.suggestions.length} hazir aksiyon
                    </span>
                  </div>
                </div>
              </div>

              <div className="relative mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                {heroMetrics.map((metric, index) => (
                  <HeroMetricCard
                    key={metric.label}
                    label={metric.label}
                    value={metric.value}
                    helper={metric.helper}
                    accent={metric.accent}
                    index={index}
                  />
                ))}
              </div>
            </div>

            <ProductSnapshotCard product={product} />
          </div>
        </div>

        <div
          className="px-4 py-4"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}
        >
          <div
            className="score-section-enter mb-3 text-[10px] font-semibold uppercase tracking-[0.16em]"
            style={{ color: 'var(--color-text-muted)', animationDelay: '160ms' }}
          >
            Kategori Dengesi
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {categoryScores.map((cat, index) => (
              <CategoryCard key={cat.key} cat={cat} value={cat.value} index={index} />
            ))}
          </div>
        </div>

        <div
          className="px-4 py-4"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}
        >
          <div className="score-section-enter mb-3" style={{ animationDelay: '320ms' }}>
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
              Hemen Odaklan
            </div>
            <p className="mt-1 text-[13px] leading-6" style={{ color: 'var(--color-text-secondary)' }}>
              En dusuk puanli alanlari on tarafa alip kullaniciyi dogrudan aksiyona tasiyan onboarding kartlari.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 xl:grid-cols-3">
            {prioritizedFields.map((item, index) => (
              <PriorityCard key={item.field.key} item={item} index={index} />
            ))}
          </div>
        </div>

        <div
          className="px-4 py-4"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}
        >
          <div className="score-section-enter mb-3" style={{ animationDelay: '420ms' }}>
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
              Alan Derinligi
            </div>
            <p className="mt-1 text-[13px] leading-6" style={{ color: 'var(--color-text-secondary)' }}>
              Her alanda mevcut degeri, skoru dusuren nedeni ve sonraki aksiyonu ayni kartta gor.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 2xl:grid-cols-2">
            {fieldCards.map((item, index) => (
              <FieldDetailCard key={item.field.key} item={item} index={index} />
            ))}
          </div>
        </div>

        {score.issues.length > 0 ? (
          <div className="px-4 py-4">
            <div className="score-section-enter mb-3" style={{ animationDelay: '520ms' }}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
                  Sorun Haritasi
                </span>
                <span
                  className="rounded-full px-2.5 py-1 text-[10px] font-semibold"
                  style={{ background: 'rgba(239,68,68,0.14)', border: '1px solid rgba(239,68,68,0.22)', color: '#f87171' }}
                >
                  {score.issues.length} sorun acik gorunumde
                </span>
              </div>
              <p className="mt-1 text-[13px] leading-6" style={{ color: 'var(--color-text-secondary)' }}>
                Liste kapali degil. Her issue daha buyuk tipografi, alan etiketi ve neden onemli aciklamasiyla acik sekilde sunuluyor.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-3 2xl:grid-cols-2">
              {score.issues.map((issue, index) => {
                const field = resolveFieldForIssue(issue);
                const suggestion = field
                  ? score.suggestions.find((item) => field.suggestionMatcher.test(item))
                  : undefined;

                return (
                  <IssueCard
                    key={`${issue}-${index}`}
                    issue={issue}
                    index={index}
                    field={field}
                    suggestion={suggestion}
                  />
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default memo(SeoScoreChatMessage);
