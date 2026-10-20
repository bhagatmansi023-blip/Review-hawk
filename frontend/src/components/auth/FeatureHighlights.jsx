import { Bug, GitPullRequest, ShieldCheck, Zap } from 'lucide-react';
import hawkLogo from '../../assets/hawk-logo.jpg';

export default function FeatureHighlights() {
  return (
    <div className="hero-showcase">
      <div className="brand-badge">
        <span className="brand-badge-dot" />
        <span>AI-Powered Automated Code Review Bot for GitHub</span>
      </div>

      <div className="hero-header">
        <div className="hawk-emblem-wrapper">
          <img
            src={hawkLogo}
            alt="CodeHawk Emblem"
            className="hawk-emblem-img"
          />
        </div>
        <div>
          <h1 className="brand-title">
            Code<span>Hawk</span>
          </h1>
          <p className="tagline">Sharp Eyes. Cleaner Code.</p>
        </div>
      </div>

      <p className="supporting-text">
        Automate GitHub pull request reviews to help developers identify bugs, security concerns, and code-quality issues. Connect your repositories for instant, automated AI feedback on every pull request.
      </p>


      {/* Feature Value Props Grid */}
      <div className="feature-list">
        <div className="feature-item">
          <div className="feature-icon-box">
            <GitPullRequest size={20} />
          </div>
          <div>
            <h4>Automated PR Reviews</h4>
            <p>Inline review comments and actionable suggestions directly on GitHub diffs.</p>
          </div>
        </div>

        <div className="feature-item">
          <div className="feature-icon-box">
            <ShieldCheck size={20} />
          </div>
          <div>
            <h4>Security & Vulnerability</h4>
            <p>Catch leaked tokens, SQL injection risks, and risky dependencies before merge.</p>
          </div>
        </div>

        <div className="feature-item">
          <div className="feature-icon-box">
            <Bug size={20} />
          </div>
          <div>
            <h4>Bug & Anti-Pattern Catch</h4>
            <p>Detect logic flaws, unhandled exceptions, and edge-case null references.</p>
          </div>
        </div>

        <div className="feature-item">
          <div className="feature-icon-box">
            <Zap size={20} />
          </div>
          <div>
            <h4>Faster Merge Cycles</h4>
            <p>Relieve engineering teams from repetitive manual syntax checks.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
