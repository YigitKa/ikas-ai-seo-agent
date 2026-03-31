import { useCallback, useEffect, useMemo, useState, type Dispatch, type SetStateAction } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import AppHeader from '../../shared/ui/AppHeader';
import ConfirmDialog from '../../shared/ui/ConfirmDialog';
import { useToast } from '../../shared/ui/Toast';
import {
  deleteSkill,
  getPromptTemplates,
  getSkills,
  previewSkill,
  resetSkill,
  saveSkill,
  validateSkill,
} from '../../api/client';
import type {
  PromptGroup,
  PromptTemplate,
  SkillDefinition,
  SkillPreview,
  SkillPromptLayer,
  SkillValidation,
} from '../../types';

type EditorTab = 'instructions' | 'layers' | 'metadata';

const APPLIES_TO_OPTIONS = [
  { value: 'chat', label: 'Chat' },
  { value: 'rewrite', label: 'Rewrite' },
  { value: 'batch', label: 'Batch' },
] as const;

const STATUS_OPTIONS = ['active', 'draft', 'disabled'] as const;

const SOURCE_BADGE: Record<string, { label: string; color: string; bg: string; border: string }> = {
  system: {
    label: 'DEFAULT',
    color: '#38bdf8',
    bg: 'rgba(56,189,248,0.10)',
    border: 'rgba(56,189,248,0.25)',
  },
  project: {
    label: 'CUSTOM',
    color: '#a78bfa',
    bg: 'rgba(167,139,250,0.10)',
    border: 'rgba(167,139,250,0.25)',
  },
};

const STATUS_BADGE: Record<string, { color: string; bg: string; border: string }> = {
  active: {
    color: '#34d399',
    bg: 'rgba(52,211,153,0.10)',
    border: 'rgba(52,211,153,0.25)',
  },
  draft: {
    color: '#fbbf24',
    bg: 'rgba(251,191,36,0.10)',
    border: 'rgba(251,191,36,0.25)',
  },
  disabled: {
    color: '#94a3b8',
    bg: 'rgba(148,163,184,0.10)',
    border: 'rgba(148,163,184,0.20)',
  },
};

const TAB_META: Record<EditorTab, { label: string; icon: string }> = {
  instructions: {
    label: 'Instructions',
    icon: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
  },
  layers: {
    label: 'Layers',
    icon: 'M3.75 9h16.5m-16.5 6.75h16.5m-12-13.5h7.5',
  },
  metadata: {
    label: 'Metadata',
    icon: 'M10.5 6h9.75M10.5 12h9.75M10.5 18h9.75M3.75 6h.008v.008H3.75V6zm0 6h.008v.008H3.75V12zm0 6h.008v.008H3.75V18z',
  },
};

const EMPTY_SKILL: SkillDefinition = {
  schema_version: 1,
  slug: 'custom-skill',
  name: 'New Skill',
  description: '',
  when_to_use: '',
  applies_to: ['chat'],
  allowed_tools: [],
  prompt_layers: [],
  tags: [],
  priority: 100,
  status: 'draft',
  instructions_markdown: '',
  source: 'project',
  content_hash: '',
  is_default: false,
};

function uniquePreserve(values: string[]) {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    if (!value || seen.has(value)) continue;
    seen.add(value);
    result.push(value);
  }
  return result;
}

function parseCsv(value: string) {
  return uniquePreserve(
    value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean),
  );
}

function formatCsv(values: string[]) {
  return values.join(', ');
}

function wordCount(text: string) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function lineCount(text: string) {
  return text.split('\n').length;
}

function flattenPrompts(groups: PromptGroup[]) {
  return groups.flatMap((group) => group.prompts);
}

function cloneLayer(layer: SkillPromptLayer): SkillPromptLayer {
  return {
    type: layer.type,
    label: layer.label,
    prompt_key: layer.prompt_key,
    content: layer.content,
  };
}

function cloneSkill(skill: SkillDefinition): SkillDefinition {
  return {
    ...skill,
    applies_to: [...skill.applies_to],
    allowed_tools: [...skill.allowed_tools],
    prompt_layers: skill.prompt_layers.map(cloneLayer),
    tags: [...skill.tags],
  };
}

function normalizeLayer(layer: SkillPromptLayer): SkillPromptLayer {
  return {
    type: layer.type === 'prompt_reference' ? 'prompt_reference' : 'inline',
    label: layer.label.trim(),
    prompt_key: layer.prompt_key.trim(),
    content: layer.content.replace(/\r\n/g, '\n').trim(),
  };
}

function serializeDraft(skill: SkillDefinition) {
  return JSON.stringify({
    ...skill,
    slug: skill.slug.trim().toLowerCase(),
    name: skill.name.trim(),
    description: skill.description.trim(),
    when_to_use: skill.when_to_use.trim(),
    applies_to: uniquePreserve(skill.applies_to.map((value) => value.trim().toLowerCase())),
    allowed_tools: uniquePreserve(skill.allowed_tools.map((value) => value.trim())),
    prompt_layers: skill.prompt_layers.map(normalizeLayer),
    tags: uniquePreserve(skill.tags.map((value) => value.trim())),
    status: skill.status.trim().toLowerCase(),
    instructions_markdown: skill.instructions_markdown.replace(/\r\n/g, '\n'),
  });
}

function normalizeSkillDraft(skill: SkillDefinition): SkillDefinition {
  return {
    ...skill,
    slug: skill.slug.trim().toLowerCase(),
    name: skill.name.trim(),
    description: skill.description.trim(),
    when_to_use: skill.when_to_use.trim(),
    applies_to: uniquePreserve(skill.applies_to.map((value) => value.trim().toLowerCase()).filter(Boolean)),
    allowed_tools: uniquePreserve(skill.allowed_tools.map((value) => value.trim()).filter(Boolean)),
    prompt_layers: skill.prompt_layers.map(normalizeLayer),
    tags: uniquePreserve(skill.tags.map((value) => value.trim()).filter(Boolean)),
    status: skill.status.trim().toLowerCase(),
    instructions_markdown: skill.instructions_markdown.replace(/\r\n/g, '\n'),
  };
}

function createNewSkill(index: number): SkillDefinition {
  return {
    ...cloneSkill(EMPTY_SKILL),
    slug: `custom-skill-${index}`,
    name: `Custom Skill ${index}`,
    instructions_markdown: [
      '# Goal',
      '',
      'Bu skill hangi durumda devreye girmeli, hangi sinirlari korumali ve nasil bir cikti bekleniyor burada yaz.',
      '',
      '## Rules',
      '- Urun verisine sadik kal.',
      '- Gerekmedikce yeni iddia uydurma.',
    ].join('\n'),
  };
}

function buildGroups(items: SkillDefinition[], searchQuery: string) {
  const query = searchQuery.trim().toLowerCase();
  const filtered = !query
    ? items
    : items.filter((item) => {
        const haystack = [
          item.name,
          item.slug,
          item.description,
          item.when_to_use,
          item.status,
          item.tags.join(' '),
        ]
          .join(' ')
          .toLowerCase();
        return haystack.includes(query);
      });

  const systemItems = filtered.filter((item) => item.is_default);
  const projectItems = filtered.filter((item) => !item.is_default);

  return [
    systemItems.length > 0 ? { label: 'Varsayilan Skilller', items: systemItems } : null,
    projectItems.length > 0 ? { label: 'Custom Skilller', items: projectItems } : null,
  ].filter(Boolean) as Array<{ label: string; items: SkillDefinition[] }>;
}

function skillBadgeMeta(skill: SkillDefinition) {
  return SOURCE_BADGE[skill.source] ?? SOURCE_BADGE.project;
}

