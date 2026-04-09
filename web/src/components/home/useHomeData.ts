import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  getSettings,
  getReportSummary,
  getStoreTrends,
  getScoreDistribution,
  fetchProducts,
  getDailyActivity,
  getBatchStats,
} from '../../api/client';
import type {
  ReportSummary,
  ScoreDistributionBucket,
  BatchStats,
} from '../../types';

export interface ActionCard {
  id: string;
  icon: string;
  title: string;
  description: string;
  tone: 'primary' | 'success' | 'warning' | 'danger';
  cta: string;
  navigateTo?: string;
  action?: string;
}

function computeActions(
  summary: ReportSummary | undefined,
  distribution: ScoreDistributionBucket[] | undefined,
  batch: BatchStats | undefined,
): ActionCard[] {
  const cards: ActionCard[] = [];

  // Quick Win — low score products
  const criticalCount = distribution
    ?.filter((b) => ['0-49', '50-59', '60-69'].includes(b.bucket))
    .reduce((sum, b) => sum + b.count, 0) ?? 0;

  if (criticalCount > 0) {
    cards.push({
      id: 'quick-win',
      icon: 'M13 10V3L4 14h7v7l9-11h-7z',
      title: `${criticalCount} urun iyilestirilebilir`,
      description: 'Dusuk skorlu urunleriniz toplu optimizasyonla hizla iyilestirilebilir.',
      tone: 'warning',
      cta: 'Toplu Isleme Git',
      navigateTo: '/batch',
    });
  }

  // Weakest pillar
  if (summary?.latest_avg) {
    const pillars = [
      { key: 'seo', label: 'SEO', score: summary.latest_avg.seo ?? 0 },
      { key: 'geo', label: 'GEO', score: summary.latest_avg.geo ?? 0 },
      { key: 'aeo', label: 'AEO', score: summary.latest_avg.aeo ?? 0 },
    ];
    const weakest = pillars.reduce((a, b) => (a.score < b.score ? a : b));
    if (weakest.score < 70) {
      cards.push({
        id: 'weakest-pillar',
        icon: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z',
        title: `${weakest.label} skorunuz en zayif`,
        description: `Ortalama ${Math.round(weakest.score)} puan. Bu alana odaklanarak genel skorunuzu yukseltin.`,
        tone: 'danger',
        cta: 'Urunleri Incele',
        navigateTo: '/workspace',
      });
    }
  }

  // Momentum
  if (summary?.improvement) {
    const delta = summary.improvement.total ?? 0;
    if (delta > 0) {
      cards.push({
        id: 'momentum',
        icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6',
        title: `+${delta.toFixed(1)} puan iyilesme`,
        description: `Son ${summary.days_tracked} gunde skorunuz yukselen bir trendde. Bu ivmeyi koruyun!`,
        tone: 'success',
        cta: 'Detayli Raporlar',
        navigateTo: '/reports',
      });
    } else if (delta < -1) {
      cards.push({
        id: 'momentum',
        icon: 'M13 17h8m0 0V9m0 8l-8-8-4 4-6-6',
        title: `${delta.toFixed(1)} puan gerileme`,
        description: 'Son donemde skor geriledi. Durumu inceleyip aksiyona gecin.',
        tone: 'danger',
        cta: 'Raporlari Incele',
        navigateTo: '/reports',
      });
    }
  }

  // Active batch
  if (batch?.active_job) {
    const job = batch.active_job;
    const pct = job.total_count > 0 ? Math.round((job.processed_count / job.total_count) * 100) : 0;
    cards.push({
      id: 'active-batch',
      icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
      title: `Toplu islem devam ediyor (${pct}%)`,
      description: `${job.processed_count}/${job.total_count} urun islendi.`,
      tone: 'primary',
      cta: 'Islemi Gor',
      navigateTo: '/batch',
    });
  }

  // Fallback: if no critical products and no active batch, suggest catalog
  if (cards.length === 0) {
    cards.push({
      id: 'explore',
      icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z',
      title: 'Urun katalogunu kesfet',
      description: 'Urunlerinizin SEO durumunu inceleyin ve iyilestirme firsatlarini kesfet.',
      tone: 'primary',
      cta: 'Katalogu Ac',
      navigateTo: '/workspace',
    });
  }

  return cards;
}

export function useHomeData() {
  const settingsQ = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
  });

  const summaryQ = useQuery({
    queryKey: ['report-summary'],
    queryFn: getReportSummary,
  });

  const trendsQ = useQuery({
    queryKey: ['store-trends-7'],
    queryFn: () => getStoreTrends(7),
  });

  const distributionQ = useQuery({
    queryKey: ['score-distribution'],
    queryFn: getScoreDistribution,
  });

  const lowProductsQ = useQuery({
    queryKey: ['products-low-score'],
    queryFn: () => fetchProducts(1, 10, 'all', { sort_by: 'total_score', sort_dir: 'asc', score_threshold: 69 }),
  });

  const activityQ = useQuery({
    queryKey: ['daily-activity'],
    queryFn: () => getDailyActivity(),
  });

  const batchQ = useQuery({
    queryKey: ['batch-stats'],
    queryFn: getBatchStats,
  });

  const actions = useMemo(
    () => computeActions(summaryQ.data, distributionQ.data, batchQ.data),
    [summaryQ.data, distributionQ.data, batchQ.data],
  );

  const isFirstUse =
    !summaryQ.data || summaryQ.data.total_products === 0;

  const isLoading =
    settingsQ.isLoading || summaryQ.isLoading;

  return {
    settings: settingsQ,
    summary: summaryQ,
    trends: trendsQ,
    distribution: distributionQ,
    lowProducts: lowProductsQ,
    activity: activityQ,
    batch: batchQ,
    actions,
    isFirstUse,
    isLoading,
  };
}
