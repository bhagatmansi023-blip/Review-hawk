import { Navigate, useLocation, Outlet } from 'react-router-dom';
import { useAuth } from '../../context/useAuth';
import hawkLogo from '../../assets/hawk-logo.jpg';

export default function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="auth-loading-screen" role="status" aria-live="polite">
        <div className="auth-loading-card">
          <div className="auth-loading-logo">
            <img src={hawkLogo} alt="CodeHawk" />
          </div>
          <div className="loading-spinner-ring" aria-hidden="true" />
          <h3 className="loading-title">Verifying Authentication</h3>
          <p className="loading-subtitle">
            Validating your CodeHawk session with GitHub...
          </p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    // Preserve intended target in location state so user can be redirected back after sign-in
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <Outlet />;
}
