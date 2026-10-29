import { FolderGit2, GitPullRequest, ShieldAlert, HeartPulse, Timer, ScanSearch } from 'lucide-react';
import { formatDuration, formatNumber } from '../../utils/analytics';

function gradeFromScore(score) {
  if (score === null || score === undefined) return '';
  if (score >= 90) return 'A+';
  if (score >= 80) return 'A';
  if (score >= 70) return 'B';
  if (score >= 60) return 'C';
  if (score >= 40) return 'D';
  return 'F';
}

/** Headline numbers. Works with a null `totals` while loading. */
export default function StatCards({ totals, isLoading = false }) {
  const t = totals || {};
  const cards = [
    { key: 'repos', icon: FolderGit2, label: 'Connected repositories', value: formatNumber(t.repositories), sub: 'Monitored for pull requests' },
    { key: 'prs', icon: GitPullRequest, label: 'Pull requests reviewed', value: formatNumber(t.pull_requests_reviewed), sub: `${formatNumber(t.reviews)} review runs` },
    {
      key: 'findings',
      icon: ShieldAlert,
      label: 'Findings',
      value: formatNumber(t.findings),
      sub: `${formatNumber(t.ai_findings)} AI · ${formatNumber(t.static_findings)} Tree-sitter`,
    },
    {
      key: 'health',
      icon: HeartPulse,
      label: 'Average PR health',
      value: t.avg_health_score === null || t.avg_health_score === undefined ? '—' : `${Math.round(t.avg_health_score)}/100`,
      sub: t.avg_health_score === null || t.avg_health_score === undefined ? 'No scored reviews yet' : `Grade ${gradeFromScore(t.avg_health_score)}`,
    },
    { key: 'time', icon: Timer, label: 'Avg review time', value: formatDuration(t.avg_review_seconds), sub: 'From start to posted' },
    { key: 'failed', icon: ScanSearch, label: 'Failed reviews', value: formatNumber(t.failed), sub: `${formatNumber(t.completed)} completed` },
  ];

  return (
    <div className="analytics-stats-grid" aria-busy={isLoading}>
      {cards.map(({ key, icon: Icon, label, value, sub }) => (
        <div className="stat-card" key={key} data-testid={`stat-${key}`}>
          <div className="stat-label">
            <Icon size={16} />
            <span>{label}</span>
          </div>
          <div className="stat-value">{isLoading ? <span className="stat-skeleton" /> : value}</div>
          <div className="stat-subtext">{isLoading ? ' ' : sub}</div>
        </div>
      ))}
    </div>
  );
}
