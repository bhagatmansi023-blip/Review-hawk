import { useState } from 'react';
import { useRepos } from '../context/useRepos';
import useStats from '../hooks/useStats';
import RangeSelector from '../components/analytics/RangeSelector';
import StatCards from '../components/analytics/StatCards';
import IssuesOverTimeChart from '../components/analytics/IssuesOverTimeChart';
import SeverityDonut from '../components/analytics/SeverityDonut';
import CategoryBarChart from '../components/analytics/CategoryBarChart';
import DetectorSplit from '../components/analytics/DetectorSplit';
import HealthDistribution from '../components/analytics/HealthDistribution';
import ChartCard from '../components/analytics/ChartCard';
import ErrorNotice from '../components/common/ErrorNotice';
import { GradeBadge } from '../components/reviews/Badges';

export default function Analytics() {
  const { connectedRepos } = useRepos();
  const [days, setDays] = useState(30);
  const [repo, setRepo] = useState('all');
  const { data, isLoading, error, reload } = useStats({ days, repo: repo === 'all' ? undefined : repo });

  const perRepo = data?.per_repository || [];

  return (
    <div className="placeholder-page analytics-page">
      <div className="placeholder-header">
        <div>
          <h1 className="placeholder-title">Analytics</h1>
          <p className="placeholder-desc">
            Code quality trends, severity mix and PR health across your repositories.
          </p>
        </div>
        <div className="analytics-controls">
          <select className="filter-select" aria-label="Repository" value={repo} onChange={(e) => setRepo(e.target.value)}>
            <option value="all">All repositories</option>
            {(connectedRepos || []).map((r) => (
              <option key={r.id} value={r.id}>
                {r.full_name || `${r.owner}/${r.name}`}
              </option>
            ))}
          </select>
          <RangeSelector value={days} onChange={setDays} />
        </div>
      </div>

      <ErrorNotice error={error} onRetry={reload} title="Could not load analytics" />

      <StatCards totals={data?.totals} isLoading={isLoading} />

      <div className="analytics-grid">
        <IssuesOverTimeChart series={data?.issues_over_time} isLoading={isLoading} />
        <SeverityDonut breakdown={data?.severity_breakdown} isLoading={isLoading} />
        <CategoryBarChart breakdown={data?.category_breakdown} isLoading={isLoading} />
        <DetectorSplit sources={data?.source_breakdown} topRules={data?.top_rules} isLoading={isLoading} />
        <HealthDistribution distribution={data?.health_distribution} isLoading={isLoading} />
      </div>

      <ChartCard
        title="By repository"
        subtitle="Reviews, findings and average PR health per repository"
        isLoading={isLoading}
        isEmpty={perRepo.length === 0}
        emptyText="No reviewed repositories in this period."
        height={120}
      >
        <div className="table-scroll">
          <table className="reviews-table">
            <thead>
              <tr>
                <th>Repository</th>
                <th>Reviews</th>
                <th>Findings</th>
                <th>Avg health</th>
              </tr>
            </thead>
            <tbody>
              {perRepo.map((r) => (
                <tr key={r.repository_id}>
                  <td>{r.repository_name}</td>
                  <td>{r.reviews}</td>
                  <td>{r.findings}</td>
                  <td>
                    {r.avg_health_score === null ? <span className="muted-dash">—</span> : <GradeBadge grade={gradeOf(r.avg_health_score)} score={Math.round(r.avg_health_score)} />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </ChartCard>
    </div>
  );
}

function gradeOf(score) {
  if (score >= 90) return 'A+';
  if (score >= 80) return 'A';
  if (score >= 70) return 'B';
  if (score >= 60) return 'C';
  if (score >= 40) return 'D';
  return 'F';
}
