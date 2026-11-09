import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { cloneElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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
vi.mock('../services/syncService', () => ({
  default: { syncAll: vi.fn(), getStatus: vi.fn(), listPullRequests: vi.fn() },
}));

import useStats from '../hooks/useStats';
import { useRepos } from '../context/useRepos';
import syncService from '../services/syncService';
import Dashboard from './Dashboard';

const stats = {
  totals: { repositories: 2, pull_requests_reviewed: 2, reviews: 2, completed: 2, failed: 0, findings: 3, ai_findings: 1, static_findings: 2, avg_health_score: 88, avg_review_seconds: 20 },
  severity_breakdown: [{ severity: 'error', count: 1 }, { severity: 'warning', count: 1 }, { severity: 'info', count: 1 }],
  category_breakdown: [], source_breakdown: [{ source: 'llm', label: 'AI review', count: 1 }, { source: 'static', label: 'Tree-sitter', count: 2 }],
  top_rules: [], health_distribution: [{ grade: 'A', count: 2 }],
  issues_over_time: [{ date: '2026-10-28', error: 1, warning: 1, info: 1, total: 3, reviews: 2 }],
  per_repository: [], recent_reviews: [],
};

const pr = (n, over = {}) => ({
  id: n, number: n, title: `Change ${n}`, author: 'mansi', state: 'open', repository_name: n % 2 ? 'me/alpha' : 'me/beta',
  html_url: `https://github.com/me/x/pull/${n}`, source_branch: 'feature/x', target_branch: 'main',
  updated_at: '2026-10-30T10:00:00Z', github_updated_at: '2026-10-30T10:00:00Z', review_status: 'completed',
  latest_review: { status: 'completed', health_grade: 'A', health_score: 90, counts: { total: 2 } }, ...over,
});
const page = (results, count = results.length) => ({ count, next: null, previous: null, results });

const syncReport = {
  status: 'partial',
  totals: { repositories: 2, succeeded: 1, failed: 1, skipped: 0, found: 3, created: 3, updated: 0, queued: 2 },
  reviews: { open_prs: 3, not_reviewed: 0, pending: 2, processing: 0, completed: 1, failed: 0 },
  results: [
    { repository: 'me/alpha', ok: true, skipped: false, error: '', fetched: 3, reviews_queued: 2, reviews_retried: 0, auth_mode: 'app' },
    { repository: 'me/beta', ok: false, skipped: false, error: 'The GitHub App is not installed on me/beta.', fetched: 0, reviews_queued: 0, reviews_retried: 0 },
  ],
  warnings: [],
};

const renderPage = () => render(<MemoryRouter><Dashboard /></MemoryRouter>);
const syncButton = () => screen.getByRole('button', { name: /Sync Pull Requests|Syncing/ });

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useRepos.mockReturnValue({ connectedRepos: [{ id: 1, owner: 'me', name: 'alpha', full_name: 'me/alpha', default_branch: 'main' }, { id: 2, owner: 'me', name: 'beta', full_name: 'me/beta' }] });
    useStats.mockReturnValue({ data: stats, isLoading: false, error: null, reload: vi.fn() });
    syncService.listPullRequests.mockResolvedValue(page([pr(1), pr(2, { review_status: 'failed', latest_review: { status: 'failed', error_message: 'NotFound: 404 models/gemini-x' } })]));
    syncService.getStatus.mockResolvedValue({ repositories: [], reviews: { open_prs: 0, not_reviewed: 0, pending: 0, processing: 0, completed: 0, failed: 0 }, celery: null });
  });

  afterEach(() => vi.useRealTimers());

  it('lists the real pull requests from every repository with their review status', async () => {
    renderPage();
    const rows = await screen.findAllByTestId('pr-row');
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText('me/alpha')).toBeInTheDocument();
    expect(within(rows[1]).getByText('me/beta')).toBeInTheDocument();
    expect(within(rows[0]).getByText('Completed')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Failed')).toBeInTheDocument();
    expect(screen.getByText(/NotFound: 404 models\/gemini-x/)).toBeInTheDocument();
    expect(syncService.listPullRequests).toHaveBeenCalledWith({ page: 1, state: 'open' });
  });

  it('still shows the charts and stats', async () => {
    renderPage();
    expect(screen.getByTestId('stat-findings')).toHaveTextContent('3');
    expect(screen.getByText('Issues over time')).toBeInTheDocument();
    await screen.findAllByTestId('pr-row');
  });

  it('Sync Pull Requests starts one sync, shows the counts and refreshes the list', async () => {
    syncService.syncAll.mockResolvedValue(syncReport);
    renderPage();
    await screen.findAllByTestId('pr-row');
    const reload = useStats().reload;
    const loadsBefore = syncService.listPullRequests.mock.calls.length;
    fireEvent.click(syncButton());
    expect(await screen.findByText('Sync partial')).toBeInTheDocument();
    expect(syncService.syncAll).toHaveBeenCalledTimes(1);
    expect(syncService.syncAll).toHaveBeenCalledWith({ review: true });
    expect(screen.getByTestId('sync-found')).toHaveTextContent('3');
    expect(screen.getByTestId('sync-queued')).toHaveTextContent('2');
    expect(screen.getByTestId('sync-completed')).toHaveTextContent('1');
    expect(screen.getByText('The GitHub App is not installed on me/beta.')).toBeInTheDocument();
    await waitFor(() => expect(syncService.listPullRequests.mock.calls.length).toBeGreaterThan(loadsBefore));
    expect(reload).toBeDefined();
  });

  it('cannot start a second sync while one is running (no duplicate tasks)', async () => {
    let finish;
    syncService.syncAll.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    renderPage();
    await screen.findAllByTestId('pr-row');
    fireEvent.click(syncButton());
    fireEvent.click(syncButton());
    fireEvent.click(syncButton());
    expect(syncService.syncAll).toHaveBeenCalledTimes(1);
    expect(syncButton()).toBeDisabled();
    expect(syncButton()).toHaveTextContent('Syncing…');
    await act(async () => finish(syncReport));
    await waitFor(() => expect(syncButton()).not.toBeDisabled());
  });

  it('explains a failed sync request', async () => {
    syncService.syncAll.mockRejectedValue(new Error('No repository is connected.'));
    renderPage();
    await screen.findAllByTestId('pr-row');
    fireEvent.click(syncButton());
    expect(await screen.findByRole('alert')).toHaveTextContent('Sync failed. No repository is connected.');
  });

  it('turns an HTTP 409 into a friendly "already running" message', async () => {
    syncService.syncAll.mockRejectedValue(Object.assign(new Error('API error (409)'), { status: 409 }));
    renderPage();
    await screen.findAllByTestId('pr-row');
    fireEvent.click(syncButton());
    expect(await screen.findByRole('alert')).toHaveTextContent('A sync is already running');
  });

  it('is disabled until a repository is connected, and explains the empty state', async () => {
    useRepos.mockReturnValue({ connectedRepos: [] });
    syncService.listPullRequests.mockResolvedValue(page([]));
    renderPage();
    expect(syncButton()).toBeDisabled();
    expect(await screen.findByText(/Connect a repository first/)).toBeInTheDocument();
    expect(screen.getByText('No repository connected yet')).toBeInTheDocument();
  });

  it('tells the user to sync when repositories are connected but no PRs are stored', async () => {
    syncService.listPullRequests.mockResolvedValue(page([]));
    renderPage();
    expect(await screen.findByText(/Click Sync Pull Requests to fetch the open ones from GitHub/)).toBeInTheDocument();
  });

  it('shows an error with retry when the pull request list cannot be loaded', async () => {
    syncService.listPullRequests.mockRejectedValueOnce(new Error('Server exploded'));
    renderPage();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Server exploded');
    fireEvent.click(within(alert).getByRole('button', { name: /Retry/ }));
    expect(await screen.findAllByTestId('pr-row')).toHaveLength(2);
  });

  it('switches between open and all pull requests', async () => {
    renderPage();
    await screen.findAllByTestId('pr-row');
    fireEvent.click(screen.getByRole('button', { name: 'All' }));
    await waitFor(() => expect(syncService.listPullRequests).toHaveBeenLastCalledWith({ page: 1, state: undefined }));
  });

  it('keeps refreshing while a review is pending or processing', async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    syncService.listPullRequests.mockResolvedValue(page([pr(1, { review_status: 'running', latest_review: null })]));
    renderPage();
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByText(/reviews running, updating automatically/)).toBeInTheDocument();
    const before = syncService.listPullRequests.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(5100); });
    expect(syncService.listPullRequests.mock.calls.length).toBeGreaterThan(before);
  });
});
