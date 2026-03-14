// ── Score color & status helpers (single source of truth) ────────────────────

export const SUMMARY_FIELDS = [
  {
    key: 'seo_score',
    label: 'SEO',
    description: 'Arama motoru gorunurlugu, meta sinyalleri ve teknik uygunluk.',
  },
  {
    key: 'geo_score',
    label: 'GEO',
    description: 'AI alintilanabilirlik ve generative engine uygunlugu.',
  },
  {
    key: 'aeo_score',
    label: 'AEO',
    description: 'Yanitlanabilirlik, icerik netligi ve answer-engine uyumu.',
  },
] as const;

export const SCORE_FIELDS = [
  { key: 'title_score', label: 'Baslik', max: 15, description: 'Urun adinin uzunlugu, okunabilirligi ve arama niyetiyle uyumu.' },
  { key: 'description_score', label: 'Aciklama', max: 20, description: 'Aciklamanin uzunlugu, paragraf yapisi ve zengin HTML kullanimi.' },
  { key: 'english_description_score', label: 'EN Aciklama', max: 5, description: 'Ingilizce aciklamanin varligi ve temel kalite seviyesi.' },
  { key: 'meta_score', label: 'Meta Title', max: 15, description: 'Arama sonucundaki basligin uzunlugu, farkliligi ve keyword uyumu.' },
  { key: 'meta_desc_score', label: 'Meta Description', max: 10, description: 'Arama sonucunda gorunen aciklama metninin ikna ediciligi.' },
  { key: 'keyword_score', label: 'Keyword Kullanimi', max: 10, description: 'Hedef kelimelerin urun metni ve meta alanlarda kullanimi.' },
  { key: 'content_quality_score', label: 'Icerik Kalitesi', max: 10, description: 'Kelime cesitliligi, tekrar kontrolu ve icerik tutarliligi.' },
  { key: 'technical_seo_score', label: 'Teknik SEO', max: 10, description: 'Gorsel, etiket, kategori, fiyat ve teknik sinyallerin tamligi.' },
  { key: 'readability_score', label: 'Okunabilirlik', max: 5, description: 'Cumle akisi, uzunluk dengesi ve gecis kelimeleri.' },
  { key: 'ai_citability_score', label: 'AI Alıntılanabilirlik', max: 10, description: 'Aciklamanin ChatGPT/Perplexity gibi yapay zekalar tarafından kaynak gösterilme potansiyeli (istatistik, teknik veri, objektif dil).' },
] as const;

export function getScoreColor(pct: number): string {
  if (pct >= 80) return 'var(--score-excellent)';
  if (pct >= 60) return 'var(--score-good)';
  if (pct >= 40) return 'var(--score-fair)';
  return 'var(--score-poor)';
}

export function getScoreGradient(pct: number): string {
  if (pct >= 80) return 'linear-gradient(135deg, #10b981, #06b6d4)';
  if (pct >= 60) return 'linear-gradient(135deg, #f59e0b, #f97316)';
  if (pct >= 40) return 'linear-gradient(135deg, #f97316, #ef4444)';
  return 'linear-gradient(135deg, #ef4444, #dc2626)';
}

export function getFieldStatusText(pct: number): string {
  if (pct >= 80) return 'Guclu';
  if (pct >= 60) return 'Gelistirilebilir';
  if (pct >= 40) return 'Zayif';
  return 'Kritik';
}

