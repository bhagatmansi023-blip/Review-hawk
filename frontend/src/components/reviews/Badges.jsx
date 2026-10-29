import { CheckCircle2, Clock, Loader2, XCircle, Bot, Code2 } from 'lucide-react';
import { SEVERITY_META, SOURCE_META, gradeColor } from '../../utils/analytics';

export function SeverityBadge({ severity }) {
  const meta = SEVERITY_META[severity] || { label: severity, color: '#94a3b8' };
  return (
    <span className="pill pill-severity" style={{ '--pill-color': meta.color }}>
      {meta.label}
    </span>
  );
}

/** Shows where a finding came from: the LLM or a Tree-sitter rule. */
export function SourceBadge({ source, ruleLabel = '' }) {
  const meta = SOURCE_META[source] || { label: source, color: '#94a3b8' };
  const Icon = source === 'static' ? Code2 : Bot;
  return (
    <span className="pill pill-source" style={{ '--pill-color': meta.color }} title={ruleLabel || meta.label}>
      <Icon size={12} />
      {meta.label}
      {ruleLabel ? <em>· {ruleLabel}</em> : null}
    </span>
  );
}

export function GradeBadge({ grade, score = null }) {
  if (!grade) return <span className="muted-dash">—</span>;
  return (
    <span className="pill pill-grade" style={{ '--pill-color': gradeColor(grade) }} title={score !== null ? `${score}/100` : undefined}>
      {grade}
      {score !== null && score !== undefined ? <em>{score}</em> : null}
    </span>
  );
}

const STATUS = {
  completed: { label: 'Completed', icon: CheckCircle2, color: '#22c55e' },
  running: { label: 'Running', icon: Loader2, color: '#38bdf8' },
  pending: { label: 'Pending', icon: Clock, color: '#eab308' },
  failed: { label: 'Failed', icon: XCircle, color: '#ef4444' },
};

export function StatusBadge({ status }) {
  const meta = STATUS[status] || { label: status || '—', icon: Clock, color: '#94a3b8' };
  const Icon = meta.icon;
  return (
    <span className="pill pill-status" style={{ '--pill-color': meta.color }}>
      <Icon size={12} className={status === 'running' ? 'spin-icon' : undefined} />
      {meta.label}
    </span>
  );
}
