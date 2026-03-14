import { SectionCard, StatusRow } from '../../components/settings/UiPrimitives';

interface LiveStatusCardProps {
  provider: string;
  model: string;
  storeName: string;
  languages: string;
  keywords: string;
  promptCount: number;
}

export default function LiveStatusCard({
  provider,
  model,
  storeName,
  languages,
  keywords,
  promptCount,
}: LiveStatusCardProps) {
  return (
    <SectionCard
      eyebrow="Durum"
      title="Canli Ozet"
      description="Kayitli konfigirasyonun aktif durumu."
    >
      <dl className="space-y-4 text-sm">
        <StatusRow label="Secili provider" value={provider} />
        <StatusRow label="Model" value={model || 'Secilmedi'} />
        <StatusRow label="Magaza" value={storeName || 'Tanimlanmadi'} />
        <StatusRow label="Diller" value={languages || 'tr'} />
        <StatusRow label="Keywords" value={keywords || 'Tanimsiz'} mono={false} />
        <StatusRow label="Promptlar" value={`${promptCount} duzenlenebilir dosya`} />
      </dl>
    </SectionCard>
  );
}
