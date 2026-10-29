import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import ChartCard from './ChartCard';
import { SEVERITY_META, SEVERITY_ORDER, formatDay, hasData } from '../../utils/analytics';

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <strong>{formatDay(label)}</strong>
      {payload.map((p) => (
        <div key={p.dataKey} className="chart-tooltip-row">
          <span className="chart-dot" style={{ background: p.color }} />
          <span>{SEVERITY_META[p.dataKey]?.label || p.dataKey}</span>
          <b>{p.value}</b>
        </div>
      ))}
    </div>
  );
}

/** Stacked area: findings per day, split by severity. */
export default function IssuesOverTimeChart({ series = [], isLoading = false }) {
  return (
    <ChartCard
      title="Issues over time"
      subtitle="Findings per day by severity"
      isLoading={isLoading}
      isEmpty={!hasData(series, 'total')}
      emptyText="No findings yet. Open a pull request on a connected repository."
      height={280}
      className="chart-wide"
    >
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={series} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tickFormatter={formatDay} minTickGap={28} tickLine={false} axisLine={false} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
          <Tooltip content={<ChartTooltip />} />
          {[...SEVERITY_ORDER].reverse().map((sev) => (
            <Area
              key={sev}
              type="monotone"
              dataKey={sev}
              stackId="issues"
              stroke={SEVERITY_META[sev].color}
              fill={SEVERITY_META[sev].color}
              fillOpacity={0.28}
              strokeWidth={2}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
      <div className="chart-legend">
        {SEVERITY_ORDER.map((sev) => (
          <span key={sev}>
            <i className="chart-dot" style={{ background: SEVERITY_META[sev].color }} />
            {SEVERITY_META[sev].label}
          </span>
        ))}
      </div>
    </ChartCard>
  );
}
