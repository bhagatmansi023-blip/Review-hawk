import { Link } from 'react-router-dom';
import { GitBranch, Lock, Globe, Check, ExternalLink, CheckCircle2, GitPullRequest } from 'lucide-react';
import { useRepos } from '../../context/useRepos';

export default function RepoTable() {
  const {
    filteredRepositories,
    connectedRepos,
    selectedRepo,
    selectRepo,
    disconnectRepo,
    setActiveRepo,
    isConnecting,
  } = useRepos();

  return (
    <div className="repo-table-container">
      {/* 1. Desktop Responsive Table View */}
      <div className="repo-table-wrapper repo-desktop-table">
        <table className="repo-table" aria-label="Repositories Table">
          <thead>
            <tr>
              <th scope="col" style={{ width: '38%' }}>Repository</th>
              <th scope="col" style={{ width: '15%' }}>Visibility</th>
              <th scope="col" style={{ width: '15%' }}>Default Branch</th>
              <th scope="col" style={{ width: '16%' }}>Connection Status</th>
              <th scope="col" style={{ width: '16%', textAlign: 'right' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredRepositories.map((repo) => {
              const repoId = Number(repo.github_repo_id || repo.id);
              const owner = typeof repo.owner === 'object' ? repo.owner?.login : repo.owner;
              const name = repo.name;
              const fullName = repo.full_name || `${owner}/${name}`;
              const isPrivate = Boolean(repo.is_private || repo.private);
              const defaultBranch = repo.default_branch || 'main';

              const isConnected = Boolean(
                repo.registered ||
                repo.is_connected ||
                connectedRepos.some((c) => Number(c.github_repo_id || c.id) === repoId)
              );

              const isSelected = Boolean(
                selectedRepo && Number(selectedRepo.github_repo_id || selectedRepo.id) === repoId
              );

              return (
                <tr
                  key={repoId}
                  className={`repo-row ${isSelected ? 'row-selected' : ''} ${isConnected ? 'row-connected' : ''}`}
                  onClick={() => !isConnected && selectRepo(repo)}
                  tabIndex={0}
                  role="button"
                  aria-pressed={isSelected}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      if (!isConnected) selectRepo(repo);
                    }
                  }}
                >
                  {/* Repository details */}
                  <td>
                    <div className="repo-info-cell">
                      <div className="repo-title-row">
                        <span className="repo-name">{fullName}</span>
                        {repo.html_url && (
                          <a
                            href={repo.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="repo-external-link"
                            onClick={(e) => e.stopPropagation()}
                            title="View on GitHub"
                            aria-label={`View ${fullName} on GitHub`}
                          >
                            <ExternalLink size={13} />
                          </a>
                        )}
                      </div>
                      {repo.description && (
                        <p className="repo-card-desc" style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '2px 0 0' }}>
                          {repo.description}
                        </p>
                      )}
                      {repo.language && (
                        <span className="repo-language-tag">
                          <span className="repo-lang-dot" />
                          <span>{repo.language}</span>
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Visibility */}
                  <td>
                    {isPrivate ? (
                      <span className="badge-visibility badge-private">
                        <Lock size={12} />
                        <span>Private</span>
                      </span>
                    ) : (
                      <span className="badge-visibility badge-public">
                        <Globe size={12} />
                        <span>Public</span>
                      </span>
                    )}
                  </td>

                  {/* Default branch */}
                  <td>
                    <div className="repo-branch-cell">
                      <GitBranch size={13} />
                      <span>{defaultBranch}</span>
                    </div>
                  </td>

                  {/* Connection Status */}
                  <td>
                    {isConnected ? (
                      <span className="badge-status badge-status-active">
                        <CheckCircle2 size={13} />
                        <span>Connected</span>
                      </span>
                    ) : (
                      <span className="badge-status badge-status-available">
                        <span>Not Connected</span>
                      </span>
                    )}
                  </td>

                  {/* Selection / Action */}
                  <td style={{ textAlign: 'right' }}>
                    {isConnected ? (
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                        <Link
                          to={`/pull-requests?repo=${repoId}`}
                          className="btn-table-prs"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (setActiveRepo) setActiveRepo(repo);
                          }}
                          title="View pull requests for this repository"
                        >
                          <GitPullRequest size={13} />
                          <span>View PRs</span>
                        </Link>
                        <button
                          type="button"
                          className="btn-repo-disconnect"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (window.confirm(`Disconnect CodeHawk from ${fullName}?`)) {
                              disconnectRepo(repoId);
                            }
                          }}
                          disabled={isConnecting}
                          title="Disconnect repository"
                        >
                          Disconnect
                        </button>
                      </div>
                    ) : isSelected ? (
                      <span className="badge-selected-pill">
                        <Check size={12} />
                        <span>Selected</span>
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="btn-repo-select"
                        onClick={(e) => {
                          e.stopPropagation();
                          selectRepo(repo);
                        }}
                      >
                        Select
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 2. Mobile / Tablet Card View */}
      <div className="repo-mobile-card-list">
        {filteredRepositories.map((repo) => {
          const repoId = Number(repo.github_repo_id || repo.id);
          const owner = typeof repo.owner === 'object' ? repo.owner?.login : repo.owner;
          const name = repo.name;
          const fullName = repo.full_name || `${owner}/${name}`;
          const isPrivate = Boolean(repo.is_private || repo.private);
          const defaultBranch = repo.default_branch || 'main';

          const isConnected = Boolean(
            repo.registered ||
            repo.is_connected ||
            connectedRepos.some((c) => Number(c.github_repo_id || c.id) === repoId)
          );

          const isSelected = Boolean(
            selectedRepo && Number(selectedRepo.github_repo_id || selectedRepo.id) === repoId
          );

          return (
            <div
              key={repoId}
              className={`repo-mobile-card ${isSelected ? 'card-selected' : ''} ${isConnected ? 'card-connected' : ''}`}
              onClick={() => !isConnected && selectRepo(repo)}
            >
              <div className="repo-mobile-card-top">
                <div className="repo-mobile-card-title-group">
                  <span className="repo-mobile-name">{fullName}</span>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginTop: '4px' }}>
                    {isPrivate ? (
                      <span className="badge-visibility badge-private">
                        <Lock size={11} />
                        <span>Private</span>
                      </span>
                    ) : (
                      <span className="badge-visibility badge-public">
                        <Globe size={11} />
                        <span>Public</span>
                      </span>
                    )}
                    <span className="repo-branch-cell">
                      <GitBranch size={11} />
                      <span>{defaultBranch}</span>
                    </span>
                  </div>
                </div>

                {isConnected ? (
                  <span className="badge-status badge-status-active">
                    <CheckCircle2 size={12} />
                    <span>Connected</span>
                  </span>
                ) : (
                  <span className="badge-status badge-status-available">
                    <span>Available</span>
                  </span>
                )}
              </div>

              {repo.description && (
                <p className="repo-mobile-desc">{repo.description}</p>
              )}

              <div className="repo-mobile-card-actions">
                {repo.html_url && (
                  <a
                    href={repo.html_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="repo-external-link"
                    onClick={(e) => e.stopPropagation()}
                    title="View on GitHub"
                  >
                    <ExternalLink size={14} />
                    <span>GitHub</span>
                  </a>
                )}

                <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
                  {isConnected ? (
                    <>
                      <Link
                        to={`/pull-requests?repo=${repoId}`}
                        className="btn-table-prs"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (setActiveRepo) setActiveRepo(repo);
                        }}
                      >
                        <GitPullRequest size={12} />
                        <span>PRs</span>
                      </Link>
                      <button
                        type="button"
                        className="btn-repo-disconnect"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (window.confirm(`Disconnect CodeHawk from ${fullName}?`)) {
                            disconnectRepo(repoId);
                          }
                        }}
                        disabled={isConnecting}
                      >
                        Disconnect
                      </button>
                    </>
                  ) : isSelected ? (
                    <span className="badge-selected-pill">
                      <Check size={12} />
                      <span>Selected</span>
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="btn-repo-select"
                      onClick={(e) => {
                        e.stopPropagation();
                        selectRepo(repo);
                      }}
                    >
                      Select
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
