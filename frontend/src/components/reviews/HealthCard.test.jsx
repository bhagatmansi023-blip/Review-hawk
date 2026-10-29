import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import HealthCard from './HealthCard';

const health = {
  score: 62, grade: 'C', risk_level: 'Medium', badges: ['⚠️ No Tests'],
  recommendations: ['Add unit or integration tests for the changed logic.'],
  signals: [
    { code: 'NO_TESTS_INCLUDED', score_delta: -15, description: 'No test file was touched.' },
    { code: 'RICH_DESCRIPTION', score_delta: 3, description: 'Detailed PR description.' },
  ],
};

describe('HealthCard', () => {
  it('shows score, grade, risk and badges', () => {
    render(<HealthCard health={health} />);
    expect(screen.getByLabelText('PR health score')).toBeInTheDocument();
    expect(screen.getByText('62')).toBeInTheDocument();
    expect(screen.getByText('Grade C')).toBeInTheDocument();
    expect(screen.getByText('Risk: Medium')).toBeInTheDocument();
    expect(screen.getByText('⚠️ No Tests')).toBeInTheDocument();
  });

  it('explains every point gained or lost', () => {
    render(<HealthCard health={health} />);
    expect(screen.getByText('No test file was touched.')).toBeInTheDocument();
    expect(screen.getByText('-15')).toBeInTheDocument();
    expect(screen.getByText('+3')).toBeInTheDocument();
    expect(screen.getByText(/Add unit or integration tests/)).toBeInTheDocument();
  });

  it('falls back to the plain score and grade props', () => {
    render(<HealthCard score={88} grade="A" />);
    expect(screen.getByText('Grade A')).toBeInTheDocument();
  });

  it('renders nothing when the review has no score', () => {
    const { container } = render(<HealthCard health={{}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
