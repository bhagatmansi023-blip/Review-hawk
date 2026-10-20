import { X, CheckCircle, Database, GitPullRequest } from 'lucide-react';

export default function PRContractModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div
      className="modal-overlay"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="pr-contract-title"
    >
      <div
        className="modal-content"
        style={{ maxWidth: '680px' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div className="modal-title" id="pr-contract-title">
            <GitPullRequest size={22} color="#6366f1" />
            <span>Pull Request API Contract Specification</span>
          </div>
          <button
            className="modal-close-btn"
            onClick={onClose}
            aria-label="Close modal"
          >
            <X size={20} />
          </button>
        </div>

        <p style={{ fontSize: '0.92rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          Specifications for the Django REST Framework backend teammate to implement Pull Request listings and details (Phase 4):
        </p>

        <div className="contract-code-block">
{`# 1. GET /api/repos/{repo_id}/pulls/
# Retrieves pull requests for a connected repository with optional filters
Query Parameters:
  ?state=open|closed|merged (optional, default: all)
  ?search=keyword (optional, filters title, number, author)
  ?page=1 (optional, DRF pagination)

Response 200 OK:
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "number": 42,
      "title": "Add OAuth callback handling and error boundaries",
      "author": "octocat",
      "state": "open",
      "html_url": "https://github.com/acme/core-api/pull/42",
      "latest_head_sha": "a1b2c3d4e5f6789012345678901234567890abcd",
      "source_branch": "feature/oauth",
      "target_branch": "main",
      "created_at": "2026-10-18T10:00:00Z",
      "updated_at": "2026-10-18T14:30:00Z",
      "latest_review": {
        "id": 10,
        "status": "completed",
        "summary": "AI code review completed. 0 critical vulnerabilities found.",
        "created_at": "2026-10-18T14:35:00Z"
      }
    }
  ]
}

# 2. GET /api/pull-requests/{id}/
# Retrieves full details and review history for a specific pull request
Response 200 OK:
{
  "id": 1,
  "number": 42,
  "title": "Add OAuth callback handling and error boundaries",
  "author": "octocat",
  "state": "open",
  "html_url": "https://github.com/acme/core-api/pull/42",
  "latest_head_sha": "a1b2c3d4e5f6789012345678901234567890abcd",
  "source_branch": "feature/oauth",
  "target_branch": "main",
  "created_at": "2026-10-18T10:00:00Z",
  "updated_at": "2026-10-18T14:30:00Z",
  "repository": {
    "id": 101,
    "name": "core-api",
    "owner": "acme",
    "full_name": "acme/core-api",
    "default_branch": "main"
  },
  "latest_review": {
    "id": 10,
    "status": "completed",
    "summary": "Clean code structure. No syntax regressions.",
    "llm_model": "gemini-1.5-pro",
    "input_tokens": 1420,
    "output_tokens": 340,
    "files_reviewed": 4,
    "created_at": "2026-10-18T14:35:00Z",
    "started_at": "2026-10-18T14:35:02Z",
    "finished_at": "2026-10-18T14:35:12Z"
  }
}`}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            <Database size={15} color="#6366f1" />
            <span>Maps directly to backend <code>PullRequest</code> and <code>Review</code> models in <code>repos/models.py</code></span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            <CheckCircle size={15} color="#22c55e" />
            <span>Frontend supports both DRF pagination (<code>PageNumberPagination</code>) and raw array responses</span>
          </div>
        </div>

        <div className="modal-footer" style={{ marginTop: '20px' }}>
          <button type="button" className="btn-primary" onClick={onClose}>
            Understood
          </button>
        </div>
      </div>
    </div>
  );
}
