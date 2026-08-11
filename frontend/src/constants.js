// Shared vocabulary for learner profiles. Used by the student profile editor
// and by the teacher's create/edit student forms so the three stay in sync.

export const LEARNING_STYLES = [
  'analogy-heavy',
  'visual',
  'story-based',
  'step-by-step',
  'repetition',
];

export const NEURO_PROFILES = ['adhd', 'dyslexia', 'autism', 'dyscalculia'];

// Comma-separated text field <-> string array, used for interests and
// neuro profile inputs.
export const csvToList = (value) =>
  String(value || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

export const listToCsv = (value) =>
  Array.isArray(value) ? value.join(', ') : String(value || '');

// The goals endpoints return { active, archived }, not a flat list. Callers
// want one array with is_active intact so they can label each entry; the
// active goal comes first.
export const goalsFromResponse = (d) => [...(d?.active || []), ...(d?.archived || [])];
