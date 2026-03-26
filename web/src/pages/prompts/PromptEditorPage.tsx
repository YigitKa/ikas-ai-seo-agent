import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useToast } from '../../shared/ui/Toast';
import { getPromptTemplates, savePromptTemplates, resetPromptTemplates, getPromptLayeringOrder } from '../../api/client';
import type { PromptGroup, PromptTemplate, PromptLayeringOrder } from '../../types';
import ConfirmDialog from '../../shared/ui/ConfirmDialog';

/* ─── helpers ────────────────────────────────────────────────────────────── */

function flattenAll(groups: PromptGroup[]): PromptTemplate[] {
  return groups.flatMap((g) => g.prompts);
}

function flattenValues(groups: PromptGroup[]): Record<string, string> {
  const m: Record<string, string> = {};
  for (const g of groups) for (const p of g.prompts) m[p.key] = p.content;
  return m;
}

function wordCount(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function lineCount(text: string): number {
  return text.split('\n').length;
}

const GROUP_ICONS: Record<string, string> = {
  Aciklama: 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z', // edit
  Ceviri: 'M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129', // translate
  'GEO Yeniden Yazim': 'M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9', // globe
  'llms.txt Ozet': 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z', // document
  'Chat Ajanlari': 'M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a2 2 0 01-2-2v-1m0-3V4a2 2 0 012-2h8a2 2 0 012 2v4a2 2 0 01-2 2H7l-4 4V6', // chat bubbles
  'Chat Akisi': 'M13 10V3L4 14h7v7l9-11h-7z', // lightning bolt
  'Otonom Ajanlar': 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z', // desktop/robot
};

function getGroupIcon(label: string) {
  return GROUP_ICONS[label] ?? 'M4 6h16M4 12h16M4 18h7';
}

const TYPE_BADGE: Record<string, { label: string; color: string; bg: string; border: string }> = {
  system: { label: 'SYSTEM', color: '#a78bfa', bg: 'rgba(167,139,250,0.10)', border: 'rgba(167,139,250,0.25)' },
  user: { label: 'USER', color: '#34d399', bg: 'rgba(52,211,153,0.10)', border: 'rgba(52,211,153,0.25)' },
};

function promptType(key: string): 'system' | 'user' {
  return key.endsWith('_system') ? 'system' : 'user';
}

/* ─── Main Page ──────────────────────────────────────────────────────────── */

export default function PromptEditorPage() {
  const qc = useQueryClient();
  const toast = useToast();

  /* data */
  const promptsQ = useQuery({ queryKey: ['prompt-templates'], queryFn: getPromptTemplates });
  const layeringQ = useQuery({ queryKey: ['prompt-layering'], queryFn: getPromptLayeringOrder });
  const groups: PromptGroup[] = promptsQ.data?.groups ?? [];
  const allPrompts = useMemo(() => flattenAll(groups), [groups]);

  /* state */
  const [values, setValues] = useState<Record<string, string>>({});
  const [originals, setOriginals] = useState<Record<string, string>>({});
  const [activeKey, setActiveKey] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [confirmReset, setConfirmReset] = useState<string | null>(null); // key or '__all__'
  const [showPreview, setShowPreview] = useState(false);
  const [showLayering, setShowLayering] = useState(false);
  const editorRef = useRef<HTMLTextAreaElement>(null);

  /* sync server data → local state (once) */
  useEffect(() => {
    if (!promptsQ.data) return;
    const flat = flattenValues(promptsQ.data.groups);
    setOriginals(flat);
    setValues((prev) => {
      // only set if empty (first load)
      if (Object.keys(prev).length === 0) return flat;
      return prev;
    });
    setExpandedGroups(new Set(promptsQ.data.groups.map((g) => g.label)));
    if (!activeKey && promptsQ.data.groups[0]?.prompts[0]) {
      setActiveKey(promptsQ.data.groups[0].prompts[0].key);
    }
  }, [promptsQ.data, activeKey]);

  /* dirty tracking */
  const dirtyKeys = useMemo(() => {
    const set = new Set<string>();
    for (const key of Object.keys(values)) {
      if (values[key] !== originals[key]) set.add(key);
    }
    return set;
  }, [values, originals]);
  const hasDirty = dirtyKeys.size > 0;

  /* current prompt */
  const current = allPrompts.find((p) => p.key === activeKey);
  const currentValue = values[activeKey] ?? current?.content ?? '';

  /* search filter */
  const filteredGroups = useMemo(() => {
    if (!searchQuery.trim()) return groups;
    const q = searchQuery.toLowerCase();
    return groups
      .map((g) => ({
        ...g,
        prompts: g.prompts.filter(
          (p) =>
            p.title.toLowerCase().includes(q) ||
            p.key.toLowerCase().includes(q) ||
            p.description.toLowerCase().includes(q),
        ),
      }))
      .filter((g) => g.prompts.length > 0);
  }, [groups, searchQuery]);

  /* mutations */
  const saveMut = useMutation({
    mutationFn: (templates: Record<string, string>) => savePromptTemplates(templates),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['prompt-templates'] });
      setOriginals({ ...values });
      toast.success('Tum promptlar kaydedildi.');
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : 'Kaydetme basarisiz.'),
  });

  const resetMut = useMutation({
    mutationFn: (keys: string[]) => resetPromptTemplates(keys),
    onSuccess: (data, keys) => {
      const flat = flattenValues(data.groups);
      setOriginals(flat);
      setValues(flat);
      qc.invalidateQueries({ queryKey: ['prompt-templates'] });
      toast.success(keys.length === 0 ? 'Tum promptlar varsayilana dondu.' : 'Prompt varsayilana dondu.');
    },
    onError: (err) => toast.error(err instanceof Error ? err.message : 'Sifirlama basarisiz.'),
  });

  /* handlers */
  const handleChange = useCallback(
    (val: string) => setValues((prev) => ({ ...prev, [activeKey]: val })),
    [activeKey],
  );

  const handleSaveAll = useCallback(() => {
    // only send dirty values
    const toSave: Record<string, string> = {};
    for (const key of dirtyKeys) toSave[key] = values[key];
    if (Object.keys(toSave).length === 0) {
      toast.info('Degisiklik yok.');
      return;
    }
    saveMut.mutate(toSave);
  }, [dirtyKeys, values, saveMut, toast]);

  const handleDiscard = useCallback(() => {
    setValues({ ...originals });
    toast.info('Degisiklikler geri alindi.');
  }, [originals, toast]);

  /* keyboard shortcut: Ctrl+S */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSaveAll();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleSaveAll]);

  /* insert variable at cursor */
  const insertVariable = useCallback(
    (varName: string) => {
      const ta = editorRef.current;
      if (!ta) return;
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      const text = `{{${varName}}}`;
      const next = currentValue.slice(0, start) + text + currentValue.slice(end);
      handleChange(next);
      requestAnimationFrame(() => {
        ta.focus();
        ta.selectionStart = ta.selectionEnd = start + text.length;
      });
    },
    [currentValue, handleChange],
  );

  /* ─── Loading ────────────────────────────────────────────────────────── */

  if (promptsQ.isLoading) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ background: 'var(--color-bg-base)' }}>
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-transparent" style={{ borderTopColor: 'var(--color-primary)' }} />
          <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>Promptlar yukleniyor...</span>
        </div>
      </div>
    );
  }

  /* ─── Render ─────────────────────────────────────────────────────────── */

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--color-bg-base)' }}>
      {/* Reset confirm dialog */}
      <ConfirmDialog
        open={confirmReset !== null}
        title={confirmReset === '__all__' ? 'Tum Promptlari Sifirla' : 'Promptu Sifirla'}
        message={
          confirmReset === '__all__'
            ? 'Tum prompt dosyalari varsayilan haline donecek. Bu islem geri alinamaz.'
            : `"${allPrompts.find((p) => p.key === confirmReset)?.title ?? confirmReset}" varsayilana donecek.`
        }
        confirmLabel="Sifirla"
        cancelLabel="Iptal"
        variant="danger"
        onConfirm={() => {
          if (confirmReset === '__all__') resetMut.mutate([]);
          else if (confirmReset) resetMut.mutate([confirmReset]);
          setConfirmReset(null);
        }}
        onCancel={() => setConfirmReset(null)}
      />

      {/* ── LEFT SIDEBAR ─────────────────────────────────────────────────── */}
      <aside
        className="flex h-full w-[280px] flex-shrink-0 flex-col"
        style={{
          background: 'linear-gradient(180deg, rgba(11,17,32,0.98), rgba(2,6,23,0.98))',
          borderRight: '1px solid var(--color-border)',
        }}
      >
        {/* Header */}
        <div className="flex items-center gap-3 px-4 pt-4 pb-3">
          <Link
            to="/settings"
            className="flex h-8 w-8 items-center justify-center rounded-lg transition-all duration-200 hover:scale-105"
            style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)' }}
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} style={{ color: 'var(--color-primary-light)' }}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <div>
            <h1 className="text-[15px] font-semibold tracking-tight" style={{ color: 'var(--color-text-primary)' }}>Prompt Studio</h1>
            <p className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>{allPrompts.length} prompt dosyasi</p>
          </div>
        </div>

        {/* Layering order toggle */}
        <div className="px-3 pb-2">
          <button
            onClick={() => { setShowLayering(!showLayering); if (!showLayering) setActiveKey(''); }}
            className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left transition-all duration-150 hover:brightness-125"
            style={{
              background: showLayering ? 'rgba(168,85,247,0.12)' : 'rgba(168,85,247,0.04)',
              border: showLayering ? '1px solid rgba(168,85,247,0.3)' : '1px solid rgba(168,85,247,0.12)',
              color: showLayering ? '#c084fc' : 'var(--color-text-secondary)',
            }}
          >
            <svg className="h-4 w-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 12c0-1.232-.046-2.453-.138-3.662a4.006 4.006 0 00-3.7-3.7 48.678 48.678 0 00-7.324 0 4.006 4.006 0 00-3.7 3.7c-.017.22-.032.441-.046.662M19.5 12l3-3m-3 3l-3-3m-12 3c0 1.232.046 2.453.138 3.662a4.006 4.006 0 003.7 3.7 48.656 48.656 0 007.324 0 4.006 4.006 0 003.7-3.7c.017-.22.032-.441.046-.662M4.5 12l3 3m-3-3l-3 3" />
            </svg>
            <span className="flex-1 text-[12px] font-medium">Prompt Katmanlama Sirasi</span>
            <svg
              className="h-3 w-3 transition-transform duration-200"
              style={{ transform: showLayering ? 'rotate(90deg)' : 'rotate(0deg)' }}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        {/* Search */}
        <div className="px-3 pb-2">
          <div className="relative">
            <svg className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} style={{ color: 'var(--color-text-muted)' }}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Prompt ara..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-xl py-2.5 pl-9 pr-3 text-xs outline-none transition duration-200"
              style={{
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid var(--color-border)',
                color: 'var(--color-text-primary)',
              }}
            />
          </div>
        </div>

        {/* Tree */}
        <nav className="flex-1 overflow-y-auto px-2 pb-4">
          {filteredGroups.map((group) => {
            const isExpanded = expandedGroups.has(group.label);
            const groupDirty = group.prompts.some((p) => dirtyKeys.has(p.key));
            return (
              <div key={group.label} className="mb-1">
                {/* Group header */}
                <button
                  onClick={() =>
                    setExpandedGroups((prev) => {
                      const next = new Set(prev);
                      next.has(group.label) ? next.delete(group.label) : next.add(group.label);
                      return next;
                    })
                  }
                  className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left transition-all duration-150 hover:brightness-125"
                  style={{
                    background: isExpanded ? 'rgba(99,102,241,0.08)' : 'transparent',
                    color: 'var(--color-text-secondary)',
                  }}
                >
                  <svg
                    className="h-4 w-4 flex-shrink-0 transition-transform duration-200"
                    style={{ transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)', color: 'var(--color-text-muted)' }}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                  <svg className="h-4 w-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} style={{ color: 'var(--color-primary-light)' }}>
                    <path strokeLinecap="round" strokeLinejoin="round" d={getGroupIcon(group.label)} />
                  </svg>
                  <span className="flex-1 text-[13px] font-medium">{group.label}</span>
                  {groupDirty && (
                    <span className="h-2 w-2 rounded-full" style={{ background: 'var(--color-warning)' }} />
                  )}
                </button>

                {/* Prompt items */}
                {isExpanded && (
                  <div className="ml-3 mt-0.5 space-y-0.5 border-l" style={{ borderColor: 'var(--color-border)' }}>
                    {group.prompts.map((prompt) => {
                      const isActive = prompt.key === activeKey;
                      const isDirty = dirtyKeys.has(prompt.key);
                      const type = promptType(prompt.key);
                      const badge = TYPE_BADGE[type];
                      return (
                        <button
                          key={prompt.key}
                          onClick={() => setActiveKey(prompt.key)}
                          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left transition-all duration-150"
                          style={{
                            background: isActive
                              ? 'linear-gradient(135deg, rgba(99,102,241,0.18), rgba(79,70,229,0.12))'
                              : 'transparent',
                            borderLeft: isActive ? '2px solid var(--color-primary)' : '2px solid transparent',
                            marginLeft: '-1px',
                          }}
                        >
                          <span
                            className="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider"
                            style={{ color: badge.color, background: badge.bg, border: `1px solid ${badge.border}` }}
                          >
                            {badge.label}
                          </span>
                          <span
                            className="flex-1 truncate text-[12px]"
                            style={{ color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}
                          >
                            {prompt.title.replace(/(System|User) Prompt$/, '').trim() || prompt.title}
                          </span>
                          {isDirty && (
                            <span className="h-1.5 w-1.5 rounded-full flex-shrink-0" style={{ background: 'var(--color-warning)' }} />
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}

          {filteredGroups.length === 0 && (
            <div className="mt-6 text-center text-xs" style={{ color: 'var(--color-text-muted)' }}>
              Sonuc bulunamadi.
            </div>
          )}
        </nav>

        {/* Sidebar footer */}
        <div className="px-3 pb-4 space-y-2">
          <button
            onClick={handleSaveAll}
            disabled={!hasDirty || saveMut.isPending}
            className="flex w-full items-center justify-center gap-2 rounded-xl py-2.5 text-[13px] font-medium transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-40"
            style={{
              background: hasDirty
                ? 'linear-gradient(135deg, rgba(99,102,241,0.5), rgba(79,70,229,0.45))'
                : 'rgba(255,255,255,0.04)',
              border: hasDirty ? '1px solid rgba(99,102,241,0.5)' : '1px solid var(--color-border)',
              color: hasDirty ? '#e2e8f0' : 'var(--color-text-muted)',
            }}
          >
            {saveMut.isPending ? (
              <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-transparent" style={{ borderTopColor: 'currentColor' }} />
            ) : (
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
              </svg>
            )}
            {saveMut.isPending ? 'Kaydediliyor...' : hasDirty ? `${dirtyKeys.size} Degisiklik Kaydet` : 'Kaydet'}
          </button>

          {hasDirty && (
            <button
              onClick={handleDiscard}
              className="flex w-full items-center justify-center gap-2 rounded-xl py-2 text-[12px] transition-all duration-200"
              style={{ color: 'var(--color-text-muted)', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)' }}
            >
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
              Geri Al
            </button>
          )}
        </div>
      </aside>

      {/* ── MAIN EDITOR AREA ─────────────────────────────────────────────── */}
      <main className="flex flex-1 flex-col overflow-hidden">
        {current ? (
          <>
            {/* Editor toolbar */}
            <div
              className="flex items-center justify-between px-5 py-3"
              style={{
                background: 'linear-gradient(180deg, rgba(11,17,32,0.95), rgba(2,6,23,0.88))',
                borderBottom: '1px solid var(--color-border)',
              }}
            >
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <span
                    className="rounded-md px-2 py-1 text-[10px] font-bold uppercase tracking-wider"
                    style={{
                      ...(() => {
                        const b = TYPE_BADGE[promptType(activeKey)];
                        return { color: b.color, background: b.bg, border: `1px solid ${b.border}` };
                      })(),
                    }}
                  >
                    {TYPE_BADGE[promptType(activeKey)].label}
                  </span>
                  <h2 className="text-[15px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    {current.title}
                  </h2>
                </div>
                {dirtyKeys.has(activeKey) && (
                  <span
                    className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                    style={{ background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.3)', color: '#fbbf24' }}
                  >
                    Kaydedilmemis
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowPreview(!showPreview)}
                  className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-medium transition-all duration-200"
                  style={{
                    background: showPreview ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.04)',
                    border: showPreview ? '1px solid rgba(99,102,241,0.3)' : '1px solid var(--color-border)',
                    color: showPreview ? 'var(--color-primary-light)' : 'var(--color-text-secondary)',
                  }}
                >
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                  Onizleme
                </button>
                <button
                  onClick={() => setConfirmReset(activeKey)}
                  disabled={resetMut.isPending}
                  className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-medium transition-all duration-200"
                  style={{
                    background: 'rgba(239,68,68,0.08)',
                    border: '1px solid rgba(239,68,68,0.2)',
                    color: '#fca5a5',
                  }}
                >
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Varsayilan
                </button>
                <div className="h-5 w-px" style={{ background: 'var(--color-border)' }} />
                <span className="text-[10px] tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
                  Ctrl+S kaydet
                </span>
              </div>
            </div>

            {/* Editor + Preview + Right panel */}
            <div className="flex flex-1 overflow-hidden">
              {/* Editor + Preview */}
              <div className="flex flex-1 flex-col overflow-hidden">
                <div className="flex flex-1 overflow-hidden">
                  {/* Code Editor */}
                  <div className={`flex flex-1 flex-col overflow-hidden ${showPreview ? 'w-1/2' : ''}`}>
                    {/* Line gutter + textarea wrapper */}
                    <div className="relative flex flex-1 overflow-hidden">
                      <LineGutter text={currentValue} />
                      <textarea
                        ref={editorRef}
                        value={currentValue}
                        onChange={(e) => handleChange(e.target.value)}
                        spellCheck={false}
                        className="flex-1 resize-none overflow-auto py-4 pr-5 pl-2 outline-none"
                        style={{
                          background: 'var(--color-bg-base)',
                          color: 'var(--color-text-primary)',
                          fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace",
                          fontSize: '13px',
                          lineHeight: '1.7',
                          tabSize: 2,
                          caretColor: 'var(--color-primary-light)',
                        }}
                      />
                    </div>

                    {/* Status bar */}
                    <div
                      className="flex items-center justify-between px-4 py-1.5"
                      style={{
                        background: 'rgba(11,17,32,0.95)',
                        borderTop: '1px solid var(--color-border)',
                      }}
                    >
                      <div className="flex items-center gap-4">
                        <span className="text-[10px] tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
                          {lineCount(currentValue)} satir
                        </span>
                        <span className="text-[10px] tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
                          {currentValue.length} karakter
                        </span>
                        <span className="text-[10px] tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
                          {wordCount(currentValue)} kelime
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="rounded px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wider" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--color-border)', color: 'var(--color-text-muted)' }}>
                          {PROMPT_FILE_NAMES[activeKey] ?? `${activeKey}.txt`}
                        </span>
                        <span className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>UTF-8</span>
                      </div>
                    </div>
                  </div>

                  {/* Preview panel */}
                  {showPreview && (
                    <div
                      className="flex w-1/2 flex-col overflow-hidden"
                      style={{ borderLeft: '1px solid var(--color-border)' }}
                    >
                      <div
                        className="flex items-center gap-2 px-4 py-2"
                        style={{
                          background: 'rgba(11,17,32,0.95)',
                          borderBottom: '1px solid var(--color-border)',
                        }}
                      >
                        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} style={{ color: 'var(--color-primary-light)' }}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                        <span className="text-[12px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
                          Onizleme
                        </span>
                      </div>
                      <div className="flex-1 overflow-auto p-5" style={{ background: 'rgba(2,6,23,0.6)' }}>
                        <HighlightedPreview text={currentValue} variables={current.variables} />
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* ── RIGHT PANEL ─────────────────────────────────────────────── */}
              <aside
                className="flex h-full w-[260px] flex-shrink-0 flex-col overflow-y-auto"
                style={{
                  background: 'linear-gradient(180deg, rgba(11,17,32,0.98), rgba(2,6,23,0.98))',
                  borderLeft: '1px solid var(--color-border)',
                }}
              >
                {/* Prompt info */}
                <div className="p-4 space-y-4">
                  {/* Description */}
                  <div>
                    <div className="text-[10px] font-semibold uppercase tracking-[0.15em] mb-2" style={{ color: 'var(--color-text-muted)' }}>
                      Aciklama
                    </div>
                    <p className="text-[12px] leading-5" style={{ color: 'var(--color-text-secondary)' }}>
                      {current.description}
                    </p>
                  </div>

                  {/* Variables */}
                  <div>
                    <div className="text-[10px] font-semibold uppercase tracking-[0.15em] mb-2" style={{ color: 'var(--color-text-muted)' }}>
                      Degiskenler
                    </div>
                    {current.variables.length > 0 ? (
                      <div className="space-y-1.5">
                        {current.variables.map((v) => (
                          <button
                            key={v}
                            onClick={() => insertVariable(v)}
                            className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left transition-all duration-150 hover:brightness-125"
                            style={{
                              background: 'rgba(6,182,212,0.06)',
                              border: '1px solid rgba(6,182,212,0.15)',
                            }}
                          >
                            <span className="flex-1 font-mono text-[11px]" style={{ color: 'var(--color-accent-light)' }}>
                              {`{{${v}}}`}
                            </span>
                            <svg className="h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} style={{ color: 'var(--color-text-muted)' }}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                            </svg>
                          </button>
                        ))}
                        <p className="mt-1 text-[10px] leading-4" style={{ color: 'var(--color-text-muted)' }}>
                          Tikla = imleç konumuna ekle
                        </p>
                      </div>
                    ) : current.runtime_variables?.length > 0 ? (
                      <div
                        className="rounded-lg px-3 py-2.5 text-[11px]"
                        style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)', color: 'var(--color-text-muted)' }}
                      >
                        Yalnizca runtime degiskenleri kullanir (asagiya bkz).
                      </div>
                    ) : (
                      <div
                        className="rounded-lg px-3 py-2.5 text-[11px]"
                        style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--color-border)', color: 'var(--color-text-muted)' }}
                      >
                        Bu prompt degisken kullanmiyor.
                      </div>
                    )}
                  </div>

                  {/* Runtime variables */}
                  {current.runtime_variables?.length > 0 && (
                    <div>
                      <div className="text-[10px] font-semibold uppercase tracking-[0.15em] mb-2" style={{ color: 'var(--color-text-muted)' }}>
                        Runtime Degiskenler
                      </div>
                      <div className="space-y-1.5">
                        {current.runtime_variables.map((v) => (
                          <div
                            key={v}
                            className="flex items-center gap-2 rounded-lg px-2.5 py-2"
                            style={{
                              background: 'rgba(245,158,11,0.06)',
                              border: '1px solid rgba(245,158,11,0.15)',
                            }}
                          >
                            <svg className="h-3 w-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} style={{ color: '#fbbf24' }}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                            <span className="font-mono text-[11px]" style={{ color: '#fbbf24' }}>
                              {`{${v}}`}
                            </span>
                          </div>
                        ))}
                        <p className="mt-1 text-[10px] leading-4" style={{ color: 'var(--color-text-muted)' }}>
                          Calisma zamaninda otomatik enjekte edilir. Yerlerini degistirmeyin, silmeyin.
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Stats */}
                  <div>
                    <div className="text-[10px] font-semibold uppercase tracking-[0.15em] mb-2" style={{ color: 'var(--color-text-muted)' }}>
                      Istatistikler
                    </div>
                    <div className="space-y-2">
                      <StatRow label="Karakter" value={currentValue.length.toString()} />
                      <StatRow label="Kelime" value={wordCount(currentValue).toString()} />
                      <StatRow label="Satir" value={lineCount(currentValue).toString()} />
                      <StatRow label="Degisken" value={`${(currentValue.match(/\{\{[^}]+\}\}/g) || []).length} kullanim`} />
                    </div>
                  </div>

                  {/* File info */}
                  <div>
                    <div className="text-[10px] font-semibold uppercase tracking-[0.15em] mb-2" style={{ color: 'var(--color-text-muted)' }}>
                      Dosya
                    </div>
                    <div className="space-y-2">
                      <StatRow label="Anahtar" value={current.key} mono />
                      <StatRow label="Dosya Adi" value={PROMPT_FILE_NAMES[activeKey] ?? ''} mono />
                      <StatRow label="Konum" value="prompts/" mono />
                    </div>
                  </div>
                </div>

                {/* Quick actions */}
                <div className="mt-auto p-4 space-y-2" style={{ borderTop: '1px solid var(--color-border)' }}>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.15em] mb-2" style={{ color: 'var(--color-text-muted)' }}>
                    Islemler
                  </div>
                  <button
                    onClick={() => setConfirmReset(activeKey)}
                    disabled={resetMut.isPending}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[11px] transition-all duration-200 disabled:opacity-40"
                    style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)', color: '#fca5a5' }}
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Bu Promptu Sifirla
                  </button>
                  <button
                    onClick={() => setConfirmReset('__all__')}
                    disabled={resetMut.isPending}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[11px] transition-all duration-200 disabled:opacity-40"
                    style={{ background: 'rgba(239,68,68,0.04)', border: '1px solid rgba(239,68,68,0.1)', color: 'var(--color-text-muted)' }}
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    Tumunu Sifirla
                  </button>
                </div>
              </aside>
            </div>
          </>
        ) : showLayering ? (
          /* Layering order visualization */
          <LayeringOrderPanel data={layeringQ.data ?? null} onSelectPrompt={(key) => { setShowLayering(false); setActiveKey(key); }} />
        ) : (
          /* Empty state */
          <div className="flex flex-1 items-center justify-center">
            <div className="flex flex-col items-center gap-4 text-center">
              <div
                className="flex h-16 w-16 items-center justify-center rounded-2xl"
                style={{ background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)' }}
              >
                <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} style={{ color: 'var(--color-primary-light)' }}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </div>
              <div>
                <h3 className="text-[15px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                  Prompt Sec
                </h3>
                <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                  Sol panelden duzenlemek istedigin promptu sec.
                </p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

/* ─── File name mapping ──────────────────────────────────────────────────── */

const PROMPT_FILE_NAMES: Record<string, string> = {
  description_system: 'description_rewrite.system.txt',
  description_user: 'description_rewrite.user.txt',
  translation_system: 'translation_en.system.txt',
  translation_user: 'translation_en.user.txt',
  geo_rewrite_system: 'geo_rewrite.system.txt',
  geo_rewrite_user: 'geo_rewrite.user.txt',
  llms_summary_system: 'llms_summary.system.txt',
  llms_summary_user: 'llms_summary.user.txt',
  agent_seo_expert_system: 'agent_seo_expert.system.txt',
  agent_store_operator_system: 'agent_store_operator.system.txt',
  agent_general_system: 'agent_general.system.txt',
  chat_option_buttons_system: 'chat_option_buttons.system.txt',
  ikas_operation_guide_system: 'ikas_operation_guide.system.txt',
  rewrite_agent_system: 'rewrite_agent.system.txt',
  batch_agent_system: 'batch_agent.system.txt',
  geo_agent_system: 'geo_agent.system.txt',
};

/* ─── Layering Order Panel ────────────────────────────────────────────────── */

const FLOW_COLORS: Record<string, { accent: string; bg: string; border: string }> = {
  chat: { accent: '#818cf8', bg: 'rgba(129,140,248,0.06)', border: 'rgba(129,140,248,0.18)' },
  rewrite: { accent: '#34d399', bg: 'rgba(52,211,153,0.06)', border: 'rgba(52,211,153,0.18)' },
  batch: { accent: '#fbbf24', bg: 'rgba(251,191,36,0.06)', border: 'rgba(251,191,36,0.18)' },
  product_rewrite: { accent: '#f472b6', bg: 'rgba(244,114,182,0.06)', border: 'rgba(244,114,182,0.18)' },
};

function LayeringOrderPanel({
  data,
  onSelectPrompt,
}: {
  data: PromptLayeringOrder | null;
  onSelectPrompt: (key: string) => void;
}) {
  if (!data) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-transparent" style={{ borderTopColor: 'var(--color-primary)' }} />
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto p-8" style={{ background: 'var(--color-bg-base)' }}>
      <div className="mx-auto max-w-4xl">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-3">
            <div
              className="flex h-10 w-10 items-center justify-center rounded-xl"
              style={{ background: 'rgba(168,85,247,0.1)', border: '1px solid rgba(168,85,247,0.25)' }}
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5} style={{ color: '#c084fc' }}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 12c0-1.232-.046-2.453-.138-3.662a4.006 4.006 0 00-3.7-3.7 48.678 48.678 0 00-7.324 0 4.006 4.006 0 00-3.7 3.7c-.017.22-.032.441-.046.662M19.5 12l3-3m-3 3l-3-3m-12 3c0 1.232.046 2.453.138 3.662a4.006 4.006 0 003.7 3.7 48.656 48.656 0 007.324 0 4.006 4.006 0 003.7-3.7c.017-.22.032-.441.046-.662M4.5 12l3 3m-3-3l-3 3" />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-semibold" style={{ color: 'var(--color-text-primary)' }}>Prompt Katmanlama Sirasi</h2>
              <p className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                Her akista promptlar belirtilen sirada birlestirilir ve AI'a gonderilir.
              </p>
            </div>
          </div>
        </div>

        {/* Flow cards */}
        <div className="space-y-6">
          {data.flows.map((flow) => {
            const colors = FLOW_COLORS[flow.id] ?? FLOW_COLORS.chat;
            return (
              <div
                key={flow.id}
                className="rounded-2xl p-5"
                style={{ background: colors.bg, border: `1px solid ${colors.border}` }}
              >
                <div className="flex items-center gap-3 mb-4">
                  <div
                    className="flex h-7 w-7 items-center justify-center rounded-lg text-[12px] font-bold"
                    style={{ background: colors.border, color: colors.accent }}
                  >
                    {flow.layers.length}
                  </div>
                  <div>
                    <h3 className="text-[14px] font-semibold" style={{ color: colors.accent }}>{flow.title}</h3>
                    <p className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>{flow.description}</p>
                  </div>
                </div>

                {/* Layers */}
                <div className="space-y-0">
                  {flow.layers.map((layer, idx) => {
                    const isLast = idx === flow.layers.length - 1;
                    const isEditable = !!layer.prompt_key;
                    return (
                      <div key={idx} className="flex items-stretch gap-3">
                        {/* Timeline connector */}
                        <div className="flex flex-col items-center" style={{ width: '24px' }}>
                          <div
                            className="flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold flex-shrink-0"
                            style={{
                              background: isEditable ? colors.border : 'rgba(255,255,255,0.06)',
                              color: isEditable ? colors.accent : 'var(--color-text-muted)',
                              border: `1.5px solid ${isEditable ? colors.accent : 'rgba(255,255,255,0.1)'}`,
                            }}
                          >
                            {layer.order}
                          </div>
                          {!isLast && (
                            <div className="flex-1 w-px my-0.5" style={{ background: 'rgba(255,255,255,0.08)', minHeight: '8px' }} />
                          )}
                        </div>

                        {/* Content */}
                        <div className={`flex-1 ${isLast ? '' : 'pb-3'}`}>
                          <div
                            className={`rounded-xl px-3.5 py-2.5 ${isEditable ? 'cursor-pointer transition-all duration-150 hover:brightness-125' : ''}`}
                            style={{
                              background: isEditable ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.02)',
                              border: isEditable ? `1px solid ${colors.border}` : '1px solid rgba(255,255,255,0.05)',
                            }}
                            onClick={() => isEditable && layer.prompt_key && onSelectPrompt(layer.prompt_key)}
                          >
                            <div className="flex items-center gap-2 mb-0.5">
                              <span className="text-[12px] font-medium" style={{ color: isEditable ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}>
                                {layer.label}
                              </span>
                              {isEditable && (
                                <span
                                  className="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider"
                                  style={{ background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.25)', color: '#a78bfa' }}
                                >
                                  Duzenlenebilir
                                </span>
                              )}
                              {!isEditable && (
                                <span
                                  className="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider"
                                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'var(--color-text-muted)' }}
                                >
                                  Dinamik
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] leading-4" style={{ color: 'var(--color-text-muted)' }}>
                              {layer.description}
                            </p>
                            {layer.linked_keys.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1">
                                {layer.linked_keys.map((lk) => (
                                  <button
                                    key={lk}
                                    onClick={(e) => { e.stopPropagation(); onSelectPrompt(lk); }}
                                    className="rounded-md px-2 py-0.5 text-[10px] font-mono transition-all duration-150 hover:brightness-125"
                                    style={{ background: colors.border, color: colors.accent }}
                                  >
                                    {lk}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ─── Sub-components ─────────────────────────────────────────────────────── */

function LineGutter({ text }: { text: string }) {
  const lines = text.split('\n').length;
  return (
    <div
      className="flex flex-col items-end overflow-hidden py-4 pr-3 pl-4 select-none"
      style={{
        background: 'rgba(11,17,32,0.6)',
        borderRight: '1px solid var(--color-border)',
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace",
        fontSize: '13px',
        lineHeight: '1.7',
        color: 'var(--color-text-muted)',
        minWidth: '48px',
      }}
    >
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="text-right" style={{ opacity: 0.5 }}>
          {i + 1}
        </div>
      ))}
    </div>
  );
}

function HighlightedPreview({ text, variables }: { text: string; variables: string[] }) {
  const parts: { type: 'text' | 'variable' | 'runtime_var' | 'json'; content: string }[] = [];
  const varSet = new Set(variables);

  // Split by {{...}} and {...} placeholders
  const regex = /(\{\{[^}]+\}\}|\{[a-z_]+\})/g;
  let lastIdx = 0;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push({ type: 'text', content: text.slice(lastIdx, match.index) });
    }
    const raw = match[1];
    if (raw.startsWith('{{')) {
      const varName = raw.replace(/^\{\{\s*|\s*\}\}$/g, '');
      parts.push({
        type: varSet.has(varName) ? 'variable' : 'text',
        content: raw,
      });
    } else {
      // Single-brace runtime variable like {product_context}
      parts.push({ type: 'runtime_var', content: raw });
    }
    lastIdx = regex.lastIndex;
  }
  if (lastIdx < text.length) {
    const tail = text.slice(lastIdx);
    if (tail.trim().startsWith('{') || tail.trim().startsWith('SADECE JSON')) {
      parts.push({ type: 'json', content: tail });
    } else {
      parts.push({ type: 'text', content: tail });
    }
  }

  return (
    <pre
      className="whitespace-pre-wrap break-words"
      style={{
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace",
        fontSize: '12.5px',
        lineHeight: '1.8',
        color: 'var(--color-text-secondary)',
      }}
    >
      {parts.map((part, i) => {
        if (part.type === 'variable') {
          return (
            <span
              key={i}
              className="rounded px-1 py-0.5"
              style={{
                background: 'rgba(6,182,212,0.12)',
                border: '1px solid rgba(6,182,212,0.25)',
                color: 'var(--color-accent-light)',
              }}
            >
              {part.content}
            </span>
          );
        }
        if (part.type === 'runtime_var') {
          return (
            <span
              key={i}
              className="rounded px-1 py-0.5"
              style={{
                background: 'rgba(245,158,11,0.12)',
                border: '1px solid rgba(245,158,11,0.25)',
                color: '#fbbf24',
              }}
            >
              {part.content}
            </span>
          );
        }
        if (part.type === 'json') {
          return (
            <span key={i} style={{ color: 'var(--color-warning)' }}>
              {part.content}
            </span>
          );
        }
        return <span key={i}>{part.content}</span>;
      })}
    </pre>
  );
}

function StatRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>{label}</span>
      <span
        className={`text-[11px] ${mono ? 'font-mono' : ''}`}
        style={{ color: 'var(--color-text-secondary)' }}
      >
        {value}
      </span>
    </div>
  );
}
