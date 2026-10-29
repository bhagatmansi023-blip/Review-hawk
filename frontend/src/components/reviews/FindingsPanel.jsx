import { useMemo, useState } from 'react';
import { FileCode2, SearchX } from 'lucide-react';
import { SeverityBadge, SourceBadge } from './Badges';
import { SEVERITY_META, SEVERITY_ORDER, countBySource, filterFindings, groupByFile } from '../../utils/analytics';

const SOURCE_TABS = [
  { key: 'all', label: 'All' },
  { key: 'llm', label: 'AI review' },
  { key: 'static', label: 'Tree-sitter' },
];

/**
 * Every finding for one review, side by side: AI review and Tree-sitter rules,
 * grouped by file. Filter by detector and severity.
 */
export default function FindingsPanel({ comments = [] }) {
  const [source, setSource] = useState('all');
  const [severity, setSeverity] = useState('all');

  const counts = useMemo(() => ({ ...countBySource(comments), all: comments.length }), [comments]);
  const groups = useMemo(() => groupByFile(filterFindings(comments, { source, severity })), [comments, source, severity]);
  const visible = groups.reduce((n, g) => n + g.items.length, 0);

  return (
    <section className="findings-panel" aria-label="Review findings">
      <header className="findings-header">
        <div>
          <h3 className="findings-title">Findings</h3>
          <p className="findings-subtitle">{comments.length} total, shown side by side from both detectors</p>
        </div>

        <div className="findings-filters">
          <div className="tab-group" role="tablist" aria-label="Detector">
            {SOURCE_TABS.map((tab) => (
              <button
                key={tab.key}
                role="tab"
                type="button"
                aria-selected={source === tab.key}
                className={`tab-btn ${source === tab.key ? 'active' : ''}`}
                onClick={() => setSource(tab.key)}
              >
                {tab.label} <span className="tab-count">{counts[tab.key] ?? 0}</span>
              </button>
            ))}
          </div>

          <select
            className="filter-select"
            aria-label="Severity"
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
          >
            <option value="all">All severities</option>
            {SEVERITY_ORDER.map((s) => (
              <option key={s} value={s}>
                {SEVERITY_META[s].label}
              </option>
            ))}
          </select>
        </div>
      </header>

      {comments.length === 0 ? (
        <div className="findings-empty">
          <SearchX size={28} />
          <p>No findings for this review. Nice work!</p>
        </div>
      ) : visible === 0 ? (
        <div className="findings-empty">
          <SearchX size={28} />
          <p>No findings match these filters.</p>
        </div>
      ) : (
        groups.map(({ file, items }) => (
          <div className="findings-file" key={file}>
            <div className="findings-file-name">
              <FileCode2 size={15} />
              <code>{file}</code>
              <span className="tab-count">{items.length}</span>
            </div>
            <ul className="findings-list">
              {items.map((c) => (
                <li key={c.id} className={`finding finding-${c.severity}`} data-testid="finding">
                  <div className="finding-meta">
                    <span className="finding-line">Line {c.line_number}</span>
                    <SeverityBadge severity={c.severity} />
                    <SourceBadge source={c.source} ruleLabel={c.rule_label} />
                    {c.category && <span className="finding-category">{c.category}</span>}
                  </div>
                  <p className="finding-message">{c.message}</p>
                  {c.suggestion && (
                    <p className="finding-suggestion">
                      <strong>Suggestion:</strong> {c.suggestion}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </section>
  );
}
