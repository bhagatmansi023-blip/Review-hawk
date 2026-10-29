const OPTIONS = [
  { days: 7, label: '7 days' },
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
];

export default function RangeSelector({ value, onChange }) {
  return (
    <div className="tab-group" role="group" aria-label="Date range">
      {OPTIONS.map((o) => (
        <button
          key={o.days}
          type="button"
          aria-pressed={value === o.days}
          className={`tab-btn ${value === o.days ? 'active' : ''}`}
          onClick={() => onChange(o.days)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
