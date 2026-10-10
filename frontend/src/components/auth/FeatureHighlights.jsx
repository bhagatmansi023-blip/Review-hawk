import { Bug, GitPullRequest, ShieldCheck, Zap } from 'lucide-react';
import hawkLogo from '../../assets/hawk-logo.jpg';

export default function FeatureHighlights() {
  return (
    <div className="hero-showcase">
      <div className="brand-badge">
        <span className="brand-badge-dot" />
        <span>AI-Powered Automated Code Review Platform</span>
      </div>

      <div className="hero-header">
        <div className="hawk-emblem-wrapper">
          <img
            src={hawkLogo}
            alt="Review Hawk Emblem"
            className="hawk-emblem-img"
          />
        </div>
        <div>
          <h1 className="brand-title">
            Review <span>Hawk</span>
          </h1>
          <p className="tagline">Sharp Eyes. Cleaner Code.</p>
        </div>
      </div>

      <p className="supporting-text">
        AI-powered code reviews that help you catch bugs, improve code quality, and ship with confidence. Connect your GitHub repositories and get immediate automated feedback on every pull request.
      </p>

      {/* Terminal / Live PR Analysis Preview */}
      <div className="code-preview-card">
        <div className="code-preview-header">
          <div className="window-dots">
            <span className="window-dot dot-red" />
            <span className="window-dot dot-yellow" />
            <span className="window-dot dot-green" />
          </div>
          <span>hawk-review-engine v1.0.0</span>
          <span>github-action:active</span>
        </div>
        <div className="code-preview-body">
          <div className="terminal-line">
            <span className="terminal-prompt">❯</span>
            <span style={{ color: 'var(--text-primary)' }}>review-hawk analyze --pr 142 --repo acme/core-api</span>
          </div>
          <div className="terminal-line" style={{ color: 'var(--text-muted)' }}>
            <span>Analyzing 8 files (+342, -58)...</span>
          </div>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '4px' }}>
            <span className="terminal-badge badge-pass">✓ Static Analysis: Passed</span>
            <span className="terminal-badge badge-pass">✓ Security Audit: 0 High CVEs</span>
            <span className="terminal-badge badge-warning">⚡ 2 Performance Recommendations</span>
          </div>
        </div>
      </div>

      {/* Feature Value Props Grid */}
      <div className="feature-list">
        <div className="feature-item">
          <div className="feature-icon-box">
            <GitPullRequest size={20} />
          </div>
          <div>
            <h4>Automated PR Reviews</h4>
            <p>Instant inline suggestions and actionable feedback right inside GitHub.</p>
          </div>
        </div>

        <div className="feature-item">
          <div className="feature-icon-box">
            <ShieldCheck size={20} />
          </div>
          <div>
            <h4>Security & Vulnerability</h4>
            <p>Detect leaked secrets, injection vulnerabilities, and dependency flaws.</p>
          </div>
        </div>

        <div className="feature-item">
          <div className="feature-icon-box">
            <Bug size={20} />
          </div>
          <div>
            <h4>Bug & Anti-Pattern Catch</h4>
            <p>Catch logic regressions, edge-case null pointers, and resource leaks early.</p>
          </div>
        </div>

        <div className="feature-item">
          <div className="feature-icon-box">
            <Zap size={20} />
          </div>
          <div>
            <h4>Fast CI/CD Pipeline</h4>
            <p>Frees up senior engineers from repetitive manual syntax reviews.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
