import { GitPullRequest, Clock, CheckCircle2, AlertTriangle } from 'lucide-react';

export default function PullRequests() {
  return (
    <div className="placeholder-page">
      <div className="placeholder-header">
        <div>
          <h1 className="placeholder-title">Pull Requests</h1>
          <p className="placeholder-desc">
            Monitor active pull requests across all connected repositories and track AI review verdicts.
          </p>
        </div>
        <span className="placeholder-badge">
          <Clock size={14} />
          <span>Scheduled for Next Phase</span>
        </span>
      </div>

      <div className="placeholder-card">
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          PR Review Pipeline
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.5 }}>
          Once the Django backend PR webhook listener is active, incoming pull requests will appear here with automated status indicators and analysis summaries.
        </p>

        <div className="roadmap-list">
          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-primary)', marginBottom: '4px' }}>
              <GitPullRequest size={18} />
              <h5>Real-time PR Stream</h5>
            </div>
            <p>Filter by repository, author, or review status (Pending, Approved, Changes Requested).</p>
          </div>

          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#22c55e', marginBottom: '4px' }}>
              <CheckCircle2 size={18} />
              <h5>Automated GitHub Comments</h5>
            </div>
            <p>Direct synchronization with GitHub PR conversation threads with inline code suggestions.</p>
          </div>

          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#f43f5e', marginBottom: '4px' }}>
              <AlertTriangle size={18} />
              <h5>Blocking Issue Flags</h5>
            </div>
            <p>Automatic checks blocking merges if critical vulnerabilities or syntax regressions are discovered.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
