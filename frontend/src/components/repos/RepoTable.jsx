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
      <div className="repo-table-wrapper">
        <table className="repo-table">
          <thead>
            <tr>
              <th scope="col" style={{ width: '40%' }}>Repository</th>
              <th scope="col" style={{ width: '15%' }}>Visibility</th>
              <th scope="col" style={{ width: '15%' }}>Default Branch</th>
              <th scope="col" style={{ width: '15%' }}>Bot Status</th>
              <th scope="col" style={{ width: '15%', textAlign: 'right' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredRepositories.map((repo) => {
              const repoId = repo.github_repo_id || repo.id;
              const owner = typeof repo.owner === 'object' ? repo.owner?.login : repo.owner;
              const name = repo.name;
              const fullName = repo.full_name || `${owner}/${name}`;
              const isPrivate = Boolean(repo.is_private || repo.private);
              const defaultBranch = repo.default_branch || 'main';

              const isConnected = Boolean(
                repo.is_connected ||
                connectedRepos.some((c) => (c.github_repo_id || c.id) === repoId)
              );

              const isSelected = Boolean(
                selectedRepo && (selectedRepo.github_repo_id || selectedRepo.id) === repoId
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

                  {/* Bot Status */}
                  <td>
                    {isConnected ? (
                      <span className="badge-status badge-status-active">
                        <CheckCircle2 size={13} />
                        <span>Connected</span>
                      </span>
                    ) : (
                      <span className="badge-status badge-status-available">
                        <span>Available</span>
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
    </div>
  );
}
