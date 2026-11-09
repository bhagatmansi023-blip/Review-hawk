import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import PullRequestsTable from './PullRequestsTable';

const pr = (over = {}) => ({
  id: 12, number: 7, title: 'Add JWT login', author: 'mansi', state: 'open', repository_name: 'me/review-hawk',
  html_url: 'https://github.com/me/review-hawk/pull/7', source_branch: 'feature/login', target_branch: 'main',
  updated_at: '2026-10-30T10:00:00Z', github_updated_at: '2026-10-30T10:00:00Z', review_status: 'completed',
  latest_review: { status: 'completed', health_grade: 'B', health_score: 74, counts: { total: 3 }, error_message: '' }, ...over,
});

const renderTable = (pullRequests) => render(<MemoryRouter><PullRequestsTable pullRequests={pullRequests} /></MemoryRouter>);

describe('PullRequestsTable', () => {
  it('shows repository, number, title, author, state, review status and a GitHub link', () => {
    renderTable([pr()]);
    const row = screen.getByTestId('pr-row');
    expect(within(row).getByText('me/review-hawk')).toBeInTheDocument();
    expect(within(row).getByRole('link', { name: /#7 Add JWT login/ })).toHaveAttribute('href', '/pull-requests/12');
    expect(within(row).getByText('mansi')).toBeInTheDocument();
    expect(within(row).getByText('Open')).toBeInTheDocument();
    expect(within(row).getByText('Completed')).toBeInTheDocument();
    expect(within(row).getByText('B')).toBeInTheDocument();
    expect(within(row).getByText('3 findings')).toBeInTheDocument();
    expect(within(row).getByRole('link', { name: 'Open pull request #7 on GitHub' })).toHaveAttribute('href', 'https://github.com/me/review-hawk/pull/7');
  });

  it('shows branches and PR states', () => {
    renderTable([pr({ state: 'merged' }), pr({ id: 13, number: 8, state: 'closed' })]);
    expect(screen.getAllByText('feature/login')).toHaveLength(2);
    expect(screen.getByText('Merged')).toBeInTheDocument();
    expect(screen.getByText('Closed')).toBeInTheDocument();
  });

  it('labels every review state: pending, processing, failed and not reviewed', () => {
    renderTable([
      pr({ id: 1, number: 1, review_status: 'pending', latest_review: null }),
      pr({ id: 2, number: 2, review_status: 'running', latest_review: null }),
      pr({ id: 3, number: 3, review_status: 'failed', latest_review: { status: 'failed', error_message: 'NotFound: 404 models/gemini-x is not found' } }),
      pr({ id: 4, number: 4, review_status: '', latest_review: null }),
    ]);
    const rows = screen.getAllByTestId('pr-row');
    expect(within(rows[0]).getByText('Pending')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Processing')).toBeInTheDocument();
    expect(within(rows[2]).getByText('Failed')).toBeInTheDocument();
    expect(within(rows[3]).getByText('Not reviewed')).toBeInTheDocument();
  });

  it('shows the real analysis error of a failed review', () => {
    renderTable([pr({ review_status: 'failed', latest_review: { status: 'failed', error_message: 'NotFound: 404 models/gemini-x is not found' } })]);
    expect(screen.getByText(/NotFound: 404 models\/gemini-x is not found/)).toBeInTheDocument();
  });
});
