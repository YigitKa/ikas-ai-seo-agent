import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { deleteStoreMemory, getStoreMemories, saveStoreMemory } from '../../api/client';
import type { StoreMemoryEntry, StoreMemoryType } from '../../types';
import { useToast } from '../../shared/ui/Toast';
import {
  EnterpriseButton,
  EnterprisePill,
  EnterpriseSectionCard,
  EnterpriseSelectField,
  EnterpriseToggleField,
} from '../../shared/ui/EnterprisePrimitives';
import { Banner, type BannerTone } from '../../components/settings/UiPrimitives';

const MEMORY_TYPE_OPTIONS: Array<{ value: StoreMemoryType; label: string }> = [
  { value: 'brand_tone', label: 'Marka tonu' },
  { value: 'forbidden_claim', label: 'Yasak claim' },
  { value: 'category_glossary', label: 'Kategori sozlugu' },
  { value: 'approved_preference', label: 'Onayli tercih' },
  { value: 'operation_note', label: 'Operasyon notu' },
];

function createMemoryId() {
  return globalThis.crypto?.randomUUID?.() ?? `memory-${Date.now()}`;
}

function createEmptyMemory(): StoreMemoryEntry {
  const now = new Date().toISOString();
  return {
    id: createMemoryId(),
    memory_type: 'brand_tone',
    title: '',
    content: '',
    summary: '',
    category: '',
    source: 'manual',
    enabled: true,
    metadata: {},
    created_at: now,
    updated_at: now,
  };
}

function toneForType(memoryType: string): 'primary' | 'warning' | 'danger' | 'success' | 'neutral' {
  if (memoryType === 'forbidden_claim') return 'danger';
  if (memoryType === 'approved_preference') return 'success';
  if (memoryType === 'operation_note') return 'warning';
  if (memoryType === 'brand_tone') return 'primary';
  return 'neutral';
}

