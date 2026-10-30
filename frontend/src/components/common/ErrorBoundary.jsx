import React from 'react';
import { AlertCircle, RotateCw } from 'lucide-react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary caught error]:', error, errorInfo);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="placeholder-page" style={{ padding: '40px 20px', textAlign: 'center' }}>
          <div className="chart-empty" style={{ maxWidth: 500, margin: '0 auto', background: 'var(--bg-surface)', padding: 32, borderRadius: 12, border: '1px solid var(--border-subtle)' }}>
            <AlertCircle size={40} color="var(--accent-danger, #ef4444)" />
            <h2 style={{ fontSize: '1.25rem', marginTop: 16, color: 'var(--text-primary)' }}>Something went wrong</h2>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: 20 }}>
              {this.state.error?.message || 'An unexpected error occurred while displaying this page.'}
            </p>
            <button
              type="button"
              className="btn-primary"
              onClick={this.handleReload}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
            >
              <RotateCw size={16} />
              <span>Reload page</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
