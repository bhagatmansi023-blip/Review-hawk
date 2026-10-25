import { FileCode, X, CheckCircle, Database } from 'lucide-react';
import { useRepos } from '../../context/useRepos';

export default function RepoContractModal() {
  const { isContractModalOpen, setIsContractModalOpen } = useRepos();

  if (!isContractModalOpen) return null;

  return (
    <div className="modal-overlay" onClick={() => setIsContractModalOpen(false)} role="dialog" aria-modal="true" aria-labelledby="repo-contract-title">
      <div className="modal-content" style={{ maxWidth: '680px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title" id="repo-contract-title">
            <FileCode size={22} color="#6366f1" />
            <span>CodeHawk Django Repository API Endpoints</span>
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
          Specifications of the Django REST Framework endpoints for GitHub repository listing, registration, and disconnection:
        </p>

        <div className="contract-code-block">
{`# 1. GET /api/repos/
# Returns list of repositories accessible to authenticated user
Response 200 OK:
[
  {
    "github_repo_id": 89234120,
    "owner": "acme",
    "name": "core-api",
    "full_name": "acme/core-api",
    "default_branch": "main",
    "is_private": false,
    "html_url": "https://github.com/acme/core-api",
    "description": "Core backend API services",
    "registered": true
  }
]

# 2. POST /api/repos/register/
# Registers webhook on GitHub repository and saves in database
Request Body:
{
  "repos": [
    {
      "github_repo_id": 89234120,
      "owner": "acme",
      "name": "core-api"
    }
  ]
}
Response 200 OK:
{
  "results": [
    {
      "full_name": "acme/core-api",
      "success": true,
      "detail": "Webhook registered successfully.",
      "repo": {
        "id": 1,
        "github_repo_id": 89234120,
        "owner": "acme",
        "name": "core-api",
        "full_name": "acme/core-api",
        "default_branch": "main",
        "is_private": false,
        "is_enabled": true
      }
    }
  ]
}

# 3. DELETE /api/repos/<int:github_repo_id>/unregister/
# Removes webhook from GitHub and disables repository in database
Response 200 OK:
{
  "detail": "Webhook removed and acme/core-api disabled."
}`}
        </div>

        <div className="modal-info-box" style={{ marginTop: '16px' }}>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
            <Database size={18} color="#6366f1" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                Backend Teammate Implementation Note
              </div>
              <div style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', marginTop: '4px', lineHeight: 1.5 }}>
                Ensure <code>GitHubRepoSerializer</code> in <code>backend/repos/serializers.py</code> includes <code>registered = serializers.BooleanField(default=False)</code> so that DRF preserves the registered flag computed by <code>ListGitHubReposView</code>.
              </div>
            </div>
          </div>
        </div>

        <div className="modal-footer" style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end' }}>
          <button
            type="button"
            className="btn-primary"
            onClick={() => setIsContractModalOpen(false)}
          >
            <CheckCircle size={15} />
            <span>Understood</span>
          </button>
        </div>
      </div>
    </div>
  );
}
