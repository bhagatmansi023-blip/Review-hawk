import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import StatCards from './StatCards';

const totals = {
  repositories: 2, pull_requests_reviewed: 5, reviews: 7, completed: 6, failed: 1,
  findings: 12, ai_findings: 8, static_findings: 4, avg_health_score: 82.4, avg_review_seconds: 75,
};

describe('StatCards', () => {
  it('renders the headline numbers', () => {
    render(<StatCards totals={totals} />);
    expect(screen.getByTestId('stat-repos')).toHaveTextContent('2');
    expect(screen.getByTestId('stat-prs')).toHaveTextContent('5');
    expect(screen.getByTestId('stat-findings')).toHaveTextContent('12');
    expect(screen.getByTestId('stat-findings')).toHaveTextContent('8 AI · 4 Tree-sitter');
    expect(screen.getByTestId('stat-health')).toHaveTextContent('82/100');
    expect(screen.getByTestId('stat-health')).toHaveTextContent('Grade A');
    expect(screen.getByTestId('stat-time')).toHaveTextContent('1m 15s');
    expect(screen.getByTestId('stat-failed')).toHaveTextContent('1');
  });

  it('shows dashes instead of fake numbers when there is no data', () => {
    render(<StatCards totals={{ ...totals, avg_health_score: null, avg_review_seconds: null }} />);
    expect(screen.getByTestId('stat-health')).toHaveTextContent('—');
    expect(screen.getByTestId('stat-health')).toHaveTextContent('No scored reviews yet');
    expect(screen.getByTestId('stat-time')).toHaveTextContent('—');
  });

  it('marks the grid busy while loading and hides values', () => {
    const { container } = render(<StatCards totals={null} isLoading />);
    expect(container.firstChild).toHaveAttribute('aria-busy', 'true');
    expect(container.querySelectorAll('.stat-skeleton')).toHaveLength(6);
  });
});
