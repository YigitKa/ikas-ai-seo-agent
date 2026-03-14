import type { ReactNode } from 'react';
import { PromptCard, SectionCard } from '../../components/settings/UiPrimitives';
import type { PromptGroup } from '../../types';

interface PromptEditorSectionProps {
  promptGroups: PromptGroup[];
  selectedGroup: PromptGroup | undefined;
  promptValues: Record<string, string>;
  onGroupChange: (label: string) => void;
  onPromptChange: (key: string, value: string) => void;
  onPromptReset: (key: string) => void;
  onResetAll: () => void;
  isResetting: boolean;
}

export default function PromptEditorSection({
  promptGroups,
  selectedGroup,
  promptValues,
  onGroupChange,
  onPromptChange,
  onPromptReset,
  onResetAll,
  isResetting,
}: PromptEditorSectionProps) {
  const actions: ReactNode = (
    <button
      onClick={onResetAll}
      disabled={isResetting || promptGroups.length === 0}
      className="rounded-xl border border-slate-700 px-3 py-2 text-sm text-slate-200 transition hover:border-slate-500 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
    >
      Tumunu Varsayilana Don
    </button>
  );

  return (
    <SectionCard
      eyebrow="Prompt"
      title="Prompt Editoru"
      description="Aciklama ve ceviri promptlarini dosya bazli olarak yonetin."
      actions={actions}
    >
      {promptGroups.length === 0 ? (
        <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-6 text-sm text-slate-400">
          Prompt metadata yuklenemedi.
        </div>
      ) : (
        <>
          <div className="mb-5 flex flex-wrap gap-2">
            {promptGroups.map((group) => (
              <button
                key={group.label}
                onClick={() => onGroupChange(group.label)}
                className={`rounded-2xl px-4 py-2 text-sm font-medium transition ${
                  selectedGroup?.label === group.label
                    ? 'bg-sky-500 text-slate-950'
                    : 'border border-slate-700 bg-slate-900/80 text-slate-300 hover:border-slate-500 hover:text-white'
                }`}
              >
                {group.label}
              </button>
            ))}
          </div>

          <div className="space-y-4">
            {selectedGroup?.prompts.map((prompt) => (
              <PromptCard
                key={prompt.key}
                template={prompt}
                value={promptValues[prompt.key] ?? prompt.content}
                onChange={(value) => onPromptChange(prompt.key, value)}
                onReset={() => onPromptReset(prompt.key)}
                disabled={isResetting}
              />
            ))}
          </div>
        </>
      )}
    </SectionCard>
  );
}
