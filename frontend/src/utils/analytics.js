/**
 * Pure helpers shared by the dashboard, analytics and review pages.
 * Kept free of React so they are easy to unit-test.
 */

export const SEVERITY_ORDER = ['error', 'warning', 'info'];

export const SEVERITY_META = {
  error: { label: 'Error', color: '#ef4444' },
  warning: { label: 'Warning', color: '#f59e0b' },
  info: { label: 'Info', color: '#38bdf8' },
};

export const SOURCE_META = {
  llm: { label: 'AI review', color: '#6366f1' },
  static: { label: 'Tree-sitter', color: '#22c55e' },
};

export const GRADE_COLORS = {
  'A+': '#22c55e',
  A: '#4ade80',
  B: '#eab308',
  C: '#f97316',
  D: '#ef4444',
  F: '#b91c1c',
};

export function gradeColor(grade) {
  return GRADE_COLORS[grade] || 'var(--text-muted)';
}

export function titleCase(text = '') {
  return String(text)
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatNumber(n) {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return '—';
  return new Intl.NumberFormat('en-US').format(Number(n));
}

/** "2026-10-29" -> "Oct 29" (parsed as a plain date so time zones never shift it). */
export function formatDay(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.split('-').map(Number);
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(new Date(y, m - 1, d));
}

export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return '—';
  const s = Math.round(Number(seconds));
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

export function timeAgo(iso, now = Date.now()) {
  if (!iso) return '—';
  const diff = Math.max(0, Math.floor((now - new Date(iso).getTime()) / 1000));
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)}d ago`;
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(iso));
}

/** True when at least one item has a count above zero (decides chart vs empty state). */
export function hasData(items = [], key = 'count') {
  return items.some((item) => Number(item?.[key]) > 0);
}

/** Filter findings by source ('all' | 'llm' | 'static') and severity ('all' | 'error' | ...). */
export function filterFindings(comments = [], { source = 'all', severity = 'all' } = {}) {
  return comments.filter(
    (c) => (source === 'all' || c.source === source) && (severity === 'all' || c.severity === severity),
  );
}

/** Group findings by file, files A-Z, findings by line number then severity. */
export function groupByFile(comments = []) {
  const rank = { error: 0, warning: 1, info: 2 };
  const map = new Map();
  for (const c of comments) {
    if (!map.has(c.file_path)) map.set(c.file_path, []);
    map.get(c.file_path).push(c);
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([file, items]) => ({
      file,
      items: [...items].sort((x, y) => x.line_number - y.line_number || rank[x.severity] - rank[y.severity]),
    }));
}

/** Counts per source for a list of findings. */
export function countBySource(comments = []) {
  return comments.reduce(
    (acc, c) => ({ ...acc, [c.source]: (acc[c.source] || 0) + 1 }),
    { llm: 0, static: 0 },
  );
}
