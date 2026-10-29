import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import ChartCard from './ChartCard';
import { hasData, titleCase } from '../../utils/analytics';

/** Horizontal bars: what kind of problems are most common. */
export default function CategoryBarChart({ breakdown = [], isLoading = false }) {
  const data = breakdown.map((b) => ({ ...b, name: titleCase(b.category) }));
  const height = Math.max(180, data.length * 38 + 40);
  return (
    <ChartCard
      title="Findings by category"
      subtitle="Bug, security, performance, style..."
      isLoading={isLoading}
      isEmpty={!hasData(breakdown)}
      height={height}
    >
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} />
          <YAxis type="category" dataKey="name" width={110} tickLine={false} axisLine={false} />
          <Tooltip cursor={{ fillOpacity: 0.08 }} />
          <Bar dataKey="count" name="Findings" fill="#6366f1" radius={[0, 6, 6, 0]} barSize={18} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
