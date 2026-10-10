import { useState } from 'react';
import { Shield, Lock, Info } from 'lucide-react';
import FeatureHighlights from '../components/auth/FeatureHighlights';
import GitHubLoginButton from '../components/auth/GitHubLoginButton';
import ThemeToggle from '../components/common/ThemeToggle';
import BackendStatusModal from '../components/common/BackendStatusModal';
import hawkLogo from '../assets/hawk-logo.jpg';
import authService from '../services/auth';

export default function Login() {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleGitHubClick = async () => {
    // Initiate login via auth service
    await authService.initiateGitHubLogin();
    // In Phase 1, open the integration modal to inform developer about backend status
    setIsModalOpen(true);
  };

  return (
    <div className="login-split-wrapper">
      {/* Left Column: SaaS Branding, Features, and Live Analysis Preview */}
      <FeatureHighlights />

      {/* Right Column: Authentication Card */}
      <section className="auth-card-container" aria-label="Sign In">
        <div className="auth-card">
          <div className="auth-card-topbar">
            <ThemeToggle />
          </div>

          <div className="auth-card-header">
            <div className="auth-card-avatar">
              <img src={hawkLogo} alt="Review Hawk" />
            </div>
            <h2 className="auth-card-title">Welcome to Review Hawk</h2>
            <p className="auth-card-subtitle">
              Sign in to connect your GitHub repositories and start automated AI code reviews.
            </p>
          </div>

          {/* GitHub Action CTA */}
          <GitHubLoginButton onInitiateLogin={handleGitHubClick} />

          {/* Trust & Compliance Pills */}
          <div className="trust-badges">
            <div className="trust-item">
              <Shield size={14} />
              <span>Read-only PR scopes</span>
            </div>
            <div className="trust-item">
              <Lock size={14} />
              <span>OAuth 2.0 Security</span>
            </div>
          </div>

          {/* Backend Contract Status Banner */}
          <aside className="backend-status-card" aria-label="Backend Integration Status">
            <div className="status-header">
              <span>Backend OAuth Status</span>
              <span className="status-tag">
                <Info size={12} />
                <span>Awaiting Django Endpoints</span>
              </span>
            </div>
            <p className="status-text">
              Frontend OAuth UI and service integration points are prepared. Secure client credentials will be managed by the Django backend.
            </p>
            <div className="status-actions">
              <button
                type="button"
                className="btn-text-action"
                onClick={() => setIsModalOpen(true)}
              >
                View Backend Contract & Routes
              </button>
            </div>
          </aside>
        </div>
      </section>

      {/* Backend Status & Route Navigation Modal */}
      <BackendStatusModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </div>
  );
}
