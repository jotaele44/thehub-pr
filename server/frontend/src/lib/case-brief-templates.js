export const DEFAULT_TEMPLATE_ID = 'standard';
export const BRIEF_TEMPLATE_LIST = [
  { id: 'standard', name: 'Standard Case Brief', sections: ['summary', 'timeline', 'sources', 'gates'] },
  { id: 'field', name: 'Field Review Brief', sections: ['summary', 'location', 'sources', 'next_steps'] },
];

export function getBriefTemplate(id = DEFAULT_TEMPLATE_ID) {
  return BRIEF_TEMPLATE_LIST.find((t) => t.id === id) || BRIEF_TEMPLATE_LIST[0];
}
