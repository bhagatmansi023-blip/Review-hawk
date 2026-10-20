import { X, GitBranch, Server, ShieldCheck, CheckCircle } from 'lucide-react';

export default function BackendStatusModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title" id="modal-title">
            <Server size={22} color="#6366f1" />
            <span>GitHub OAuth Integration Architecture</span>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close modal">
            <X size={20} />
          </button>
        </div>

        <p style={{ fontSize: '0.92rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          <strong>CodeHawk</strong> authenticates with GitHub via the Django backend using <code>django-allauth</code>. Client secrets are never exposed to the frontend.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <h4 style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            Active Flow Discovered in Backend:
          </h4>
          <div className="contract-code-block">
{`# 1. OAuth Initiation (Configured in Django Allauth)
GET /accounts/github/login/?process=login
-> Redirects to GitHub OAuth authorize with scopes:
   'read:user', 'user:email', 'repo'

# 2. GitHub Callback (Managed by Django)
GET /accounts/github/login/callback/?code=...&state=...
-> Exchanges code with GitHub using server GITHUB_CLIENT_SECRET
-> Sets HttpOnly session cookie (sessionid)
-> Redirects browser to LOGIN_REDIRECT_URL:
   http://localhost:5173/dashboard`}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <h4 style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            Outstanding Items for Backend Teammate:
          </h4>
          <div className="contract-code-block">
{`# 3. Session Check REST Endpoint (Needed for SPA user profile)
GET /api/auth/user/
-> Returns: { "id": 1, "username": "octocat", "email": "...", "avatar_url": "..." }

# 4. CORS & Cookie Settings (in backend/config/settings.py)
MIDDLEWARE: Add 'corsheaders.middleware.CorsMiddleware'
CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173"]`}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            <ShieldCheck size={16} color="#22c55e" />
            <span>Client secret is strictly protected on the Django backend</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            <CheckCircle size={16} color="#38bdf8" />
            <span>Frontend routes and ProtectedRoute gates are fully wired</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            <GitBranch size={16} color="#818cf8" />
            <span>Backend Base URL: {import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}</span>
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" className="btn-primary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
