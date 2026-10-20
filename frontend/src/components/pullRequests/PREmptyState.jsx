import { Link } from 'react-router-dom';
import { 
  GitPullRequest, 
  FolderGit2, 
  Search, 
  RotateCw, 
  LogIn, 
  FileCode, 
  AlertCircle, 
  ShieldAlert,
  ArrowRight,
  ExternalLink
} from 'lucide-react';
import repoService from '../../services/repos';

export default function PREmptyState({
  type = 'no_prs',
  activeRepo = null,
  error = null,
  onRetry = null,
  onClearFilters = null,
  onOpenContract = null,
}) {
  // State 1: No repository connected or selected
  if (type === 'no_repo_selected') {
    return (
      <div className="repo-empty-card" role="status">
        <div className="empty-icon-box">
          <FolderGit2 size={28} />
        </div>
        <h3 className="empty-title">No Repository Selected</h3>
        <p className="empty-desc">
          To view and track pull requests and their automated code reviews, choose or connect a GitHub repository first.
        </p>
        <Link to="/repositories" className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
          <span>Connect a Repository</span>
          <ArrowRight size={16} />
        </Link>
      </div>
    );
  }

  // State 2: Pull requests loading
  if (type === 'loading') {
    return (
      <div className="repo-loading-card" role="status" aria-live="polite">
        <div className="loading-spinner-ring" aria-hidden="true" />
        <h3 className="loading-title">Fetching Pull Requests...</h3>
        <p className="loading-subtitle">
          Synchronizing pull requests from CodeHawk backend services.
        </p>
      </div>
    );
  }

  // State 7: Authentication Expired
  if (type === 'unauthorized' || (error && error.isUnauthorized)) {
    return (
      <div className="repo-empty-card repo-missing-endpoint" role="status">
        <div className="empty-icon-box icon-warning">
          <LogIn size={28} />
        </div>
        <h3 className="empty-title">Authentication Session Expired</h3>
        <p className="empty-desc">
          Your GitHub authentication session has expired or is invalid. Please sign in again to view pull requests.
        </p>
        <Link to="/login" className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
          <LogIn size={15} />
          <span>Sign In with GitHub</span>
        </Link>
      </div>
    );
  }

  // State 8: Forbidden / Lacks repository access
  if (type === 'forbidden' || (error && error.isForbidden)) {
    return (
      <div className="repo-empty-card repo-missing-endpoint" role="status">
        <div className="empty-icon-box icon-warning">
          <ShieldAlert size={28} />
        </div>
        <h3 className="empty-title">Insufficient Repository Permissions</h3>
        <p className="empty-desc">
          You do not have access to view pull requests for this repository. Ensure your GitHub account has read permissions.
        </p>
        <div className="empty-actions">
          {onRetry && (
            <button type="button" className="btn-secondary" onClick={onRetry}>
              <RotateCw size={14} />
              <span>Retry</span>
            </button>
          )}
          <a
            href={repoService.getGitHubPermissionsUrl()}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
          >
            <span>Review GitHub Permissions</span>
            <ExternalLink size={14} />
          </a>
        </div>
      </div>
    );
  }

  // Missing Endpoint (Backend in progress)
  if (type === 'missing_endpoint' || (error && error.isMissingEndpoint)) {
    return (
      <div className="repo-empty-card repo-missing-endpoint" role="status">
        <div className="empty-icon-box icon-warning">
          <AlertCircle size={28} />
        </div>
        <h3 className="empty-title">Pull Request Endpoints Pending</h3>
        <p className="empty-desc">
          The Django REST Framework backend does not yet serve <code>GET /api/repos/{activeRepo ? (activeRepo.id || activeRepo.github_repo_id) : '{repo_id}'}/pulls/</code>.
          Our team is developing backend and frontend in parallel. You can inspect the required API contract specification below.
        </p>
        <div className="empty-actions">
          {onRetry && (
            <button type="button" className="btn-secondary" onClick={onRetry}>
              <RotateCw size={14} />
              <span>Retry Fetch</span>
            </button>
          )}
          {onOpenContract && (
            <button type="button" className="btn-primary" onClick={onOpenContract}>
              <FileCode size={14} />
              <span>View Required API Contract</span>
            </button>
          )}
        </div>
      </div>
    );
  }

  // State 6: General API Request Failure
  if (type === 'request_failed' || error) {
    return (
      <div className="repo-empty-card repo-missing-endpoint" role="status">
        <div className="empty-icon-box icon-warning">
          <AlertCircle size={28} />
        </div>
        <h3 className="empty-title">Failed to Load Pull Requests</h3>
        <p className="empty-desc">
          {error?.message || 'Unable to communicate with the CodeHawk API backend. Please check your network connection.'}
        </p>
        <div className="empty-actions">
          {onRetry && (
            <button type="button" className="btn-primary" onClick={onRetry}>
              <RotateCw size={14} />
              <span>Retry Request</span>
            </button>
          )}
          <Link to="/repositories" className="btn-secondary">
            Switch Repository
          </Link>
        </div>
      </div>
    );
  }

  // State 5: Search & Filter with no matches
  if (type === 'search_no_match') {
    return (
      <div className="repo-empty-card" role="status">
        <div className="empty-icon-box">
          <Search size={28} />
        </div>
        <h3 className="empty-title">No matching pull requests found</h3>
        <p className="empty-desc">
          No pull requests matched your active search query or filter selections. Try adjusting or resetting your filters.
        </p>
        {onClearFilters && (
          <button type="button" className="btn-primary" onClick={onClearFilters}>
            <span>Reset All Filters</span>
          </button>
        )}
      </div>
    );
  }

  // State 9: Pull Request Details Not Found (404)
  if (type === 'pr_not_found') {
    return (
      <div className="repo-empty-card" role="status">
        <div className="empty-icon-box icon-warning">
          <GitPullRequest size={28} />
        </div>
        <h3 className="empty-title">Pull Request Not Found</h3>
        <p className="empty-desc">
          The requested pull request could not be found or has been removed from CodeHawk.
        </p>
        <Link to="/pull-requests" className="btn-primary">
          <span>Return to Pull Requests</span>
        </Link>
      </div>
    );
  }

  // State 4: Connected Repository has zero pull requests
  const repoName = activeRepo?.full_name || `${activeRepo?.owner}/${activeRepo?.name}` || 'this repository';
  return (
    <div className="repo-empty-card" role="status">
      <div className="empty-icon-box">
        <GitPullRequest size={28} />
      </div>
      <h3 className="empty-title">No pull requests available</h3>
      <p className="empty-desc">
        There are currently no pull requests recorded for <strong>{repoName}</strong>.
        When new pull requests are opened on GitHub, they will appear here automatically for review.
      </p>
      {activeRepo?.html_url && (
        <a
          href={`${activeRepo.html_url}/pulls`}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-secondary"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
        >
          <span>View on GitHub</span>
          <ExternalLink size={14} />
        </a>
      )}
    </div>
  );
}
