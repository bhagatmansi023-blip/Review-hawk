import { LayoutDashboard, Clock, Activity, GitPullRequest } from 'lucide-react';

export default function Dashboard() {
  return (
    <div className="placeholder-page">
      <div className="placeholder-header">
        <div>
          <h1 className="placeholder-title">Dashboard</h1>
          <p className="placeholder-desc">
            Central command center for repository status, active PR reviews, and code quality health.
          </p>
        </div>
        <span className="placeholder-badge">
          <Clock size={14} />
          <span>Phase 2 Integration Placeholder</span>
        </span>
      </div>

      <div className="placeholder-card">
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          Upcoming Dashboard Features
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.5 }}>
          This route is structured as part of the Phase 1 routing foundation. Once the Django REST Framework authentication and repository endpoints are connected, this page will present real-time insights:
        </p>

        <div className="roadmap-list">
          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-primary)', marginBottom: '4px' }}>
              <Activity size={18} />
              <h5>Review Activity Feed</h5>
            </div>
            <p>Live stream of incoming GitHub pull requests and completed AI code analysis runs.</p>
          </div>

          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-secondary)', marginBottom: '4px' }}>
              <GitPullRequest size={18} />
              <h5>Connected Repositories</h5>
            </div>
            <p>Direct view of active branches, security scorecards, and pending PR reviews.</p>
          </div>

          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#eab308', marginBottom: '4px' }}>
              <LayoutDashboard size={18} />
              <h5>Quality Metrics Summary</h5>
            </div>
            <p>Summaries of detected bugs, security notices, and code smell reduction trends.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