function layerLabel(layer: SkillPromptLayer, promptLookup: Map<string, PromptTemplate>) {
  if (layer.label.trim()) return layer.label.trim();
  if (layer.type === 'prompt_reference') {
    return promptLookup.get(layer.prompt_key)?.title ?? layer.prompt_key ?? 'Prompt Reference';
  }
  return 'Inline Layer';
}

export default function SkillStudioPage() {
  const qc = useQueryClient();
  const toast = useToast();

  const skillsQ = useQuery({
    queryKey: ['skills'],
    queryFn: getSkills,
  });

  const promptsQ = useQuery({
    queryKey: ['prompt-templates'],
    queryFn: getPromptTemplates,
  });

  const items = skillsQ.data?.items ?? [];
  const availableTools = skillsQ.data?.available_tools ?? [];
  const promptGroups = promptsQ.data?.groups ?? [];
  const promptTemplates = useMemo(() => flattenPrompts(promptGroups), [promptGroups]);
  const promptLookup = useMemo(
    () => new Map(promptTemplates.map((prompt) => [prompt.key, prompt])),
    [promptTemplates],
  );

  const [selectedSlug, setSelectedSlug] = useState('');
  const [draft, setDraft] = useState<SkillDefinition>(cloneSkill(EMPTY_SKILL));
  const [originalSnapshot, setOriginalSnapshot] = useState<SkillDefinition | null>(null);
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [editorTab, setEditorTab] = useState<EditorTab>('instructions');
  const [showPreview, setShowPreview] = useState(false);
  const [previewTarget, setPreviewTarget] = useState('chat');
  const [tagsText, setTagsText] = useState('');
  const [preview, setPreview] = useState<SkillPreview | null>(null);
  const [validation, setValidation] = useState<SkillValidation | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [previewAttemptKey, setPreviewAttemptKey] = useState('');

  const groupedItems = useMemo(() => buildGroups(items, searchQuery), [items, searchQuery]);
  const selectedExistingSkill = useMemo(
    () => items.find((item) => item.slug === selectedSlug) ?? null,
    [items, selectedSlug],
  );

  const draftWithTags = useMemo(
    () => ({
      ...draft,
      tags: parseCsv(tagsText),
    }),
    [draft, tagsText],
  );

  const normalizedDraft = useMemo(() => {
    try {
      return { skill: normalizeSkillDraft(draftWithTags), error: '' };
    } catch (error) {
      return {
        skill: null,
        error: error instanceof Error ? error.message : 'Skill formu gecersiz.',
      };
    }
  }, [draftWithTags]);

  const draftFingerprint = useMemo(() => serializeDraft(draftWithTags), [draftWithTags]);
  const originalFingerprint = useMemo(
    () => (originalSnapshot ? serializeDraft(originalSnapshot) : ''),
    [originalSnapshot],
  );
  const hasDirty = isCreatingNew || draftFingerprint !== originalFingerprint;
  const previewRequestKey = `${previewTarget}:${draftFingerprint}`;
  const previewTargets = draft.applies_to.length > 0
    ? draft.applies_to
    : APPLIES_TO_OPTIONS.map((option) => option.value);
  const activeValidation = preview?.validation ?? validation;
  const resolvedLayers = activeValidation?.resolved_prompt_layers ?? [];
  const dirtyLabel = isCreatingNew
    ? 'Yeni skill kaydedilmeyi bekliyor'
    : hasDirty
      ? 'Kaydedilmemis degisiklik var'
      : 'Kayitla senkron';

  const loadSkillIntoEditor = useCallback((skill: SkillDefinition) => {
    const cloned = cloneSkill(skill);
    setDraft(cloned);
    setOriginalSnapshot(cloned);
    setTagsText(formatCsv(cloned.tags));
    setSelectedSlug(skill.slug);
    setIsCreatingNew(false);
    setValidation(null);
    setPreview(null);
    setPreviewAttemptKey('');
  }, []);

  const handleCreateSkill = useCallback(() => {
    const next = createNewSkill(items.length + 1);
    setDraft(next);
    setOriginalSnapshot(next);
    setTagsText('');
    setSelectedSlug('__new__');
    setIsCreatingNew(true);
    setEditorTab('instructions');
    setValidation(null);
    setPreview(null);
    setPreviewAttemptKey('');
    setShowPreview(false);
  }, [items.length]);

  useEffect(() => {
    if (items.length === 0) return;
    if (!selectedSlug) {
      loadSkillIntoEditor(items[0]);
      return;
    }
    if (selectedSlug === '__new__') return;
    const next = items.find((item) => item.slug === selectedSlug);
    if (!next) {
      loadSkillIntoEditor(items[0]);
      return;
    }
    if (!hasDirty && originalSnapshot && originalSnapshot.content_hash !== next.content_hash) {
      loadSkillIntoEditor(next);
    }
  }, [items, selectedSlug, loadSkillIntoEditor, hasDirty, originalSnapshot]);

  useEffect(() => {
    if (previewTargets.length === 0) return;
    if (!previewTargets.includes(previewTarget)) {
      setPreviewTarget(previewTargets[0]);
    }
  }, [previewTarget, previewTargets]);

  useEffect(() => {
    setPreview(null);
    setValidation(null);
    setPreviewAttemptKey('');
  }, [draftFingerprint, previewTarget]);

  const buildPayload = useCallback(() => {
    if (!normalizedDraft.skill) {
      throw new Error(normalizedDraft.error || 'Skill formu gecersiz.');
    }
    return normalizedDraft.skill;
  }, [normalizedDraft]);

  const saveMut = useMutation({
    mutationFn: async (skill: SkillDefinition) => saveSkill(skill.slug, skill),
    onSuccess: async (saved) => {
      const cloned = cloneSkill(saved);
      setDraft(cloned);
      setOriginalSnapshot(cloned);
      setTagsText(formatCsv(cloned.tags));
      setSelectedSlug(saved.slug);
      setIsCreatingNew(false);
      setValidation(null);
      setPreview(null);
      setPreviewAttemptKey('');
      await qc.invalidateQueries({ queryKey: ['skills'] });
      toast.success('Skill kaydedildi.');
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Skill kaydedilemedi.');
    },
  });

  const validateMut = useMutation({
    mutationFn: async (skill: SkillDefinition) => validateSkill(skill),
    onSuccess: (result) => {
      setValidation(result);
      toast.success(result.ok ? 'Validation basarili.' : 'Validation hata verdi.');
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Validation basarisiz.');
    },
  });

  const previewMut = useMutation({
    mutationFn: async (input: { skill: SkillDefinition; appliesTo: string }) =>
      previewSkill(input.skill, input.appliesTo),
    onSuccess: (result) => {
      setPreview(result);
      setValidation(result.validation);
      toast.success('Prompt preview hazirlandi.');
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Preview olusturulamadi.');
    },
  });

  const resetMut = useMutation({
    mutationFn: async () => {
      if (!selectedExistingSkill) throw new Error('Reset icin mevcut bir skill secin.');
      return resetSkill(selectedExistingSkill.slug);
    },
    onSuccess: async (saved) => {
      setConfirmReset(false);
      loadSkillIntoEditor(saved);
      await qc.invalidateQueries({ queryKey: ['skills'] });
      toast.success('Skill varsayilan haline dondu.');
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Reset basarisiz.');
    },
  });

  const deleteMut = useMutation({
    mutationFn: async () => {
      if (!selectedExistingSkill) throw new Error('Silmek icin mevcut bir skill secin.');
      return deleteSkill(selectedExistingSkill.slug);
    },
    onSuccess: async () => {
      setConfirmDelete(false);
      setSelectedSlug('');
      setOriginalSnapshot(null);
      setDraft(cloneSkill(EMPTY_SKILL));
      setTagsText('');
      setIsCreatingNew(false);
      setValidation(null);
      setPreview(null);
      setPreviewAttemptKey('');
      await qc.invalidateQueries({ queryKey: ['skills'] });
      toast.success('Skill silindi.');
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Skill silinemedi.');
    },
  });

  const runValidate = useCallback(() => {
    try {
      validateMut.mutate(buildPayload());
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Validation baslatilamadi.');
    }
  }, [buildPayload, toast, validateMut]);

  const runPreview = useCallback(() => {
    try {
      const skill = buildPayload();
      setPreviewAttemptKey(previewRequestKey);
      previewMut.mutate({ skill, appliesTo: previewTarget });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Preview baslatilamadi.');
    }
  }, [buildPayload, previewMut, previewRequestKey, previewTarget, toast]);

  const handleSave = useCallback(() => {
    try {
      const skill = buildPayload();
      saveMut.mutate(skill);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Kayit baslatilamadi.');
    }
  }, [buildPayload, saveMut, toast]);

  const handleDiscard = useCallback(() => {
    if (!originalSnapshot) return;
    const cloned = cloneSkill(originalSnapshot);
    setDraft(cloned);
    setTagsText(formatCsv(cloned.tags));
    setValidation(null);
    setPreview(null);
    setPreviewAttemptKey('');
    toast.info(isCreatingNew ? 'Yeni skill taslagi sifirlandi.' : 'Degisiklikler geri alindi.');
  }, [isCreatingNew, originalSnapshot, toast]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handleSave]);

  useEffect(() => {
    if (!showPreview || previewAttemptKey === previewRequestKey) return;
    if (!normalizedDraft.skill) return;
    setPreviewAttemptKey(previewRequestKey);
    previewMut.mutate({ skill: normalizedDraft.skill, appliesTo: previewTarget });
  }, [normalizedDraft, previewAttemptKey, previewMut, previewRequestKey, previewTarget, showPreview]);

  const toggleAppliesTo = (target: string) => {
    setDraft((prev) => {
      const nextTargets = prev.applies_to.includes(target)
        ? prev.applies_to.filter((item) => item !== target)
        : [...prev.applies_to, target];
      return { ...prev, applies_to: nextTargets };
    });
  };

  const toggleTool = (toolName: string) => {
    setDraft((prev) => {
      const nextTools = prev.allowed_tools.includes(toolName)
        ? prev.allowed_tools.filter((item) => item !== toolName)
        : [...prev.allowed_tools, toolName];
      return { ...prev, allowed_tools: nextTools };
    });
  };

  const updateLayer = (index: number, patch: Partial<SkillPromptLayer>) => {
    setDraft((prev) => ({
      ...prev,
      prompt_layers: prev.prompt_layers.map((layer, currentIndex) =>
        currentIndex === index ? { ...layer, ...patch } : layer,
      ),
    }));
  };

  const addLayer = (type: SkillPromptLayer['type']) => {
    const fallbackPrompt = promptTemplates[0]?.key ?? '';
    setDraft((prev) => ({
      ...prev,
      prompt_layers: [
        ...prev.prompt_layers,
        type === 'prompt_reference'
          ? { type, label: '', prompt_key: fallbackPrompt, content: '' }
          : { type, label: '', prompt_key: '', content: '' },
      ],
    }));
  };

  const removeLayer = (index: number) => {
    setDraft((prev) => ({
      ...prev,
      prompt_layers: prev.prompt_layers.filter((_, currentIndex) => currentIndex !== index),
    }));
  };

  const moveLayer = (index: number, direction: -1 | 1) => {
    setDraft((prev) => {
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= prev.prompt_layers.length) return prev;
      const nextLayers = [...prev.prompt_layers];
      const [currentLayer] = nextLayers.splice(index, 1);
      nextLayers.splice(nextIndex, 0, currentLayer);
      return { ...prev, prompt_layers: nextLayers };
    });
  };

  const loading = skillsQ.isLoading || promptsQ.isLoading;
  const currentSkillLabel = draft.name.trim() || draft.slug.trim() || 'Yeni Skill';
  const badge = skillBadgeMeta(draft);
  const statusBadge = STATUS_BADGE[draft.status] ?? STATUS_BADGE.draft;
  const tagList = parseCsv(tagsText);

  if (loading) {
    return <LoadingState />;
  }

  return (
    <div className="page-bg flex h-screen flex-col overflow-hidden">
      <ConfirmDialog
        open={confirmReset}
        title="Skill Reset"
        message="Bu skill varsayilan seed haline geri donecek. Mevcut duzenlemeler kaybolur."
        confirmLabel="Reset"
        cancelLabel="Iptal"
        variant="danger"
        onConfirm={() => resetMut.mutate()}
        onCancel={() => setConfirmReset(false)}
      />
      <ConfirmDialog
        open={confirmDelete}
        title="Skill Sil"
        message="Custom skill klasorden silinecek. Bu islem geri alinamaz."
        confirmLabel="Sil"
        cancelLabel="Iptal"
        variant="danger"
        onConfirm={() => deleteMut.mutate()}
        onCancel={() => setConfirmDelete(false)}
      />

      <AppHeader
        title="Skill Studio"
        description="Prompt Studio duzeniyle skill secin, SKILL.md talimatlarini duzenleyin, layer ve tool sinirlarini yonetin."
        eyebrow={{ label: 'Skill Runtime', tone: 'primary' }}
        breadcrumbs={[
          { label: 'Dashboard', to: '/' },
          { label: 'Ayarlar', to: '/settings' },
          { label: 'Skill Studio' },
        ]}
        meta={[
          { label: 'Skill', value: items.length, tone: 'primary' },
          { label: 'Tool Registry', value: availableTools.length, tone: 'neutral' },
          { label: 'Durum', value: dirtyLabel, tone: hasDirty ? 'warning' : 'success' },
        ]}
        wrapperClassName="px-5"
      />

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <SkillSidebar
          groupedItems={groupedItems}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          handleCreateSkill={handleCreateSkill}
          isCreatingNew={isCreatingNew}
          selectedSlug={selectedSlug}
          draft={draft}
          loadSkillIntoEditor={loadSkillIntoEditor}
          handleSave={handleSave}
          handleDiscard={handleDiscard}
          hasDirty={hasDirty}
          savePending={saveMut.isPending}
        />

        <main className="flex flex-1 flex-col overflow-hidden">
          <div
            className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"
            style={{
              background: 'linear-gradient(180deg, rgba(11,17,32,0.95), rgba(2,6,23,0.88))',
              borderBottom: '1px solid var(--color-border)',
            }}
          >
            <div className="flex min-w-0 items-center gap-3">
              <span
                className="rounded-md px-2 py-1 text-[10px] font-bold uppercase tracking-wider"
                style={{
                  color: badge.color,
                  background: badge.bg,
                  border: `1px solid ${badge.border}`,
                }}
              >
                {badge.label}
              </span>
              <span
                className="rounded-md px-2 py-1 text-[10px] font-bold uppercase tracking-wider"
                style={{
                  color: statusBadge.color,
                  background: statusBadge.bg,
                  border: `1px solid ${statusBadge.border}`,
                }}
              >
                {draft.status}
              </span>
              <h2 className="truncate text-[15px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                {currentSkillLabel}
              </h2>
              {hasDirty && (
                <span
                  className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                  style={{
                    background: 'rgba(245,158,11,0.15)',
                    border: '1px solid rgba(245,158,11,0.3)',
                    color: '#fbbf24',
                  }}
                >
                  Kaydedilmemis
                </span>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {(Object.keys(TAB_META) as EditorTab[]).map((tab) => {
                const meta = TAB_META[tab];
                const isActive = editorTab === tab;
                return (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setEditorTab(tab)}
                    className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-medium transition-all duration-200"
                    style={{
                      background: isActive ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.04)',
                      border: isActive ? '1px solid rgba(99,102,241,0.3)' : '1px solid var(--color-border)',
                      color: isActive ? 'var(--color-primary-light)' : 'var(--color-text-secondary)',
                    }}
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d={meta.icon} />
                    </svg>
                    {meta.label}
                  </button>
                );
              })}

              <div className="h-5 w-px" style={{ background: 'var(--color-border)' }} />

              <select
                value={previewTarget}
                onChange={(event) => setPreviewTarget(event.target.value)}
                className="rounded-lg px-2.5 py-1.5 text-[11px] font-medium outline-none"
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                {previewTargets.map((target) => (
                  <option key={target} value={target}>
                    {target}
                  </option>
                ))}
              </select>

              <button
                type="button"
                onClick={() => setShowPreview((prev) => !prev)}
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
                type="button"
                onClick={runValidate}
                className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-medium transition-all duration-200"
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid var(--color-border)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m6 2.25a9 9 0 11-18 0 9 9 0 0118 0Z" />
                </svg>
                Validate
              </button>
            </div>
          </div>

          <div className="flex flex-1 overflow-hidden">
            <div className="flex flex-1 overflow-hidden">
              <div className={`flex flex-1 flex-col overflow-hidden ${showPreview ? 'w-1/2' : ''}`}>
                {editorTab === 'instructions' && (
                  <>
                    <div className="relative flex flex-1 overflow-hidden">
                      <LineGutter text={draft.instructions_markdown} />
                      <textarea
                        value={draft.instructions_markdown}
                        onChange={(event) =>
                          setDraft((prev) => ({
                            ...prev,
                            instructions_markdown: event.target.value,
                          }))}
                        spellCheck={false}
                        className="flex-1 resize-none overflow-auto py-4 pr-5 pl-2 outline-none"
                        placeholder="Bu skill'in SKILL.md icerigini buradan duzenleyin."
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

                    <div
                      className="flex items-center justify-between px-4 py-1.5"
                      style={{
                        background: 'rgba(11,17,32,0.95)',
                        borderTop: '1px solid var(--color-border)',
                      }}
                    >
                      <div className="flex items-center gap-4">
                        <span className="text-[10px] tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
                          {lineCount(draft.instructions_markdown)} satir
                        </span>
                        <span className="text-[10px] tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
                          {draft.instructions_markdown.length} karakter
                        </span>
                        <span className="text-[10px] tabular-nums" style={{ color: 'var(--color-text-muted)' }}>
                          {wordCount(draft.instructions_markdown)} kelime
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span
                          className="rounded px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wider"
                          style={{
                            background: 'rgba(255,255,255,0.04)',
                            border: '1px solid var(--color-border)',
                            color: 'var(--color-text-muted)',
                          }}
                        >
                          SKILL.md
                        </span>
                        <span className="text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
                          Ctrl+S kaydet
                        </span>
                      </div>
                    </div>
                  </>
                )}

                {editorTab === 'layers' && (
                  <SkillLayersEditor
                    draft={draft}
                    promptGroups={promptGroups}
                    promptTemplates={promptTemplates}
                    promptLookup={promptLookup}
                    addLayer={addLayer}
                    updateLayer={updateLayer}
                    removeLayer={removeLayer}
                    moveLayer={moveLayer}
                  />
                )}

                {editorTab === 'metadata' && (
                  <SkillMetadataEditor
                    draft={draft}
                    isCreatingNew={isCreatingNew}
                    tagsText={tagsText}
                    setTagsText={setTagsText}
                    setDraft={setDraft}
                    toggleAppliesTo={toggleAppliesTo}
                    availableTools={availableTools}
                    toggleTool={toggleTool}
                  />
                )}
              </div>

              {showPreview && (
                <SkillPreviewPanel
                  normalizedDraftError={normalizedDraft.error}
                  previewPending={previewMut.isPending}
                  preview={preview}
                  runPreview={runPreview}
                />
              )}
            </div>

            <SkillInspectorPanel
              draft={draft}
              tagList={tagList}
              normalizedDraftError={normalizedDraft.error}
              activeValidation={activeValidation}
              resolvedLayers={resolvedLayers}
              selectedExistingSkill={selectedExistingSkill}
              setConfirmReset={setConfirmReset}
              setConfirmDelete={setConfirmDelete}
              runValidate={runValidate}
              runPreview={runPreview}
              previewPending={previewMut.isPending}
              validatePending={validateMut.isPending}
              resetPending={resetMut.isPending}
              deletePending={deleteMut.isPending}
            />
          </div>
        </main>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div
      className="flex h-screen items-center justify-center"
      style={{ background: 'var(--color-bg-base)' }}
    >
      <div className="flex flex-col items-center gap-3">
        <div
          className="h-8 w-8 animate-spin rounded-full border-2 border-transparent"
          style={{ borderTopColor: 'var(--color-primary)' }}
        />
        <span className="text-sm" style={{ color: 'var(--color-text-muted)' }}>
          Skill Studio yukleniyor...
        </span>
      </div>
    </div>
  );
}

