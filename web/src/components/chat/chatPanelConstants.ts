import type { StarterPrompt } from './promptParams';

export const STARTER_PROMPTS: StarterPrompt[] = [
  {
    label: 'SEO metriklerini yorumla',
    template:
      'Bu mevcut SEO metriklerini alan bazinda yorumla ve sadece bu skorlara gore 3 oncelikli tavsiye ver.\n\n{seoMetricsSummary}',
  },
  {
    label: 'Urun aciklamasini yorumla',
    template: 'Bu urunun mevcut aciklamasini yorumla. Yalnizca eldeki metni kullan.\n\n{productDescription}',
  },
  {
    label: 'Meta titlei yorumla',
    template: 'Bu mevcut meta titlei SEO acisindan yorumla.\n\n{productMetaTitle}',
  },
  {
    label: 'Meta descriptioni yorumla',
    template:
      'Bu mevcut meta descriptioni SEO acisindan yorumla.\n\n{productMetaDescription}',
  },
];
