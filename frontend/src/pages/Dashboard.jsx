import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, CheckCircle2, ArrowRight, ChevronLeft, ChevronRight, GitPullRequest, FolderGit2, GitBranch, RefreshCw } from 'lucide-react';
import { useRepos } from '../context/useRepos';
import useStats from '../hooks/useStats';
import syncService from '../services/syncService';
import StatCards from '../components/analytics/StatCards';
import IssuesOverTimeChart from '../components/analytics/IssuesOverTimeChart';
import SeverityDonut from '../components/analytics/SeverityDonut';
import DetectorSplit from '../components/analytics/DetectorSplit';
import HealthDistribution from '../components/analytics/HealthDistribution';
import ReviewsTable from '../components/reviews/ReviewsTable';
import PullRequestsTable from '../components/dashboard/PullRequestsTable';
import SyncPanel from '../components/dashboard/SyncPanel';
import ErrorNotice from '../components/common/ErrorNotice';

const PAGE_SIZE = 10;
const POLL_MS = 5000;
const MAX_POLLS = 120; // stop checking after ~10 minutes

export default function Dashboard() {
  const { connectedRepos } = useRepos();
  const hasConnectedRepo = connectedRepos && connectedRepos.length > 0;
  const primaryRepo = hasConnectedRepo ? connectedRepos[0] : null;
  const { data, isLoading, error, reload } = useStats({ days: 30 });

  // ── pull requests (real rows from the database) ─────────────────────────
  const [prState, setPrState] = useState('open'); // 'open' | 'all'
  const [prPage, setPrPage] = useState(1);
  const [prData, setPrData] = useState({ count: 0, next: null, results: [] });
  const [prLoading, setPrLoading] = useState(true);
  const [prError, setPrError] = useState(null);
  const [prTick, setPrTick] = useState(0);
  const polls = useRef(0);

  useEffect(() => {
    let active = true;
    Promise.resolve().then(async () => {
      if (!active) return;
      setPrLoading(true);
      setPrError(null);
      try {
        const res = await syncService.listPullRequests({ page: prPage, state: prState === 'all' ? undefined : 'open' });
        if (active) setPrData(res);
        polls.current = 0;
      } catch (err) {
        if (active) setPrError(err);
      } finally {
        if (active) setPrLoading(false);
      }
    });
    return () => {
      active = false;
    };
  }, [prPage, prState, prTick]);

  // While any review is pending or processing, quietly refresh until it finishes.
  const inProgress = prData.results.some((p) => p.review_status === 'pending' || p.review_status === 'running');
  useEffect(() => {
    if (!inProgress || polls.current >= MAX_POLLS) return undefined;
    let cancelled = false;
    const timer = setTimeout(async () => {
      polls.current += 1;
      try {
        const res = await syncService.listPullRequests({ page: prPage, state: prState === 'all' ? undefined : 'open' });
        if (!cancelled) {
          setPrData(res);
          reload();
        }
      } catch {
        /* keep the last good data; a manual refresh will surface the error */
      }
    }, POLL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [inProgress, prData, prPage, prState, reload]);

  // ── synchronisation ─────────────────────────────────────────────────────
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState(null);
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncError, setSyncError] = useState(null);

  useEffect(() => {
    let active = true;
    syncService
      .getStatus({ celery: true })
      .then((s) => active && setSyncStatus(s))
      .catch(() => {}); // non-essential: the panel just stays hidden
    return () => {
      active = false;
    };
  }, []);

  const handleSync = useCallback(async () => {
    if (isSyncing) return; // a double click must not start a second sync
    setIsSyncing(true);
    setSyncError(null);
    try {
      setSyncResult(await syncService.syncAll({ review: true }));
    } catch (err) {
      setSyncResult(null);
      setSyncError(err.status === 409 ? new Error('A sync is already running. Please wait a moment and try again.') : err);
    } finally {
      setIsSyncing(false);
      setPrPage(1);
      setPrTick((t) => t + 1);
      reload();
    }
  }, [isSyncing, reload]);

  const recent = data?.recent_reviews || [];
  const totalPages = Math.max(1, Math.ceil((prData.count || 0) / PAGE_SIZE));

  return (
    <div className="placeholder-page analytics-page">
      <div className="placeholder-header">
        <div>
          <h1 className="placeholder-title">Dashboard</h1>
          <p className="placeholder-desc">
            Live pull requests, AI review results, findings and PR health across your connected repositories.
          </p>
        </div>
        <div className="analytics-controls">
          <button
            type="button"
            className="btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
            onClick={handleSync}
            disabled={isSyncing || !hasConnectedRepo}
            title="Fetch open pull requests from GitHub for every connected repository and queue reviews"
          >
            <RefreshCw size={16} className={isSyncing ? 'spin-icon' : ''} />
            <span>{isSyncing ? 'Syncing…' : 'Sync Pull Requests'}</span>
          </button>
          <Link to="/repositories" className="btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
            <Plus size={16} />
            <span>Connect Repository</span>
          </Link>
        </div>
      </div>

      {hasConnectedRepo ? (
        <div className="dashboard-active-repo-card">
          <div className="active-repo-header">
            <div className="active-repo-badge">
              <span className="badge-dot-green" />
              <CheckCircle2 size={16} />
              <span>Connected Repository</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Link to={`/pull-requests?repo=${primaryRepo.id || primaryRepo.github_repo_id}`} className="btn-text-action" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                <GitPullRequest size={14} />
                <span>View Pull Requests</span>
              </Link>
              <Link to="/repositories" className="btn-text-action">
                Manage Repositories
              </Link>
            </div>
          </div>
          <div className="active-repo-content">
            <div className="active-repo-title-row">
              <FolderGit2 size={24} className="active-repo-icon" />
              <div>
                <h3 className="active-repo-name">{primaryRepo.full_name || `${primaryRepo.owner}/${primaryRepo.name}`}</h3>
                <div className="active-repo-meta">
                  <span className="meta-item">
                    <GitBranch size={13} />
                    <span>{primaryRepo.default_branch || 'main'}</span>
                  </span>
                  <span className="meta-separator">•</span>
                  <span className="meta-item">{primaryRepo.is_private ? 'Private repository' : 'Public repository'}</span>
                  <span className="meta-separator">•</span>
                  <span className="meta-item">{connectedRepos.length} connected</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="dashboard-connect-cta-card">
          <div className="cta-icon-box">
            <FolderGit2 size={28} />
          </div>
          <div className="cta-content">
            <h3 className="cta-title">No repository connected yet</h3>
            <p className="cta-desc">
              Connect a GitHub repository to activate CodeHawk&apos;s AI review bot. Incoming pull requests will be automatically reviewed for bugs, security vulnerabilities, and code quality.
            </p>
          </div>
          <Link to="/repositories" className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
            <span>Connect a Repository</span>
            <ArrowRight size={16} />
          </Link>
        </div>
      )}

      <SyncPanel result={syncResult} status={syncStatus} isSyncing={isSyncing} error={syncError} />

      <section className="chart-card" aria-label="Pull requests">
        <header className="chart-card-header">
          <div>
            <h3 className="chart-card-title">Pull requests</h3>
            <p className="chart-card-subtitle">
              {prData.count} {prState === 'open' ? 'open' : 'total'} across your connected repositories
              {inProgress ? ' · reviews running, updating automatically' : ''}
            </p>
          </div>
          <div className="tab-group" role="group" aria-label="Pull request state">
            {[['open', 'Open'], ['all', 'All']].map(([key, label]) => (
              <button
                key={key}
                type="button"
                aria-pressed={prState === key}
                className={`tab-btn ${prState === key ? 'active' : ''}`}
                onClick={() => {
                  setPrState(key);
                  setPrPage(1);
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </header>

        <ErrorNotice error={prError} onRetry={() => setPrTick((t) => t + 1)} title="Could not load pull requests" />

        {prLoading && prData.results.length === 0 ? (
          <div className="chart-skeleton" style={{ height: 160 }} role="status" aria-label="Loading pull requests" />
        ) : !prError && prData.results.length === 0 ? (
          <div className="chart-empty" style={{ height: 160 }}>
            <GitPullRequest size={28} />
            <p>
              No pull requests stored yet. {hasConnectedRepo ? 'Click Sync Pull Requests to fetch the open ones from GitHub.' : 'Connect a repository first.'}
            </p>
          </div>
        ) : (
          <PullRequestsTable pullRequests={prData.results} />
        )}

        {prData.count > PAGE_SIZE && (
          <footer className="pagination-bar">
            <span>
              Page {prPage} of {totalPages}
            </span>
            <div>
              <button type="button" className="btn-secondary-sm" disabled={prPage <= 1} onClick={() => setPrPage((p) => p - 1)}>
                <ChevronLeft size={14} /> Previous
              </button>
              <button type="button" className="btn-secondary-sm" disabled={!prData.next} onClick={() => setPrPage((p) => p + 1)}>
                Next <ChevronRight size={14} />
              </button>
            </div>
          </footer>
        )}
      </section>

      <ErrorNotice error={error} onRetry={reload} title="Could not load dashboard statistics" />

      <StatCards totals={data?.totals} isLoading={isLoading} />

      <div className="analytics-grid analytics-grid-4">
        <IssuesOverTimeChart series={data?.issues_over_time} isLoading={isLoading} />
        <SeverityDonut breakdown={data?.severity_breakdown} isLoading={isLoading} />
        <DetectorSplit sources={data?.source_breakdown} topRules={data?.top_rules} isLoading={isLoading} />
        <HealthDistribution distribution={data?.health_distribution} isLoading={isLoading} />
      </div>

      <section className="chart-card" aria-label="Recent reviews">
        <header className="chart-card-header">
          <div>
            <h3 className="chart-card-title">Recent reviews</h3>
            <p className="chart-card-subtitle">Latest automated reviews across your repositories</p>
          </div>
          <Link to="/reviews" className="btn-text-action" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
            View all <ArrowRight size={14} />
          </Link>
        </header>
        {isLoading ? (
          <div className="chart-skeleton" style={{ height: 160 }} role="status" aria-label="Loading reviews" />
        ) : recent.length === 0 ? (
          <div className="chart-empty" style={{ height: 160 }}>
            <GitPullRequest size={28} />
            <p>No reviews yet. Sync pull requests or open one on a connected repository to see one here.</p>
          </div>
        ) : (
          <ReviewsTable reviews={recent} compact />
        )}
      </section>
    </div>
  );
}
