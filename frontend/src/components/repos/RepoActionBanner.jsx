import { CheckCircle2, AlertCircle, X, Shield, ArrowRight } from 'lucide-react';
import { useRepos } from '../../context/useRepos';

export default function RepoActionBanner() {
  const {
    selectedRepo,
    clearSelection,
    connectSelectedRepo,
    isConnecting,
    error,
    clearError,
    successMessage,
    clearSuccessMessage,
  } = useRepos();

  if (!selectedRepo && !error && !successMessage) {
    return null;
  }

  const owner = selectedRepo ? (typeof selectedRepo.owner === 'object' ? selectedRepo.owner?.login : selectedRepo.owner) : '';
  const name = selectedRepo ? selectedRepo.name : '';
  const fullName = selectedRepo ? (selectedRepo.full_name || `${owner}/${name}`) : '';

  return (
    <aside className="repo-action-banner" aria-label="Repository Action Confirmation">
      {/* Success banner */}
      {successMessage && (
        <div className="banner-alert banner-success" role="status">
          <CheckCircle2 size={18} className="banner-icon-success" />
          <div className="banner-text">
            <strong>Connected Successfully:</strong> {successMessage}
          </div>
          <button
            type="button"
            className="btn-banner-close"
            onClick={clearSuccessMessage}
            aria-label="Dismiss success message"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="banner-alert banner-error" role="alert">
          <AlertCircle size={18} className="banner-icon-error" />
          <div className="banner-text">
            <strong>Connection Failed:</strong> {error.message || String(error)}
          </div>
          <button
            type="button"
            className="btn-banner-close"
            onClick={clearError}
            aria-label="Dismiss error message"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Selection Confirmation Bar */}
      {selectedRepo && (
        <div className="repo-confirm-bar">
          <div className="confirm-repo-details">
            <div className="confirm-badge">Ready to Connect</div>
            <div className="confirm-name-group">
              <span className="confirm-repo-name">{fullName}</span>
              <span className="confirm-repo-desc">
                Default branch: <code>{selectedRepo.default_branch || 'main'}</code>
              </span>
            </div>
          </div>

          <div className="confirm-actions">
            <button
              type="button"
              className="btn-confirm-cancel"
              onClick={clearSelection}
              disabled={isConnecting}
            >
              Cancel
            </button>

            <button
              type="button"
              id="btn-confirm-connect-repo"
              className="btn-confirm-connect"
              onClick={connectSelectedRepo}
              disabled={isConnecting}
              aria-busy={isConnecting}
            >
              {isConnecting ? (
                <>
                  <span className="btn-spinner" aria-hidden="true" />
                  <span>Connecting to CodeHawk...</span>
                </>
              ) : (
                <>
                  <Shield size={16} />
                  <span>Connect Repository</span>
                  <ArrowRight size={14} />
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </aside>
  );
}
