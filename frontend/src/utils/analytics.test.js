import { describe, expect, it } from 'vitest';
import {
  countBySource, filterFindings, formatDay, formatDuration, formatNumber, gradeColor,
  groupByFile, hasData, timeAgo, titleCase,
} from './analytics';

const F = (id, file, line, severity, source) => ({ id, file_path: file, line_number: line, severity, source });

describe('formatters', () => {
  it('formats numbers and handles missing values', () => {
    expect(formatNumber(12345)).toBe('12,345');
    expect(formatNumber(null)).toBe('—');
    expect(formatNumber(undefined)).toBe('—');
  });
  it('formats a date string without shifting time zones', () => {
    expect(formatDay('2026-10-29')).toBe('Oct 29');
    expect(formatDay('')).toBe('');
  });
  it('formats durations', () => {
    expect(formatDuration(null)).toBe('—');
    expect(formatDuration(34.4)).toBe('34s');
    expect(formatDuration(125)).toBe('2m 5s');
  });
  it('formats relative time', () => {
    const now = new Date('2026-10-29T12:00:00Z').getTime();
    expect(timeAgo('2026-10-29T11:59:50Z', now)).toBe('just now');
    expect(timeAgo('2026-10-29T11:30:00Z', now)).toBe('30m ago');
    expect(timeAgo('2026-10-29T07:00:00Z', now)).toBe('5h ago');
    expect(timeAgo('2026-10-26T12:00:00Z', now)).toBe('3d ago');
    expect(timeAgo(null)).toBe('—');
  });
  it('title-cases labels', () => {
    expect(titleCase('maintainability')).toBe('Maintainability');
    expect(titleCase('code_smell')).toBe('Code Smell');
  });
  it('maps grades to colours with a fallback', () => {
    expect(gradeColor('A+')).toBe('#22c55e');
    expect(gradeColor('')).toBe('var(--text-muted)');
  });
});

describe('chart data helpers', () => {
  it('detects whether there is anything to chart', () => {
    expect(hasData([{ count: 0 }, { count: 0 }])).toBe(false);
    expect(hasData([{ count: 0 }, { count: 2 }])).toBe(true);
    expect(hasData([{ total: 3 }], 'total')).toBe(true);
    expect(hasData(undefined)).toBe(false);
  });
});

describe('findings helpers', () => {
  const items = [
    F(1, 'b.py', 9, 'info', 'static'),
    F(2, 'a.py', 5, 'warning', 'llm'),
    F(3, 'a.py', 5, 'error', 'static'),
    F(4, 'a.py', 1, 'info', 'llm'),
  ];

  it('filters by source and severity', () => {
    expect(filterFindings(items, { source: 'llm' }).map((f) => f.id)).toEqual([2, 4]);
    expect(filterFindings(items, { severity: 'error' }).map((f) => f.id)).toEqual([3]);
    expect(filterFindings(items, { source: 'static', severity: 'info' }).map((f) => f.id)).toEqual([1]);
    expect(filterFindings(items)).toHaveLength(4);
  });

  it('groups by file (A-Z) and sorts by line, then severity', () => {
    const groups = groupByFile(items);
    expect(groups.map((g) => g.file)).toEqual(['a.py', 'b.py']);
    expect(groups[0].items.map((f) => f.id)).toEqual([4, 3, 2]); // line 1, then error before warning on line 5
  });

  it('counts findings per detector', () => {
    expect(countBySource(items)).toEqual({ llm: 2, static: 2 });
    expect(countBySource([])).toEqual({ llm: 0, static: 0 });
  });
});
