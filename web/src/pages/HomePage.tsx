import { useState } from 'react';
import AppHeader from '../shared/ui/AppHeader';
import { EnterpriseButton } from '../shared/ui/EnterprisePrimitives';
import { useHomeData } from '../components/home/useHomeData';
import ScorePulseRow from '../components/home/ScorePulseRow';
import ActionRadarSection from '../components/home/ActionRadarSection';
import ScoreDistributionBar from '../components/home/ScoreDistributionBar';
import NeedsAttentionSection from '../components/home/NeedsAttentionSection';
import StoreChatAdvisor from '../components/home/StoreChatAdvisor';
import OnboardingFlow from '../components/home/OnboardingFlow';

export default function HomePage() {
  const [chatOpen, setChatOpen] = useState(false);

  const {
    settings,
    summary,
    trends,
    distribution,
    lowProducts,
    actions,
    isFirstUse,
  } = useHomeData();

  const storeName = settings.data?.store_name || 'Magaza';

  return (
    <div className="flex h-screen flex-col" style={{ background: 'var(--color-bg-base)' }}>
      <AppHeader
        title="Komuta Merkezi"
        description={isFirstUse ? 'Magazanizi kurmaya baslayin' : `${storeName} SEO durumu ve aksiyonlar`}
        eyebrow={{ label: 'Overview', tone: 'primary', withDot: true }}
        meta={
          !isFirstUse && summary.data
            ? [
                {
                  label: 'Urun Sayisi',
                  value: String(summary.data.total_products),
                  tone: 'neutral',
                },
                {
                  label: 'Ortalama Skor',
                  value: `${Math.round(summary.data.latest_avg?.total ?? 0)}/100`,
                  tone:
                    (summary.data.latest_avg?.total ?? 0) >= 70
                      ? 'success'
                      : (summary.data.latest_avg?.total ?? 0) >= 50
                        ? 'warning'
                        : 'danger',
                },
              ]
            : []
        }
        actions={
          !isFirstUse ? (
            <EnterpriseButton
              tone="primary"
              size="sm"
              onClick={() => setChatOpen(true)}
              className="gap-1.5"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
              AI Danismani
            </EnterpriseButton>
          ) : undefined
        }
      />

      <main className="flex-1 overflow-y-auto">
        <div className="space-y-5 p-5">
          {isFirstUse ? (
            <OnboardingFlow settings={settings.data} summary={summary.data} />
          ) : (
            <>
              {/* Row 1: SEO / GEO / AEO pillar scores */}
              <ScorePulseRow
                summary={summary.data}
                trends={trends.data}
                isLoading={trends.isLoading}
              />

              {/* Row 2: Score distribution across catalog */}
              <ScoreDistributionBar
                distribution={distribution.data}
                isLoading={distribution.isLoading}
              />

              {/* Row 3: Products needing attention (left 2/3) + Action cards (right 1/3) */}
              <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
                <div className="xl:col-span-2">
                  <NeedsAttentionSection
                    lowProducts={lowProducts.data}
                    isLoading={lowProducts.isLoading}
                  />
                </div>
                <div>
                  <ActionRadarSection actions={actions} />
                </div>
              </div>
            </>
          )}
        </div>
      </main>

      <StoreChatAdvisor
        storeName={storeName}
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
      />
    </div>
  );
}
