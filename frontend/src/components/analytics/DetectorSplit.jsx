import ChartCard from './ChartCard';
import { SOURCE_META, formatNumber, hasData } from '../../utils/analytics';

/**
 * Who found the issues: AI review vs Tree-sitter rules, plus the most common
 * Tree-sitter rules. Plain CSS bars (no chart library needed).
 */
export default function DetectorSplit({ sources = [], topRules = [], isLoading = false }) {
  const total = sources.reduce((sum, s) => sum + s.count, 0);
  const maxRule = Math.max(1, ...topRules.map((r) => r.count));

  return (
    <ChartCard
      title="AI vs Tree-sitter"
      subtitle="Which detector found the issues"
      isLoading={isLoading}
      isEmpty={!hasData(sources)}
      height={220}
    >
      <div className="split-bar" role="img" aria-label="Share of findings by detector">
        {sources.map((s) => (
          <div
            key={s.source}
            className="split-bar-seg"
            style={{ flexGrow: s.count, background: SOURCE_META[s.source]?.color }}
            title={`${s.label}: ${s.count}`}
          />
        ))}
      </div>
      <ul className="split-legend">
        {sources.map((s) => (
          <li key={s.source}>
            <i className="chart-dot" style={{ background: SOURCE_META[s.source]?.color }} />
            <span>{s.label}</span>
            <b>
              {formatNumber(s.count)}
              {total > 0 && <small> ({Math.round((s.count / total) * 100)}%)</small>}
            </b>
          </li>
        ))}
      </ul>

      {topRules.length > 0 && (
        <div className="top-rules">
          <h4>Most common Tree-sitter rules</h4>
          {topRules.map((r) => (
            <div className="top-rule-row" key={r.rule_id}>
              <span className="top-rule-label">{r.label}</span>
              <div className="top-rule-track">
                <div className="top-rule-fill" style={{ width: `${(r.count / maxRule) * 100}%` }} />
              </div>
              <b>{r.count}</b>
            </div>
          ))}
        </div>
      )}
    </ChartCard>
  );
}
