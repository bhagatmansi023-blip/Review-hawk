import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import SyncPanel from './SyncPanel';

const result = {
  status: 'partial',
  totals: { found: 7, queued: 5, failed: 1, succeeded: 1, repositories: 2, skipped: 0, created: 7, updated: 0 },
  reviews: { open_prs: 7, not_reviewed: 0, pending: 3, processing: 1, completed: 2, failed: 1 },
  results: [
    { repository: 'me/good', ok: true, skipped: false, error: '', fetched: 7, reviews_queued: 5, reviews_retried: 0, auth_mode: 'app' },
    { repository: 'me/bad', ok: false, skipped: false, error: 'The GitHub App is not installed on me/bad.', fetched: 0, reviews_queued: 0, reviews_retried: 0 },
  ],
  warnings: ['No Celery worker is running, so queued reviews will stay pending.'],
};

describe('SyncPanel', () => {
  it('shows how many PRs were found, queued, completed and failed', () => {
    render(<SyncPanel result={result} />);
    expect(screen.getByTestId('sync-found')).toHaveTextContent('7');
    expect(screen.getByTestId('sync-queued')).toHaveTextContent('5');
    expect(screen.getByTestId('sync-completed')).toHaveTextContent('2');
    expect(screen.getByTestId('sync-failed')).toHaveTextContent('1');
    expect(screen.getByText('Sync partial')).toBeInTheDocument();
    expect(screen.getByText(/3 pending · 1 processing · 0 not reviewed/)).toBeInTheDocument();
  });

  it('lists each repository, including the real error for the ones that failed', () => {
    render(<SyncPanel result={result} />);
    expect(screen.getByText('me/good')).toBeInTheDocument();
    expect(screen.getByText('7 open PRs, 5 queued')).toBeInTheDocument();
    expect(screen.getByText('The GitHub App is not installed on me/bad.')).toBeInTheDocument();
    expect(screen.getByText(/No Celery worker is running/)).toBeInTheDocument();
  });

  it('flags repositories that were read through the OAuth fallback', () => {
    render(<SyncPanel result={{ ...result, status: 'ok', results: [{ ...result.results[0], auth_mode: 'oauth' }], warnings: [] }} />);
    expect(screen.getByText(/via OAuth fallback/)).toBeInTheDocument();
  });

  it('says so when another sync is already running', () => {
    render(<SyncPanel result={{ ...result, status: 'busy', results: [{ ...result.results[0], skipped: true }] }} />);
    expect(screen.getByText('A sync is already running')).toBeInTheDocument();
    expect(screen.getByText('already syncing')).toBeInTheDocument();
  });

  it('shows progress while syncing and the last known state before any click', () => {
    const status = {
      reviews: { open_prs: 4, not_reviewed: 1, pending: 0, processing: 0, completed: 3, failed: 0 },
      repositories: [{ repository: 'me/app', status: 'ok', error: '', pull_requests_fetched: 4, last_synced_at: null }, { repository: 'me/new', status: 'never', error: '', pull_requests_fetched: 0 }],
    };
    const { rerender } = render(<SyncPanel status={status} />);
    expect(screen.getByTestId('sync-found')).toHaveTextContent('4');
    expect(screen.getByText('never synced')).toBeInTheDocument();
    rerender(<SyncPanel status={status} isSyncing />);
    expect(screen.getByText('Syncing pull requests…')).toBeInTheDocument();
    expect(screen.getByLabelText('Synchronisation status')).toHaveAttribute('aria-busy', 'true');
  });

  it('shows a clear error when the request itself fails', () => {
    render(<SyncPanel error={new Error('Failed to fetch')} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Sync failed. Failed to fetch');
  });

  it('renders nothing when there is nothing to show', () => {
    const { container } = render(<SyncPanel />);
    expect(container).toBeEmptyDOMElement();
  });
});
