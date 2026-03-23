import { useMemo, useState, useRef, useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
      className="flex flex-col gap-1 rounded-2xl p-4 text-left shadow-lg transition hover:-translate-y-0.5 hover:shadow-xl"
      style={{
        background: 'linear-gradient(145deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02))',
        border: '1px solid rgba(255,255,255,0.08)',
      }}
    >
      <span className="text-xs uppercase tracking-[0.08em]" style={{ color: 'rgba(226,232,240,0.7)' }}>
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
      className="flex items-center justify-between rounded-xl px-4 py-3 text-sm"
      style={{
        background: 'rgba(15,23,42,0.4)',
        border: '1px solid rgba(255,255,255,0.06)',
        boxShadow: `0 10px 40px ${glow}`,
      }}
    >
      <div>
        <div className="font-semibold text-slate-50">{title}</div>
        {subtitle && <div className="text-xs text-slate-400">{subtitle}</div>}
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
        <button
          onClick={() => startMut.mutate()}
          className="rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-500 px-4 py-2 text-sm font-semibold text-white shadow-lg transition hover:opacity-90"
        >
          Ozet Isini Baslat
        </button>
      );
    }
    return (
      <div className="flex flex-wrap items-center gap-2">
        {!isRunning && (
          <button
            onClick={() => resumeMut.mutate()}
            className="rounded-lg bg-gradient-to-r from-indigo-500 to-blue-500 px-3 py-2 text-sm font-semibold text-white shadow-lg transition hover:opacity-90"
          >
            Devam Et
          </button>
        )}
        {isRunning && (
          <button
            onClick={() => pauseMut.mutate()}
            className="rounded-lg bg-gradient-to-r from-amber-500 to-orange-500 px-3 py-2 text-sm font-semibold text-white shadow-lg transition hover:opacity-90"
          >
            Duraklat
          </button>
        )}
        <button
          onClick={() => stopMut.mutate()}
          className="rounded-lg bg-gradient-to-r from-rose-500 to-red-500 px-3 py-2 text-sm font-semibold text-white shadow-lg transition hover:opacity-90"
        >
          Durdur
        </button>
        <button
          onClick={() => downloadMut.mutate()}
          disabled={downloadMut.isPending}
          className="rounded-lg border border-white/20 px-3 py-2 text-sm font-semibold text-white/90 transition hover:bg-white/10 disabled:opacity-50"
        >
          {downloadMut.isPending ? 'Hazirlaniyor...' : 'llms.txt indir'}
        </button>
      </div>
    );
  }, [jobStatus, status?.job, startMut, resumeMut, pauseMut, stopMut, downloadMut]);

  return (
    <div className="min-h-screen overflow-hidden" style={{ background: 'radial-gradient(circle at 20% 20%, rgba(79,70,229,0.16), transparent 32%), radial-gradient(circle at 80% 0%, rgba(14,165,233,0.18), transparent 28%), linear-gradient(180deg, #0b1222, #0b1222 40%, #0f172a)' }}>
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/8 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-emerald-200">
              llms.txt Studio
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
            </div>
            <h1 className="mt-3 text-3xl font-extrabold tracking-tight text-white md:text-4xl">
              AI icin bilgi yogun llms.txt uretimi
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-300">
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
          <div
            className="rounded-2xl border border-white/10 p-5 shadow-lg"
            style={{ background: 'linear-gradient(160deg, rgba(255,255,255,0.05), rgba(15,23,42,0.9))' }}
          >
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-xs uppercase tracking-[0.12em] text-slate-400">Anlık is parcalari</div>
                <div className="text-lg font-semibold text-white">
                  {jobStatus === 'running' ? 'Ozet olusturuluyor' : 'Beklemede'}
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-300">
                <span className="h-2 w-2 rounded-full" style={{ background: jobStatus === 'running' ? '#22c55e' : '#fbbf24' }} />
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
              <div className="rounded-xl border border-dashed border-white/12 px-4 py-6 text-sm text-slate-400">
                Su an calisan bir parca yok. {jobStatus === 'running' ? 'Siradaki urun bekleniyor.' : 'Is baslat veya devam et.'}
              </div>
            )}
            <div className="mt-4 text-xs text-slate-400">
              Sıra otomatik saklanır; backend ayaktayken kaldığı yerden devam eder.
            </div>
          </div>

          <div
            className="rounded-2xl border border-white/10 p-5 shadow-lg"
            style={{ background: 'linear-gradient(160deg, rgba(14,165,233,0.08), rgba(15,23,42,0.9))' }}
          >
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-xs uppercase tracking-[0.12em] text-slate-400">Yeni / islenmemis</div>
                <div className="text-lg font-semibold text-white">
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
                <div className="rounded-xl border border-dashed border-white/12 px-4 py-6 text-sm text-slate-400">
                  Tum urunler icin ozet var. Yeni eklenen urunler burada belirecek.
                </div>
              )}
            </div>
          </div>
        </section>

        <section
          ref={listSectionRef}
          className="mt-8 rounded-2xl border border-white/10 p-5 shadow-lg"
          style={{ background: 'rgba(15,23,42,0.7)' }}
        >
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="text-xs uppercase tracking-[0.12em] text-slate-400">Son ozetler</div>
              <div className="text-lg font-semibold text-white">AI icin hazir bloklar</div>
            </div>
            <div className="flex gap-2 text-xs text-slate-300">
              <button
                type="button"
                onClick={() => {
                  setListMode('processed');
                  processedQ.refetch();
                }}
                className={`rounded-lg border px-3 py-1.5 font-semibold transition ${listMode === 'processed' ? 'bg-white/20 border-white/40' : 'border-white/20 hover:bg-white/10'}`}
              >
                Tum ozetleri goster
              </button>
              <button
                type="button"
                onClick={() => {
                  setListMode('pending');
                  pendingQ.refetch();
                }}
                className={`rounded-lg border px-3 py-1.5 font-semibold text-amber-200 transition ${listMode === 'pending' ? 'bg-amber-300/20 border-amber-300/70' : 'border-amber-300/50 hover:bg-amber-300/10'}`}
              >
                Bekleyenleri goster
              </button>
              <button
                type="button"
                onClick={() => setListMode('recent')}
                className={`rounded-lg border px-3 py-1.5 font-semibold text-slate-200 transition ${listMode === 'recent' ? 'bg-white/15 border-white/40' : 'border-white/15 hover:bg-white/8'}`}
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
                className="rounded-xl border border-white/10 p-4"
                style={{ background: 'linear-gradient(120deg, rgba(99,102,241,0.06), rgba(15,23,42,0.9))' }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-semibold text-white">{entry.product_name}</div>
                    <div className="text-xs text-slate-400">{entry.category ?? 'Kategori yok'}</div>
                  </div>
                  <span className="rounded-full bg-emerald-500/20 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-emerald-200">
                    Hazir
                  </span>
                </div>
                <p
                  className="mt-2 text-sm leading-relaxed text-slate-200"
                  style={{ whiteSpace: 'pre-line' }}
                >
                  {entry.summary}
                </p>
                <div className="mt-3 flex items-center justify-between text-[11px] uppercase tracking-[0.08em] text-slate-400">
                  <span>{new Date(entry.updated_at).toLocaleString('tr-TR')}</span>
                  <button
                    type="button"
                    onClick={() => regenMut.mutate(entry.product_id)}
                    disabled={regenTarget === entry.product_id || regenMut.isPending}
                    className="rounded-full border border-emerald-300/60 px-3 py-1 text-[11px] font-semibold text-emerald-200 transition hover:bg-emerald-300/15 disabled:opacity-50"
                  >
                    {regenTarget === entry.product_id ? 'Yeniden üretiliyor...' : 'Yeniden üret'}
                  </button>
                </div>
              </div>
            ))}
            {listMode !== 'pending' && !( (listMode === 'processed' ? processedQ.data?.items?.length : status?.latest_processed?.length) ) && (
              <div className="rounded-xl border border-dashed border-white/12 px-4 py-6 text-sm text-slate-400">
                Henuz kaydedilmis ozet yok. Islem baslayinca sonuclar burada gorunecek.
              </div>
            )}

            {listMode === 'pending' && pendingQ.data?.items?.length ? (
              <div className="md:col-span-2">
                <div className="mb-2 text-xs uppercase tracking-[0.12em] text-amber-200">Bekleyenler</div>
                <div className="grid gap-2 md:grid-cols-2">
                  {pendingQ.data.items.map((p) => (
                    <div
                      key={p.product_id}
                      className="rounded-xl border border-amber-300/30 px-4 py-3"
                      style={{ background: 'rgba(251,191,36,0.06)' }}
                    >
                      <div className="text-sm font-semibold text-white">{p.product_name}</div>
                      <div className="text-xs text-slate-400">{p.category ?? 'Kategori yok'}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {listMode === 'pending' && pendingQ.isFetching && (
              <div className="md:col-span-2 rounded-xl border border-dashed border-amber-200/40 px-4 py-6 text-center text-sm text-amber-100">
                Bekleyenler yukleniyor...
              </div>
            )}

            {listMode === 'processed' && processedQ.isFetching && (
              <div className="md:col-span-2 rounded-xl border border-dashed border-white/30 px-4 py-6 text-center text-sm text-slate-200">
                Tum ozetler yukleniyor...
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
