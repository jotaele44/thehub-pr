import { getBriefTemplate, DEFAULT_TEMPLATE_ID } from '@/lib/case-brief-templates';
import { getCaseGateProgress } from '@/lib/case-gate-progress';

export async function generateCaseBriefPdf(record = {}, options = {}) {
  const template = getBriefTemplate(options.templateId || DEFAULT_TEMPLATE_ID);
  const progress = getCaseGateProgress(record);
  const text = [
    `INTSYS-PR Case Brief: ${record.title || record.case_id || record.id || 'Untitled'}`,
    `Template: ${template.name}`,
    `Status: ${record.status || record.review_status || 'Unknown'}`,
    `Gate progress: ${progress.completed}/${progress.total}`,
    '',
    record.summary || 'No summary available.',
  ].join('\n');
  if (typeof window !== 'undefined') {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${record.case_id || record.id || 'case'}-brief.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }
  return { fileName: `${record.case_id || record.id || 'case'}-brief.txt`, text };
}
