import AppHeader from '../shared/ui/AppHeader';
import { useHomeData } from '../components/home/useHomeData';
import StoreHeroSection from '../components/home/StoreHeroSection';
import ScorePulseRow from '../components/home/ScorePulseRow';
import ActionRadarSection from '../components/home/ActionRadarSection';
import ScoreDistributionBar from '../components/home/ScoreDistributionBar';
import NeedsAttentionSection from '../components/home/NeedsAttentionSection';
import StoreChatAdvisor from '../components/home/StoreChatAdvisor';
import OnboardingFlow from '../components/home/OnboardingFlow';

export default function HomePage() {
  const {
    settings,
    summary,
    trends,
    distribution,
    lowProducts,
    activity,
    actions,
    isFirstUse,
    isLoading,
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
      />

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-7xl space-y-4 px-4 py-5 sm:px-6">
          {isFirstUse ? (
            <OnboardingFlow settings={settings.data} summary={summary.data} />
          ) : (
            <>
              {/* A: Store Hero */}
              <StoreHeroSection
                settings={settings.data}
                summary={summary.data}
                isLoading={isLoading}
              />

              {/* B: Score Pulse Row */}
              <ScorePulseRow
                summary={summary.data}
                trends={trends.data}
                isLoading={trends.isLoading}
              />

              {/* C: Action Radar */}
              <ActionRadarSection actions={actions} />

              {/* D: Score Distribution */}
              <ScoreDistributionBar
                distribution={distribution.data}
                isLoading={distribution.isLoading}
              />

              {/* E + F: Needs Attention + Store Chat */}
              <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                <NeedsAttentionSection
                  lowProducts={lowProducts.data}
                  activity={activity.data}
                  isLoading={lowProducts.isLoading}
                />
                <StoreChatAdvisor storeName={storeName} />
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
