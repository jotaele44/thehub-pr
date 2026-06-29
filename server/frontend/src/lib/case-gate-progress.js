export const CASE_STAGES = [
  { key: 'intake', label: 'Intake' },
  { key: 'source_review', label: 'Source Review' },
  { key: 'correlation', label: 'Correlation' },
  { key: 'brief', label: 'Brief' },
  { key: 'archive', label: 'Archive' },
];

export function getCaseGateProgress(record = {}) {
  const status = record.status || record.review_status || 'New';
  const completed = status === 'Archived' || status === 'Closed' ? CASE_STAGES.length : status === 'Reviewing' ? 2 : status === 'Correlated' ? 3 : 1;
  return { completed, total: CASE_STAGES.length, percent: Math.round((completed / CASE_STAGES.length) * 100), current: CASE_STAGES[Math.min(completed, CASE_STAGES.length) - 1] };
}
