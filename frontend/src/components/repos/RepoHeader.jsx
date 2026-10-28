import { Link } from 'react-router-dom';
import { LayoutDashboard, CheckCircle2, AlertTriangle, FileCode, Shield, Plus, FolderGit2 } from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import { useRepos } from '../../context/useRepos';

export default function RepoHeader() {
  const { user, isAuthenticated } = useAuth();
  const { setIsContractModalOpen, setIsPermissionModalOpen, setIsConnectModalOpen } = useRepos();

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

          <Link to="/dashboard" className="btn-header-secondary">
            <LayoutDashboard size={14} />
            <span>Dashboard</span>
          </Link>

          <button
            type="button"
            id="btn-connect-repository"
            className="btn-header-primary"
            onClick={() => setIsConnectModalOpen(true)}
            title="Connect a GitHub repository to CodeHawk"
          >
            <Plus size={14} />
            <span>Connect Repository</span>
          </button>
        </div>
      </div>

      <div className="repo-header-main">
        <div className="repo-title-group">
          <h1 className="repo-page-title">
            <FolderGit2 size={28} className="repo-title-icon" style={{ display: 'inline', verticalAlign: 'middle', marginRight: '10px', color: 'var(--accent-primary)' }} />
            Repositories
          </h1>
          <p className="repo-page-description">
            Connect your GitHub repositories to enable automated pull request code reviews. Select any repository below to start monitoring, or click <strong>Connect Repository</strong> to learn about the connection process.
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
