import type { SeoScore } from '../types';

interface Props {
  score: SeoScore;
}

const FIELDS = [
  {
    key: 'title_score',
    label: 'Baslik',
    max: 15,
    description: 'Urun adinin uzunlugu, okunabilirligi ve arama niyetiyle uyumu.',
  },
  {
    key: 'description_score',
    label: 'Aciklama',
    max: 20,
    description: 'Aciklamanin uzunlugu, paragraf yapisi ve zengin HTML kullanimi.',
  },
  {
    key: 'english_description_score',
    label: 'EN Aciklama',
    max: 5,
    description: 'Ingilizce aciklamanin varligi ve temel kalite seviyesi.',
  },
  {
    key: 'meta_score',
    label: 'Meta Title',
    max: 15,
    description: 'Arama sonucundaki basligin uzunlugu, farkliligi ve keyword uyumu.',
  },
  {
    key: 'meta_desc_score',
    label: 'Meta Description',
    max: 10,
    description: 'Arama sonucunda gorunen aciklama metninin ikna ediciligi.',
  },
  {
    key: 'keyword_score',
    label: 'Keyword Kullanimi',
    max: 10,
    description: 'Hedef kelimelerin urun metni ve meta alanlarda kullanimi.',
  },
  {
    key: 'content_quality_score',
    label: 'Icerik Kalitesi',
    max: 10,
    description: 'Kelime cesitliligi, tekrar kontrolu ve icerik tutarliligi.',
  },
  {
    key: 'technical_seo_score',
    label: 'Teknik SEO',
    max: 10,
    description: 'Gorsel, etiket, kategori, fiyat ve teknik sinyallerin tamligi.',
  },
  {
    key: 'readability_score',
    label: 'Okunabilirlik',
    max: 5,
    description: 'Cumle akisi, uzunluk dengesi ve gecis kelimeleri.',
  },
] as const;

function getScoreColor(pct: number): string {
  if (pct >= 80) return '#10b981';
  if (pct >= 60) return '#f59e0b';
  if (pct >= 40) return '#f97316';
  return '#ef4444';
}

function getScoreGradient(pct: number): string {
  if (pct >= 80) return 'linear-gradient(135deg, #10b981, #06b6d4)';
  if (pct >= 60) return 'linear-gradient(135deg, #f59e0b, #f97316)';
  if (pct >= 40) return 'linear-gradient(135deg, #f97316, #ef4444)';
  return 'linear-gradient(135deg, #ef4444, #dc2626)';
}

function getFieldStatusText(pct: number): string {
  if (pct >= 80) return 'Guclu';
  if (pct >= 60) return 'Gelistirilebilir';
  if (pct >= 40) return 'Zayif';
  return 'Kritik';
}

function explainIssue(issue: string): string {
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

function CircularScore({ score }: { score: number }) {
  const size = 104;
  const strokeWidth = 6;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = getScoreColor(score);

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg className="score-ring" width={size} height={size}>
        <circle
          className="score-ring-track"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
        />
        <circle
          className="score-ring-fill"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={strokeWidth}
          stroke={color}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-2xl font-bold" style={{ color }}>
          {score}
        </span>
        <span className="text-[10px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
          /100
        </span>
      </div>
    </div>
  );
}

export default function ScoreCard({ score }: Props) {
  return (
    <div
      className="rounded-xl p-5"
      style={{
        background: 'var(--glass-bg)',
        border: '1px solid var(--color-border)',
      }}
    >
      <div className="flex items-center gap-4 pb-4" style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <CircularScore score={score.total_score} />
        <div className="min-w-0 flex-1">
          <div
            className="text-[10px] font-semibold uppercase tracking-[0.18em]"
            style={{ color: 'var(--color-text-muted)' }}
          >
            SEO Skoru
          </div>
          <div className="mt-1 text-[18px] font-semibold text-white">
            Genel durum: {getFieldStatusText(score.total_score)}
          </div>
          <p className="mt-2 text-[12px] leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
            Asagidaki her satir, SEO puaninin hangi alandan geldigini ve o alanin neyi olctugunu aciklar.
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {FIELDS.map(({ key, label, max, description }) => {
          const val = score[key] as number;
          const pct = (val / max) * 100;
          const color = getScoreColor(pct);

          return (
            <div
              key={key}
              className="rounded-xl px-4 py-3"
              style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-semibold text-white">{label}</div>
                  <p className="mt-1 text-[12px] leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
                    {description}
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-[14px] font-semibold" style={{ color }}>
                    {val}<span style={{ color: 'var(--color-text-muted)' }}>/{max}</span>
                  </div>
                  <div className="text-[10px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
                    {getFieldStatusText(pct)}
                  </div>
                </div>
              </div>

              <div
                className="mt-3 h-1.5 w-full overflow-hidden rounded-full"
                style={{ background: 'rgba(255,255,255,0.06)' }}
              >
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${pct}%`,
                    background: getScoreGradient(pct),
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-5">
        <div
          className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em]"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Tespit Edilen Sorunlar ({score.issues.length})
        </div>

        {score.issues.length > 0 ? (
          <div className="space-y-3">
            {score.issues.map((issue, index) => (
              <div
                key={`${issue}-${index}`}
                className="rounded-xl px-4 py-3"
                style={{
                  background: 'rgba(239, 68, 68, 0.05)',
                  border: '1px solid rgba(239, 68, 68, 0.12)',
                }}
              >
                <div className="flex items-start gap-2">
                  <span
                    className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full"
                    style={{ background: '#ef4444' }}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-[12px] font-medium text-white">{issue}</div>
                    <p className="mt-1 text-[12px] leading-relaxed" style={{ color: 'var(--color-text-secondary)' }}>
                      {explainIssue(issue)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div
            className="rounded-xl px-4 py-3 text-[12px]"
            style={{
              background: 'rgba(16, 185, 129, 0.06)',
              border: '1px solid rgba(16, 185, 129, 0.14)',
              color: '#a7f3d0',
            }}
          >
            Bu urun icin kritik bir SEO sorunu tespit edilmedi.
          </div>
        )}
      </div>
    </div>
  );
}
