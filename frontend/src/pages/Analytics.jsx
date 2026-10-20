import { BarChart3, Clock, TrendingUp, Award } from 'lucide-react';

export default function Analytics() {
  return (
    <div className="placeholder-page">
      <div className="placeholder-header">
        <div>
          <h1 className="placeholder-title">Analytics</h1>
          <p className="placeholder-desc">
            Track code quality trends, PR review turnaround times, and recurring team anti-patterns.
          </p>
        </div>
        <span className="placeholder-badge">
          <Clock size={14} />
          <span>Scheduled for Next Phase</span>
        </span>
      </div>

      <div className="placeholder-card">
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          Engineering Quality Analytics
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.5 }}>
          Engineering leaders and developers can track long-term code health improvements as CodeHawk runs continuous analysis across team repositories.
        </p>

        <div className="roadmap-list">
          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-primary)', marginBottom: '4px' }}>
              <TrendingUp size={18} />
              <h5>Review Velocity & Speed</h5>
            </div>
            <p>Average time from PR open to AI review completion and merge velocity improvements.</p>
          </div>

          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-secondary)', marginBottom: '4px' }}>
              <BarChart3 size={18} />
              <h5>Vulnerability Deflection</h5>
            </div>
            <p>Count of security vulnerabilities intercepted prior to reaching production releases.</p>
          </div>

          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#818cf8', marginBottom: '4px' }}>
              <Award size={18} />
              <h5>Team Code Health Score</h5>
            </div>
            <p>Aggregated maintainability index, test coverage correlations, and documentation coverage.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
