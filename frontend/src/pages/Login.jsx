import { useState, useEffect } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { Shield, Lock, AlertCircle, RotateCw, X } from 'lucide-react';
import FeatureHighlights from '../components/auth/FeatureHighlights';
import GitHubLoginButton from '../components/auth/GitHubLoginButton';
import ThemeToggle from '../components/common/ThemeToggle';
import hawkLogo from '../assets/hawk-logo.jpg';
import { useAuth } from '../context/useAuth';

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { isAuthenticated, login, authError, setAuthError } = useAuth();

  const [isInitiating, setIsInitiating] = useState(false);
  const [localError, setLocalError] = useState(() => {
    const errorParam = searchParams.get('error');
    const errorDesc = searchParams.get('error_description');
    if (!errorParam) return null;
    if (errorParam === 'access_denied') {
      return 'GitHub authorization was declined. Please try again to connect CodeHawk.';
    } else if (errorParam === 'backend_unavailable') {
      return 'Unable to connect to the CodeHawk authentication backend.';
    }
    return errorDesc || `Authentication failed (${errorParam}).`;
  });

  // If already authenticated, redirect to target or /dashboard
  useEffect(() => {
    if (isAuthenticated) {
      const target = location.state?.from?.pathname || '/dashboard';
      navigate(target, { replace: true });
    }
  }, [isAuthenticated, navigate, location]);

  // Clean up URL query parameters if present
  useEffect(() => {
    if (searchParams.has('error') || searchParams.has('error_description')) {
      const nextParams = new URLSearchParams(searchParams);
      nextParams.delete('error');
      nextParams.delete('error_description');
      setSearchParams(nextParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const handleGitHubClick = async () => {
    if (isInitiating) return;
    setIsInitiating(true);
    setLocalError(null);
    if (setAuthError) setAuthError(null);

    try {
      await login();
    } catch (err) {
      setLocalError(
        err.message ||
        'Could not initiate GitHub login. Ensure your backend server is running at http://localhost:8000.'
      );
      setIsInitiating(false);
    }
  };

  const activeError = localError || authError;

  const handleDismissError = () => {
    setLocalError(null);
    if (setAuthError) setAuthError(null);
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
              <img src={hawkLogo} alt="CodeHawk" />
            </div>
            <h2 className="auth-card-title">Review code smarter.</h2>
            <p className="auth-card-subtitle">
              Sign in with your GitHub account to connect repositories and run automated AI reviews on every pull request.
            </p>
          </div>

          {/* Error & Retry Banner */}
          {activeError && (
            <div className="auth-error-banner" role="alert">
              <div className="auth-error-icon">
                <AlertCircle size={18} />
              </div>
              <div className="auth-error-content">
                <p className="auth-error-text">{activeError}</p>
                <div className="auth-error-actions">
                  <button
                    type="button"
                    className="btn-error-retry"
                    onClick={handleGitHubClick}
                    disabled={isInitiating}
                  >
                    <RotateCw size={12} />
                    <span>Retry Login</span>
                  </button>
                  <button
                    type="button"
                    className="btn-error-dismiss"
                    onClick={handleDismissError}
                    aria-label="Dismiss error"
                  >
                    <X size={12} />
                    <span>Dismiss</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* GitHub Action CTA */}
          <GitHubLoginButton
            onInitiateLogin={handleGitHubClick}
            isLoading={isInitiating}
            disabled={isInitiating}
          />

          {/* Trust & Compliance Pills */}
          <div className="trust-badges">
            <div className="trust-item">
              <Shield size={14} />
              <span>Granular repository access</span>
            </div>
            <div className="trust-item">
              <Lock size={14} />
              <span>OAuth 2.0 Handshake</span>
            </div>
          </div>

        </div>
      </section>
    </div>
  );
}
