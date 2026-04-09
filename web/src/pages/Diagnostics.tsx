import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import { getDiagnosticsSummary } from '../api/client';
import type {
  DiagnosticsComponent,
  DiagnosticsIssue,
  DiagnosticsSummary,
  DiagnosticsTaskSummary,
} from '../types';
import AppHeader from '../shared/ui/AppHeader';
import {
  EnterpriseButton,
  EnterprisePill,
  EnterpriseSurface,
} from '../shared/ui/EnterprisePrimitives';
import { useToast } from '../shared/ui/Toast';
import { formatError } from './settings/constants';

function statusTone(status: string): 'neutral' | 'primary' | 'success' | 'warning' | 'danger' {
  switch (status) {
    case 'healthy':
      return 'success';
    case 'degraded':
      return 'warning';
    case 'down':
      return 'danger';
    default:
      return 'neutral';
  }
}

function statusLabel(status: string) {
  switch (status) {
    case 'healthy':
      return 'Saglikli';
    case 'degraded':
      return 'Sorunlu';
    case 'down':
      return 'Kapali';
    default:
      return 'Bilinmiyor';
  }
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return '-';
  return new Date(value).toLocaleString('tr-TR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatLatency(ms: number | null | undefined) {
  if (typeof ms !== 'number') return '-';
  return `${ms} ms`;
}

function ComponentCard({
  title,
  subtitle,
  block,
  children,
}: {
  title: string;
  subtitle?: string;
  block: DiagnosticsComponent;
  children?: ReactNode;
}) {
  return (
    <EnterpriseSurface className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>
            {title}
          </div>
          {subtitle && (
            <div className="mt-1 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
              {subtitle}
            </div>
          )}
        </div>
        <EnterprisePill tone={statusTone(block.status)}>{statusLabel(block.status)}</EnterprisePill>
      </div>

      <div className="mt-4 text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
        {block.summary || '-'}
      </div>

      <div className="mt-3 grid gap-2 text-[11px] sm:grid-cols-2">
        <div style={{ color: 'var(--color-text-secondary)' }}>
          Son kontrol: <strong style={{ color: 'var(--color-text-primary)' }}>{formatDateTime(block.checked_at)}</strong>
        </div>
        <div style={{ color: 'var(--color-text-secondary)' }}>
          Gecikme: <strong style={{ color: 'var(--color-text-primary)' }}>{formatLatency(block.latency_ms)}</strong>
        </div>
      </div>

      {block.reason_codes.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {block.reason_codes.map((reasonCode) => (
            <span
              key={reasonCode}
              className="rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em]"
              style={{
                background: 'rgba(15,23,42,0.72)',
                border: '1px solid rgba(148,163,184,0.18)',
                color: 'var(--color-text-secondary)',
              }}
            >
              {reasonCode}
            </span>
          ))}
        </div>
      )}

      {block.checks.length > 0 && (
        <div className="mt-4 space-y-2">
          {block.checks.map((check) => (
            <div
              key={check.name}
              className="flex items-center justify-between rounded-xl px-3 py-2 text-[11px]"
              style={{
                background: 'rgba(15,23,42,0.48)',
                border: '1px solid rgba(148,163,184,0.14)',
              }}
            >
              <div>
                <div style={{ color: 'var(--color-text-primary)' }}>{check.name}</div>
                {check.error_summary && (
                  <div className="mt-1" style={{ color: 'var(--color-text-secondary)' }}>
                    {check.error_summary}
                  </div>
                )}
              </div>
              <div className="text-right" style={{ color: 'var(--color-text-secondary)' }}>
                <div>{statusLabel(check.status)}</div>
                <div>{formatLatency(check.latency_ms)}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {children}
    </EnterpriseSurface>
  );
}

function IssueList({ issues }: { issues: DiagnosticsIssue[] }) {
  return (
    <EnterpriseSurface className="p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>
            Reason Codes
          </div>
          <div className="mt-1 text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
            Acik sorun listesi
          </div>
        </div>
        <EnterprisePill tone={issues.length > 0 ? 'warning' : 'success'}>
          {issues.length > 0 ? `${issues.length} issue` : 'Temiz'}
        </EnterprisePill>
      </div>

      <div className="mt-4 space-y-3">
        {issues.length === 0 ? (
          <div className="rounded-xl px-4 py-3 text-sm" style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', color: '#a7f3d0' }}>
            Kritik veya acik issue gorunmuyor.
          </div>
        ) : (
          issues.map((issue, index) => (
            <div
              key={`${issue.component}-${issue.reason_code}-${issue.target_id ?? index}`}
              className="rounded-2xl px-4 py-3"
              style={{
                background: 'rgba(15,23,42,0.48)',
                border: '1px solid rgba(148,163,184,0.16)',
              }}
            >
              <div className="flex flex-wrap items-center gap-2">
                <EnterprisePill tone={issue.scope === 'global' ? 'danger' : issue.scope === 'job' ? 'warning' : 'primary'}>
                  {issue.scope}
                </EnterprisePill>
                <span className="text-xs font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  {issue.reason_code}
                </span>
                <span className="text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
                  {issue.component}
                  {issue.target_id ? ` / ${issue.target_id}` : ''}
                </span>
              </div>
              <div className="mt-2 text-sm" style={{ color: 'var(--color-text-primary)' }}>
                {issue.summary}
              </div>
              {issue.recommended_action && (
                <div className="mt-2 text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
                  Oneri: {issue.recommended_action}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </EnterpriseSurface>
  );
}

function ActiveJobCard({ job }: { job: DiagnosticsTaskSummary }) {
  return (
    <div
      className="rounded-2xl px-4 py-3"
      style={{
        background: 'rgba(15,23,42,0.48)',
        border: `1px solid ${job.stuck ? 'rgba(245,158,11,0.3)' : 'rgba(148,163,184,0.16)'}`,
      }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
            {job.id}
          </div>
          <div className="mt-1 text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
            {job.type} / {job.stage_label}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {job.stuck && <EnterprisePill tone="warning">Stuck</EnterprisePill>}
          <EnterprisePill tone={statusTone(job.stuck ? 'degraded' : job.status === 'failed' ? 'down' : 'healthy')}>
            %{job.progress}
          </EnterprisePill>
        </div>
      </div>

      <div className="mt-3 text-sm" style={{ color: 'var(--color-text-primary)' }}>
        {job.status_message}
      </div>

      <div className="mt-3 grid gap-2 text-[11px] sm:grid-cols-3">
        <div style={{ color: 'var(--color-text-secondary)' }}>
          Guncelleme: <strong style={{ color: 'var(--color-text-primary)' }}>{formatDateTime(job.updated_at)}</strong>
        </div>
        <div style={{ color: 'var(--color-text-secondary)' }}>
          Heartbeat: <strong style={{ color: 'var(--color-text-primary)' }}>{formatDateTime(job.heartbeat_at)}</strong>
        </div>
        <div style={{ color: 'var(--color-text-secondary)' }}>
          Anlik item: <strong style={{ color: 'var(--color-text-primary)' }}>{job.current_item || '-'}</strong>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
        <span style={{ color: 'var(--color-text-secondary)' }}>total {job.counts.total}</span>
        <span style={{ color: 'var(--color-text-secondary)' }}>processed {job.counts.processed}</span>
        <span style={{ color: 'var(--color-text-secondary)' }}>failed {job.counts.failed}</span>
        <span style={{ color: 'var(--color-text-secondary)' }}>remaining {job.counts.remaining}</span>
      </div>
    </div>
  );
}

function DiagnosticsActions({ data }: { data: DiagnosticsSummary }) {
  if (data.recommended_actions.length === 0) return null;
  return (
    <EnterpriseSurface className="p-5">
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>
        Onerilen Aksiyonlar
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {data.recommended_actions.map((action) => (
          <div
            key={action}
            className="rounded-2xl px-4 py-3 text-sm"
            style={{
              background: 'rgba(15,23,42,0.48)',
              border: '1px solid rgba(148,163,184,0.16)',
              color: 'var(--color-text-primary)',
            }}
          >
            {action}
          </div>
        ))}
      </div>
    </EnterpriseSurface>
  );
}

export default function Diagnostics() {
  const { addToast } = useToast();
  const diagnosticsQ = useQuery({
    queryKey: ['diagnostics-summary'],
    queryFn: getDiagnosticsSummary,
    refetchInterval: 15000,
  });

  const data = diagnosticsQ.data;

  const copyDebugReport = async () => {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(data.debug_report);
      addToast({ tone: 'success', message: 'Debug raporu panoya kopyalandi.' });
    } catch {
      addToast({ tone: 'error', message: 'Debug raporu kopyalanamadi.' });
    }
  };

  if (diagnosticsQ.isLoading && !data) {
    return (
      <div className="flex h-screen flex-col" style={{ background: 'var(--color-bg-base)' }}>
        <AppHeader
          title="Diagnostics"
          description="Sistem sagligi, aktif isler ve teknik issue ozetini tek ekranda izleyin."
          eyebrow={{ label: 'Diagnostics', tone: 'primary' }}
          breadcrumbs={[{ label: 'Dashboard', to: '/' }, { label: 'Diagnostics' }]}
          showPanel={false}
          wrapperClassName="px-4"
        />
        <div className="flex flex-1 items-center justify-center text-sm" style={{ color: 'var(--color-text-secondary)' }}>
          Diagnostics yukleniyor...
        </div>
      </div>
    );
  }

  if (diagnosticsQ.error || !data) {
    return (
      <div className="flex h-screen flex-col" style={{ background: 'var(--color-bg-base)' }}>
        <AppHeader
          title="Diagnostics"
          description="Sistem sagligi, aktif isler ve teknik issue ozetini tek ekranda izleyin."
          eyebrow={{ label: 'Diagnostics', tone: 'primary' }}
          breadcrumbs={[{ label: 'Dashboard', to: '/' }, { label: 'Diagnostics' }]}
          showPanel={false}
          wrapperClassName="px-4"
        />
        <div className="px-4 py-6">
          <EnterpriseSurface className="p-5">
            <div className="text-sm" style={{ color: 'var(--color-danger)' }}>
              {formatError(diagnosticsQ.error, 'Diagnostics ozeti alinamadi.')}
            </div>
          </EnterpriseSurface>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col" style={{ background: 'var(--color-bg-base)' }}>
      <AppHeader
        title="Diagnostics"
        description="Sistem sagligi, aktif isler ve teknik issue ozetini tek ekranda izleyin."
        eyebrow={{ label: 'Diagnostics', tone: statusTone(data.overall_status) }}
        breadcrumbs={[{ label: 'Dashboard', to: '/' }, { label: 'Diagnostics' }]}
        meta={[
          { label: 'Genel Durum', value: statusLabel(data.overall_status), tone: statusTone(data.overall_status) },
          { label: 'Issue', value: `${data.issues.length}`, tone: data.issues.length > 0 ? 'warning' : 'success' },
          { label: 'Aktif Is', value: `${data.active_jobs.total}`, tone: data.active_jobs.total > 0 ? 'primary' : 'neutral' },
          { label: 'Guncellendi', value: formatDateTime(data.generated_at) },
        ]}
        actions={(
          <div className="flex items-center gap-2">
            <EnterpriseButton tone="neutral" onClick={() => diagnosticsQ.refetch()}>
              Yenile
            </EnterpriseButton>
            <EnterpriseButton tone="primary" onClick={copyDebugReport}>
              Debug Raporu Kopyala
            </EnterpriseButton>
          </div>
        )}
        wrapperClassName="px-4"
        panelClassName="mb-0"
      />

      <main className="flex-1 overflow-y-auto px-4 py-4">
        <div className="mx-auto flex max-w-[1600px] flex-col gap-4">
          <div className="grid gap-4 xl:grid-cols-5">
            <ComponentCard
              title="Provider"
              subtitle={`${data.providers.provider || 'none'} / ${data.providers.configured_model || 'model secilmemis'}`}
              block={data.providers}
            />
            <ComponentCard
              title="MCP"
              subtitle={`${data.mcp.tool_count} arac`}
              block={data.mcp}
            />
            <ComponentCard
              title="Database"
              subtitle={data.database.journal_mode || 'journal bilinmiyor'}
              block={data.database}
            >
              <div className="mt-4 grid gap-2 text-[11px] sm:grid-cols-2">
                <div style={{ color: 'var(--color-text-secondary)' }}>Urun: <strong style={{ color: 'var(--color-text-primary)' }}>{data.database.product_count}</strong></div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Task: <strong style={{ color: 'var(--color-text-primary)' }}>{data.database.task_count}</strong></div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Suggestion: <strong style={{ color: 'var(--color-text-primary)' }}>{data.database.suggestion_count}</strong></div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Write test: <strong style={{ color: 'var(--color-text-primary)' }}>{data.database.write_test_ok ? 'OK' : 'Fail'}</strong></div>
              </div>
            </ComponentCard>
            <ComponentCard
              title="Workers"
              subtitle={data.workers.last_crash_summary || 'Son crash yok'}
              block={data.workers}
            >
              <div className="mt-4 grid gap-2 text-[11px] sm:grid-cols-2">
                <div style={{ color: 'var(--color-text-secondary)' }}>Aktif: <strong style={{ color: 'var(--color-text-primary)' }}>{data.workers.active_count}</strong></div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Bekleyen: <strong style={{ color: 'var(--color-text-primary)' }}>{data.workers.waiting_count}</strong></div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Stuck: <strong style={{ color: 'var(--color-text-primary)' }}>{data.workers.stuck_count}</strong></div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Heartbeat: <strong style={{ color: 'var(--color-text-primary)' }}>{formatDateTime(data.workers.latest_heartbeat_at)}</strong></div>
              </div>
            </ComponentCard>
            <ComponentCard
              title="Prompt Cache"
              subtitle={`${data.prompt_cache.loaded_templates}/${data.prompt_cache.total_templates} yuklu`}
              block={data.prompt_cache}
            >
              {data.prompt_cache.missing_templates.length > 0 && (
                <div className="mt-4 text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
                  Eksikler: {data.prompt_cache.missing_templates.join(', ')}
                </div>
              )}
            </ComponentCard>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
            <ComponentCard
              title="Task Runtime"
              subtitle={data.task_runtime.longest_running_task?.id || 'Uzun task yok'}
              block={data.task_runtime}
            >
              <div className="mt-4 grid gap-2 text-[11px] sm:grid-cols-3">
                <div style={{ color: 'var(--color-text-secondary)' }}>Queue: <strong style={{ color: 'var(--color-text-primary)' }}>{data.task_runtime.queued_count}</strong></div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Aktif: <strong style={{ color: 'var(--color-text-primary)' }}>{data.task_runtime.active_count}</strong></div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Bekleyen: <strong style={{ color: 'var(--color-text-primary)' }}>{data.task_runtime.waiting_count}</strong></div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Terminal: <strong style={{ color: 'var(--color-text-primary)' }}>{data.task_runtime.terminal_count}</strong></div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Hata: <strong style={{ color: 'var(--color-text-primary)' }}>{data.task_runtime.failed_count}</strong></div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Stuck: <strong style={{ color: 'var(--color-text-primary)' }}>{data.task_runtime.stuck_count}</strong></div>
              </div>

              {data.task_runtime.stuck_tasks.length > 0 && (
                <div className="mt-4 space-y-3">
                  {data.task_runtime.stuck_tasks.map((job) => (
                    <ActiveJobCard key={job.id} job={job} />
                  ))}
                </div>
              )}
            </ComponentCard>

            <ComponentCard
              title="Store Context"
              subtitle={data.store_context.store_name || 'Store tanimli degil'}
              block={data.store_context}
            >
              <div className="mt-4 grid gap-2 text-[11px] sm:grid-cols-2">
                <div style={{ color: 'var(--color-text-secondary)' }}>Dil: <strong style={{ color: 'var(--color-text-primary)' }}>{data.store_context.languages.join(', ') || '-'}</strong></div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Dry run: <strong style={{ color: 'var(--color-text-primary)' }}>{data.store_context.dry_run ? 'Acik' : 'Kapali'}</strong></div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Cached urun: <strong style={{ color: 'var(--color-text-primary)' }}>{data.store_context.product_count}</strong></div>
                <div style={{ color: 'var(--color-text-secondary)' }}>Pending suggestion: <strong style={{ color: 'var(--color-text-primary)' }}>{data.store_context.pending_suggestions}</strong></div>
              </div>
            </ComponentCard>
          </div>

          <DiagnosticsActions data={data} />

          <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <IssueList issues={data.issues} />

            <EnterpriseSurface className="p-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>
                    Active Jobs
                  </div>
                  <div className="mt-1 text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                    Canli task akisi
                  </div>
                </div>
                <EnterprisePill tone={data.active_jobs.total > 0 ? 'primary' : 'neutral'}>
                  {data.active_jobs.total}
                </EnterprisePill>
              </div>

              <div className="mt-4 space-y-3">
                {data.active_jobs.items.length === 0 ? (
                  <div className="rounded-xl px-4 py-3 text-sm" style={{ background: 'rgba(15,23,42,0.48)', border: '1px solid rgba(148,163,184,0.16)', color: 'var(--color-text-secondary)' }}>
                    Su anda aktif veya bekleyen job yok.
                  </div>
                ) : (
                  data.active_jobs.items.map((job) => (
                    <ActiveJobCard key={job.id} job={job} />
                  ))
                )}
              </div>
            </EnterpriseSurface>
          </div>

          <EnterpriseSurface className="p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>
                  Debug Report
                </div>
                <div className="mt-1 text-sm font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  Kopyalanabilir teknik ozet
                </div>
              </div>
              <EnterpriseButton tone="neutral" onClick={copyDebugReport}>
                Kopyala
              </EnterpriseButton>
            </div>

            <pre
              className="mt-4 overflow-x-auto rounded-2xl p-4 text-[11px] leading-6"
              style={{
                background: 'rgba(2,6,23,0.72)',
                border: '1px solid rgba(148,163,184,0.14)',
                color: 'var(--color-text-secondary)',
              }}
            >
              {data.debug_report}
            </pre>
          </EnterpriseSurface>
        </div>
      </main>
    </div>
  );
}
