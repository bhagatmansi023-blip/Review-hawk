import { BarChart3 } from 'lucide-react';

/**
 * Shared frame for every chart: title, loading skeleton, empty state, error state.
 */
export default function ChartCard({
  title,
  subtitle,
  isLoading = false,
  isEmpty = false,
  emptyText = 'No data in this period yet.',
  height = 260,
  action = null,
  className = '',
  children,
}) {
  return (
    <section className={`chart-card ${className}`.trim()} aria-label={title}>
      <header className="chart-card-header">
        <div>
          <h3 className="chart-card-title">{title}</h3>
          {subtitle && <p className="chart-card-subtitle">{subtitle}</p>}
        </div>
        {action}
      </header>

      <div className="chart-card-body" style={{ minHeight: height }}>
        {isLoading ? (
          <div className="chart-skeleton" style={{ height }} role="status" aria-label="Loading chart" />
        ) : isEmpty ? (
          <div className="chart-empty" style={{ height }}>
            <BarChart3 size={28} />
            <p>{emptyText}</p>
          </div>
        ) : (
          children
        )}
      </div>
    </section>
  );
}
