import { useMemo, useState, useRef, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { EnterpriseButton } from '../shared/ui/EnterprisePrimitives';
import {
  generateLlmsTxt,
  getLlmsStatus,
  listLlmsPending,
  listLlmsProcessed,
  regenerateLlmsSummary,
  pauseLlmsJob,
  resumeLlmsJob,
  startLlmsJob,
  stopLlmsJob,
} from '../api/client';
import type { LlmsEntrySummary, LlmsStatus } from '../types';

function StatCard({
  label,
  value,
  accent,
  onClick,
}: {
  label: string;
  value: number | string;
  accent: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="enterprise-list-item flex flex-col gap-1 rounded-2xl p-4 text-left shadow-lg transition-all duration-200 hover:-translate-y-0.5 hover:shadow-xl"
    >
      <span className="text-[11px] uppercase tracking-[0.08em]" style={{ color: 'var(--color-text-muted)' }}>
        {label}
      </span>
      <span className="text-3xl font-bold tracking-tight" style={{ color: accent }}>
        {value}
      </span>
    </button>
  );
}

function ProductPill({
  title,
  subtitle,
  glow,
}: {
  title: string;
  subtitle?: string;
  glow: string;
}) {
  return (
    <div
      className="enterprise-list-item flex items-center justify-between rounded-xl px-4 py-3 text-sm transition-all duration-200"
      style={{ boxShadow: `0 10px 40px ${glow}` }}
    >
      <div>
        <div className="text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>{title}</div>
        {subtitle && <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{subtitle}</div>}
      </div>
      <div
        className="h-2 w-2 rounded-full"
        style={{ background: glow.replace('0.28', '0.9') ?? '#22c55e' }}
      />
    </div>
  );
}

export default function LlmsLab() {
  const queryClient = useQueryClient();
  const listSectionRef = useRef<HTMLDivElement | null>(null);
  const [listMode, setListMode] = useState<'recent' | 'processed' | 'pending'>('recent');

  const statusQ = useQuery<LlmsStatus>({
    queryKey: ['llms-status'],
    queryFn: getLlmsStatus,
  refetchInterval: (query) => (query.state.data?.job?.status === 'running' ? 4000 : false),
});

  const processedQ = useQuery<{ items: LlmsEntrySummary[] }>({
    queryKey: ['llms-processed'],
    queryFn: () => listLlmsProcessed(),
    enabled: false,
  });

  const pendingQ = useQuery<{ items: LlmsEntrySummary[] }>({
    queryKey: ['llms-pending'],
    queryFn: () => listLlmsPending(),
    enabled: false,
  });

  const [regenTarget, setRegenTarget] = useState<string | null>(null);
  const regenMut = useMutation({
    mutationFn: (productId: string) => regenerateLlmsSummary(productId),
    onMutate: (productId) => setRegenTarget(productId),
    onSettled: (_, __) => {
      setRegenTarget(null);
      processedQ.refetch();
      statusQ.refetch();
    },
  });

  const downloadMut = useMutation({
    mutationFn: generateLlmsTxt,
    onSuccess: (text) => {
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'llms.txt';
      a.click();
      URL.revokeObjectURL(url);
    },
  });

  const startMut = useMutation({
    mutationFn: startLlmsJob,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['llms-status'] }),
  });
  const resumeMut = useMutation({
    mutationFn: resumeLlmsJob,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['llms-status'] }),
  });
  const pauseMut = useMutation({
    mutationFn: pauseLlmsJob,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['llms-status'] }),
  });
  const stopMut = useMutation({
    mutationFn: stopLlmsJob,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['llms-status'] }),
  });

  const status = statusQ.data;
  const counts = status?.counts;
  const jobStatus = status?.job?.status ?? 'idle';

  // scroll to list section when mode changes via stat cards
  useEffect(() => {
    if (listMode !== 'recent' && listSectionRef.current) {
      listSectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [listMode]);

  const actionButtons = useMemo(() => {
    const isRunning = jobStatus === 'running' || jobStatus === 'queued';
    if (!status?.job) {
      return (
        <EnterpriseButton onClick={() => startMut.mutate()} tone="success" size="md">
          Ozet Isini Baslat
        </EnterpriseButton>
      );
    }
    return (
      <div className="flex flex-wrap items-center gap-2">
        {!isRunning && (
          <EnterpriseButton onClick={() => resumeMut.mutate()} tone="primary" size="md">
            Devam Et
          </EnterpriseButton>
        )}
        {isRunning && (
          <EnterpriseButton onClick={() => pauseMut.mutate()} tone="warning" size="md">
            Duraklat
          </EnterpriseButton>
        )}
        <EnterpriseButton onClick={() => stopMut.mutate()} tone="danger" size="md">
          Durdur
        </EnterpriseButton>
        <EnterpriseButton onClick={() => downloadMut.mutate()} disabled={downloadMut.isPending} tone="neutral" size="md">
          {downloadMut.isPending ? 'Hazirlaniyor...' : 'llms.txt indir'}
        </EnterpriseButton>
      </div>
    );
  }, [jobStatus, status?.job, startMut, resumeMut, pauseMut, stopMut, downloadMut]);

  return (
    <div className="page-bg overflow-hidden">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div
              className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em]"
              style={{ background: 'rgba(16,185,129,0.16)', border: '1px solid rgba(16,185,129,0.35)', color: '#a7f3d0' }}
            >
              llms.txt Studio
              <span className="h-2 w-2 rounded-full" style={{ background: 'var(--color-success)' }} />
            </div>
            <h1 className="mt-3 text-3xl font-extrabold tracking-tight md:text-4xl" style={{ color: 'var(--color-text-primary)' }}>
              AI icin bilgi yogun llms.txt uretimi
            </h1>
            <p className="mt-2 max-w-2xl text-[13px]" style={{ color: 'var(--color-text-secondary)' }}>
              Urun aciklamalarini modele ozetlettir, islenmis ve yeni eklenen urunleri gor, istedigin an duraklat veya devam ettir.
            </p>
          </div>
          {actionButtons}
        </header>

        <section className="mt-8 grid gap-4 md:grid-cols-4">
          <StatCard label="Toplam urun" value={counts?.total_products ?? '—'} accent="#e2e8f0" />
          <StatCard
            label="Ozetlendi"
            value={counts?.processed ?? 0}
            accent="#34d399"
            onClick={() => {
              setListMode('processed');
              processedQ.refetch();
            }}
          />
          <StatCard
            label="Bekleyen"
            value={counts?.unprocessed ?? 0}
            accent="#fbbf24"
            onClick={() => {
              setListMode('pending');
              pendingQ.refetch();
            }}
          />
          <StatCard label="Hata" value={counts?.failed ?? 0} accent="#f472b6" />
        </section>

        <section className="mt-8 grid gap-6 md:grid-cols-2">
          <div className="enterprise-surface rounded-2xl p-5">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-[11px] uppercase tracking-[0.12em]" style={{ color: 'var(--color-text-muted)' }}>Anlık is parcalari</div>
                <div className="text-[17px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {jobStatus === 'running' ? 'Ozet olusturuluyor' : 'Beklemede'}
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
                <span className="h-2 w-2 rounded-full" style={{ background: jobStatus === 'running' ? 'var(--color-success)' : 'var(--color-warning)' }} />
                {jobStatus}
              </div>
            </div>
            {status?.current ? (
              <ProductPill
                title={status.current.product_name}
                subtitle={status.current.category ?? 'Kategori yok'}
                glow="rgba(34,197,94,0.28)"
              />
            ) : (
              <div
                className="rounded-xl px-4 py-6 text-[13px]"
                style={{ border: '1px dashed rgba(148,163,184,0.2)', color: 'var(--color-text-muted)' }}
              >
                Su an calisan bir parca yok. {jobStatus === 'running' ? 'Siradaki urun bekleniyor.' : 'Is baslat veya devam et.'}
              </div>
            )}
            <div className="mt-4 text-xs" style={{ color: 'var(--color-text-muted)' }}>
              Sıra otomatik saklanır; backend ayaktayken kaldığı yerden devam eder.
            </div>
          </div>

          <div className="enterprise-surface rounded-2xl p-5">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-[11px] uppercase tracking-[0.12em]" style={{ color: 'var(--color-text-muted)' }}>Yeni / islenmemis</div>
                <div className="text-[17px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {status?.unprocessed?.length ? `${status.unprocessed.length} aday` : 'Hepsi islenmis'}
                </div>
              </div>
            </div>
            <div className="flex flex-col gap-3">
              {status?.unprocessed?.slice(0, 6).map((p) => (
                <ProductPill
                  key={p.product_id}
                  title={p.product_name}
                  subtitle={p.category ?? 'Kategori yok'}
                  glow="rgba(251,191,36,0.26)"
                />
              ))}
              {!status?.unprocessed?.length && (
                <div
                  className="rounded-xl px-4 py-6 text-[13px]"
                  style={{ border: '1px dashed rgba(148,163,184,0.2)', color: 'var(--color-text-muted)' }}
                >
                  Tum urunler icin ozet var. Yeni eklenen urunler burada belirecek.
                </div>
              )}
            </div>
          </div>
        </section>

        <section
          ref={listSectionRef}
          className="enterprise-surface mt-8 rounded-2xl p-5"
        >
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="text-[11px] uppercase tracking-[0.12em]" style={{ color: 'var(--color-text-muted)' }}>Son ozetler</div>
              <div className="text-[17px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>AI icin hazir bloklar</div>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => { setListMode('processed'); processedQ.refetch(); }}
                className="rounded-xl px-3 py-1.5 text-[13px] font-medium transition-all duration-200"
                style={listMode === 'processed'
                  ? { background: 'linear-gradient(135deg, rgba(30,64,175,0.54), rgba(67,56,202,0.54))', border: '1px solid rgba(125,211,252,0.34)', color: '#e2e8f0' }
                  : { background: 'rgba(15,23,42,0.52)', border: '1px solid rgba(148,163,184,0.22)', color: 'var(--color-text-secondary)' }}
              >
                Tum ozetleri goster
              </button>
              <button
                type="button"
                onClick={() => { setListMode('pending'); pendingQ.refetch(); }}
                className="rounded-xl px-3 py-1.5 text-[13px] font-medium transition-all duration-200"
                style={listMode === 'pending'
                  ? { background: 'rgba(245,158,11,0.22)', border: '1px solid rgba(245,158,11,0.5)', color: '#fde68a' }
                  : { background: 'rgba(15,23,42,0.52)', border: '1px solid rgba(148,163,184,0.22)', color: 'var(--color-text-secondary)' }}
              >
                Bekleyenleri goster
              </button>
              <button
                type="button"
                onClick={() => setListMode('recent')}
                className="rounded-xl px-3 py-1.5 text-[13px] font-medium transition-all duration-200"
                style={listMode === 'recent'
                  ? { background: 'linear-gradient(135deg, rgba(30,64,175,0.54), rgba(67,56,202,0.54))', border: '1px solid rgba(125,211,252,0.34)', color: '#e2e8f0' }
                  : { background: 'rgba(15,23,42,0.52)', border: '1px solid rgba(148,163,184,0.22)', color: 'var(--color-text-secondary)' }}
              >
                Son eklenenler
              </button>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {(listMode === 'pending'
              ? []
              : listMode === 'processed'
                ? processedQ.data?.items ?? []
                : status?.latest_processed ?? []
            ).map((entry) => (
              <div
                key={entry.product_id}
                className="enterprise-list-item rounded-xl p-4 transition-all duration-200"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>{entry.product_name}</div>
                    <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{entry.category ?? 'Kategori yok'}</div>
                  </div>
                  <span
                    className="rounded-full px-2 py-1 text-[11px] font-semibold uppercase tracking-wide"
                    style={{ background: 'rgba(16,185,129,0.16)', border: '1px solid rgba(16,185,129,0.35)', color: '#a7f3d0' }}
                  >
                    Hazir
                  </span>
                </div>
                <p
                  className="mt-2 text-[13px] leading-relaxed"
                  style={{ whiteSpace: 'pre-line', color: 'var(--color-text-secondary)' }}
                >
                  {entry.summary}
                </p>
                <div className="mt-3 flex items-center justify-between text-[11px] uppercase tracking-[0.08em]" style={{ color: 'var(--color-text-muted)' }}>
                  <span>{new Date(entry.updated_at).toLocaleString('tr-TR')}</span>
                  <button
                    type="button"
                    onClick={() => regenMut.mutate(entry.product_id)}
                    disabled={regenTarget === entry.product_id || regenMut.isPending}
                    className="rounded-full px-3 py-1 text-[11px] font-semibold transition hover:-translate-y-0.5 disabled:opacity-50"
                    style={{ border: '1px solid rgba(16,185,129,0.4)', color: '#a7f3d0' }}
                  >
                    {regenTarget === entry.product_id ? 'Yeniden üretiliyor...' : 'Yeniden üret'}
                  </button>
                </div>
              </div>
            ))}
            {listMode !== 'pending' && !( (listMode === 'processed' ? processedQ.data?.items?.length : status?.latest_processed?.length) ) && (
              <div
                className="rounded-xl px-4 py-6 text-[13px]"
                style={{ border: '1px dashed rgba(148,163,184,0.2)', color: 'var(--color-text-muted)' }}
              >
                Henuz kaydedilmis ozet yok. Islem baslayinca sonuclar burada gorunecek.
              </div>
            )}

            {listMode === 'pending' && pendingQ.data?.items?.length ? (
              <div className="md:col-span-2">
                <div className="mb-2 text-[11px] uppercase tracking-[0.12em]" style={{ color: 'var(--color-warning)' }}>Bekleyenler</div>
                <div className="grid gap-2 md:grid-cols-2">
                  {pendingQ.data.items.map((p) => (
                    <div
                      key={p.product_id}
                      className="enterprise-list-item rounded-xl px-4 py-3 transition-all duration-200"
                    >
                      <div className="text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>{p.product_name}</div>
                      <div className="text-xs" style={{ color: 'var(--color-text-secondary)' }}>{p.category ?? 'Kategori yok'}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {listMode === 'pending' && pendingQ.isFetching && (
              <div
                className="md:col-span-2 rounded-xl px-4 py-6 text-center text-[13px]"
                style={{ border: '1px dashed rgba(245,158,11,0.3)', color: 'var(--color-warning)' }}
              >
                Bekleyenler yukleniyor...
              </div>
            )}

            {listMode === 'processed' && processedQ.isFetching && (
              <div
                className="md:col-span-2 rounded-xl px-4 py-6 text-center text-[13px]"
                style={{ border: '1px dashed rgba(148,163,184,0.25)', color: 'var(--color-text-secondary)' }}
              >
                Tum ozetler yukleniyor...
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
