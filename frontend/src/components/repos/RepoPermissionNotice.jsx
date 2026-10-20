import { ShieldAlert, ExternalLink, X, Info } from 'lucide-react';
import { useRepos } from '../../context/useRepos';

export default function RepoPermissionNotice() {
  const { isPermissionModalOpen, setIsPermissionModalOpen } = useRepos();

  if (!isPermissionModalOpen) return null;

  return (
    <div className="modal-overlay" onClick={() => setIsPermissionModalOpen(false)} role="dialog" aria-modal="true" aria-labelledby="perm-modal-title">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title" id="perm-modal-title">
            <ShieldAlert size={22} color="#38bdf8" />
            <span>GitHub Repository Permissions & Scopes</span>
          </div>
          <button
            className="modal-close-btn"
            onClick={() => setIsPermissionModalOpen(false)}
            aria-label="Close permissions modal"
          >
            <X size={20} />
          </button>
        </div>

        <p style={{ fontSize: '0.92rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          GitHub OAuth login and repository access are distinct steps. CodeHawk requests minimal permissions necessary to read PR diffs and post review comments.
        </p>

        <div className="contract-code-block">
{`# Required OAuth Scopes (configured in Django settings)
1. "read:user", "user:email"
   -> Authenticates developer identity and fetches user profile.

2. "repo" (or GitHub App installation permissions)
   -> Required to read pull request diffs and publish automated code review feedback.
   -> Access can be limited to select repositories during GitHub authorization.`}
        </div>

        <aside className="backend-status-card">
          <div className="status-header">
            <span>Organization Repository Access</span>
            <span className="status-tag">
              <Info size={12} />
              <span>GitHub Note</span>
            </span>
          </div>
          <p className="status-text">
            If your repository belongs to a GitHub Organization, organization owners may need to approve third-party application access under <strong>Organization Settings → Third-party Access</strong>.
          </p>
        </aside>

        <div className="modal-footer">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => setIsPermissionModalOpen(false)}
          >
            Close
          </button>
          <a
            href="https://github.com/settings/connections/applications"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
          >
            <span>Manage GitHub Permissions</span>
            <ExternalLink size={14} />
          </a>
        </div>
      </div>
    </div>
  );
}
