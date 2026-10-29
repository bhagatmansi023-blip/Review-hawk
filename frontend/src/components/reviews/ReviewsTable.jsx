import { Link } from 'react-router-dom';
import { GradeBadge, StatusBadge } from './Badges';
import { SEVERITY_META, formatDuration, timeAgo } from '../../utils/analytics';

/** Review history rows. Used on the Reviews page and as "recent reviews" on the dashboard. */
export default function ReviewsTable({ reviews = [], compact = false }) {
  return (
    <div className="table-scroll">
      <table className="reviews-table">
        <thead>
          <tr>
            <th>Pull request</th>
            <th>Status</th>
            <th>Findings</th>
            <th>Health</th>
            {!compact && <th>Duration</th>}
            <th>When</th>
          </tr>
        </thead>
        <tbody>
          {reviews.map((r) => (
            <tr key={r.id} data-testid="review-row">
              <td>
                <Link to={`/pull-requests/${r.pr_id}`} className="review-link">
                  <span className="review-pr-title">
                    #{r.pr_number} {r.pr_title}
                  </span>
                </Link>
                <span className="review-repo">
                  {r.repository_name} · <code>{r.head_sha.slice(0, 7)}</code>
                </span>
              </td>
              <td>
                <StatusBadge status={r.status} />
              </td>
              <td>
                <div className="finding-counts">
                  {['error', 'warning', 'info'].map((sev) => (
                    <span key={sev} title={`${SEVERITY_META[sev].label}: ${r.counts[sev]}`} className={r.counts[sev] ? '' : 'zero'}>
                      <i className="chart-dot" style={{ background: SEVERITY_META[sev].color }} />
                      {r.counts[sev]}
                    </span>
                  ))}
                </div>
                <span className="review-repo">
                  {r.counts.llm} AI · {r.counts.static} Tree-sitter
                </span>
              </td>
              <td>
                <GradeBadge grade={r.health_grade} score={r.health_score} />
              </td>
              {!compact && <td>{formatDuration(r.duration_seconds)}</td>}
              <td className="review-when">{timeAgo(r.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
