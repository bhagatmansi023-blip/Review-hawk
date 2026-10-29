import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import FindingsPanel from './FindingsPanel';

const comments = [
  { id: 1, file_path: 'app.py', line_number: 3, severity: 'error', category: 'security', message: 'Hardcoded secret', suggestion: 'Use env vars', source: 'static', rule_id: 'TS-PY-005', rule_label: 'Hardcoded secret' },
  { id: 2, file_path: 'app.py', line_number: 9, severity: 'warning', category: 'bug', message: 'Off by one', suggestion: '', source: 'llm', rule_id: '', rule_label: '' },
  { id: 3, file_path: 'util.py', line_number: 1, severity: 'info', category: 'maintainability', message: 'Unused import os', suggestion: '', source: 'static', rule_id: 'TS-PY-001', rule_label: 'Unused import' },
];

describe('FindingsPanel', () => {
  it('shows AI and Tree-sitter findings together, grouped by file', () => {
    render(<FindingsPanel comments={comments} />);
    expect(screen.getAllByTestId('finding')).toHaveLength(3);
    expect(screen.getByText('app.py')).toBeInTheDocument();
    expect(screen.getByText('util.py')).toBeInTheDocument();
    expect(screen.getByText('Hardcoded secret', { selector: 'p' })).toBeInTheDocument();
    expect(screen.getByText(/Use env vars/)).toBeInTheDocument();
  });

  it('labels where each finding came from', () => {
    render(<FindingsPanel comments={comments} />);
    const rows = screen.getAllByTestId('finding');
    expect(within(rows[0]).getByText(/Tree-sitter/)).toBeInTheDocument();
    expect(within(rows[1]).getByText(/AI review/)).toBeInTheDocument();
  });

  it('filters by detector using the tabs', () => {
    render(<FindingsPanel comments={comments} />);
    fireEvent.click(screen.getByRole('tab', { name: /AI review/ }));
    expect(screen.getAllByTestId('finding')).toHaveLength(1);
    fireEvent.click(screen.getByRole('tab', { name: /Tree-sitter/ }));
    expect(screen.getAllByTestId('finding')).toHaveLength(2);
    fireEvent.click(screen.getByRole('tab', { name: /All/ }));
    expect(screen.getAllByTestId('finding')).toHaveLength(3);
  });

  it('filters by severity', () => {
    render(<FindingsPanel comments={comments} />);
    fireEvent.change(screen.getByLabelText('Severity'), { target: { value: 'error' } });
    expect(screen.getAllByTestId('finding')).toHaveLength(1);
  });

  it('shows tab counts', () => {
    render(<FindingsPanel comments={comments} />);
    expect(screen.getByRole('tab', { name: /All/ })).toHaveTextContent('3');
    expect(screen.getByRole('tab', { name: /AI review/ })).toHaveTextContent('1');
    expect(screen.getByRole('tab', { name: /Tree-sitter/ })).toHaveTextContent('2');
  });

  it('shows a friendly empty state', () => {
    render(<FindingsPanel comments={[]} />);
    expect(screen.getByText(/No findings for this review/)).toBeInTheDocument();
  });

  it('explains when filters hide everything', () => {
    render(<FindingsPanel comments={[comments[1]]} />);
    fireEvent.click(screen.getByRole('tab', { name: /Tree-sitter/ }));
    expect(screen.getByText(/No findings match these filters/)).toBeInTheDocument();
  });
});
