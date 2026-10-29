import { render, screen } from '@testing-library/react';
import { cloneElement } from 'react';
import { describe, expect, it, vi } from 'vitest';

// jsdom has no layout, so give ResponsiveContainer a fixed size to let recharts draw.
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    ResponsiveContainer: ({ children, height = 300 }) => (
      <div style={{ width: 600, height }}>{cloneElement(children, { width: 600, height })}</div>
    ),
  };
});

import ChartCard from './ChartCard';
import IssuesOverTimeChart from './IssuesOverTimeChart';
import SeverityDonut from './SeverityDonut';
import CategoryBarChart from './CategoryBarChart';
import HealthDistribution from './HealthDistribution';
import DetectorSplit from './DetectorSplit';

const series = [
  { date: '2026-10-27', error: 1, warning: 2, info: 0, total: 3, reviews: 1 },
  { date: '2026-10-28', error: 0, warning: 1, info: 4, total: 5, reviews: 2 },
];

describe('ChartCard', () => {
  it('shows children, a loading skeleton, or an empty state', () => {
    const { rerender } = render(<ChartCard title="T"><p>content</p></ChartCard>);
    expect(screen.getByText('content')).toBeInTheDocument();
    rerender(<ChartCard title="T" isLoading><p>content</p></ChartCard>);
    expect(screen.getByRole('status', { name: 'Loading chart' })).toBeInTheDocument();
    expect(screen.queryByText('content')).not.toBeInTheDocument();
    rerender(<ChartCard title="T" isEmpty emptyText="Nothing here"><p>content</p></ChartCard>);
    expect(screen.getByText('Nothing here')).toBeInTheDocument();
  });
});

describe('empty states (no fake charts)', () => {
  it('IssuesOverTimeChart', () => {
    render(<IssuesOverTimeChart series={[{ date: '2026-10-28', error: 0, warning: 0, info: 0, total: 0, reviews: 0 }]} />);
    expect(screen.getByText(/No findings yet/)).toBeInTheDocument();
  });
  it('SeverityDonut', () => {
    render(<SeverityDonut breakdown={[{ severity: 'error', count: 0 }, { severity: 'warning', count: 0 }, { severity: 'info', count: 0 }]} />);
    expect(screen.getByText(/No findings to break down/)).toBeInTheDocument();
  });
  it('CategoryBarChart, HealthDistribution, DetectorSplit', () => {
    render(<>
      <CategoryBarChart breakdown={[]} />
      <HealthDistribution distribution={[{ grade: 'A+', count: 0 }]} />
      <DetectorSplit sources={[{ source: 'llm', label: 'AI review', count: 0 }]} />
    </>);
    expect(screen.getByText(/No scored reviews yet/)).toBeInTheDocument();
    expect(screen.getAllByText(/No data in this period yet/)).toHaveLength(2);
  });
});

describe('charts with data', () => {
  it('IssuesOverTimeChart draws severities in the legend', () => {
    render(<IssuesOverTimeChart series={series} />);
    expect(screen.getByText('Issues over time')).toBeInTheDocument();
    ['Error', 'Warning', 'Info'].forEach((l) => expect(screen.getByText(l)).toBeInTheDocument());
  });

  it('SeverityDonut shows the total and per-severity counts', () => {
    render(<SeverityDonut breakdown={[{ severity: 'error', count: 2 }, { severity: 'warning', count: 3 }, { severity: 'info', count: 5 }]} />);
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('Warning').closest('li')).toHaveTextContent('3');
  });

  it('DetectorSplit shows percentages and the most common Tree-sitter rules', () => {
    render(<DetectorSplit
      sources={[{ source: 'llm', label: 'AI review', count: 3 }, { source: 'static', label: 'Tree-sitter', count: 1 }]}
      topRules={[{ rule_id: 'TS-PY-001', label: 'Unused import', count: 4 }]}
    />);
    expect(screen.getByText('AI review').closest('li')).toHaveTextContent('75%');
    expect(screen.getByText('Tree-sitter').closest('li')).toHaveTextContent('25%');
    expect(screen.getByText('Unused import')).toBeInTheDocument();
  });

  it('CategoryBarChart and HealthDistribution render their titles', () => {
    render(<>
      <CategoryBarChart breakdown={[{ category: 'bug', count: 3 }]} />
      <HealthDistribution distribution={[{ grade: 'A+', count: 2 }, { grade: 'F', count: 1 }]} />
    </>);
    expect(screen.getByText('Findings by category')).toBeInTheDocument();
    expect(screen.getByText('PR health grades')).toBeInTheDocument();
  });
});
