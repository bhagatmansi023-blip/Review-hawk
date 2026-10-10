import { FolderGit2, Clock, Plus, GitFork } from 'lucide-react';

export default function Repositories() {
  return (
    <div className="placeholder-page">
      <div className="placeholder-header">
        <div>
          <h1 className="placeholder-title">Repositories</h1>
          <p className="placeholder-desc">
            Manage your synchronized GitHub repositories, webhooks, and automated review policies.
          </p>
        </div>
        <span className="placeholder-badge">
          <Clock size={14} />
          <span>Scheduled for Next Phase</span>
        </span>
      </div>

      <div className="placeholder-card">
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          Repository Synchronization Foundation
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.5 }}>
          In the upcoming phase, this view will query the Django backend endpoint (<code>/api/repositories/</code>) to retrieve synchronized repositories from your connected GitHub account.
        </p>

        <div className="roadmap-list">
          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-primary)', marginBottom: '4px' }}>
              <Plus size={18} />
              <h5>Repository Linking</h5>
            </div>
            <p>One-click repository import with granular permission selection for public and private codebases.</p>
          </div>

          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-secondary)', marginBottom: '4px' }}>
              <GitFork size={18} />
              <h5>Webhook Management</h5>
            </div>
            <p>Automated GitHub webhook registration for instant PR event listening and triggers.</p>
          </div>

          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#818cf8', marginBottom: '4px' }}>
              <FolderGit2 size={18} />
              <h5>Custom Rule Configuration</h5>
            </div>
            <p>Set custom review strictness, ignored files (.reviewhawkignore), and linter rules.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
