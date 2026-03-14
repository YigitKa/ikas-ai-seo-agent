import { Banner, SectionCard, StatusRow } from '../../components/settings/UiPrimitives';
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
    <SectionCard
      eyebrow="LM Studio"
      title="Anlik Durum"
      description="Secili modelin loaded context bilgisini ve varsa indirme job durumunu gosterir."
    >
      <div className="space-y-4">
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-slate-200">Download Job ID</span>
          <input
            value={downloadJobId}
            onChange={(event) => onDownloadJobIdChange(event.target.value)}
            placeholder="Opsiyonel job id"
            className="h-11 w-full rounded-2xl border border-slate-700 bg-slate-950/90 px-4 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-sky-400"
          />
          <span className="mt-2 block text-xs leading-5 text-slate-500">
            Girersen `/api/v1/models/download/status/:job_id` ile anlik indirme bilgisi izlenir.
          </span>
        </label>

        {liveStatusError ? (
          <Banner
            tone="error"
            message={formatError(liveStatusError, 'LM Studio anlik durum bilgisi okunamadi.')}
          />
        ) : (
          <>
            <dl className="space-y-4 text-sm">
              <StatusRow
                label="Secili model"
                value={liveStatus?.selected_model?.display_name || fallbackModelName || 'Bilinmiyor'}
                mono={false}
              />
              <StatusRow
                label="Model durumu"
                value={liveStatus?.selected_model?.status || 'Bilinmiyor'}
                mono={false}
              />
              <StatusRow
                label="Loaded context"
                value={
                  typeof liveStatus?.selected_model?.context_length === 'number'
                    ? String(liveStatus.selected_model.context_length)
                    : 'Bilinmiyor'
                }
              />
            </dl>

            {liveStatus?.download_status && (
              <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
                <div className="text-sm font-medium text-white">Download Job</div>
                <dl className="mt-3 space-y-3 text-sm">
                  <StatusRow
                    label="Durum"
                    value={liveStatus.download_status.status || 'Bilinmiyor'}
                    mono={false}
                  />
                  <StatusRow
                    label="Indirilen"
                    value={formatByteProgress(
                      liveStatus.download_status.downloaded_bytes,
                      liveStatus.download_status.total_size_bytes,
                    )}
                    mono={false}
                  />
                  <StatusRow
                    label="Hiz"
                    value={
                      typeof liveStatus.download_status.bytes_per_second === 'number'
                        ? `${formatBytes(liveStatus.download_status.bytes_per_second)}/sn`
                        : 'Bilinmiyor'
                    }
                    mono={false}
                  />
                  <StatusRow
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
    </SectionCard>
  );
}
