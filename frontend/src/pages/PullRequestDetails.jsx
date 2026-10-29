import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  ArrowLeft, 
  GitPullRequest, 
  ExternalLink, 
  FolderGit2, 
  GitBranch, 
  GitCommit, 
  Clock, 
  CheckCircle2, 
  AlertCircle, 
  User as UserIcon, 
  Calendar, 
  ShieldCheck, 
  Bot,
  RotateCw
} from 'lucide-react';
import { useRepos } from '../context/useRepos';
import pullRequestsService from '../services/pullRequests';
import PREmptyState from '../components/pullRequests/PREmptyState';
import PRContractModal from '../components/pullRequests/PRContractModal';
import HealthCard from '../components/reviews/HealthCard';
import FindingsPanel from '../components/reviews/FindingsPanel';

export default function PullRequestDetails() {
  const { id } = useParams();
  const { activeRepo, connectedRepos } = useRepos();

  const [pullRequest, setPullRequest] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isContractModalOpen, setIsContractModalOpen] = useState(false);

  const fetchDetails = useCallback(async () => {
    if (!id) return;
    setIsLoading(true);
    setError(null);

    const repoId = activeRepo ? (activeRepo.id || activeRepo.github_repo_id) : null;

    try {
      const data = await pullRequestsService.getPullRequestDetails(id, repoId);
      setPullRequest(data);
    } catch (err) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  }, [id, activeRepo]);

  useEffect(() => {
    let isMounted = true;
    Promise.resolve().then(() => {
      if (isMounted) {
        fetchDetails();
      }
    });
    return () => {
      isMounted = false;
    };
  }, [fetchDetails]);

  const formatDate = (isoString) => {
    if (!isoString) return '—';
    try {
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return '—';
      return new Intl.DateTimeFormat('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: 'numeric',
        hour12: true,
      }).format(date);
    } catch {
      return '—';
    }
  };

  const getStatusBadge = (state) => {
    const s = (state || '').toLowerCase();
    if (s === 'open') {
      return (
        <span className="badge-visibility badge-public" style={{ backgroundColor: 'rgba(34, 197, 94, 0.12)', color: '#22c55e', borderColor: 'rgba(34, 197, 94, 0.3)', padding: '4px 10px' }}>
          <span className="badge-dot-green" />
          <span>Open</span>
        </span>
      );
    }
    if (s === 'merged') {
      return (
        <span className="badge-visibility badge-private" style={{ backgroundColor: 'rgba(168, 85, 247, 0.12)', color: '#a855f7', borderColor: 'rgba(168, 85, 247, 0.3)', padding: '4px 10px' }}>
          <GitPullRequest size={13} />
          <span>Merged</span>
        </span>
      );
    }
    if (s === 'closed') {
      return (
        <span className="badge-visibility" style={{ backgroundColor: 'rgba(239, 68, 68, 0.12)', color: '#ef4444', borderColor: 'rgba(239, 68, 68, 0.3)', padding: '4px 10px' }}>
          <span>Closed</span>
        </span>
      );
    }
    return (
      <span className="badge-visibility" style={{ padding: '4px 10px' }}>
        <span>{state || '—'}</span>
      </span>
    );
  };

  // State: Loading
  if (isLoading) {
    return (
      <div className="pr-details-container">
        <div style={{ marginBottom: '20px' }}>
          <Link to="/pull-requests" className="btn-text-action" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <ArrowLeft size={16} />
            <span>Back to Pull Requests</span>
          </Link>
        </div>
        <PREmptyState type="loading" />
      </div>
    );
  }

  // State: Error or Missing Endpoint
  if (error) {
    return (
      <div className="pr-details-container">
        <div style={{ marginBottom: '20px' }}>
          <Link to="/pull-requests" className="btn-text-action" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <ArrowLeft size={16} />
            <span>Back to Pull Requests</span>
          </Link>
        </div>

        {error.isNotFound ? (
          <PREmptyState type="pr_not_found" />
        ) : error.isMissingEndpoint ? (
          <PREmptyState
            type="missing_endpoint"
            activeRepo={activeRepo}
            error={error}
            onRetry={fetchDetails}
            onOpenContract={() => setIsContractModalOpen(true)}
          />
        ) : (
          <PREmptyState
            type="request_failed"
            error={error}
            onRetry={fetchDetails}
          />
        )}

        <PRContractModal
          isOpen={isContractModalOpen}
          onClose={() => setIsContractModalOpen(false)}
        />
      </div>
    );
  }

  if (!pullRequest) {
    return (
      <div className="pr-details-container">
        <div style={{ marginBottom: '20px' }}>
          <Link to="/pull-requests" className="btn-text-action" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <ArrowLeft size={16} />
            <span>Back to Pull Requests</span>
          </Link>
        </div>
        <PREmptyState type="pr_not_found" />
      </div>
    );
  }

  // PR fields (display only fields actually available from API)
  const prNumber = pullRequest.number ? `#${pullRequest.number}` : `#${pullRequest.id}`;
  const title = pullRequest.title || 'Untitled Pull Request';
  const author = pullRequest.author || pullRequest.user?.login || '—';
  const description = pullRequest.description || pullRequest.body || pullRequest.summary;
  const sourceBranch = pullRequest.source_branch || pullRequest.head?.ref || (pullRequest.latest_head_sha ? pullRequest.latest_head_sha.slice(0, 7) : '—');
  const targetBranch = pullRequest.target_branch || pullRequest.base?.ref || activeRepo?.default_branch || 'main';
  const latestHeadSha = pullRequest.latest_head_sha;
  const createdAt = pullRequest.created_at;
  const updatedAt = pullRequest.updated_at || pullRequest.created_at;
  const htmlUrl = pullRequest.html_url;

  // Associated Repository Name
  const repoName = pullRequest.repository?.full_name ||
    pullRequest.repository_name ||
    activeRepo?.full_name ||
    (connectedRepos.length > 0 ? connectedRepos[0].full_name : '—');

  // Review Status details
  const review = pullRequest.latest_review || (typeof pullRequest.review === 'object' ? pullRequest.review : null);
  const reviewStatus = (review?.status || pullRequest.review_status || '').toLowerCase();

  return (
    <div className="pr-details-container" aria-label="Pull Request Details">
      {/* Top Back Navigation Bar */}
      <div className="pr-details-nav-bar">
        <Link to="/pull-requests" className="btn-text-action" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
          <ArrowLeft size={16} />
          <span>Back to Pull Requests</span>
        </Link>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button
            type="button"
            className="btn-repo-refresh"
            onClick={fetchDetails}
            disabled={isLoading}
            title="Refresh pull request details"
            aria-label="Refresh pull request details"
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

      {/* Main PR Header Card */}
      <div className="pr-details-header-card">
        <div className="pr-details-title-row">
          <span className="pr-number-pill">{prNumber}</span>
          <h1 className="pr-details-title">{title}</h1>
        </div>

        <div className="pr-details-status-strip">
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="status-label">GitHub State:</span>
            {getStatusBadge(pullRequest.state)}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="status-label">Author:</span>
            <div className="pr-author-cell">
              <div className="pr-author-avatar-placeholder">
                <UserIcon size={12} />
              </div>
              <span className="pr-author-name">{author}</span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className="status-label">Repository:</span>
            <span className="pr-repo-tag">
              <FolderGit2 size={13} />
              <span>{repoName}</span>
            </span>
          </div>
        </div>
      </div>

      {/* Metadata & Branch Architecture Grid */}
      <div className="pr-meta-cards-grid">
        {/* Branches & Commit Card */}
        <div className="pr-meta-card">
          <h3 className="meta-card-title">
            <GitBranch size={16} color="var(--accent-primary)" />
            <span>Branch Topology</span>
          </h3>
          <div className="meta-card-content">
            <div className="meta-row">
              <span className="meta-key">Source (Head):</span>
              <span className="meta-val font-mono">{sourceBranch}</span>
            </div>
            <div className="meta-row">
              <span className="meta-key">Target (Base):</span>
              <span className="meta-val font-mono">{targetBranch}</span>
            </div>
            {latestHeadSha && (
              <div className="meta-row">
                <span className="meta-key">Head Commit:</span>
                <span className="meta-val font-mono" title={latestHeadSha}>
                  <GitCommit size={12} style={{ display: 'inline', marginRight: '4px' }} />
                  {latestHeadSha.slice(0, 10)}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Timestamps & Audit Card */}
        <div className="pr-meta-card">
          <h3 className="meta-card-title">
            <Calendar size={16} color="#0284c7" />
            <span>Timeline</span>
          </h3>
          <div className="meta-card-content">
            <div className="meta-row">
              <span className="meta-key">Created:</span>
              <span className="meta-val">{formatDate(createdAt)}</span>
            </div>
            <div className="meta-row">
              <span className="meta-key">Last Updated:</span>
              <span className="meta-val">{formatDate(updatedAt)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Pull Request Description / Summary if available */}
      {description && (
        <div className="pr-description-card">
          <h3 className="description-card-title">Pull Request Description</h3>
          <div className="description-body">
            <p>{description}</p>
          </div>
        </div>
      )}

      {/* CodeHawk Automated Review Status Section */}
      <section className="pr-review-status-section" aria-label="CodeHawk Review Status">
        <div className="review-section-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Bot size={20} color="var(--accent-primary)" />
            <h2 className="review-section-title">CodeHawk Automated Review Verdict</h2>
          </div>
          <span className="review-phase-badge">
            <ShieldCheck size={14} />
            <span>AI Code Review Integration</span>
          </span>
        </div>

        {reviewStatus === 'completed' && (
          <div className="review-verdict-box verdict-completed">
            <div className="verdict-header">
              <div className="verdict-icon success">
                <CheckCircle2 size={24} />
              </div>
              <div>
                <h4 className="verdict-title">Automated Review Completed</h4>
                <p className="verdict-subtitle">
                  AI analysis and static tree-sitter checks have been executed for this commit.
                </p>
              </div>
            </div>

            {review?.summary && (
              <div className="verdict-summary-block">
                <strong>Review Summary:</strong>
                <p>{review.summary}</p>
              </div>
            )}

            {/* Execution Metrics if provided by backend */}
            {(review?.files_reviewed > 0 || review?.input_tokens > 0 || review?.llm_model) && (
              <div className="verdict-stats-row">
                {review.llm_model && (
                  <div className="v-stat-item">
                    <span className="v-stat-label">Model</span>
                    <span className="v-stat-val">{review.llm_model}</span>
                  </div>
                )}
                {review.files_reviewed > 0 && (
                  <div className="v-stat-item">
                    <span className="v-stat-label">Files Reviewed</span>
                    <span className="v-stat-val">{review.files_reviewed}</span>
                  </div>
                )}
                {review.input_tokens > 0 && (
                  <div className="v-stat-item">
                    <span className="v-stat-label">Tokens</span>
                    <span className="v-stat-val">{review.input_tokens + (review.output_tokens || 0)}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {reviewStatus === 'running' && (
          <div className="review-verdict-box verdict-running">
            <div className="verdict-header">
              <div className="verdict-icon info">
                <Clock size={24} className="spin-icon" />
              </div>
              <div>
                <h4 className="verdict-title">Review in Progress</h4>
                <p className="verdict-subtitle">
                  The automated review bot is currently analyzing changes in commit <code>{latestHeadSha ? latestHeadSha.slice(0, 7) : ''}</code>.
                </p>
              </div>
            </div>
          </div>
        )}

        {reviewStatus === 'pending' && (
          <div className="review-verdict-box verdict-pending">
            <div className="verdict-header">
              <div className="verdict-icon warning">
                <Clock size={24} />
              </div>
              <div>
                <h4 className="verdict-title">Review Queued</h4>
                <p className="verdict-subtitle">
                  This pull request is scheduled in the Celery task queue for automated review.
                </p>
              </div>
            </div>
          </div>
        )}

        {reviewStatus === 'failed' && (
          <div className="review-verdict-box verdict-failed">
            <div className="verdict-header">
              <div className="verdict-icon error">
                <AlertCircle size={24} />
              </div>
              <div>
                <h4 className="verdict-title">Automated Review Failed</h4>
                <p className="verdict-subtitle">
                  {review?.error_message || 'The review runner encountered an error processing this diff.'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* State 10: Honest neutral state when no review record exists */}
        {!reviewStatus && (
          <div className="review-verdict-box verdict-none">
            <div className="verdict-header">
              <div className="verdict-icon muted">
                <Bot size={24} />
              </div>
              <div>
                <h4 className="verdict-title">No review recorded yet</h4>
                <p className="verdict-subtitle">
                  CodeHawk has not yet performed an automated review on this pull request.
                  Reviews will trigger automatically upon incoming webhook events from GitHub once the Celery worker is activated.
                </p>
              </div>
            </div>

            <div className="verdict-note-strip">
              <span>Note: Reviews are triggered server-side by the Django webhook listener on <code>pull_request.opened</code> and <code>pull_request.synchronize</code>.</span>
            </div>
          </div>
        )}
      </section>

      {/* PR health score + findings from AI review and Tree-sitter (side by side) */}
      {review && Array.isArray(review.comments) && (
        <>
          <HealthCard health={review.health} score={review.health_score} grade={review.health_grade} />
          <FindingsPanel comments={review.comments} />
        </>
      )}

      {/* Contract Modal Helper */}
      <PRContractModal
        isOpen={isContractModalOpen}
        onClose={() => setIsContractModalOpen(false)}
      />
    </div>
  );
}
