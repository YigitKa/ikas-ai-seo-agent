import { EnterpriseSectionCard, EnterpriseStatusRow } from '../../shared/ui/EnterprisePrimitives';

interface LiveStatusCardProps {
  provider: string;
  model: string;
  storeName: string;
  languages: string;
  keywords: string;
}

export default function LiveStatusCard({
  provider,
  model,
  storeName,
  languages,
  keywords,
}: LiveStatusCardProps) {
  return (
    <EnterpriseSectionCard
      eyebrow="Durum"
      title="Canli Ozet"
      description="Kayitli konfigirasyonun aktif durumu."
    >
      <dl className="space-y-4">
        <EnterpriseStatusRow label="Secili provider" value={provider} />
        <EnterpriseStatusRow label="Model" value={model || 'Secilmedi'} />
        <EnterpriseStatusRow label="Magaza" value={storeName || 'Tanimlanmadi'} />
        <EnterpriseStatusRow label="Diller" value={languages || 'tr'} />
        <EnterpriseStatusRow label="Keywords" value={keywords || 'Tanimsiz'} mono={false} />
      </dl>
    </EnterpriseSectionCard>
  );
}
