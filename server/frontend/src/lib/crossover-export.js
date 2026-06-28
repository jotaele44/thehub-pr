const cell = (value) => {
  if (value === null || value === undefined) return '';
  const text = Array.isArray(value) ? value.join('; ') : typeof value === 'object' ? JSON.stringify(value) : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

export function exportCrossoversCsv(rows = [], fileName = 'crossover-links.csv') {
  const fields = ['crossover_id','source_module','source_record_id','target_module','target_record_id','correlation_type','status','confidence_score','confidence_band','evidence_tier','municipality','agency','rationale','matching_criteria','source_ids'];
  const csv = [fields.join(','), ...rows.map((r) => fields.map((f) => cell(r[f])).join(','))].join('\n');
  if (typeof window !== 'undefined') {
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    a.click();
    URL.revokeObjectURL(url);
  }
  return { fileName, recordCount: rows.length };
}
