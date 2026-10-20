import { FileCode, X, CheckCircle, Database } from 'lucide-react';
import { useRepos } from '../../context/useRepos';

export default function RepoContractModal() {
  const { isContractModalOpen, setIsContractModalOpen } = useRepos();

  if (!isContractModalOpen) return null;

  return (
    <div className="modal-overlay" onClick={() => setIsContractModalOpen(false)} role="dialog" aria-modal="true" aria-labelledby="repo-contract-title">
      <div className="modal-content" style={{ maxWidth: '640px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title" id="repo-contract-title">
            <FileCode size={22} color="#6366f1" />
            <span>Repository API Contract Specification</span>
          </div>
          <button
            className="modal-close-btn"
            onClick={() => setIsContractModalOpen(false)}
            aria-label="Close modal"
          >
            <X size={20} />
          </button>
        </div>

        <p style={{ fontSize: '0.92rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          Specifications for the Django REST Framework backend teammate to implement repository discovery and connection:
        </p>

        <div className="contract-code-block">
{`# 1. GET /api/repos/
# Returns list of repositories accessible to authenticated user
Response 200 OK:
[
  {
    "id": 101,
    "github_repo_id": 89234120,
    "name": "core-api",
    "full_name": "acme/core-api",
    "owner": "acme",
    "is_private": false,
    "default_branch": "main",
    "language": "Python",
    "is_connected": false
  }
]

# 2. POST /api/repos/connect/
# Connects repository and enables CodeHawk bot
Request Body:
{
  "github_repo_id": 89234120,
  "owner": "acme",
  "name": "core-api",
  "default_branch": "main",
  "is_private": false
}
Response 201 Created:
{
  "id": 1,
  "github_repo_id": 89234120,
  "full_name": "acme/core-api",
  "is_enabled": true,
  "created_at": "2026-10-13T10:00:00Z"
}

# 3. GET /api/repos/connected/
# Returns currently connected repositories for user`}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            <Database size={16} color="#38bdf8" />
            <span>Maps directly to backend <code>repos.models.Repository</code> model</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            <CheckCircle size={16} color="#22c55e" />
            <span>Frontend service & context integration is fully prepared</span>
          </div>
        </div>

        <div className="modal-footer">
          <button
            type="button"
            className="btn-primary"
            onClick={() => setIsContractModalOpen(false)}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
