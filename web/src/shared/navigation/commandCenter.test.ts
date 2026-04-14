import { describe, expect, it } from 'vitest';
import {
  LOW_SCORE_THRESHOLD,
  buildAttentionWorkspaceUrl,
  buildQuickWinBatchUrl,
  buildWeakestPillarWorkspaceUrl,
  parseBatchPreset,
  parseWorkspacePreset,
} from './commandCenter';

function getSearchParams(url: string) {
  return new URL(url, 'https://example.test').searchParams;
}

describe('commandCenter navigation presets', () => {
  it('builds attention workspace links that preserve product focus', () => {
    const preset = parseWorkspacePreset(getSearchParams(buildAttentionWorkspaceUrl('product-42')));

    expect(preset.productId).toBe('product-42');
    expect(preset.filter).toBe('low_score');
    expect(preset.sortBy).toBe('total_score');
    expect(preset.sortDir).toBe('asc');
    expect(preset.contextLabel).toBe('Dikkat gerektiren urunler');
  });

  it('builds weakest pillar workspace links with pillar-specific thresholds', () => {
    const preset = parseWorkspacePreset(getSearchParams(buildWeakestPillarWorkspaceUrl('seo')));

    expect(preset.filter).toBe('all');
    expect(preset.sortBy).toBe('seo_score');
    expect(preset.sortDir).toBe('asc');
    expect(preset.seoScoreThreshold).toBe(LOW_SCORE_THRESHOLD);
    expect(preset.geoScoreThreshold).toBeNull();
    expect(preset.contextLabel).toBe('SEO skoru zayif urunler');
  });

  it('builds quick win batch links with low-score defaults', () => {
    const preset = parseBatchPreset(getSearchParams(buildQuickWinBatchUrl()));

    expect(preset.scoreThreshold).toBe(LOW_SCORE_THRESHOLD);
    expect(preset.sortBy).toBe('total_score');
    expect(preset.sortDir).toBe('asc');
    expect(preset.contextLabel).toBe('Hizli kazanim: dusuk skorlu urunler');
    expect(preset.missingEnglishOnly).toBe(false);
  });
});
