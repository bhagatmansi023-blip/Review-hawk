import { AlertTriangle, CheckCircle2, Loader2, XCircle } from 'lucide-react';
import { timeAgo } from '../../utils/analytics';

const SUMMARY_LABELS = [
  ['found', 'PRs found'],
  ['queued', 'Reviews queued'],
  ['completed', 'Completed'],
  ['failed', 'Failed'],
];

/**
 * What the last synchronisation did, per repository, plus review progress.
 * `result` is the POST /api/sync/ response, `status` the GET /api/sync/status/ response.
 */
export default function SyncPanel({ result = null, status = null, isSyncing = false, error = null }) {
  if (error) {
    return (
      <div className="action-notice action-error" role="alert">
        <strong>Sync failed.</strong> {error.message || 'The server could not be reached.'}
      </div>
    );
  }

  const reviews = result?.reviews || status?.reviews;
  if (!result && !status) return null;

  const counts = {
    found: result?.totals?.found ?? reviews?.open_prs ?? 0,
    queued: result?.totals?.queued ?? 0,
    completed: reviews?.completed ?? 0,
    failed: reviews?.failed ?? 0,
  };
  const rows = result?.results
    || (status?.repositories || []).map((r) => ({
      repository: r.repository, ok: r.status === 'ok', error: r.error, fetched: r.pull_requests_fetched,
      never: r.status === 'never', last_synced_at: r.last_synced_at,
    }));
  const tone = result ? { ok: 'success', partial: 'warning', failed: 'error', busy: 'warning' }[result.status] || 'info' : 'info';

  return (
    <section className={`sync-panel action-${tone}`} aria-label="Synchronisation status" aria-busy={isSyncing}>
      <header className="sync-panel-header">
        {isSyncing ? <Loader2 size={16} className="spin-icon" /> : tone === 'success' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
        <strong>
          {isSyncing ? 'Syncing pull requests…'
            : result?.status === 'busy' ? 'A sync is already running'
            : result ? `Sync ${result.status === 'ok' ? 'complete' : result.status}` : 'Synchronisation status'}
        </strong>
        {reviews && (
          <span className="sync-progress">
            {reviews.pending} pending · {reviews.processing} processing · {reviews.not_reviewed} not reviewed
          </span>
        )}
      </header>

      <dl className="sync-counts">
        {SUMMARY_LABELS.map(([key, label]) => (
          <div key={key} data-testid={`sync-${key}`}>
            <dt>{label}</dt>
            <dd>{counts[key]}</dd>
          </div>
        ))}
      </dl>

      {result?.warnings?.length > 0 && (
        <ul className="sync-warnings">
          {result.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      <ul className="sync-repos">
        {rows.map((r) => (
          <li key={r.repository} className={r.ok === false || r.error ? 'sync-repo-bad' : ''}>
            {r.skipped ? <Loader2 size={14} /> : r.error ? <XCircle size={14} /> : <CheckCircle2 size={14} />}
            <span className="sync-repo-name">{r.repository}</span>
            <span className="sync-repo-detail">
              {r.error ? r.error
                : r.skipped ? 'already syncing'
                : r.never ? 'never synced'
                : `${r.fetched} open PR${r.fetched === 1 ? '' : 's'}${r.reviews_queued ? `, ${r.reviews_queued + (r.reviews_retried || 0)} queued` : ''}${r.auth_mode === 'oauth' ? ' (via OAuth fallback)' : ''}${r.last_synced_at && !result ? `, ${timeAgo(r.last_synced_at)}` : ''}`}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
