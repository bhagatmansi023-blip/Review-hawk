import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import ChartCard from './ChartCard';
import { gradeColor, hasData } from '../../utils/analytics';

/** How many reviews landed in each health grade (A+ ... F). */
export default function HealthDistribution({ distribution = [], isLoading = false }) {
  return (
    <ChartCard
      title="PR health grades"
      subtitle="Rule-based score from size, tests, docs and findings"
      isLoading={isLoading}
      isEmpty={!hasData(distribution)}
      emptyText="No scored reviews yet."
      height={220}
    >
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={distribution} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="grade" tickLine={false} axisLine={false} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
          <Tooltip cursor={{ fillOpacity: 0.08 }} />
          <Bar dataKey="count" name="Reviews" radius={[6, 6, 0, 0]} barSize={32}>
            {distribution.map((d) => (
              <Cell key={d.grade} fill={gradeColor(d.grade)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
