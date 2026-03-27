import {
  EnterpriseBanner,
  EnterpriseField,
  EnterpriseSectionCard,
  EnterpriseStatusRow,
} from '../../shared/ui/EnterprisePrimitives';
import type { LMStudioLiveStatus } from '../../types';
import { formatBytes, formatByteProgress, formatError, formatIsoDateTime } from './constants';

interface LmStudioStatusCardProps {
  liveStatus?: LMStudioLiveStatus | null;
  liveStatusError?: Error | null;
  fallbackModelName: string;
  downloadJobId: string;
  onDownloadJobIdChange: (value: string) => void;
}

export default function LmStudioStatusCard({
  liveStatus,
  liveStatusError,
  fallbackModelName,
  downloadJobId,
  onDownloadJobIdChange,
}: LmStudioStatusCardProps) {
  return (
    <EnterpriseSectionCard
      eyebrow="LM Studio"
      title="Anlik Durum"
      description="Secili modelin loaded context bilgisini ve varsa indirme job durumunu gosterir."
    >
      <div className="space-y-4">
        <EnterpriseField
          label="Download Job ID"
          value={downloadJobId}
          onChange={onDownloadJobIdChange}
          placeholder="Opsiyonel job id"
          hint="Girersen `/api/v1/models/download/status/:job_id` ile anlik indirme bilgisi izlenir."
        />

        {liveStatusError ? (
          <EnterpriseBanner
            tone="error"
            message={formatError(liveStatusError, 'LM Studio anlik durum bilgisi okunamadi.')}
          />
        ) : (
          <>
            <dl className="space-y-4">
              <EnterpriseStatusRow
                label="Secili model"
                value={liveStatus?.selected_model?.display_name || fallbackModelName || 'Bilinmiyor'}
                mono={false}
              />
              <EnterpriseStatusRow
                label="Model durumu"
                value={liveStatus?.selected_model?.status || 'Bilinmiyor'}
                mono={false}
              />
              <EnterpriseStatusRow
                label="Loaded context"
                value={
                  typeof liveStatus?.selected_model?.context_length === 'number'
                    ? String(liveStatus.selected_model.context_length)
                    : 'Bilinmiyor'
                }
              />
            </dl>

            {liveStatus?.download_status && (
              <div
                className="enterprise-list-item rounded-xl p-4 transition-all duration-200"
              >
                <div className="mb-3 text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  Download Job
                </div>
                <dl className="space-y-3">
                  <EnterpriseStatusRow
                    label="Durum"
                    value={liveStatus.download_status.status || 'Bilinmiyor'}
                    mono={false}
                  />
                  <EnterpriseStatusRow
                    label="Indirilen"
                    value={formatByteProgress(
                      liveStatus.download_status.downloaded_bytes,
                      liveStatus.download_status.total_size_bytes,
                    )}
                    mono={false}
                  />
                  <EnterpriseStatusRow
                    label="Hiz"
                    value={
                      typeof liveStatus.download_status.bytes_per_second === 'number'
                        ? `${formatBytes(liveStatus.download_status.bytes_per_second)}/sn`
                        : 'Bilinmiyor'
                    }
                    mono={false}
                  />
                  <EnterpriseStatusRow
                    label="ETA"
                    value={formatIsoDateTime(liveStatus.download_status.estimated_completion)}
                    mono={false}
                  />
                </dl>
              </div>
            )}
          </>
        )}
      </div>
    </EnterpriseSectionCard>
  );
}
