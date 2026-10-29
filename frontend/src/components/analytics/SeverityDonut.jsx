import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import ChartCard from './ChartCard';
import { SEVERITY_META, formatNumber, hasData } from '../../utils/analytics';

/** Donut: share of errors / warnings / infos. */
export default function SeverityDonut({ breakdown = [], isLoading = false }) {
  const total = breakdown.reduce((sum, b) => sum + b.count, 0);
  const data = breakdown.map((b) => ({ ...b, name: SEVERITY_META[b.severity]?.label || b.severity }));

  return (
    <ChartCard
      title="Severity breakdown"
      subtitle="How serious are the findings?"
      isLoading={isLoading}
      isEmpty={!hasData(breakdown)}
      emptyText="No findings to break down yet."
      height={280}
    >
      <div className="donut-wrap">
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Pie data={data} dataKey="count" nameKey="name" innerRadius={58} outerRadius={84} paddingAngle={2} stroke="none">
              {data.map((d) => (
                <Cell key={d.severity} fill={SEVERITY_META[d.severity]?.color || '#94a3b8'} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-center" aria-hidden="true">
          <strong>{formatNumber(total)}</strong>
          <span>findings</span>
        </div>
      </div>
      <ul className="donut-legend">
        {data.map((d) => (
          <li key={d.severity}>
            <i className="chart-dot" style={{ background: SEVERITY_META[d.severity]?.color }} />
            <span>{d.name}</span>
            <b>{formatNumber(d.count)}</b>
          </li>
        ))}
      </ul>
    </ChartCard>
  );
}
