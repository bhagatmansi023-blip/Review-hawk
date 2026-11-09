import { Link } from 'react-router-dom';
import { ExternalLink, GitPullRequest } from 'lucide-react';
import { GradeBadge, StatusBadge } from '../reviews/Badges';
import { timeAgo } from '../../utils/analytics';

const PR_STATE = {
  open: { label: 'Open', color: '#22c55e' },
  merged: { label: 'Merged', color: '#a855f7' },
  closed: { label: 'Closed', color: '#ef4444' },
};

/**
 * Real pull requests from the database (all connected repositories).
 * Review status reflects the PR's current commit: pending, processing, completed or failed.
 */
export default function PullRequestsTable({ pullRequests = [] }) {
  return (
    <div className="table-scroll">
      <table className="reviews-table" data-testid="pr-table">
        <thead>
          <tr>
            <th>Repository</th>
            <th>Pull request</th>
            <th>Author</th>
            <th>Status</th>
            <th>Updated</th>
            <th>AI review</th>
            <th>GitHub</th>
          </tr>
        </thead>
        <tbody>
          {pullRequests.map((pr) => {
            const state = PR_STATE[pr.state] || { label: pr.state, color: '#94a3b8' };
            const review = pr.latest_review;
            return (
              <tr key={pr.id} data-testid="pr-row">
                <td>{pr.repository_name}</td>
                <td>
                  <Link to={`/pull-requests/${pr.id}`} className="review-link">
                    <span className="review-pr-title">
                      #{pr.number} {pr.title}
                    </span>
                  </Link>
                  {pr.source_branch && (
                    <span className="review-repo">
                      <code>{pr.source_branch}</code> → <code>{pr.target_branch}</code>
                    </span>
                  )}
                </td>
                <td>{pr.author || '—'}</td>
                <td>
                  <span className="pill pill-status" style={{ '--pill-color': state.color }}>
                    {state.label}
                  </span>
                </td>
                <td className="review-when">{timeAgo(pr.github_updated_at || pr.updated_at)}</td>
                <td>
                  <div className="pr-review-cell">
                    <StatusBadge status={pr.review_status || 'not_reviewed'} />
                    {review?.health_grade ? <GradeBadge grade={review.health_grade} score={review.health_score} /> : null}
                  </div>
                  {review?.status === 'completed' && review.counts && (
                    <span className="review-repo">{review.counts.total} finding{review.counts.total === 1 ? '' : 's'}</span>
                  )}
                  {review?.status === 'failed' && review.error_message && (
                    <span className="review-repo pr-review-error" title={review.error_message}>
                      {review.error_message.slice(0, 80)}
                      {review.error_message.length > 80 ? '…' : ''}
                    </span>
                  )}
                </td>
                <td>
                  {pr.html_url ? (
                    <a href={pr.html_url} target="_blank" rel="noopener noreferrer" className="review-link" aria-label={`Open pull request #${pr.number} on GitHub`}>
                      <ExternalLink size={14} />
                    </a>
                  ) : (
                    <GitPullRequest size={14} className="muted-dash" />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
