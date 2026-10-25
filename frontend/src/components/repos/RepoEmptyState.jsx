import { Link } from 'react-router-dom';
import { 
  FolderGit2, 
  Search, 
  RotateCw, 
  LogIn, 
  FileCode, 
  AlertCircle 
} from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import { useRepos } from '../../context/useRepos';

export default function RepoEmptyState({ type = 'no_repos' }) {
  const { isAuthenticated } = useAuth();
  const {
    searchQuery,
    setSearchQuery,
    setFilterVisibility,
    setFilterConnected,
    fetchRepositories,
    setIsContractModalOpen,
    error,
    isLoading,
  } = useRepos();

  // State 1: Unauthenticated
  if (!isAuthenticated) {
    return (
      <div className="repo-empty-card" role="status">
        <div className="empty-icon-box">
          <LogIn size={28} />
        </div>
        <h3 className="empty-title">GitHub Account Not Connected</h3>
        <p className="empty-desc">
          Sign in with your GitHub account to access your repositories and configure CodeHawk automated reviews.
        </p>
        <Link to="/login" className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
          <LogIn size={16} />
          <span>Sign In with GitHub</span>
        </Link>
      </div>
    );
  }

  // State 2: Loading State
  if (isLoading) {
    return (
      <div className="repo-loading-card" role="status" aria-live="polite">
        <div className="loading-spinner-ring" aria-hidden="true" />
        <h3 className="loading-title">Fetching Repositories...</h3>
        <p className="loading-subtitle">
          Querying CodeHawk backend for synchronized GitHub repositories.
        </p>
      </div>
    );
  }

  // State 3: Error / API Unavailable State (with Retry action)
  if (type === 'error' || error) {
    const isMissingEndpoint = error?.isMissingEndpoint || error?.status === 404;
    return (
      <div className="repo-empty-card repo-error-card" role="alert">
        <div className="empty-icon-box" style={{ background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>
          <AlertCircle size={28} />
        </div>
        <h3 className="empty-title">
          {isMissingEndpoint ? 'Backend Repository Endpoint Pending' : 'Unable to Load Repositories'}
        </h3>
        <p className="empty-desc">
          {error?.message ||
            'Could not retrieve repositories from the backend server. Ensure the Django server is running and accessible at http://localhost:8000.'}
        </p>
        <div className="empty-actions" style={{ display: 'flex', gap: '10px', justifyContent: 'center', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn-primary"
            onClick={fetchRepositories}
            disabled={isLoading}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
          >
            <RotateCw size={14} className={isLoading ? 'spin-icon' : ''} />
            <span>Retry Connection</span>
          </button>

          {error?.status === 401 && (
            <Link to="/login" className="btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
              <LogIn size={14} />
              <span>Sign In with GitHub</span>
            </Link>
          )}

          {isMissingEndpoint && (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setIsContractModalOpen(true)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
            >
              <FileCode size={14} />
              <span>View API Contract</span>
            </button>
          )}
        </div>
      </div>
    );
  }

  // State 4: Search with no matching results
  if (type === 'search_no_match') {
    return (
      <div className="repo-empty-card" role="status">
        <div className="empty-icon-box">
          <Search size={28} />
        </div>
        <h3 className="empty-title">No matching repositories found</h3>
        <p className="empty-desc">
          No repositories match your search query <strong>&quot;{searchQuery}&quot;</strong>. Try adjusting your query or reset filters.
        </p>
        <div className="empty-actions">
          <button
            type="button"
            className="btn-primary"
            onClick={() => {
              setSearchQuery('');
              setFilterVisibility('all');
              setFilterConnected('all');
            }}
          >
            <span>Reset Search & Filters</span>
          </button>
        </div>
      </div>
    );
  }

  // State 5: No repositories returned from GitHub
  return (
    <div className="repo-empty-card" role="status">
      <div className="empty-icon-box">
        <FolderGit2 size={28} />
      </div>
      <h3 className="empty-title">No repositories found</h3>
      <p className="empty-desc">
        No GitHub repositories were returned for your account. Ensure you have created repositories on GitHub or granted repository access to CodeHawk.
      </p>
      <div className="empty-actions" style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
        <button
          type="button"
          className="btn-secondary"
          onClick={fetchRepositories}
          disabled={isLoading}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
        >
          <RotateCw size={14} className={isLoading ? 'spin-icon' : ''} />
          <span>Refresh</span>
        </button>
        <a
          href="https://github.com/new"
          target="_blank"
          rel="noopener noreferrer"
          className="btn-primary"
        >
          Create Repository on GitHub
        </a>
      </div>
    </div>
  );
}
