import { Link } from 'react-router-dom';
import {
  GitPullRequest,
  RotateCw,
  FolderGit2,
  GitBranch,
  ChevronDown,
  Plus,
  CheckCircle2,
  Lock,
  Globe
} from 'lucide-react';

export default function PRHeader({
  activeRepo = null,
  connectedRepos = [],
  onSelectRepo = null,
  onRefresh = null,
  isLoading = false,
}) {
  const repoName = activeRepo?.full_name || (activeRepo ? `${activeRepo.owner}/${activeRepo.name}` : null);
  const isPrivate = Boolean(activeRepo?.is_private || activeRepo?.private);
  const hasMultipleRepos = connectedRepos && connectedRepos.length > 1;

  return (
    <header className="pr-header" aria-label="Pull Requests Header">
      <div className="repo-header-top">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 className="placeholder-title" style={{ margin: 0 }}>Pull Requests</h1>
            <span className="placeholder-badge" style={{ backgroundColor: 'var(--accent-badge-bg)', color: 'var(--accent-primary)', border: '1px solid var(--accent-badge-border)' }}>
              <GitPullRequest size={14} />
              <span>Phase 5: PR Listing</span>
            </span>
          </div>
          <p className="placeholder-desc" style={{ marginTop: '6px' }}>
            Track pull requests and their automated code review status.
          </p>
        </div>

        <div className="header-actions" style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          {onRefresh && (
            <button
              type="button"
              className="btn-repo-refresh"
              onClick={onRefresh}
              disabled={isLoading || !activeRepo}
              title="Refresh pull request list"
              aria-label="Refresh pull requests"
            >
              <RotateCw size={14} className={isLoading ? 'spin-icon' : ''} />
              <span>Refresh</span>
            </button>
          )}

          <Link to="/repositories" className="btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <FolderGit2 size={15} />
            <span>Manage Repos</span>
          </Link>
        </div>
      </div>

      {/* Selected Repository Indicator & Selector */}
      {activeRepo ? (
        <div className="pr-selected-repo-bar">
          <div className="selected-repo-indicator">
            <div className="repo-indicator-icon">
              <FolderGit2 size={18} />
            </div>
            <div className="repo-indicator-info">
              <span className="indicator-label">Active Repository:</span>
              <strong className="indicator-name">{repoName}</strong>
            </div>

            <div className="indicator-meta-pills">
              <span className="repo-pill-branch">
                <GitBranch size={12} />
                <span>{activeRepo.default_branch || 'main'}</span>
              </span>
              <span className={`repo-pill-vis ${isPrivate ? 'vis-private' : 'vis-public'}`}>
                {isPrivate ? <Lock size={11} /> : <Globe size={11} />}
                <span>{isPrivate ? 'Private' : 'Public'}</span>
              </span>
              <span className="repo-pill-status">
                <CheckCircle2 size={12} />
                <span>Bot Active</span>
              </span>
            </div>
          </div>

          {/* Repository Selector Dropdown if user has connected multiple repositories */}
          {hasMultipleRepos && (
            <div className="repo-selector-wrapper">
              <label htmlFor="repo-select-dropdown" className="selector-label">
                Switch Repository:
              </label>
              <div className="selector-dropdown-box">
                <select
                  id="repo-select-dropdown"
                  className="repo-select-dropdown"
                  value={activeRepo.id || activeRepo.github_repo_id || ''}
                  onChange={(e) => {
                    const selectedId = e.target.value;
                    const found = connectedRepos.find(
                      (r) => String(r.id) === selectedId || String(r.github_repo_id) === selectedId
                    );
                    if (found && onSelectRepo) {
                      onSelectRepo(found);
                    }
                  }}
                  aria-label="Select connected repository"
                >
                  {connectedRepos.map((r) => {
                    const rId = r.id || r.github_repo_id;
                    const rName = r.full_name || `${r.owner}/${r.name}`;
                    return (
                      <option key={rId} value={rId}>
                        {rName}
                      </option>
                    );
                  })}
                </select>
                <ChevronDown size={14} className="dropdown-arrow-icon" />
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="pr-no-repo-warning">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FolderGit2 size={18} color="var(--accent-primary)" />
            <span>No repository is currently connected. Connect a repository to load pull requests.</span>
          </div>
          <Link to="/repositories" className="btn-primary" style={{ padding: '6px 14px', fontSize: '0.85rem' }}>
            <Plus size={14} />
            <span>Connect Repository</span>
          </Link>
        </div>
      )}
    </header>
  );
}
