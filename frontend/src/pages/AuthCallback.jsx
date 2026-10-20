import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { AlertCircle, CheckCircle2, ArrowRight, RotateCw, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/useAuth';
import authService from '../services/auth';
import hawkLogo from '../assets/hawk-logo.jpg';

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { setUserSession } = useAuth();

  const code = searchParams.get('code');
  const state = searchParams.get('state');
  const oauthError = searchParams.get('error');
  const errorDescription = searchParams.get('error_description');

  const [status, setStatus] = useState('processing'); // 'processing' | 'success' | 'error'
  const [errorMessage, setErrorMessage] = useState(null);
  const [errorDetails, setErrorDetails] = useState(null);
  const exchangeAttemptedRef = useRef(false);

  const processCallback = useCallback(async () => {
    // 1. Handle GitHub error parameter (e.g. user denied permissions)
    if (oauthError) {
      setStatus('error');
      setErrorMessage(
        oauthError === 'access_denied'
          ? 'GitHub authorization was denied or cancelled.'
          : `GitHub error: ${oauthError}`
      );
      setErrorDetails(
        errorDescription || 'The authorization request was not approved on GitHub.'
      );
      return;
    }

    // 2. Validate that a code is present
    if (!code) {
      setStatus('error');
      setErrorMessage('Missing authorization code');
      setErrorDetails('No OAuth authorization code was provided in the GitHub callback redirect.');
      return;
    }

    // 3. Attempt token exchange with Django backend
    setStatus('processing');
    try {
      const response = await authService.handleOAuthCallback(code, state);
      setStatus('success');
      if (response?.user) {
        setUserSession(response.user);
      }
      // Redirect to dashboard after a brief confirmation
      setTimeout(() => {
        navigate('/dashboard', { replace: true });
      }, 1200);
    } catch (err) {
      setStatus('error');
      setErrorMessage('Backend Code Exchange Pending');
      setErrorDetails(
        err.message ||
        'The temporary code from GitHub could not be exchanged. Please verify that the Django backend server is running and the exchange endpoint (POST /api/auth/github/callback/) is implemented.'
      );
    }
  }, [code, state, oauthError, errorDescription, navigate, setUserSession]);

  useEffect(() => {
    if (!exchangeAttemptedRef.current) {
      exchangeAttemptedRef.current = true;
      processCallback();
    }
  }, [processCallback]);

  return (
    <div className="login-page">
      <div className="callback-card" role="status" aria-live="polite">
        <div className="auth-card-avatar" style={{ margin: '0 auto' }}>
          <img src={hawkLogo} alt="CodeHawk" />
        </div>

        {status === 'processing' && (
          <div className="callback-body">
            <div className="loading-spinner-ring" aria-hidden="true" />
            <h2 className="callback-title">Completing GitHub Sign In</h2>
            <p className="callback-subtitle">
              Exchanging authorization code with CodeHawk backend services...
            </p>
            <div className="callback-hint">
              <ShieldCheck size={16} />
              <span>Validating OAuth handshake securely</span>
            </div>
          </div>
        )}

        {status === 'success' && (
          <div className="callback-body">
            <div className="callback-icon-success">
              <CheckCircle2 size={40} />
            </div>
            <h2 className="callback-title">Authentication Successful</h2>
            <p className="callback-subtitle">
              Welcome back to CodeHawk. Redirecting to your dashboard...
            </p>
            <Link to="/dashboard" className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', marginTop: '12px' }}>
              <span>Continue to Dashboard</span>
              <ArrowRight size={16} />
            </Link>
          </div>
        )}

        {status === 'error' && (
          <div className="callback-body">
            <div className="callback-icon-error">
              <AlertCircle size={40} />
            </div>
            <h2 className="callback-title">{errorMessage}</h2>
            <p className="callback-subtitle">{errorDetails}</p>

            <div className="callback-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  exchangeAttemptedRef.current = false;
                  processCallback();
                }}
              >
                <RotateCw size={14} />
                <span>Retry Exchange</span>
              </button>

              <Link to="/login" className="btn-primary">
                Return to Login
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
