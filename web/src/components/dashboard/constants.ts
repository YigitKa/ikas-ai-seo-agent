export type FilterTab = 'all' | 'low_score' | 'missing_english' | 'pending' | 'approved';

export const FILTER_TABS: FilterTab[] = [
  'all',
  'low_score',
  'missing_english',
  'pending',
  'approved',
];

export const FILTER_LABELS: Record<FilterTab, string> = {
  all: 'Tumu',
  low_score: 'Dusuk Skor',
  missing_english: 'EN Eksik',
  pending: 'Bekleyen',
  approved: 'Onaylanan',
};
