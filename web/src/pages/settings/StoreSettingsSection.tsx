import {
  EnterpriseField,
  EnterpriseSectionCard,
  EnterpriseToggleField,
} from '../../shared/ui/EnterprisePrimitives';
import type { SettingsData } from '../../types';

interface StoreSettingsSectionProps {
  form: SettingsData;
  setValue: <K extends keyof SettingsData>(key: K, value: SettingsData[K]) => void;
}

export default function StoreSettingsSection({ form, setValue }: StoreSettingsSectionProps) {
  return (
    <EnterpriseSectionCard
      eyebrow="ikas"
      title="Magaza ve SEO Ayarlari"
      description="Magaza baglantisi ve rewrite islerinde kullanilan genel hedefler."
    >
      <div className="grid gap-4 md:grid-cols-2">
        <EnterpriseField
          label="Magaza Adi"
          value={form.store_name}
          onChange={(value) => setValue('store_name', value)}
          placeholder="my-store"
        />
        <EnterpriseField
          label="Client ID"
          value={form.client_id}
          onChange={(value) => setValue('client_id', value)}
          placeholder="ikas oauth client id"
        />
        <EnterpriseField
          label="Client Secret"
          value={form.client_secret}
          onChange={(value) => setValue('client_secret', value)}
          type="password"
          placeholder="ikas oauth client secret"
        />
        <EnterpriseField
          label="MCP Token"
          value={form.mcp_token}
          onChange={(value) => setValue('mcp_token', value)}
          type="password"
          placeholder="mcp_..."
        />
        <EnterpriseField
          label="Magaza Dilleri"
          value={form.languages}
          onChange={(value) => setValue('languages', value)}
          placeholder="tr,en,de"
          hint="Virgul ile ayirin. Ilk dil ana dil olarak kabul edilir."
        />
        <EnterpriseField
          label="Hedef Keywordler"
          value={form.keywords}
          onChange={(value) => setValue('keywords', value)}
          placeholder="spor ayakkabi, kosu ayakkabisi"
          hint="Rewrite ve SEO analizinde kullanilir."
        />
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <EnterpriseToggleField
          title="Dry Run"
          description="Aciksa onaylanan oneriler ikas'a yazilmaz."
          checked={form.dry_run}
          onChange={(checked) => setValue('dry_run', checked)}
        />
        <EnterpriseToggleField
          title="Chat Thinking Mode"
          description="Chat akisinda derin dusunme (reasoning) ciktisini gosterir."
          checked={form.ai_thinking_mode_chat}
          onChange={(checked) => setValue('ai_thinking_mode_chat', checked)}
        />
        <EnterpriseToggleField
          title="Toplu Islem Thinking Mode"
          description="Rewrite, ceviri ve toplu islemlerde derin dusunme aktif olur."
          checked={form.ai_thinking_mode_batch}
          onChange={(checked) => setValue('ai_thinking_mode_batch', checked)}
        />
      </div>
    </EnterpriseSectionCard>
  );
}
