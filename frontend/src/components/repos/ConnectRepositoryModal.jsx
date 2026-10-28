import { Plus, X, GitBranch, ChevronDown, ChevronUp, ExternalLink, FolderGit2, CheckCircle2, Info } from 'lucide-react';
import { useState } from 'react';
import { useRepos } from '../../context/useRepos';
import { useAuth } from '../../context/useAuth';

/**
 * ConnectRepositoryModal
 *
 * Explains the repository connection process and lets the user browse and
 * select a repository for connection. Uses real data from RepoContext.
 *
 * How connection works:
 * 1. User clicks "Connect Repository" in the page header.
 * 2. This modal opens and shows all GitHub repositories returned by
 *    GET /api/repos/ (already fetched in RepoContext).
 * 3. The user selects one (calls selectRepo) and closes the modal.
 * 4. The selection confirmation banner (RepoActionBanner) slides in below
 *    the header, where the user clicks "Connect Repository" to confirm.
 * 5. That fires POST /api/repos/register/ with the selected repo details.
 */
export default function ConnectRepositoryModal() {
  const { isConnectModalOpen, setIsConnectModalOpen, repositories, connectedRepos, selectRepo, isLoading, fetchRepositories } = useRepos();
  const { isAuthenticated } = useAuth();
  const [searchTerm, setSearchTerm] = useState('');
  const [showAll, setShowAll] = useState(false);

  if (!isConnectModalOpen) return null;

  const filtered = repositories.filter((repo) => {
    if (!searchTerm.trim()) return true;
    const q = searchTerm.toLowerCase();
    const owner = typeof repo.owner === 'object' ? repo.owner?.login || '' : repo.owner || '';
    const full = (repo.full_name || `${owner}/${repo.name}`).toLowerCase();
    return full.includes(q) || owner.toLowerCase().includes(q);
  });

  const unconnected = filtered.filter((r) => {
    const rId = Number(r.github_repo_id || r.id);
    return !r.registered && !r.is_connected && !connectedRepos.some((c) => Number(c.github_repo_id || c.id) === rId);
  });

  const LIST_LIMIT = 8;
  const displayList = showAll ? unconnected : unconnected.slice(0, LIST_LIMIT);

  const handleSelect = (repo) => {
    selectRepo(repo);
    setIsConnectModalOpen(false);
    setSearchTerm('');
    setShowAll(false);
  };

  return (
    <div
      className="modal-overlay"
      onClick={() => { setIsConnectModalOpen(false); setSearchTerm(''); setShowAll(false); }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="connect-repo-modal-title"
    >
      <div
        className="modal-content connect-repo-modal"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <div className="modal-title" id="connect-repo-modal-title">
            <FolderGit2 size={22} color="var(--accent-primary)" />
            <span>Connect a Repository</span>
          </div>
          <button
            className="modal-close-btn"
            onClick={() => { setIsConnectModalOpen(false); setSearchTerm(''); setShowAll(false); }}
            aria-label="Close modal"
          >
            <X size={20} />
          </button>
        </div>

        {/* Explanation */}
        <aside className="connect-modal-info" role="note">
          <Info size={16} />
          <div>
            <strong>How it works:</strong> Selecting a repository enables CodeHawk to install a GitHub webhook
            on that repo. Incoming pull request events are automatically forwarded to the CodeHawk AI review engine.
            Your GitHub OAuth token is never stored in the frontend — all webhook registration is handled securely
            by the Django backend via <code>POST /api/repos/register/</code>.
          </div>
        </aside>

        {/* Already connected summary */}
        {connectedRepos.length > 0 && (
          <div className="connect-modal-connected-summary">
            <CheckCircle2 size={15} color="#22c55e" />
            <span>
              <strong>{connectedRepos.length}</strong> {connectedRepos.length === 1 ? 'repository is' : 'repositories are'} already connected.{' '}
              You can manage them in the table below the search bar.
            </span>
          </div>
        )}

        {/* Auth gate */}
        {!isAuthenticated && (
          <div className="connect-modal-auth-notice">
            Sign in with GitHub first to view and connect your repositories.
          </div>
        )}

        {/* Search */}
        {isAuthenticated && repositories.length > 0 && (
          <div className="connect-modal-search-wrapper">
            <input
              type="text"
              className="repo-search-input"
              placeholder="Search repositories by name or owner…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              aria-label="Filter repositories"
              autoFocus
            />
          </div>
        )}

        {/* List */}
        {isAuthenticated && (
          <div className="connect-modal-list" role="listbox" aria-label="Available repositories">
            {isLoading && (
              <div className="connect-modal-loading">
                <div className="loading-spinner-ring" style={{ width: '32px', height: '32px' }} />
                <span>Loading repositories…</span>
              </div>
            )}

            {!isLoading && repositories.length === 0 && (
              <div className="connect-modal-empty">
                <FolderGit2 size={32} />
                <p>No repositories found for your account.</p>
                <button type="button" className="btn-secondary" onClick={fetchRepositories}>
                  Refresh
                </button>
              </div>
            )}

            {!isLoading && repositories.length > 0 && unconnected.length === 0 && (
              <div className="connect-modal-empty">
                <CheckCircle2 size={32} color="#22c55e" />
                <p>
                  {searchTerm
                    ? 'No available repositories match your search.'
                    : 'All your repositories are already connected to CodeHawk!'}
                </p>
              </div>
            )}

            {!isLoading && displayList.map((repo) => {
              const rId = Number(repo.github_repo_id || repo.id);
              const owner = typeof repo.owner === 'object' ? repo.owner?.login : repo.owner;
              const fullName = repo.full_name || `${owner}/${repo.name}`;
              const isPrivate = Boolean(repo.is_private || repo.private);

              return (
                <div
                  key={rId}
                  className="connect-modal-repo-row"
                  role="option"
                  aria-selected={false}
                  tabIndex={0}
                  onClick={() => handleSelect(repo)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSelect(repo); } }}
                >
                  <div className="connect-modal-repo-info">
                    <span className="connect-modal-repo-name">{fullName}</span>
                    <div className="connect-modal-repo-meta">
                      <span className={`badge-visibility ${isPrivate ? 'badge-private' : 'badge-public'}`} style={{ fontSize: '0.72rem', padding: '2px 7px' }}>
                        {isPrivate ? 'Private' : 'Public'}
                      </span>
                      {repo.default_branch && (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                          <GitBranch size={11} />
                          {repo.default_branch}
                        </span>
                      )}
                      {repo.html_url && (
                        <a
                          href={repo.html_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="repo-external-link"
                          title="View on GitHub"
                        >
                          <ExternalLink size={11} />
                        </a>
                      )}
                    </div>
                    {repo.description && (
                      <p className="connect-modal-repo-desc">{repo.description}</p>
                    )}
                  </div>
                  <button
                    type="button"
                    className="btn-repo-select"
                    onClick={(e) => { e.stopPropagation(); handleSelect(repo); }}
                    aria-label={`Select ${fullName}`}
                  >
                    <Plus size={13} />
                    <span>Select</span>
                  </button>
                </div>
              );
            })}

            {!isLoading && unconnected.length > LIST_LIMIT && (
              <button
                type="button"
                className="connect-modal-show-more"
                onClick={() => setShowAll((v) => !v)}
              >
                {showAll
                  ? <><ChevronUp size={14} /> Show fewer</>
                  : <><ChevronDown size={14} /> Show {unconnected.length - LIST_LIMIT} more repositories</>
                }
              </button>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="modal-footer" style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            After selecting, confirm the connection in the banner that appears on the page.
          </span>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => { setIsConnectModalOpen(false); setSearchTerm(''); setShowAll(false); }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
