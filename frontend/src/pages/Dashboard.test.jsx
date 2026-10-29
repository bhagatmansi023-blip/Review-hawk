import { render, screen } from '@testing-library/react';
import { cloneElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    ResponsiveContainer: ({ children, height = 300 }) => (
      <div style={{ width: 600, height }}>{cloneElement(children, { width: 600, height })}</div>
    ),
  };
});
vi.mock('../hooks/useStats', () => ({ default: vi.fn() }));
vi.mock('../context/useRepos', () => ({ useRepos: vi.fn() }));

import useStats from '../hooks/useStats';
import { useRepos } from '../context/useRepos';
import Dashboard from './Dashboard';

const stats = {
  totals: { repositories: 1, pull_requests_reviewed: 2, reviews: 2, completed: 2, failed: 0, findings: 3, ai_findings: 1, static_findings: 2, avg_health_score: 88, avg_review_seconds: 20 },
  severity_breakdown: [{ severity: 'error', count: 1 }, { severity: 'warning', count: 1 }, { severity: 'info', count: 1 }],
  category_breakdown: [], source_breakdown: [{ source: 'llm', label: 'AI review', count: 1 }, { source: 'static', label: 'Tree-sitter', count: 2 }],
  top_rules: [], health_distribution: [{ grade: 'A', count: 2 }],
  issues_over_time: [{ date: '2026-10-28', error: 1, warning: 1, info: 1, total: 3, reviews: 2 }],
  per_repository: [],
  recent_reviews: [{
    id: 9, pr_id: 3, pr_number: 3, pr_title: 'Add login', repository_name: 'me/app', head_sha: 'abcdef123', status: 'completed',
    created_at: '2026-10-28T10:00:00Z', duration_seconds: 20, health_score: 88, health_grade: 'A',
    counts: { error: 1, warning: 1, info: 1, total: 3, llm: 1, static: 2 },
  }],
};

const renderPage = () => render(<MemoryRouter><Dashboard /></MemoryRouter>);

describe('Dashboard', () => {
  beforeEach(() => {
    useRepos.mockReturnValue({ connectedRepos: [{ id: 1, owner: 'me', name: 'app', full_name: 'me/app', default_branch: 'main' }] });
  });

  it('shows real stats, charts and the recent review', () => {
    useStats.mockReturnValue({ data: stats, isLoading: false, error: null, reload: vi.fn() });
    renderPage();
    expect(screen.getByTestId('stat-findings')).toHaveTextContent('3');
    expect(screen.getByText('Issues over time')).toBeInTheDocument();
    expect(screen.getByText('Severity breakdown')).toBeInTheDocument();
    expect(screen.getByText(/#3 Add login/)).toBeInTheDocument();
    expect(screen.getByText('me/app', { selector: 'h3' })).toBeInTheDocument();
  });

  it('shows loading skeletons while the request is in flight', () => {
    useStats.mockReturnValue({ data: null, isLoading: true, error: null, reload: vi.fn() });
    renderPage();
    expect(screen.getAllByRole('status').length).toBeGreaterThan(0);
  });

  it('shows an error with a retry button when the API fails', () => {
    const reload = vi.fn();
    useStats.mockReturnValue({ data: null, isLoading: false, error: new Error('Server exploded'), reload });
    renderPage();
    expect(screen.getByRole('alert')).toHaveTextContent('Server exploded');
    screen.getByRole('button', { name: /Retry/ }).click();
    expect(reload).toHaveBeenCalled();
  });

  it('prompts to connect a repository and explains the empty state', () => {
    useRepos.mockReturnValue({ connectedRepos: [] });
    useStats.mockReturnValue({
      data: { ...stats, totals: { ...stats.totals, repositories: 0, findings: 0 }, recent_reviews: [], issues_over_time: [], severity_breakdown: [] },
      isLoading: false, error: null, reload: vi.fn(),
    });
    renderPage();
    expect(screen.getByText('No repository connected yet')).toBeInTheDocument();
    expect(screen.getByText(/No reviews yet/)).toBeInTheDocument();
  });
});
