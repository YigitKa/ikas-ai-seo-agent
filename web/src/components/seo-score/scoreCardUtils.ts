// Re-export from shared — this file is kept for backward compatibility during migration.
// All score utilities are now maintained in shared/score/scoreUtils.ts
export {
  SUMMARY_FIELDS,
  SCORE_FIELDS,
  getScoreColor,
  getScoreGradient,
  getFieldStatusText,
  explainIssue,
} from '../../shared/score/scoreUtils';