function SkillSidebar({
  groupedItems,
  searchQuery,
  setSearchQuery,
  handleCreateSkill,
  isCreatingNew,
  selectedSlug,
  draft,
  loadSkillIntoEditor,
  handleSave,
  handleDiscard,
  hasDirty,
  savePending,
}: {
  groupedItems: Array<{ label: string; items: SkillDefinition[] }>;
  searchQuery: string;
  setSearchQuery: (value: string) => void;
  handleCreateSkill: () => void;
  isCreatingNew: boolean;
  selectedSlug: string;
  draft: SkillDefinition;
  loadSkillIntoEditor: (skill: SkillDefinition) => void;
  handleSave: () => void;
  handleDiscard: () => void;
  hasDirty: boolean;
  savePending: boolean;
}) {
  return (
    <aside
      className="flex h-full w-[300px] flex-shrink-0 flex-col"
      style={{
        background: 'linear-gradient(180deg, rgba(11,17,32,0.98), rgba(2,6,23,0.98))',
        borderRight: '1px solid var(--color-border)',
      }}
    >
      <div className="px-3 pb-2">
        <button
          type="button"
          onClick={handleCreateSkill}
          className="flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left transition-all duration-150 hover:brightness-125"
          style={{
            background: 'rgba(37,99,235,0.10)',
            border: '1px solid rgba(59,130,246,0.22)',
            color: 'var(--color-text-primary)',
          }}
        >
          <svg className="h-4 w-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          <span className="flex-1 text-[12px] font-medium">Yeni Skill Olustur</span>
        </button>
      </div>

      <div className="px-3 pb-2">
        <div className="relative">
          <svg
            className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            style={{ color: 'var(--color-text-muted)' }}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Skill ara..."
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            className="w-full rounded-xl py-2.5 pl-9 pr-3 text-xs outline-none transition duration-200"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid var(--color-border)',
              color: 'var(--color-text-primary)',
            }}
          />
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-4">
        {isCreatingNew && (
          <div className="mb-3 rounded-xl border p-2" style={{ borderColor: 'rgba(59,130,246,0.18)' }}>
            <div className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
              Taslak
            </div>
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left"
              style={{
                background: selectedSlug === '__new__'
                  ? 'linear-gradient(135deg, rgba(59,130,246,0.18), rgba(29,78,216,0.10))'
                  : 'rgba(255,255,255,0.02)',
                border: '1px solid rgba(59,130,246,0.18)',
              }}
            >
              <span
                className="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider"
                style={{
                  color: '#60a5fa',
                  background: 'rgba(59,130,246,0.10)',
                  border: '1px solid rgba(59,130,246,0.22)',
                }}
              >
                NEW
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[12px] font-medium" style={{ color: 'var(--color-text-primary)' }}>
                  {draft.name}
                </span>
                <span className="block truncate text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                  {draft.slug}
                </span>
              </span>
            </button>
          </div>
        )}

        {groupedItems.map((group) => (
          <div key={group.label} className="mb-3">
            <div className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
              {group.label}
            </div>
            <div className="space-y-1.5">
              {group.items.map((item) => {
                const isActive = item.slug === selectedSlug;
                const itemBadge = skillBadgeMeta(item);
                const itemStatus = STATUS_BADGE[item.status] ?? STATUS_BADGE.draft;
                return (
                  <button
                    key={item.slug}
                    type="button"
                    onClick={() => loadSkillIntoEditor(item)}
                    className="w-full rounded-xl px-3 py-3 text-left transition-all duration-150 hover:brightness-125"
                    style={{
                      background: isActive
                        ? 'linear-gradient(135deg, rgba(99,102,241,0.18), rgba(79,70,229,0.12))'
                        : 'rgba(255,255,255,0.02)',
                      border: isActive
                        ? '1px solid rgba(99,102,241,0.28)'
                        : '1px solid rgba(148,163,184,0.08)',
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider"
                        style={{
                          color: itemBadge.color,
                          background: itemBadge.bg,
                          border: `1px solid ${itemBadge.border}`,
                        }}
                      >
                        {itemBadge.label}
                      </span>
                      <span
                        className="rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider"
                        style={{
                          color: itemStatus.color,
                          background: itemStatus.bg,
                          border: `1px solid ${itemStatus.border}`,
                        }}
                      >
                        {item.status}
                      </span>
                    </div>
                    <div className="mt-2 truncate text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                      {item.name}
                    </div>
                    <div className="truncate text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                      {item.slug}
                    </div>
                    <p className="mt-2 line-clamp-2 text-[11px] leading-5" style={{ color: 'var(--color-text-secondary)' }}>
                      {item.description || 'Aciklama yok.'}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>
        ))}

        {groupedItems.length === 0 && (
          <div className="mt-6 text-center text-xs" style={{ color: 'var(--color-text-muted)' }}>
            Aramaya uyan skill bulunamadi.
          </div>
        )}
      </nav>

      <div className="px-3 pb-4 space-y-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={savePending || !hasDirty}
          className="flex w-full items-center justify-center gap-2 rounded-xl py-2.5 text-[13px] font-medium transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-40"
          style={{
            background: hasDirty
              ? 'linear-gradient(135deg, rgba(99,102,241,0.5), rgba(79,70,229,0.45))'
              : 'rgba(255,255,255,0.04)',
            border: hasDirty
              ? '1px solid rgba(99,102,241,0.5)'
              : '1px solid var(--color-border)',
            color: hasDirty ? '#e2e8f0' : 'var(--color-text-muted)',
          }}
        >
          {savePending ? (
            <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-transparent" style={{ borderTopColor: 'currentColor' }} />
          ) : (
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
            </svg>
          )}
          {savePending ? 'Kaydediliyor...' : 'Degisiklikleri Kaydet'}
        </button>

        {hasDirty && (
          <button
            type="button"
            onClick={handleDiscard}
            className="flex w-full items-center justify-center gap-2 rounded-xl py-2 text-[12px] transition-all duration-200"
            style={{
              color: 'var(--color-text-muted)',
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid var(--color-border)',
            }}
          >
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            Geri Al
          </button>
        )}
      </div>
    </aside>
  );
}

function SkillLayersEditor({
  draft,
  promptGroups,
  promptTemplates,
  promptLookup,
  addLayer,
  updateLayer,
  removeLayer,
  moveLayer,
}: {
  draft: SkillDefinition;
  promptGroups: PromptGroup[];
  promptTemplates: PromptTemplate[];
  promptLookup: Map<string, PromptTemplate>;
  addLayer: (type: SkillPromptLayer['type']) => void;
  updateLayer: (index: number, patch: Partial<SkillPromptLayer>) => void;
  removeLayer: (index: number) => void;
  moveLayer: (index: number, direction: -1 | 1) => void;
}) {
  return (
    <div className="flex-1 overflow-auto p-5" style={{ background: 'var(--color-bg-base)' }}>
      <div className="mx-auto max-w-5xl">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-[15px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              Prompt Layers
            </h3>
            <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              Raw JSON yerine sirali layer kartlariyla duzenleyin. Prompt referanslari Prompt Studio anahtarlarindan secilir.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => addLayer('inline')}
              className="rounded-xl px-3 py-2 text-[12px] font-medium transition-all duration-200"
              style={{
                background: 'rgba(16,185,129,0.10)',
                border: '1px solid rgba(16,185,129,0.22)',
                color: '#6ee7b7',
              }}
            >
              Inline Layer
            </button>
            <button
              type="button"
              onClick={() => addLayer('prompt_reference')}
              className="rounded-xl px-3 py-2 text-[12px] font-medium transition-all duration-200"
              style={{
                background: 'rgba(99,102,241,0.10)',
                border: '1px solid rgba(99,102,241,0.22)',
                color: '#a5b4fc',
              }}
            >
              Prompt Reference
            </button>
          </div>
        </div>

        {draft.prompt_layers.length === 0 ? (
          <div
            className="rounded-2xl border px-5 py-10 text-center"
            style={{
              background: 'rgba(255,255,255,0.02)',
              borderColor: 'rgba(148,163,184,0.14)',
            }}
          >
            <div className="text-[14px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              Henuz layer yok
            </div>
            <p className="mx-auto mt-2 max-w-xl text-[12px] leading-6" style={{ color: 'var(--color-text-muted)' }}>
              Skill yalnizca SKILL.md talimatiyla da calisabilir. Daha kontrollu davranis icin inline bir lens ekleyin veya Prompt Studio'dan mevcut bir prompt referansi baglayin.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {draft.prompt_layers.map((layer, index) => {
              const promptMeta = promptLookup.get(layer.prompt_key);
              const promptLabel = layerLabel(layer, promptLookup);
              return (
                <div
                  key={`${layer.type}-${index}`}
                  className="rounded-2xl border p-4"
                  style={{
                    background: 'rgba(255,255,255,0.03)',
                    borderColor: 'rgba(148,163,184,0.16)',
                  }}
                >
                  <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span
                        className="flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold"
                        style={{
                          background: 'rgba(99,102,241,0.12)',
                          border: '1px solid rgba(99,102,241,0.22)',
                          color: 'var(--color-primary-light)',
                        }}
                      >
                        {index + 1}
                      </span>
                      <div>
                        <div className="text-[13px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                          {promptLabel}
                        </div>
                        <div className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
                          {layer.type === 'inline' ? 'Inline talimat' : promptMeta?.key || 'Prompt referansi'}
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => moveLayer(index, -1)}
                        disabled={index === 0}
                        className="rounded-lg px-2 py-1 text-[11px] disabled:opacity-40"
                        style={{
                          background: 'rgba(255,255,255,0.04)',
                          border: '1px solid var(--color-border)',
                          color: 'var(--color-text-secondary)',
                        }}
                      >
                        Yukari
                      </button>
                      <button
                        type="button"
                        onClick={() => moveLayer(index, 1)}
                        disabled={index === draft.prompt_layers.length - 1}
                        className="rounded-lg px-2 py-1 text-[11px] disabled:opacity-40"
                        style={{
                          background: 'rgba(255,255,255,0.04)',
                          border: '1px solid var(--color-border)',
                          color: 'var(--color-text-secondary)',
                        }}
                      >
                        Asagi
                      </button>
                      <button
                        type="button"
                        onClick={() => removeLayer(index)}
                        className="rounded-lg px-2 py-1 text-[11px]"
                        style={{
                          background: 'rgba(239,68,68,0.08)',
                          border: '1px solid rgba(239,68,68,0.18)',
                          color: '#fca5a5',
                        }}
                      >
                        Sil
                      </button>
                    </div>
                  </div>

                  <div className="grid gap-4 lg:grid-cols-[180px,1fr]">
                    <label className="space-y-1.5">
                      <span className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
                        Type
                      </span>
                      <select
                        value={layer.type}
                        onChange={(event) =>
                          updateLayer(index, event.target.value === 'prompt_reference'
                            ? { type: 'prompt_reference', prompt_key: layer.prompt_key || promptTemplates[0]?.key || '', content: '' }
                            : { type: 'inline', prompt_key: '', content: layer.content })}
                        className="w-full rounded-xl px-3 py-2 text-sm outline-none"
                        style={{
                          background: 'rgba(255,255,255,0.04)',
                          border: '1px solid rgba(148,163,184,0.2)',
                          color: 'var(--color-text-primary)',
                        }}
                      >
                        <option value="inline">inline</option>
                        <option value="prompt_reference">prompt_reference</option>
                      </select>
                    </label>

                    <label className="space-y-1.5">
                      <span className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
                        Label
                      </span>
                      <input
                        value={layer.label}
                        onChange={(event) => updateLayer(index, { label: event.target.value })}
                        className="w-full rounded-xl bg-transparent px-3 py-2 text-sm outline-none"
                        placeholder="Editor'de gorunecek isim"
                        style={{
                          border: '1px solid rgba(148,163,184,0.2)',
                          color: 'var(--color-text-primary)',
                        }}
                      />
                    </label>
                  </div>

                  {layer.type === 'prompt_reference' ? (
                    <div className="mt-4 space-y-2">
                      <label className="space-y-1.5">
                        <span className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
                          Prompt Key
                        </span>
                        <select
                          value={layer.prompt_key}
                          onChange={(event) => updateLayer(index, { prompt_key: event.target.value })}
                          className="w-full rounded-xl px-3 py-2 text-sm outline-none"
                          style={{
                            background: 'rgba(255,255,255,0.04)',
                            border: '1px solid rgba(148,163,184,0.2)',
                            color: 'var(--color-text-primary)',
                          }}
                        >
                          {promptGroups.map((group) => (
                            <optgroup key={group.label} label={group.label}>
                              {group.prompts.map((prompt) => (
                                <option key={prompt.key} value={prompt.key}>
                                  {prompt.title} ({prompt.key})
                                </option>
                              ))}
                            </optgroup>
                          ))}
                        </select>
                      </label>
                      <div
                        className="rounded-xl border p-3 text-[11px] leading-5"
                        style={{
                          background: 'rgba(99,102,241,0.05)',
                          borderColor: 'rgba(99,102,241,0.14)',
                          color: 'var(--color-text-secondary)',
                        }}
                      >
                        {promptMeta ? (
                          <>
                            <div className="font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                              {promptMeta.title}
                            </div>
                            <div className="mt-1">{promptMeta.description}</div>
                            <div className="mt-2 font-mono text-[10px]" style={{ color: 'var(--color-text-muted)' }}>
                              {promptMeta.key}
                            </div>
                          </>
                        ) : (
                          'Bu prompt anahtari Prompt Studio verisinde bulunamadi.'
                        )}
                      </div>
                    </div>
                  ) : (
                    <label className="mt-4 block space-y-1.5">
                      <span className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
                        Inline Content
                      </span>
                      <textarea
                        value={layer.content}
                        onChange={(event) => updateLayer(index, { content: event.target.value })}
                        rows={8}
                        spellCheck={false}
                        className="w-full rounded-2xl bg-transparent px-3 py-3 font-mono text-xs outline-none"
                        placeholder="Bu layer'in modele enjekte edecegi ek talimati yazin."
                        style={{
                          border: '1px solid rgba(148,163,184,0.2)',
                          color: 'var(--color-text-primary)',
                        }}
                      />
                    </label>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function SkillMetadataEditor({
  draft,
  isCreatingNew,
  tagsText,
  setTagsText,
  setDraft,
  toggleAppliesTo,
  availableTools,
  toggleTool,
}: {
  draft: SkillDefinition;
  isCreatingNew: boolean;
  tagsText: string;
  setTagsText: (value: string) => void;
  setDraft: Dispatch<SetStateAction<SkillDefinition>>;
  toggleAppliesTo: (target: string) => void;
  availableTools: string[];
  toggleTool: (toolName: string) => void;
}) {
  const tagList = parseCsv(tagsText);

  return (
    <div className="flex-1 overflow-auto p-5" style={{ background: 'var(--color-bg-base)' }}>
      <div className="mx-auto max-w-5xl space-y-6">
        <section
          className="rounded-2xl border p-5"
          style={{
            background: 'rgba(255,255,255,0.03)',
            borderColor: 'rgba(148,163,184,0.16)',
          }}
        >
          <div className="mb-4">
            <h3 className="text-[15px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              Skill Metadata
            </h3>
            <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              Skill'in ne zaman calisacagini, hangi akislar ve hangi tool sinirlariyla kullanilacagini buradan tanimlayin.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
                Slug
              </span>
              <input
                value={draft.slug}
                disabled={!isCreatingNew}
                onChange={(event) => setDraft((prev) => ({ ...prev, slug: event.target.value }))}
                className="w-full rounded-xl bg-transparent px-3 py-2 text-sm outline-none disabled:opacity-60"
                style={{
                  border: '1px solid rgba(148,163,184,0.2)',
                  color: 'var(--color-text-primary)',
                }}
              />
            </label>

            <label className="space-y-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
                Name
              </span>
              <input
                value={draft.name}
                onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))}
                className="w-full rounded-xl bg-transparent px-3 py-2 text-sm outline-none"
                style={{
                  border: '1px solid rgba(148,163,184,0.2)',
                  color: 'var(--color-text-primary)',
                }}
              />
            </label>

            <label className="space-y-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
                Status
              </span>
              <select
                value={draft.status}
                onChange={(event) => setDraft((prev) => ({ ...prev, status: event.target.value }))}
                className="w-full rounded-xl px-3 py-2 text-sm outline-none"
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(148,163,184,0.2)',
                  color: 'var(--color-text-primary)',
                }}
              >
                {STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>

            <label className="space-y-1.5">
              <span className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
                Priority
              </span>
              <input
                type="number"
                value={draft.priority}
                onChange={(event) =>
                  setDraft((prev) => ({
                    ...prev,
                    priority: Number(event.target.value || 0),
                  }))}
                className="w-full rounded-xl bg-transparent px-3 py-2 text-sm outline-none"
                style={{
                  border: '1px solid rgba(148,163,184,0.2)',
                  color: 'var(--color-text-primary)',
                }}
              />
            </label>
          </div>

          <label className="mt-4 block space-y-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
              Description
            </span>
            <textarea
              value={draft.description}
              onChange={(event) => setDraft((prev) => ({ ...prev, description: event.target.value }))}
              rows={3}
              className="w-full rounded-2xl bg-transparent px-3 py-3 text-sm outline-none"
              style={{
                border: '1px solid rgba(148,163,184,0.2)',
                color: 'var(--color-text-primary)',
              }}
            />
          </label>

          <label className="mt-4 block space-y-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
              When To Use
            </span>
            <textarea
              value={draft.when_to_use}
              onChange={(event) => setDraft((prev) => ({ ...prev, when_to_use: event.target.value }))}
              rows={4}
              className="w-full rounded-2xl bg-transparent px-3 py-3 text-sm outline-none"
              style={{
                border: '1px solid rgba(148,163,184,0.2)',
                color: 'var(--color-text-primary)',
              }}
            />
          </label>

          <div className="mt-4">
            <div className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
              Applies To
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {APPLIES_TO_OPTIONS.map((option) => {
                const checked = draft.applies_to.includes(option.value);
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => toggleAppliesTo(option.value)}
                    className="rounded-full px-3 py-1.5 text-[12px] font-medium transition-all duration-150"
                    style={{
                      background: checked ? 'rgba(14,165,233,0.12)' : 'rgba(255,255,255,0.03)',
                      border: checked
                        ? '1px solid rgba(56,189,248,0.3)'
                        : '1px solid rgba(148,163,184,0.18)',
                      color: checked ? '#67e8f9' : 'var(--color-text-secondary)',
                    }}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
          </div>

          <label className="mt-4 block space-y-1.5">
            <span className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
              Tags
            </span>
            <input
              value={tagsText}
              onChange={(event) => setTagsText(event.target.value)}
              placeholder="seo, launch, audit"
              className="w-full rounded-xl bg-transparent px-3 py-2 text-sm outline-none"
              style={{
                border: '1px solid rgba(148,163,184,0.2)',
                color: 'var(--color-text-primary)',
              }}
            />
            {tagList.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {tagList.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full px-2.5 py-1 text-[11px]"
                    style={{
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(148,163,184,0.18)',
                      color: 'var(--color-text-secondary)',
                    }}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </label>
        </section>

        <section
          className="rounded-2xl border p-5"
          style={{
            background: 'rgba(255,255,255,0.03)',
            borderColor: 'rgba(148,163,184,0.16)',
          }}
        >
          <div className="mb-4">
            <h3 className="text-[15px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
              Allowed Tools
            </h3>
            <p className="mt-1 text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
              CSV yerine tool registry'den secim yapin. Bos birakirsaniz skill tool kisiti uygulamaz.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {availableTools.map((toolName) => {
              const checked = draft.allowed_tools.includes(toolName);
              return (
                <button
                  key={toolName}
                  type="button"
                  onClick={() => toggleTool(toolName)}
                  className="rounded-xl px-3 py-2 text-left text-[11px] font-medium transition-all duration-150"
                  style={{
                    background: checked ? 'rgba(99,102,241,0.16)' : 'rgba(255,255,255,0.03)',
                    border: checked
                      ? '1px solid rgba(99,102,241,0.28)'
                      : '1px solid rgba(148,163,184,0.16)',
                    color: checked ? '#c7d2fe' : 'var(--color-text-secondary)',
                  }}
                >
                  {toolName}
                </button>
              );
            })}
          </div>

          {draft.allowed_tools.length > 0 && (
            <div className="mt-4 rounded-xl border p-3" style={{ borderColor: 'rgba(99,102,241,0.18)', background: 'rgba(99,102,241,0.06)' }}>
              <div className="text-[10px] font-semibold uppercase tracking-[0.16em]" style={{ color: 'var(--color-text-muted)' }}>
                Secili Toollar
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {draft.allowed_tools.map((toolName) => (
                  <span
                    key={toolName}
                    className="rounded-full px-2 py-1 text-[10px] font-mono"
                    style={{
                      background: 'rgba(255,255,255,0.06)',
                      border: '1px solid rgba(99,102,241,0.22)',
                      color: '#c7d2fe',
                    }}
                  >
                    {toolName}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function SkillPreviewPanel({
  normalizedDraftError,
  previewPending,
  preview,
  runPreview,
}: {
  normalizedDraftError: string;
  previewPending: boolean;
  preview: SkillPreview | null;
  runPreview: () => void;
}) {
  return (
    <div
      className="flex w-1/2 flex-col overflow-hidden"
      style={{ borderLeft: '1px solid var(--color-border)' }}
    >
      <div
        className="flex items-center justify-between gap-2 px-4 py-2"
        style={{
          background: 'rgba(11,17,32,0.95)',
          borderBottom: '1px solid var(--color-border)',
        }}
      >
        <div className="flex items-center gap-2">
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2} style={{ color: 'var(--color-primary-light)' }}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          <span className="text-[12px] font-medium" style={{ color: 'var(--color-text-secondary)' }}>
            Composed Prompt Preview
          </span>
        </div>
        <button
          type="button"
          onClick={runPreview}
          className="rounded-lg px-2.5 py-1.5 text-[11px] font-medium"
          style={{
            background: 'rgba(99,102,241,0.15)',
            border: '1px solid rgba(99,102,241,0.28)',
            color: '#c7d2fe',
          }}
        >
          Yenile
        </button>
      </div>

      <div className="flex-1 overflow-auto p-5" style={{ background: 'rgba(2,6,23,0.6)' }}>
        {normalizedDraftError ? (
          <div
            className="rounded-2xl border p-4 text-sm"
            style={{
              background: 'rgba(239,68,68,0.08)',
              borderColor: 'rgba(239,68,68,0.18)',
              color: '#fca5a5',
            }}
          >
            {normalizedDraftError}
          </div>
        ) : previewPending ? (
          <div className="flex h-full items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-transparent" style={{ borderTopColor: 'var(--color-primary-light)' }} />
              <span className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                Preview olusturuluyor...
              </span>
            </div>
          </div>
        ) : preview ? (
          <pre
            className="whitespace-pre-wrap break-words rounded-2xl p-4"
            style={{
              background: 'rgba(11,17,32,0.68)',
              border: '1px solid rgba(148,163,184,0.14)',
              color: 'var(--color-text-secondary)',
              fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace",
              fontSize: '12px',
              lineHeight: '1.75',
            }}
          >
            {preview.composed_prompt || 'Bu akis icin prompt cikisi bos.'}
          </pre>
        ) : (
          <div
            className="rounded-2xl border p-4 text-sm"
            style={{
              background: 'rgba(255,255,255,0.03)',
              borderColor: 'rgba(148,163,184,0.14)',
              color: 'var(--color-text-muted)',
            }}
          >
            Preview acik. Gecerli draft icin composed prompt burada gorunur.
          </div>
        )}
      </div>
    </div>
  );
}

function SkillInspectorPanel({
  draft,
  tagList,
  normalizedDraftError,
  activeValidation,
  resolvedLayers,
  selectedExistingSkill,
  setConfirmReset,
  setConfirmDelete,
  runValidate,
  runPreview,
  previewPending,
  validatePending,
  resetPending,
  deletePending,
}: {
  draft: SkillDefinition;
  tagList: string[];
  normalizedDraftError: string;
  activeValidation: SkillValidation | null;
  resolvedLayers: SkillValidation['resolved_prompt_layers'];
  selectedExistingSkill: SkillDefinition | null;
  setConfirmReset: (open: boolean) => void;
  setConfirmDelete: (open: boolean) => void;
  runValidate: () => void;
  runPreview: () => void;
  previewPending: boolean;
  validatePending: boolean;
  resetPending: boolean;
  deletePending: boolean;
}) {
  return (
    <aside
      className="flex h-full w-[320px] flex-shrink-0 flex-col overflow-y-auto"
      style={{
        background: 'linear-gradient(180deg, rgba(11,17,32,0.98), rgba(2,6,23,0.98))',
        borderLeft: '1px solid var(--color-border)',
      }}
    >
      <div className="space-y-4 p-4">
        <div>
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.15em]" style={{ color: 'var(--color-text-muted)' }}>
            Overview
          </div>
          <p className="text-[12px] leading-5" style={{ color: 'var(--color-text-secondary)' }}>
            {draft.description || 'Aciklama yok.'}
          </p>
          {draft.when_to_use && (
            <div
              className="mt-3 rounded-xl border p-3 text-[11px] leading-5"
              style={{
                background: 'rgba(255,255,255,0.03)',
                borderColor: 'rgba(148,163,184,0.16)',
                color: 'var(--color-text-secondary)',
              }}
            >
              {draft.when_to_use}
            </div>
          )}
        </div>

        <div>
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.15em]" style={{ color: 'var(--color-text-muted)' }}>
            Scope
          </div>
          <div className="space-y-2">
            <StatRow label="Applies To" value={draft.applies_to.join(', ') || '-'} />
            <StatRow label="Priority" value={String(draft.priority)} />
            <StatRow label="Tool Restriction" value={draft.allowed_tools.length ? `${draft.allowed_tools.length} tool` : 'Yok'} />
            <StatRow label="Layer Count" value={String(draft.prompt_layers.length)} />
          </div>
        </div>

        <div>
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.15em]" style={{ color: 'var(--color-text-muted)' }}>
            Validation
          </div>
          <div
            className="rounded-2xl border p-3"
            style={{
              background: 'rgba(255,255,255,0.03)',
              borderColor: normalizedDraftError
                ? 'rgba(239,68,68,0.16)'
                : activeValidation?.ok
                ? 'rgba(52,211,153,0.16)'
                : activeValidation
                  ? 'rgba(239,68,68,0.16)'
                  : 'rgba(148,163,184,0.16)',
            }}
          >
            {normalizedDraftError ? (
              <div className="text-[12px]" style={{ color: '#fca5a5' }}>
                {normalizedDraftError}
              </div>
            ) : activeValidation ? (
              <div className="space-y-3">
                <div style={{ color: activeValidation.ok ? 'var(--color-success)' : '#fca5a5' }}>
                  {activeValidation.ok ? 'Skill gecerli gorunuyor.' : 'Validation hata verdi.'}
                </div>
                {activeValidation.errors.length > 0 && (
                  <div>
                    <div className="text-[11px] font-semibold" style={{ color: '#fca5a5' }}>
                      Errors
                    </div>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
                      {activeValidation.errors.map((error) => (
                        <li key={error}>{error}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {activeValidation.warnings.length > 0 && (
                  <div>
                    <div className="text-[11px] font-semibold" style={{ color: '#fbbf24' }}>
                      Warnings
                    </div>
                    <ul className="mt-1 list-disc space-y-1 pl-5 text-[11px]" style={{ color: 'var(--color-text-secondary)' }}>
                      {activeValidation.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-[12px]" style={{ color: 'var(--color-text-muted)' }}>
                Henuz validation calistirilmadi.
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.15em]" style={{ color: 'var(--color-text-muted)' }}>
            Resolved Layers
          </div>
          {resolvedLayers.length > 0 ? (
            <div className="space-y-2">
              {resolvedLayers.map((layer) => (
                <div
                  key={`${layer.type}-${layer.source}-${layer.label}`}
                  className="rounded-xl border px-3 py-2"
                  style={{
                    background: 'rgba(255,255,255,0.03)',
                    borderColor: 'rgba(148,163,184,0.16)',
                  }}
                >
                  <div className="text-[11px] font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                    {layer.label}
                  </div>
                  <div className="mt-1 text-[10px] font-mono" style={{ color: 'var(--color-text-muted)' }}>
                    {layer.source}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div
              className="rounded-xl border px-3 py-2.5 text-[11px]"
              style={{
                background: 'rgba(255,255,255,0.03)',
                borderColor: 'rgba(148,163,184,0.16)',
                color: 'var(--color-text-muted)',
              }}
            >
              Henuz resolve edilen layer yok.
            </div>
          )}
        </div>

        <div>
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.15em]" style={{ color: 'var(--color-text-muted)' }}>
            Istatistikler
          </div>
          <div className="space-y-2">
            <StatRow label="Instructions" value={`${wordCount(draft.instructions_markdown)} kelime`} />
            <StatRow label="Tags" value={tagList.join(', ') || '-'} />
            <StatRow label="Secili Toollar" value={draft.allowed_tools.join(', ') || '-'} />
          </div>
        </div>

        <div>
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.15em]" style={{ color: 'var(--color-text-muted)' }}>
            Dosya
          </div>
          <div className="space-y-2">
            <StatRow label="Slug" value={draft.slug || '-'} mono />
            <StatRow label="Metadata" value={`skills/${draft.slug || '-'}/meta.json`} mono />
            <StatRow label="Instructions" value={`skills/${draft.slug || '-'}/SKILL.md`} mono />
          </div>
        </div>
      </div>

      <div className="mt-auto space-y-2 p-4" style={{ borderTop: '1px solid var(--color-border)' }}>
        <div className="text-[10px] font-semibold uppercase tracking-[0.15em]" style={{ color: 'var(--color-text-muted)' }}>
          Islemler
        </div>

        <button
          type="button"
          onClick={runPreview}
          disabled={previewPending}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[11px] transition-all duration-200 disabled:opacity-40"
          style={{
            background: 'rgba(99,102,241,0.10)',
            border: '1px solid rgba(99,102,241,0.18)',
            color: '#c7d2fe',
          }}
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          Preview Calistir
        </button>

        <button
          type="button"
          onClick={runValidate}
          disabled={validatePending}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[11px] transition-all duration-200 disabled:opacity-40"
          style={{
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text-secondary)',
          }}
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m6 2.25a9 9 0 11-18 0 9 9 0 0118 0Z" />
          </svg>
          Validation Calistir
        </button>

        {selectedExistingSkill?.is_default && (
          <button
            type="button"
            onClick={() => setConfirmReset(true)}
            disabled={resetPending}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[11px] transition-all duration-200 disabled:opacity-40"
            style={{
              background: 'rgba(245,158,11,0.08)',
              border: '1px solid rgba(245,158,11,0.18)',
              color: '#fcd34d',
            }}
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Varsayilana Don
          </button>
        )}

        {selectedExistingSkill && !selectedExistingSkill.is_default && (
          <button
            type="button"
            onClick={() => setConfirmDelete(true)}
            disabled={deletePending}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-[11px] transition-all duration-200 disabled:opacity-40"
            style={{
              background: 'rgba(239,68,68,0.08)',
              border: '1px solid rgba(239,68,68,0.18)',
              color: '#fca5a5',
            }}
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Skill Sil
          </button>
        )}
      </div>
    </aside>
  );
}

function LineGutter({ text }: { text: string }) {
  const lines = text.split('\n').length;
  return (
    <div
      className="select-none overflow-hidden py-4 pl-4 pr-3"
      style={{
        background: 'rgba(11,17,32,0.6)',
        borderRight: '1px solid var(--color-border)',
        fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace",
        fontSize: '13px',
        lineHeight: '1.7',
        color: 'var(--color-text-muted)',
        minWidth: '48px',
        textAlign: 'right',
      }}
    >
      {Array.from({ length: lines }, (_, index) => (
        <div key={index} style={{ opacity: 0.5 }}>
          {index + 1}
        </div>
      ))}
    </div>
  );
}

function StatRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="text-[11px]" style={{ color: 'var(--color-text-muted)' }}>
        {label}
      </span>
      <span
        className={`text-right text-[11px] ${mono ? 'font-mono' : ''}`}
        style={{ color: 'var(--color-text-secondary)' }}
      >
        {value}
      </span>
    </div>
  );
}
