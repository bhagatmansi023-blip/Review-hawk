import { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  FolderGit2,
  GitBranch,
  Globe,
  Lock,
  ExternalLink,
  CheckCircle2,
  RotateCw,
  GitPullRequest,
  AlertCircle,
} from 'lucide-react';
import { useRepos } from '../context/useRepos';
import pullRequestsService from '../services/pullRequests';
import PRTable from '../components/pullRequests/PRTable';
import PREmptyState from '../components/pullRequests/PREmptyState';
import PRSearchFilter from '../components/pullRequests/PRSearchFilter';
import PRContractModal from '../components/pullRequests/PRContractModal';

export default function RepositoryDetails() {
  const { repoId } = useParams();
  const navigate = useNavigate();
  const { connectedRepos, setActiveRepo } = useRepos();

  // Resolve the repository from context using the URL param
  const repo = useMemo(() => {
    if (!repoId || !connectedRepos || connectedRepos.length === 0) return null;
    return connectedRepos.find(
      (r) => String(r.id) === repoId || String(r.github_repo_id) === repoId
    ) || null;
  }, [repoId, connectedRepos]);

  // Set active repo when navigating to details
  useEffect(() => {
    if (repo) {
      setActiveRepo(repo);
    }
  }, [repo, setActiveRepo]);

  // Pull request state
  const [pullRequests, setPullRequests] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Search and filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [reviewFilter, setReviewFilter] = useState('all');

  // Contract modal
  const [isContractModalOpen, setIsContractModalOpen] = useState(false);

  const fetchPullRequests = useCallback(async () => {
    if (!repo) return;

    const id = repo.id || repo.github_repo_id;
    setIsLoading(true);
    setError(null);

    try {
      const response = await pullRequestsService.getPullRequests(id, {
        state: statusFilter !== 'all' ? statusFilter : undefined,
      });
      setPullRequests(response.results || []);
    } catch (err) {
      setError(err);
      setPullRequests([]);
    } finally {
      setIsLoading(false);
    }
  }, [repo, statusFilter]);

  // Initial load and re-fetch on filter or repo change
  useEffect(() => {
    let isMounted = true;
    Promise.resolve().then(() => {
      if (isMounted) {
        fetchPullRequests();
      }
    });
    return () => {
      isMounted = false;
    };
  }, [fetchPullRequests]);

  // Client-side search + review filter
  const filteredPullRequests = useMemo(() => {
    return pullRequests.filter((pr) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const title = (pr.title || '').toLowerCase();
        const number = String(pr.number || pr.id || '');
        const numberTag = `#${number}`;
        const author = (pr.author || pr.user?.login || '').toLowerCase();
        if (
          !title.includes(q) &&
          !number.includes(q) &&
          !numberTag.includes(q) &&
          !author.includes(q)
        ) {
          return false;
        }
      }

      if (statusFilter !== 'all') {
        const prState = (pr.state || '').toLowerCase();
        if (prState !== statusFilter) return false;
      }

      if (reviewFilter !== 'all') {
        const review =
          pr.latest_review || (typeof pr.review === 'object' ? pr.review : null);
        const reviewStatus = (review?.status || pr.review_status || '').toLowerCase();
        if (reviewFilter === 'none') {
          if (reviewStatus && reviewStatus !== 'none') return false;
        } else {
          if (reviewStatus !== reviewFilter) return false;
        }
      }

      return true;
    });
  }, [pullRequests, searchQuery, statusFilter, reviewFilter]);

  const handleClearFilters = () => {
    setSearchQuery('');
    setStatusFilter('all');
    setReviewFilter('all');
  };

  // Repo metadata
  const fullName = repo?.full_name || (repo ? `${repo.owner}/${repo.name}` : null);
  const isPrivate = Boolean(repo?.is_private || repo?.private);
  const defaultBranch = repo?.default_branch || 'main';
  const htmlUrl = repo?.html_url;

  // ── Repository not found in context ──────────────────────────────────────
  if (!repo && connectedRepos.length > 0) {
    return (
      <div className="repo-page-container">
        <div style={{ marginBottom: '20px' }}>
          <Link
            to="/repositories"
            className="btn-text-action"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
          >
            <ArrowLeft size={16} />
            <span>Back to Repositories</span>
          </Link>
        </div>
        <div className="repo-empty-card" role="status">
          <div className="empty-icon-box icon-warning">
            <AlertCircle size={28} />
          </div>
          <h3 className="empty-title">Repository Not Found</h3>
          <p className="empty-desc">
            This repository is not in your connected list, or it may have been disconnected.
          </p>
          <Link to="/repositories" className="btn-primary">
            Go to Repositories
          </Link>
        </div>
      </div>
    );
  }

  // ── Loading repos context (repo not resolved yet) ─────────────────────────
  if (!repo) {
    return (
      <div className="repo-page-container">
        <div className="repo-loading-card" role="status" aria-live="polite">
          <div className="loading-spinner-ring" aria-hidden="true" />
          <h3 className="loading-title">Loading repository...</h3>
          <p className="loading-subtitle">Resolving repository details.</p>
        </div>
      </div>
    );
  }

  const renderPRContent = () => {
    if (isLoading) {
      return <PREmptyState type="loading" />;
    }

    if (error && error.isMissingEndpoint) {
      return (
        <PREmptyState
          type="missing_endpoint"
          activeRepo={repo}
          error={error}
          onRetry={fetchPullRequests}
          onOpenContract={() => setIsContractModalOpen(true)}
        />
      );
    }

    if (error && error.isUnauthorized) {
      return <PREmptyState type="unauthorized" error={error} />;
    }

    if (error && error.isForbidden) {
      return (
        <PREmptyState
          type="forbidden"
          activeRepo={repo}
          error={error}
          onRetry={fetchPullRequests}
        />
      );
    }

    if (error) {
      return (
        <PREmptyState
          type="request_failed"
          activeRepo={repo}
          error={error}
          onRetry={fetchPullRequests}
        />
      );
    }

    if (pullRequests.length === 0) {
      return <PREmptyState type="no_prs" activeRepo={repo} />;
    }

    if (filteredPullRequests.length === 0) {
      return (
        <PREmptyState
          type="search_no_match"
          onClearFilters={handleClearFilters}
        />
      );
    }

    return <PRTable pullRequests={filteredPullRequests} activeRepo={repo} />;
  };

  return (
    <div className="repo-page-container" aria-label="Repository Details">
      {/* ── Back navigation ──────────────────────────────────────────────── */}
      <div className="rd-nav-bar">
        <Link
          to="/repositories"
          className="btn-text-action"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          <ArrowLeft size={16} />
          <span>Back to Repositories</span>
        </Link>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button
            type="button"
            className="btn-repo-refresh"
            onClick={fetchPullRequests}
            disabled={isLoading}
            title="Refresh pull requests"
            aria-label="Refresh pull requests"
          >
            <RotateCw size={13} className={isLoading ? 'spin-icon' : ''} />
            <span>Refresh</span>
          </button>

          {htmlUrl && (
            <a
              href={htmlUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            >
              <span>Open on GitHub</span>
              <ExternalLink size={14} />
            </a>
          )}
        </div>
      </div>

      {/* ── Repository Header Card ────────────────────────────────────────── */}
      <div className="rd-header-card">
        <div className="rd-header-top">
          <div className="rd-icon-wrap">
            <FolderGit2 size={28} />
          </div>
          <div className="rd-header-info">
            <h1 className="rd-repo-name">{fullName}</h1>
            {repo.description && (
              <p className="rd-repo-desc">{repo.description}</p>
            )}
          </div>
        </div>

        <div className="rd-meta-strip">
          {/* Visibility */}
          <div className="rd-meta-item">
            <span className="rd-meta-label">Visibility</span>
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
          </div>

          {/* Default Branch */}
          <div className="rd-meta-item">
            <span className="rd-meta-label">Default Branch</span>
            <span className="repo-branch-cell">
              <GitBranch size={13} />
              <span>{defaultBranch}</span>
            </span>
          </div>

          {/* Connection Status */}
          <div className="rd-meta-item">
            <span className="rd-meta-label">CodeHawk Status</span>
            <span className="badge-status badge-status-active">
              <CheckCircle2 size={13} />
              <span>Connected</span>
            </span>
          </div>

          {/* GitHub Link */}
          {htmlUrl && (
            <div className="rd-meta-item">
              <span className="rd-meta-label">GitHub</span>
              <a
                href={htmlUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="rd-github-link"
                title={`Open ${fullName} on GitHub`}
              >
                <span>{fullName}</span>
                <ExternalLink size={12} />
              </a>
            </div>
          )}

          {/* Language if available */}
          {repo.language && (
            <div className="rd-meta-item">
              <span className="rd-meta-label">Language</span>
              <span className="repo-language-tag">
                <span className="repo-lang-dot" />
                <span>{repo.language}</span>
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ── Pull Requests Section ─────────────────────────────────────────── */}
      <section className="rd-pr-section" aria-label="Pull Requests">
        <div className="rd-section-heading">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <GitPullRequest size={20} color="var(--accent-primary)" />
            <h2 className="rd-section-title">Pull Requests</h2>
            {!isLoading && !error && pullRequests.length > 0 && (
              <span className="rd-pr-count-badge">{pullRequests.length}</span>
            )}
          </div>
          <Link
            to={`/pull-requests?repo=${repo.id || repo.github_repo_id}`}
            className="btn-secondary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.84rem' }}
          >
            <span>Full PR View</span>
            <ExternalLink size={13} />
          </Link>
        </div>

        {/* Search & Filters — only when PRs are loaded */}
        {!isLoading && !error && pullRequests.length > 0 && (
          <PRSearchFilter
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            reviewFilter={reviewFilter}
            onReviewFilterChange={setReviewFilter}
            totalCount={pullRequests.length}
            filteredCount={filteredPullRequests.length}
          />
        )}

        <div className="repo-list-section">
          {renderPRContent()}
        </div>
      </section>

      {/* Contract Modal */}
      <PRContractModal
        isOpen={isContractModalOpen}
        onClose={() => setIsContractModalOpen(false)}
      />
    </div>
  );
}

