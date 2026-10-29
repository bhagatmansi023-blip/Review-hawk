import { Lightbulb, Minus, Plus } from 'lucide-react';
import { gradeColor } from '../../utils/analytics';

/** Score ring + why the score is what it is (every signal, with its points). */
export default function HealthCard({ health, score, grade }) {
  const value = health?.score ?? score;
  const letter = health?.grade ?? grade;
  if (value === null || value === undefined) return null;

  const color = gradeColor(letter);
  const radius = 46;
  const circumference = 2 * Math.PI * radius;
  const signals = health?.signals || [];
  const penalties = signals.filter((s) => s.score_delta < 0);
  const bonuses = signals.filter((s) => s.score_delta > 0);

  return (
    <section className="health-card" aria-label="PR health score">
      <div className="health-ring-wrap">
        <svg viewBox="0 0 110 110" className="health-ring" role="img" aria-label={`Health score ${value} out of 100`}>
          <circle cx="55" cy="55" r={radius} className="health-ring-track" />
          <circle
            cx="55"
            cy="55"
            r={radius}
            className="health-ring-fill"
            style={{ stroke: color }}
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - Math.min(100, Math.max(0, value)) / 100)}
            transform="rotate(-90 55 55)"
          />
        </svg>
        <div className="health-ring-label">
          <strong>{value}</strong>
          <span>/ 100</span>
        </div>
      </div>

      <div className="health-body">
        <div className="health-headline">
          <span className="pill pill-grade pill-grade-lg" style={{ '--pill-color': color }}>
            Grade {letter}
          </span>
          {health?.risk_level && <span className="health-risk">Risk: {health.risk_level}</span>}
        </div>

        {health?.badges?.length > 0 && (
          <div className="health-badges">
            {health.badges.map((b) => (
              <span key={b} className="health-badge">
                {b}
              </span>
            ))}
          </div>
        )}

        {signals.length > 0 && (
          <ul className="health-signals">
            {penalties.map((s) => (
              <li key={s.code}>
                <Minus size={14} className="sig-neg" />
                <span>{s.description}</span>
                <b className="sig-neg">{s.score_delta}</b>
              </li>
            ))}
            {bonuses.map((s) => (
              <li key={s.code}>
                <Plus size={14} className="sig-pos" />
                <span>{s.description}</span>
                <b className="sig-pos">+{s.score_delta}</b>
              </li>
            ))}
          </ul>
        )}

        {health?.recommendations?.length > 0 && (
          <div className="health-tips">
            <h4>
              <Lightbulb size={14} /> Recommendations
            </h4>
            <ul>
              {health.recommendations.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