export function getStatusBadgeStyle(pct: number): { background: string; color: string } {
  if (pct >= 80) return { background: 'rgba(16, 185, 129, 0.15)', color: '#34d399' };
  if (pct >= 60) return { background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24' };
  if (pct >= 40) return { background: 'rgba(249, 115, 22, 0.15)', color: '#fb923c' };
  return { background: 'rgba(239, 68, 68, 0.15)', color: '#f87171' };
}

export function explainIssue(issue: string): string {
  const patterns: Array<[RegExp, string]> = [
    [/Urun adi .*kisa/i, 'Baslik kisa oldugunda urunun ne oldugu arama motoru ve kullanici tarafinda yeterince net anlasilmaz.'],
    [/Urun adi .*uzun/i, 'Cok uzun basliklar odagi dagitir, arama sonucunda kesilebilir ve ana urun sinyalini zayiflatir.'],
    [/Urun adinda ozel karakterler var/i, 'Ozel karakterler okunabilirligi dusurur, URL ve baslik temizligini bozabilir.'],
    [/Urun adinda cok fazla buyuk harf/i, 'Asiri buyuk harf kullanimi spam hissi verir ve basligin profesyonel gorunmesini zedeler.'],
    [/Aciklama cok kisa|Aciklama kisa|Aciklama yeterli ama ideal degil/i, 'Kisa aciklama urunun faydasini, ozelliklerini ve arama niyetini yeterince kapsamaz.'],
    [/Aciklamada paragraf yapisi yok/i, 'Paragraf yapisi olmadiginda metin zor taranir ve kullanici sayfada daha cabuk kopar.'],
    [/Aciklamada yapisal HTML ogeleri eksik/i, 'Baslik ve liste gibi yapilar hem kullanicinin hizli okumasini hem de icerigin daha net anlasilmasini saglar.'],
    [/Ingilizce aciklama eksik/i, 'Ingilizce icerik olmadiginda yabanci dil aramalarinda urunun gorunurlugu ve anlasilirligi duser.'],
    [/Ingilizce aciklama .*kisa/i, 'Kisa Ingilizce metin urunu yabanci kullaniciya yeterince anlatmaz.'],
    [/Ingilizce aciklamada Turkce karakterler var/i, 'Dil tutarsizligi kalite sinyalini dusurur ve metnin profesyonelligini zedeler.'],
    [/Meta title .*kisa/i, 'Kisa meta title arama sonucunda sayfanin konusunu ve anahtar kelimesini yeterince tasiyamaz.'],
    [/Meta title .*uzun/i, 'Uzun meta title arama sonucunda kesilir ve onemli mesajin bir kismi gorunmez.'],
    [/Meta title urun adiyla ayni/i, 'Meta title urun adiyla birebir ayniysa arama sonucunda ek baglam ve farklilastirici sinyal verilmez.'],
    [/Meta description .*kisa/i, 'Kisa meta description kullaniciyi tiklamaya ikna edecek yeterli baglami sunmaz.'],
    [/Meta description .*uzun/i, 'Uzun meta description kesilecegi icin mesajin onemli kismi arama sonucunda kaybolur.'],
    [/Kategori adi .*icerikde gecmiyor/i, 'Kategori sinyali zayif oldugunda sayfanin hangi arama grubuna ait oldugu daha az net olur.'],
    [/Hedef keywordler aciklamada yok/i, 'Hedef kelimeler aciklamada gecmezse ilgili aramalarda metnin eslesme gucu azalir.'],
    [/Hedef keywordlerden hicbiri meta title'da yok/i, 'Title alaninda hedef kelime olmamasi arama niyetini yakalamayi zorlastirir.'],
    [/kelimesi cok sik tekrarlaniyor/i, 'Ayni kelimenin fazla tekrari dogal akisi bozar ve asiri optimizasyon izlenimi verebilir.'],
    [/Kelime cesitliligi dusuk|Kelime cesitliligi orta/i, 'Daha zengin kelime kullanimi hem icerigi daha dogal yapar hem de konuyu daha iyi kapsar.'],
    [/Tekrarlanan ifadeler tespit edildi/i, 'Tekrar eden kaliplar metni yapay ve tekduze gosterir.'],
    [/Urun adi ile aciklama arasinda icerik uyumsuzlugu var/i, 'Baslik ve aciklama farkli seyler anlattiginda sayfa niyeti tutarsiz gorunur.'],
    [/Urun gorseli yok/i, 'Gorsel eksikligi hem guveni hem de urunun algilanan kalitesini dusurur.'],
    [/Urun etiketleri \(tag\) bos|Etiket sayisi az/i, 'Etiketler urunun ic organizasyonunu ve filtrelenebilirligini destekler.'],
    [/Urun kategorisi tanimlanmamis/i, 'Kategori eksikligi urunu dogru baglamda siniflandirmayi zorlastirir.'],
    [/Urun (adi|slug'i) URL-dostu degil/i, 'Temiz ve okunabilir slug yapisi hem SEO hem de kullanici deneyimi acisindan faydalidir.'],
    [/Urun fiyati tanimlanmamis/i, 'Fiyat bilgisi eksik oldugunda satin alma karari ve zengin sonuc potansiyeli zayiflar.'],
    [/Aciklamada yeterli cumle yapisi yok/i, 'Parcali veya eksik cumle yapisi icerigin kalitesiz algilanmasina neden olabilir.'],
    [/Cumleler .*uzun/i, 'Uzun cumleler ozellikle mobilde okunabilirligi dusurur ve ana mesaji geciktirir.'],
    [/Cumle uzunluklari cok monoton/i, 'Tek tip ritim metni robotik hissettirir ve okuma akisini zayiflatir.'],
    [/Gecis kelimeleri eksik/i, 'Gecis kelimeleri olmadiginda metin kopuk okunur ve fikirler arasindaki bag zayif kalir.'],
  ];

  for (const [pattern, explanation] of patterns) {
    if (pattern.test(issue)) {
      return explanation;
    }
  }

  return 'Bu sorun, sayfanin arama motoruna verdigi sinyali veya kullanicinin icerigi anlama hizini zayiflatir.';
}
