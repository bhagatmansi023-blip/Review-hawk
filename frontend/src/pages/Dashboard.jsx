import { Link } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Clock, 
  Activity, 
  GitPullRequest, 
  FolderGit2, 
  Plus, 
  CheckCircle2, 
  ArrowRight,
  ShieldAlert,
  GitBranch
} from 'lucide-react';
import { useRepos } from '../context/useRepos';

export default function Dashboard() {
  const { connectedRepos } = useRepos();
  const hasConnectedRepo = connectedRepos && connectedRepos.length > 0;
  const primaryRepo = hasConnectedRepo ? connectedRepos[0] : null;

  return (
    <div className="placeholder-page">
      {/* Dashboard Top Header */}
      <div className="placeholder-header">
        <div>
          <h1 className="placeholder-title">Dashboard</h1>
          <p className="placeholder-desc">
            Central command center for repository status, active PR reviews, and code quality health.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <Link to="/repositories" className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
            <Plus size={16} />
            <span>Connect Repository</span>
          </Link>
          <span className="placeholder-badge">
            <Clock size={14} />
            <span>Phase 3 Repository Active</span>
          </span>
        </div>
      </div>

      {/* Connected Repository Status Card */}
      {hasConnectedRepo ? (
        <div className="dashboard-active-repo-card">
          <div className="active-repo-header">
            <div className="active-repo-badge">
              <span className="badge-dot-green" />
              <CheckCircle2 size={16} />
              <span>Connected Repository</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Link to={`/pull-requests?repo=${primaryRepo.id || primaryRepo.github_repo_id}`} className="btn-text-action" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                <GitPullRequest size={14} />
                <span>View Pull Requests</span>
              </Link>
              <Link to="/repositories" className="btn-text-action">
                Manage Repositories
              </Link>
            </div>
          </div>

          <div className="active-repo-content">
            <div className="active-repo-title-row">
              <FolderGit2 size={24} className="active-repo-icon" />
              <div>
                <h3 className="active-repo-name">
                  {primaryRepo.full_name || `${primaryRepo.owner}/${primaryRepo.name}`}
                </h3>
                <div className="active-repo-meta">
                  <span className="meta-item">
                    <GitBranch size={13} />
                    <span>{primaryRepo.default_branch || 'main'}</span>
                  </span>
                  <span className="meta-separator">•</span>
                  <span className="meta-item">
                    {primaryRepo.is_private ? 'Private repository' : 'Public repository'}
                  </span>
                  <span className="meta-separator">•</span>
                  <span className="meta-item text-success">
                    CodeHawk review bot active
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="dashboard-connect-cta-card">
          <div className="cta-icon-box">
            <FolderGit2 size={28} />
          </div>
          <div className="cta-content">
            <h3 className="cta-title">No repository connected yet</h3>
            <p className="cta-desc">
              Connect a GitHub repository to activate CodeHawk&apos;s AI review bot. Incoming pull requests will be automatically reviewed for bugs, security vulnerabilities, and code quality.
            </p>
          </div>
          <Link to="/repositories" className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
            <span>Connect a Repository</span>
            <ArrowRight size={16} />
          </Link>
        </div>
      )}

      {/* Quick Metrics Cards */}
      <div className="dashboard-stats-grid">
        <div className="stat-card">
          <div className="stat-label">
            <FolderGit2 size={16} />
            <span>Connected Repositories</span>
          </div>
          <div className="stat-value">{connectedRepos.length}</div>
          <div className="stat-subtext">Active on pull requests</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">
            <GitPullRequest size={16} />
            <span>Reviewed PRs</span>
          </div>
          <div className="stat-value">0</div>
          <div className="stat-subtext">Scheduled for Phase 4</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">
            <ShieldAlert size={16} />
            <span>Quality Findings</span>
          </div>
          <div className="stat-value">0</div>
          <div className="stat-subtext">Static & AI checks</div>
        </div>
      </div>

      {/* Feature Roadmap & Activities */}
      <div className="placeholder-card">
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          Review Engine Foundation
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.5 }}>
          Now that repository selection is established, subsequent phases will link GitHub webhook deliveries to trigger LLM diff analysis and static checks.
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
