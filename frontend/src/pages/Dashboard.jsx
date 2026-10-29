import { Link } from 'react-router-dom';
import { Plus, CheckCircle2, ArrowRight, GitPullRequest, FolderGit2, GitBranch } from 'lucide-react';
import { useRepos } from '../context/useRepos';
import useStats from '../hooks/useStats';
import StatCards from '../components/analytics/StatCards';
import IssuesOverTimeChart from '../components/analytics/IssuesOverTimeChart';
import SeverityDonut from '../components/analytics/SeverityDonut';
import DetectorSplit from '../components/analytics/DetectorSplit';
import HealthDistribution from '../components/analytics/HealthDistribution';
import ReviewsTable from '../components/reviews/ReviewsTable';
import ErrorNotice from '../components/common/ErrorNotice';

export default function Dashboard() {
  const { connectedRepos } = useRepos();
  const hasConnectedRepo = connectedRepos && connectedRepos.length > 0;
  const primaryRepo = hasConnectedRepo ? connectedRepos[0] : null;
  const { data, isLoading, error, reload } = useStats({ days: 30 });

  const recent = data?.recent_reviews || [];

  return (
    <div className="placeholder-page analytics-page">
      <div className="placeholder-header">
        <div>
          <h1 className="placeholder-title">Dashboard</h1>
          <p className="placeholder-desc">
            Live review activity, findings and PR health across your connected repositories (last 30 days).
          </p>
        </div>
        <Link to="/repositories" className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
          <Plus size={16} />
          <span>Connect Repository</span>
        </Link>
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
                  <span className="meta-item text-success">CodeHawk review bot active</span>
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
            <p>No reviews yet. Open a pull request on a connected repository to see one here.</p>
          </div>
        ) : (
          <ReviewsTable reviews={recent} compact />
        )}
      </section>
    </div>
  );
}
