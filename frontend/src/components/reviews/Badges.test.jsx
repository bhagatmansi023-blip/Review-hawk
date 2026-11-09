import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { GradeBadge, StatusBadge } from './Badges';

describe('review status badges', () => {
  it.each([
    ['pending', 'Pending'], ['running', 'Processing'], ['completed', 'Completed'],
    ['failed', 'Failed'], ['not_reviewed', 'Not reviewed'],
  ])('%s is shown as %s', (status, label) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it('shows a grade with its score, or a dash when there is none', () => {
    const { rerender } = render(<GradeBadge grade="A+" score={96} />);
    expect(screen.getByText('A+')).toBeInTheDocument();
    rerender(<GradeBadge grade="" />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
