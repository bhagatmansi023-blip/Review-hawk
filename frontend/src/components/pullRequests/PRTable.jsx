import { Link } from 'react-router-dom';
import { 
  GitPullRequest, 
  ExternalLink, 
  GitBranch, 
  User as UserIcon, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  ArrowRight,
  GitCommit
} from 'lucide-react';

export default function PRTable({ pullRequests = [], activeRepo = null }) {
  const formatDate = (isoString) => {
    if (!isoString) return '—';
    try {
      const date = new Date(isoString);
      if (isNaN(date.getTime())) return '—';
      return new Intl.DateTimeFormat('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      }).format(date);
    } catch {
      return '—';
    }
  };

  const getStatusBadge = (state) => {
    const s = (state || '').toLowerCase();
    if (s === 'open') {
      return (
        <span className="badge-visibility badge-public" style={{ backgroundColor: 'rgba(34, 197, 94, 0.1)', color: '#22c55e', borderColor: 'rgba(34, 197, 94, 0.25)' }}>
          <span className="badge-dot-green" style={{ width: '6px', height: '6px' }} />
          <span>Open</span>
        </span>
      );
    }
    if (s === 'merged') {
      return (
        <span className="badge-visibility badge-private" style={{ backgroundColor: 'rgba(168, 85, 247, 0.1)', color: '#a855f7', borderColor: 'rgba(168, 85, 247, 0.25)' }}>
          <GitPullRequest size={11} />
          <span>Merged</span>
        </span>
      );
    }
    if (s === 'closed') {
      return (
        <span className="badge-visibility" style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', borderColor: 'rgba(239, 68, 68, 0.25)' }}>
          <span>Closed</span>
        </span>
      );
    }
    return (
      <span className="badge-visibility" style={{ color: 'var(--text-muted)' }}>
        <span>{state || '—'}</span>
      </span>
    );
  };

  const getReviewBadge = (pr) => {
    // Review status from latest_review object or pr.review_status
    const review = pr.latest_review || (typeof pr.review === 'object' ? pr.review : null);
    const status = (review?.status || pr.review_status || '').toLowerCase();

    if (status === 'completed') {
      return (
        <span className="badge-status badge-status-active" title="Automated code review completed">
          <CheckCircle2 size={13} color="#22c55e" />
          <span>Completed</span>
        </span>
      );
    }
    if (status === 'running') {
      return (
        <span className="badge-status" style={{ backgroundColor: 'rgba(56, 189, 248, 0.12)', color: '#0284c7', borderColor: 'rgba(56, 189, 248, 0.3)' }} title="Code review in progress">
          <Clock size={13} className="spin-icon" />
          <span>Reviewing...</span>
        </span>
      );
    }
    if (status === 'pending') {
      return (
        <span className="badge-status" style={{ backgroundColor: 'rgba(245, 158, 11, 0.12)', color: '#d97706', borderColor: 'rgba(245, 158, 11, 0.3)' }} title="Review queued">
          <Clock size={13} />
          <span>Pending</span>
        </span>
      );
    }
    if (status === 'failed') {
      return (
        <span className="badge-status" style={{ backgroundColor: 'rgba(239, 68, 68, 0.12)', color: '#ef4444', borderColor: 'rgba(239, 68, 68, 0.3)' }} title="Review failed">
          <AlertCircle size={13} />
          <span>Failed</span>
        </span>
      );
    }

    // Neutral honest state when no review has been conducted yet
    return (
      <span className="badge-status badge-status-available" style={{ color: 'var(--text-muted)' }} title="No automated review recorded yet">
        <span>No review yet</span>
      </span>
    );
  };

  return (
    <div className="repo-table-container">
      {/* Desktop Table View */}
      <div className="repo-table-wrapper pr-desktop-table">
        <table className="repo-table" aria-label="Pull Requests Table">
          <thead>
            <tr>
              <th scope="col" style={{ width: '32%' }}>Pull Request</th>
              <th scope="col" style={{ width: '13%' }}>Author</th>
              <th scope="col" style={{ width: '13%' }}>Source Branch</th>
              <th scope="col" style={{ width: '13%' }}>Target Branch</th>
              <th scope="col" style={{ width: '9%' }}>Status</th>
              <th scope="col" style={{ width: '12%' }}>Review Status</th>
              <th scope="col" style={{ width: '10%' }}>Updated</th>
              <th scope="col" style={{ width: '8%', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {pullRequests.map((pr) => {
              const prId = pr.id || pr.number;
              const prNumber = pr.number ? `#${pr.number}` : `#${prId}`;
              const title = pr.title || 'Untitled Pull Request';
              const author = pr.author || pr.user?.login || '—';
              const sourceBranch = pr.source_branch || pr.head?.ref || (pr.latest_head_sha ? pr.latest_head_sha.slice(0, 7) : '—');
              const targetBranch = pr.target_branch || pr.base?.ref || activeRepo?.default_branch || 'main';
              const updatedAt = pr.updated_at || pr.created_at;

              return (
                <tr key={prId} className="repo-row">
                  {/* PR Title & Number */}
                  <td>
                    <div className="repo-info-cell">
                      <div className="repo-title-row">
                        <Link
                          to={`/pull-requests/${prId}`}
                          className="repo-name pr-table-title-link"
                          title={title}
                        >
                          <span className="pr-number-tag">{prNumber}</span>
                          <span>{title}</span>
                        </Link>
                        {pr.html_url && (
                          <a
                            href={pr.html_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="repo-external-link"
                            title="Open on GitHub"
                            aria-label={`Open PR ${prNumber} on GitHub`}
                          >
                            <ExternalLink size={13} />
                          </a>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* Author */}
                  <td>
                    <div className="pr-author-cell">
                      <div className="pr-author-avatar-placeholder">
                        <UserIcon size={12} />
                      </div>
                      <span className="pr-author-name">{author}</span>
                    </div>
                  </td>

                  {/* Source Branch */}
                  <td>
                    <div className="repo-branch-cell" title={`Source: ${sourceBranch}`}>
                      {pr.source_branch ? <GitBranch size={13} /> : <GitCommit size={13} />}
                      <span className="branch-name-truncate">{sourceBranch}</span>
                    </div>
                  </td>

                  {/* Target Branch */}
                  <td>
                    <div className="repo-branch-cell" title={`Target: ${targetBranch}`}>
                      <GitBranch size={13} />
                      <span className="branch-name-truncate">{targetBranch}</span>
                    </div>
                  </td>

                  {/* GitHub State */}
                  <td>
                    {getStatusBadge(pr.state)}
                  </td>

                  {/* Review Status */}
                  <td>
                    {getReviewBadge(pr)}
                  </td>

                  {/* Updated timestamp */}
                  <td>
                    <span className="pr-date-text">{formatDate(updatedAt)}</span>
                  </td>

                  {/* Actions */}
                  <td style={{ textAlign: 'right' }}>
                    <Link
                      to={`/pull-requests/${prId}`}
                      className="btn-text-action"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', whiteSpace: 'nowrap' }}
                    >
                      <span>Details</span>
                      <ArrowRight size={13} />
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile / Tablet Responsive Cards View */}
      <div className="pr-mobile-card-list">
        {pullRequests.map((pr) => {
          const prId = pr.id || pr.number;
          const prNumber = pr.number ? `#${pr.number}` : `#${prId}`;
          const title = pr.title || 'Untitled Pull Request';
          const author = pr.author || pr.user?.login || '—';
          const sourceBranch = pr.source_branch || pr.head?.ref || (pr.latest_head_sha ? pr.latest_head_sha.slice(0, 7) : '—');
          const targetBranch = pr.target_branch || pr.base?.ref || activeRepo?.default_branch || 'main';
          const updatedAt = pr.updated_at || pr.created_at;

          return (
            <div key={prId} className="pr-mobile-card">
              <div className="pr-mobile-card-header">
                <span className="pr-number-tag">{prNumber}</span>
                <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  {getStatusBadge(pr.state)}
                  {getReviewBadge(pr)}
                </div>
              </div>

              <Link to={`/pull-requests/${prId}`} className="pr-mobile-title">
                {title}
              </Link>

              <div className="pr-mobile-meta-grid">
                <div className="pr-mobile-meta-item">
                  <span className="meta-label">Author:</span>
                  <span className="meta-val">{author}</span>
                </div>
                <div className="pr-mobile-meta-item">
                  <span className="meta-label">Branches:</span>
                  <span className="meta-val">{sourceBranch} → {targetBranch}</span>
                </div>
                <div className="pr-mobile-meta-item">
                  <span className="meta-label">Updated:</span>
                  <span className="meta-val">{formatDate(updatedAt)}</span>
                </div>
              </div>

              <div className="pr-mobile-card-actions">
                {pr.html_url && (
                  <a
                    href={pr.html_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-secondary"
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem' }}
                  >
                    <span>GitHub</span>
                    <ExternalLink size={13} />
                  </a>
                )}
                <Link
                  to={`/pull-requests/${prId}`}
                  className="btn-primary"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem' }}
                >
                  <span>View Details</span>
                  <ArrowRight size={13} />
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
