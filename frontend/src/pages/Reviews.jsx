import { CheckCircle2, Clock, FileCode, ShieldAlert } from 'lucide-react';

export default function Reviews() {
  return (
    <div className="placeholder-page">
      <div className="placeholder-header">
        <div>
          <h1 className="placeholder-title">Reviews</h1>
          <p className="placeholder-desc">
            Deep dive into AI-generated automated review findings, line-by-line diffs, and remediation advice.
          </p>
        </div>
        <span className="placeholder-badge">
          <Clock size={14} />
          <span>Scheduled for Next Phase</span>
        </span>
      </div>

      <div className="placeholder-card">
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          AI Review Inspection Interface
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.5 }}>
          This route will render full AI report cards returned by the review engine, detailing static analysis, code complexity, and AI suggestions.
        </p>

        <div className="roadmap-list">
          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-primary)', marginBottom: '4px' }}>
              <FileCode size={18} />
              <h5>Side-by-Side Diff Viewer</h5>
            </div>
            <p>Interactive code diff view highlighting problematic code snippets and proposed fixes.</p>
          </div>

          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#f43f5e', marginBottom: '4px' }}>
              <ShieldAlert size={18} />
              <h5>Security Audit Matrix</h5>
            </div>
            <p>CWE categorization, severity ratings, and automated patch suggestions for vulnerabilities.</p>
          </div>

          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#22c55e', marginBottom: '4px' }}>
              <CheckCircle2 size={18} />
              <h5>One-Click Apply</h5>
            </div>
            <p>Direct GitHub commit generation allowing developers to commit AI patches in one click.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
