/** Categorized starter prompt cards for the store-wide chat panel. */

export interface StoreChatPrompt {
  label: string;
  template: string;
}

export interface StoreChatCategory {
  id: string;
  icon: string;
  label: string;
  prompts: StoreChatPrompt[];
}

export const STORE_CHAT_CATEGORIES: StoreChatCategory[] = [
  {
    id: 'orders',
    icon: '\u{1F4E6}',
    label: 'Siparisler',
    prompts: [
      { label: 'Son siparisleri goster', template: 'Son siparisleri listele.' },
      { label: 'Bekleyen siparisler', template: 'Bekleyen veya onay bekleyen siparisleri goster.' },
      { label: 'Bugunun satislari', template: 'Bugunun satis ozetini cikar.' },
    ],
  },
  {
    id: 'stock',
    icon: '\u{1F4CA}',
    label: 'Stok',
    prompts: [
      { label: 'Dusuk stok urunler', template: 'Stoku kritik seviyede olan urunleri listele.' },
      { label: 'Stok ozeti', template: 'Genel stok durumunu ozetle.' },
    ],
  },
  {
    id: 'customers',
    icon: '\u{1F465}',
    label: 'Musteriler',
    prompts: [
      { label: 'Son musteriler', template: 'Son kayit olan musterileri listele.' },
      { label: 'En cok siparis veren', template: 'En cok siparis veren musterileri goster.' },
    ],
  },
  {
    id: 'products',
    icon: '\u{1F3F7}\u{FE0F}',
    label: 'Urunler',
    prompts: [
      { label: 'Urun listesi', template: 'Urunlerimi listele.' },
      { label: 'Kategoriler', template: 'Urun kategorilerimi goster.' },
      { label: 'Fiyat analizi', template: 'Urun fiyatlarimin genel dagilimini ozetle.' },
    ],
  },
  {
    id: 'seo',
    icon: '\u{1F50D}',
    label: 'SEO',
    prompts: [
      { label: 'SEO ozeti', template: 'Magazamin genel SEO durumunu ozetle.' },
      { label: 'Dusuk skorlu urunler', template: 'SEO skoru dusuk urunleri listele.' },
      { label: 'Oncelikli iyilestirmeler', template: 'En acil iyilestirmem gereken SEO alanlari neler?' },
    ],
  },
  {
    id: 'campaigns',
    icon: '\u{1F3AF}',
    label: 'Kampanyalar',
    prompts: [
      { label: 'Aktif kampanyalar', template: 'Aktif kampanya ve indirimleri goster.' },
      { label: 'Indirim kurallari', template: 'Mevcut indirim kurallarini listele.' },
    ],
  },
];
