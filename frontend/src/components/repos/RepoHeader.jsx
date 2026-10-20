import { Link } from 'react-router-dom';
import { LayoutDashboard, CheckCircle2, AlertTriangle, FileCode, Shield } from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import { useRepos } from '../../context/useRepos';

export default function RepoHeader() {
  const { user, isAuthenticated } = useAuth();
  const { setIsContractModalOpen, setIsPermissionModalOpen } = useRepos();

  return (
    <div className="repo-page-header">
      <div className="repo-header-top">
        <div className="repo-breadcrumbs">
          <Link to="/dashboard" className="breadcrumb-link">
            <LayoutDashboard size={14} />
            <span>Dashboard</span>
          </Link>
          <span className="breadcrumb-separator">/</span>
          <span className="breadcrumb-current">Repositories</span>
        </div>

        <div className="repo-header-actions">
          <button
            type="button"
            className="btn-header-secondary"
            onClick={() => setIsPermissionModalOpen(true)}
            title="View GitHub repository permissions"
          >
            <Shield size={14} />
            <span>Permissions</span>
          </button>

          <button
            type="button"
            className="btn-header-secondary"
            onClick={() => setIsContractModalOpen(true)}
            title="View Django REST Framework endpoint contract"
          >
            <FileCode size={14} />
            <span>API Contract</span>
          </button>

          <Link to="/dashboard" className="btn-header-primary">
            <span>Return to Dashboard</span>
          </Link>
        </div>
      </div>

      <div className="repo-header-main">
        <div className="repo-title-group">
          <h1 className="repo-page-title">Connect a Repository</h1>
          <p className="repo-page-description">
            Choose a GitHub repository to enable automated pull request reviews. CodeHawk will analyze incoming diffs for bugs, security concerns, and code quality.
          </p>
        </div>

        {/* Real GitHub Account Connection Status */}
        <div className="repo-connection-badge">
          {isAuthenticated ? (
            <div className="badge-connected">
              <span className="badge-dot-green" />
              <CheckCircle2 size={15} />
              <span className="badge-text">
                GitHub Connected: <strong>@{user?.username || user?.email || 'authenticated'}</strong>
              </span>
            </div>
          ) : (
            <div className="badge-disconnected">
              <AlertTriangle size={15} />
              <span className="badge-text">GitHub Account Not Connected</span>
              <Link to="/login" className="badge-link">
                Sign In
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
