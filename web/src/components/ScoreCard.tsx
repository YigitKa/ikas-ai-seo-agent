import type { SeoScore } from '../types';

interface Props {
  score: SeoScore;
}

const FIELDS = [
  { key: 'title_score', label: 'Baslik', max: 15 },
  { key: 'description_score', label: 'Aciklama', max: 20 },
  { key: 'english_description_score', label: 'EN Aciklama', max: 5 },
  { key: 'meta_score', label: 'Meta Title', max: 15 },
  { key: 'meta_desc_score', label: 'Meta Desc', max: 10 },
  { key: 'keyword_score', label: 'Keyword', max: 10 },
  { key: 'content_quality_score', label: 'Icerik Kalite', max: 10 },
  { key: 'technical_seo_score', label: 'Teknik SEO', max: 10 },
  { key: 'readability_score', label: 'Okunabilirlik', max: 5 },
] as const;

function scoreColor(pct: number): string {
  if (pct >= 80) return 'bg-green-500';
  if (pct >= 60) return 'bg-yellow-500';
  if (pct >= 40) return 'bg-orange-500';
  return 'bg-red-500';
}

function totalBadgeColor(score: number): string {
  if (score >= 80) return 'text-green-400 border-green-500/40 bg-green-500/10';
  if (score >= 60) return 'text-yellow-400 border-yellow-500/40 bg-yellow-500/10';
  if (score >= 40) return 'text-orange-400 border-orange-500/40 bg-orange-500/10';
  return 'text-red-400 border-red-500/40 bg-red-500/10';
}

export default function ScoreCard({ score }: Props) {
  return (
    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
          SEO Skoru
        </h3>
        <span
          className={`rounded-full border px-3 py-1 text-2xl font-bold ${totalBadgeColor(score.total_score)}`}
        >
          {score.total_score}
        </span>
      </div>

      <div className="space-y-2.5">
        {FIELDS.map(({ key, label, max }) => {
          const val = score[key] as number;
          const pct = (val / max) * 100;
          return (
            <div key={key}>
              <div className="mb-0.5 flex justify-between text-xs text-gray-400">
                <span>{label}</span>
                <span>
                  {val}/{max}
                </span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-gray-700">
                <div
                  className={`h-full rounded-full transition-all ${scoreColor(pct)}`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {score.issues.length > 0 && (
        <details className="mt-4">
          <summary className="cursor-pointer text-xs font-medium text-gray-400">
            {score.issues.length} sorun
          </summary>
          <ul className="mt-2 space-y-1 text-xs text-gray-500">
            {score.issues.map((issue, i) => (
              <li key={i} className="flex items-start gap-1.5">
                <span className="mt-0.5 text-red-400">&#x2022;</span>
                {issue}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
