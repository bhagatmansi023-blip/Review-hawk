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

  // Missing Endpoint or Backend Error State
  if (error && error.isMissingEndpoint) {
    return (
      <div className="repo-empty-card repo-missing-endpoint" role="status">
        <div className="empty-icon-box icon-warning">
          <AlertCircle size={28} />
        </div>
        <h3 className="empty-title">Backend Repository Endpoints Pending</h3>
        <p className="empty-desc">
          The Django REST Framework backend does not yet serve <code>GET /api/repos/</code>.
          Our team is developing the backend and frontend together. You can inspect the required endpoint specifications below.
        </p>
        <div className="empty-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={fetchRepositories}
          >
            <RotateCw size={14} />
            <span>Retry Fetch</span>
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={() => setIsContractModalOpen(true)}
          >
            <FileCode size={14} />
            <span>View Required API Contract</span>
          </button>
        </div>
      </div>
    );
  }

  // State 6: Search with no matching results
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

  // State 4: No repositories available
  return (
    <div className="repo-empty-card" role="status">
      <div className="empty-icon-box">
        <FolderGit2 size={28} />
      </div>
      <h3 className="empty-title">No repositories found</h3>
      <p className="empty-desc">
        No GitHub repositories were returned for your account. Ensure you have created repositories on GitHub or granted repository access to CodeHawk.
      </p>
      <div className="empty-actions">
        <button
          type="button"
          className="btn-secondary"
          onClick={fetchRepositories}
        >
          <RotateCw size={14} />
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
