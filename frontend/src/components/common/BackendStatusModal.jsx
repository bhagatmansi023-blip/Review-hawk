import { X, GitBranch, Server, ShieldCheck, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function BackendStatusModal({ isOpen, onClose }) {
  const navigate = useNavigate();

  if (!isOpen) return null;

  const handleExplorePlaceholders = () => {
    onClose();
    navigate('/dashboard');
  };

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title" id="modal-title">
            <Server size={22} color="#6366f1" />
            <span>GitHub OAuth Integration Status</span>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close modal">
            <X size={20} />
          </button>
        </div>

        <p style={{ fontSize: '0.92rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          The <strong>Review Hawk</strong> frontend foundation is completely set up. To finish genuine sign-in, the Django REST Framework backend will handle the client-secret exchange.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <h4 style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            Contract Required from Backend Team (Django REST Framework):
          </h4>
          <div className="contract-code-block">
{`# Required Backend Endpoints
1. GET  /api/auth/github/url/
   -> Returns GitHub authorize URL with CSRF state
2. POST /api/auth/github/callback/ { code, state }
   -> Exchanges code with GitHub, returns JWT or Session Token
3. GET  /api/auth/user/
   -> Returns current authenticated developer profile`}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            <ShieldCheck size={16} color="#22c55e" />
            <span>Client secret is strictly protected on the backend</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            <GitBranch size={16} color="#38bdf8" />
            <span>Configured VITE_API_BASE_URL: {import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}</span>
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" className="btn-secondary" onClick={onClose}>
            Back to Login
          </button>
          <button type="button" className="btn-primary" onClick={handleExplorePlaceholders} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>Explore App Routes</span>
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
