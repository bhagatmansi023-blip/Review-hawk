import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import ReviewsTable from './ReviewsTable';

const review = (over = {}) => ({
  id: 1, pr_id: 42, pr_number: 7, pr_title: 'Fix login', repository_name: 'me/app', head_sha: 'abcdef1234567',
  status: 'completed', created_at: '2026-10-28T10:00:00Z', duration_seconds: 34,
  health_score: 91, health_grade: 'A+', counts: { error: 1, warning: 2, info: 0, total: 3, llm: 2, static: 1 }, ...over,
});

const renderTable = (props) => render(<MemoryRouter><ReviewsTable {...props} /></MemoryRouter>);

describe('ReviewsTable', () => {
  it('renders one row per review with a link to the PR details page', () => {
    renderTable({ reviews: [review(), review({ id: 2, pr_id: 43, pr_number: 8, pr_title: 'Add docs' })] });
    const rows = screen.getAllByTestId('review-row');
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByRole('link')).toHaveAttribute('href', '/pull-requests/42');
    expect(within(rows[0]).getByText(/#7 Fix login/)).toBeInTheDocument();
    expect(within(rows[0]).getByText('abcdef1')).toBeInTheDocument();
  });

  it('shows status, finding split, health grade and duration', () => {
    renderTable({ reviews: [review()] });
    const row = screen.getByTestId('review-row');
    expect(within(row).getByText('Completed')).toBeInTheDocument();
    expect(within(row).getByText('2 AI · 1 Tree-sitter')).toBeInTheDocument();
    expect(within(row).getByText('A+')).toBeInTheDocument();
    expect(within(row).getByText('34s')).toBeInTheDocument();
  });

  it('shows a dash for reviews without a health grade (e.g. failed)', () => {
    renderTable({ reviews: [review({ status: 'failed', health_grade: '', health_score: null })] });
    const row = screen.getByTestId('review-row');
    expect(within(row).getByText('Failed')).toBeInTheDocument();
    expect(within(row).getByText('—', { selector: '.muted-dash' })).toBeInTheDocument();
  });

  it('hides the duration column in compact mode', () => {
    renderTable({ reviews: [review()], compact: true });
    expect(screen.queryByText('Duration')).not.toBeInTheDocument();
  });
});
