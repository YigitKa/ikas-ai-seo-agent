import type { ReactNode } from 'react';
import type { PromptTemplate } from '../../types';

export type BannerTone = 'success' | 'error' | 'info';

export function SectionCard({
  eyebrow,
  title,
  description,
  actions,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="rounded-3xl border border-slate-800/80 bg-slate-950/65 p-5 shadow-xl shadow-slate-950/30 backdrop-blur sm:p-6">
      <div className="mb-5 flex flex-col gap-4 border-b border-slate-800 pb-5 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-300/80">{eyebrow}</div>
          <h2 className="mt-2 text-xl font-semibold text-white">{title}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">{description}</p>
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function Field({ label, value, onChange, type = 'text', placeholder, hint, disabled = false }: { label: string; value: string; onChange: (value: string) => void; type?: string; placeholder?: string; hint?: string; disabled?: boolean; }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-200">{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} disabled={disabled} className="h-11 w-full rounded-2xl border border-slate-700 bg-slate-950/90 px-4 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-sky-400 disabled:cursor-not-allowed disabled:bg-slate-900 disabled:text-slate-400" />
      {hint && <span className="mt-2 block text-xs leading-5 text-slate-500">{hint}</span>}
    </label>
  );
}

export function SelectField({ label, value, onChange, options, hint }: { label: string; value: string; onChange: (value: string) => void; options: { value: string; label: string }[]; hint?: string; }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-slate-200">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="h-11 w-full rounded-2xl border border-slate-700 bg-slate-950/90 px-4 text-sm text-slate-100 outline-none transition focus:border-sky-400">
        {options.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
      {hint && <span className="mt-2 block text-xs leading-5 text-slate-500">{hint}</span>}
    </label>
  );
}

export function ToggleField({ title, description, checked, onChange }: { title: string; description: string; checked: boolean; onChange: (checked: boolean) => void; }) {
  return (
    <label className="flex items-start gap-4 rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-900 text-sky-500" />
      <span className="block">
        <span className="block text-sm font-medium text-white">{title}</span>
        <span className="mt-1 block text-sm leading-6 text-slate-400">{description}</span>
      </span>
    </label>
  );
}

export function PromptCard({ template, value, onChange, onReset, disabled }: { template: PromptTemplate; value: string; onChange: (value: string) => void; onReset: () => void; disabled: boolean; }) {
  return (
    <article className="rounded-3xl border border-slate-800 bg-slate-950/70 p-5">
      <div className="flex flex-col gap-3 border-b border-slate-800 pb-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h3 className="text-base font-semibold text-white">{template.title}</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">{template.description}</p>
        </div>
        <button onClick={onReset} disabled={disabled} className="rounded-xl border border-slate-700 px-3 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50">Varsayilan</button>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-xs uppercase tracking-[0.2em] text-slate-400">{template.key}</span>
        {template.variables.map((variable) => (
          <span key={variable} className="rounded-full border border-sky-500/20 bg-sky-500/10 px-3 py-1 text-xs text-sky-200">{'{{'}{variable}{'}}'}</span>
        ))}
        {template.variables.length === 0 && <span className="rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-xs text-slate-500">Degisken yok</span>}
      </div>

      <textarea value={value} onChange={(event) => onChange(event.target.value)} style={{ minHeight: `${Math.max(template.height, 180)}px` }} className="mt-4 w-full rounded-2xl border border-slate-700 bg-slate-950/90 px-4 py-3 font-mono text-sm leading-6 text-slate-100 outline-none transition focus:border-sky-400" />
    </article>
  );
}

export function StatusPill({ label, value, tone }: { label: string; value: string; tone: BannerTone; }) {
  return (
    <div className={`rounded-2xl border px-4 py-3 ${toneClasses(tone)}`}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.24em] opacity-80">{label}</div>
      <div className="mt-2 text-sm font-medium">{value}</div>
    </div>
  );
}

export function StatusRow({ label, value, mono = true }: { label: string; value: string; mono?: boolean; }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-slate-800 pb-4 last:border-b-0 last:pb-0">
      <dt className="text-slate-500">{label}</dt>
      <dd className={`max-w-[60%] text-right text-slate-200 ${mono ? 'font-mono text-xs' : ''}`}>{value}</dd>
    </div>
  );
}

export function Banner({ tone, message, className = '' }: { tone: BannerTone; message: string; className?: string; }) {
  return <div className={`rounded-2xl border px-4 py-3 text-sm ${toneClasses(tone)} ${className}`}>{message}</div>;
}

function toneClasses(tone: BannerTone) {
  if (tone === 'success') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100';
  if (tone === 'error') return 'border-rose-500/30 bg-rose-500/10 text-rose-100';
  return 'border-sky-500/30 bg-sky-500/10 text-sky-100';
}