export default function StoreMemorySection() {
  const qc = useQueryClient();
  const toast = useToast();
  const [banner, setBanner] = useState<{ tone: BannerTone; message: string } | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [draft, setDraft] = useState<StoreMemoryEntry>(() => createEmptyMemory());

  const memoriesQ = useQuery({
    queryKey: ['store-memory'],
    queryFn: getStoreMemories,
  });

  const items = memoriesQ.data?.items ?? [];
  const existingSelected = useMemo(
    () => items.find((item) => item.id === selectedId) ?? null,
    [items, selectedId],
  );

  useEffect(() => {
    if (!items.length) {
      if (selectedId) setSelectedId('');
      return;
    }
    if (!selectedId || !existingSelected) {
      setSelectedId(items[0].id);
    }
  }, [items, selectedId, existingSelected]);

  useEffect(() => {
    if (existingSelected) {
      setDraft(existingSelected);
    }
  }, [existingSelected]);

  const saveMut = useMutation({
    mutationFn: async (memory: StoreMemoryEntry) => saveStoreMemory(memory.id, memory),
    onSuccess: async (saved) => {
      await qc.invalidateQueries({ queryKey: ['store-memory'] });
      setSelectedId(saved.id);
      setDraft(saved);
      setBanner({ tone: 'success', message: 'Kalici hafiza kaydedildi.' });
      toast.success('Kalici hafiza kaydedildi.');
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : 'Store memory kaydedilemedi.';
      setBanner({ tone: 'error', message });
      toast.error(message);
    },
  });

  const deleteMut = useMutation({
    mutationFn: async (memoryId: string) => deleteStoreMemory(memoryId),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['store-memory'] });
      setSelectedId('');
      setDraft(createEmptyMemory());
      setBanner({ tone: 'success', message: 'Kalici hafiza silindi.' });
      toast.success('Kalici hafiza silindi.');
    },
    onError: (error) => {
      const message = error instanceof Error ? error.message : 'Store memory silinemedi.';
      setBanner({ tone: 'error', message });
      toast.error(message);
    },
  });

  const setField = <K extends keyof StoreMemoryEntry>(key: K, value: StoreMemoryEntry[K]) => {
    setDraft((prev) => ({ ...prev, [key]: value, updated_at: new Date().toISOString() }));
  };

  const handleNew = () => {
    setBanner(null);
    setSelectedId('');
    setDraft(createEmptyMemory());
  };

  const handleDelete = () => {
    if (existingSelected) {
      deleteMut.mutate(existingSelected.id);
      return;
    }
    setDraft(createEmptyMemory());
  };

  return (
    <EnterpriseSectionCard
      eyebrow="Memory"
      title="Kalici Magaza Hafizasi"
      description="Marka tonu, yasak claim ve onayli tercihleri kalici olarak tutar. Chat ve rewrite akislari bu veriyi kontrollu boyutta prompta ekler."
    >
      <div className="flex flex-wrap gap-2">
        <EnterpriseButton tone="primary" size="lg" onClick={handleNew}>
          Yeni Hafiza
        </EnterpriseButton>
        <EnterpriseButton
          tone="success"
          size="lg"
          onClick={() => {
            setBanner(null);
            saveMut.mutate(draft);
          }}
          disabled={saveMut.isPending || !draft.content.trim()}
        >
          {saveMut.isPending ? 'Kaydediliyor...' : 'Kaydet'}
        </EnterpriseButton>
        <EnterpriseButton
          tone="danger"
          size="lg"
          onClick={handleDelete}
          disabled={deleteMut.isPending}
        >
          {deleteMut.isPending ? 'Siliniyor...' : existingSelected ? 'Sil' : 'Temizle'}
        </EnterpriseButton>
      </div>

      {banner && <Banner tone={banner.tone} message={banner.message} className="mt-4" />}

      <div className="mt-5 grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-3">
          <div className="text-xs uppercase tracking-[0.18em]" style={{ color: 'var(--color-text-muted)' }}>
            Kayitli Hafiza
          </div>
          <div className="max-h-[560px] space-y-3 overflow-auto pr-1">
            {memoriesQ.isLoading && (
              <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-4 text-sm text-slate-400">
                Hafiza kayitlari yukleniyor...
              </div>
            )}
            {!memoriesQ.isLoading && items.length === 0 && (
              <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-4 text-sm text-slate-400">
                Henuz store memory kaydi yok.
              </div>
            )}
            {items.map((item) => {
              const active = item.id === selectedId;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setSelectedId(item.id)}
                  className="w-full rounded-2xl border px-4 py-3 text-left transition-all duration-200 hover:-translate-y-0.5"
                  style={{
                    borderColor: active ? 'rgba(96,165,250,0.4)' : 'rgba(51,65,85,0.85)',
                    background: active ? 'rgba(30,41,59,0.9)' : 'rgba(2,6,23,0.65)',
                    boxShadow: active ? '0 18px 30px rgba(15,23,42,0.24)' : 'none',
                  }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold text-slate-100">
                        {item.title}
                      </div>
                      <div className="mt-1 truncate text-xs text-slate-400">
                        {item.category || 'Tum kategoriler'}
                      </div>
                    </div>
                    <EnterprisePill tone={toneForType(item.memory_type)}>
                      {MEMORY_TYPE_OPTIONS.find((option) => option.value === item.memory_type)?.label ?? item.memory_type}
                    </EnterprisePill>
                  </div>
                  <p className="mt-3 text-xs leading-5 text-slate-400">
                    {item.summary}
                  </p>
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
              Baslik
            </span>
            <input
              value={draft.title}
              onChange={(event) => setField('title', event.target.value)}
              placeholder="Orn. Premium ama iddiali olmayan ton"
              className="enterprise-field rounded-xl"
            />
          </label>

          <EnterpriseSelectField
            label="Hafiza Tipi"
            value={draft.memory_type}
            onChange={(value) => setField('memory_type', value)}
            options={MEMORY_TYPE_OPTIONS}
          />

          <label className="block">
            <span className="mb-1.5 block text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
              Kategori
            </span>
            <input
              value={draft.category}
              onChange={(event) => setField('category', event.target.value)}
              placeholder="Bos birakilirsa tum kategoriler"
              className="enterprise-field rounded-xl"
            />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
              Kaynak
            </span>
            <input
              value={draft.source}
              onChange={(event) => setField('source', event.target.value)}
              placeholder="manual"
              className="enterprise-field rounded-xl"
            />
          </label>

          <div className="md:col-span-2">
            <EnterpriseToggleField
              title="Aktif"
              description="Kapali hafizalar saklanir ama prompta dahil edilmez."
              checked={draft.enabled}
              onChange={(checked) => setField('enabled', checked)}
            />
          </div>

          <label className="block md:col-span-2">
            <span className="mb-1.5 block text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
              Ozet
            </span>
            <textarea
              value={draft.summary}
              onChange={(event) => setField('summary', event.target.value)}
              placeholder="Prompta girecek kisa versiyon. Bos birakirsan backend content'ten otomatik ozetler."
              className="enterprise-field min-h-[110px] rounded-xl px-4 py-3"
            />
          </label>

          <label className="block md:col-span-2">
            <span className="mb-1.5 block text-[13px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
              Icerik
            </span>
            <textarea
              value={draft.content}
              onChange={(event) => setField('content', event.target.value)}
              placeholder="Marka kurali, yasak claim, kategori kelime sozlugu veya operasyon notu"
              className="enterprise-field min-h-[180px] rounded-xl px-4 py-3"
            />
          </label>

          <div className="md:col-span-2 grid gap-3 md:grid-cols-3">
            <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-4">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">ID</div>
              <div className="mt-2 break-all font-mono text-xs text-slate-300">{draft.id}</div>
            </div>
            <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-4">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Olusturuldu</div>
              <div className="mt-2 text-xs text-slate-300">{draft.created_at || '-'}</div>
            </div>
            <div className="rounded-2xl border border-slate-800/80 bg-slate-950/55 p-4">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">Guncellendi</div>
              <div className="mt-2 text-xs text-slate-300">{draft.updated_at || '-'}</div>
            </div>
          </div>
        </div>
      </div>
    </EnterpriseSectionCard>
  );
}
