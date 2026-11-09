# Pull request sync, review pipeline and dashboard

## The flow

```
GitHub PR ──(A) webhook ─────────────┐
            /api/webhook/            ├─> Django ─> PostgreSQL ─> Celery worker ─> Tree-sitter + Gemini ─> saved findings ─> GitHub review ─> React dashboard
GitHub PR ──(B) Sync Pull Requests ──┘
            POST /api/sync/
```

Both entry points save the same `PullRequest` rows and queue a `Review` per head commit (never two for the same commit).

## Why the dashboard showed 0 PRs and 0 reviews

1. **Every webhook crashed.** `WebhookEvent.outcome` existed in `models.py` but no migration created the column, so the first database insert of every delivery failed. No PR or review was ever stored.
2. **Webhooks were the only way in.** The register-time backfill read at most 5 PRs and swallowed errors, so already-open PRs never appeared.
3. **Reviews could not be trusted when they did run:** the diff was downloaded without credentials (private repos return 404), retries could leave a review "running" forever, a retry duplicated findings, and Tree-sitter failures were only logged.
4. **Celery ran inside the web request** unless `CELERY_TASK_ALWAYS_EAGER` was set (it defaulted to `DEBUG`), so a worker was never used and webhooks would time out.

## Sync Pull Requests (what the button does)

For every connected repository of the logged-in user:

1. Authenticate as the **GitHub App installation** (JWT -> installation token). If the App is not installed on that repo, fall back to the connecting user's OAuth token and **say so** in the result.
2. Fetch **all open PRs**, 100 per request, following pagination (safety cap `SYNC_MAX_PRS_PER_REPO`, default 500).
3. Create or update PRs: number, title, description, URL, state (open/closed/merged), author, head SHA, head branch, base branch, installation id.
4. Re-check PRs stored as open that GitHub no longer lists (closed or merged since).
5. Queue a review for each open PR whose current head commit has none. Failed reviews are retried; pending, running and completed ones are left alone.
6. Store status, PR count and any error on the repository. One failing repository never stops the others.

Repeated clicks: the button disables itself, and a per-repository database lock makes the backend refuse a second sync of the same repo (a lock older than 5 minutes is treated as dead).

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/sync/` | Sync every connected repo (body `{"review": false}` skips queueing). Returns totals, per-repo results, review progress, Celery status, warnings. `409` if a sync is already running |
| `GET /api/sync/status/[?celery=1]` | Last sync per repository and review progress |
| `POST /api/repos/<id>/sync/` | Sync one repository |
| `POST /api/pull-requests/<id>/review/` | Run or retry the review of one PR (`?force=1` to re-run a completed one) |
| `GET /api/pull-requests/` | PRs across all repositories, with review status |
| `GET /api/pull-requests/<id>/` | One PR with summary, health, findings, errors, warnings |
| `POST /api/webhook/` (also `/api/webhook/webhook/`) | GitHub webhook |

## Webhook behaviour

`opened`, `synchronize`, `reopened`: save the PR, queue a review unless this commit already has one (a `reopened` retries a failed review). `closed`: set `closed` or `merged`. Other actions only refresh the PR. Every delivery is stored with an `outcome` or an `error`; a delivery whose processing crashed can be redelivered from GitHub.

## Review execution

Diff (authenticated, falls back to the file list for huge diffs) -> Tree-sitter on changed Python files -> Gemini -> merge and dedupe -> save findings, health score -> post one GitHub review.

- **Gemini fails:** review is `failed` with the real error; nothing is saved or posted.
- **Temporary errors (quota, network, GitHub 5xx):** retried with backoff; after the last attempt the review is `failed` with the reason.
- **Tree-sitter fails on a file:** review continues; the problem is saved in `analysis_warnings` and shown on the PR page.
- **GitHub refuses the comment** (for example a missing permission): the analysis is kept, status stays `completed`, and `github_post_error` is shown on the PR page.

## Environment variables (`backend/.env`)

| Variable | Purpose |
|---|---|
| `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY_PATH` | GitHub App identity (keep the `.pem` outside the repo) |
| `GITHUB_WEBHOOK_SECRET` | Must equal the secret in the GitHub App settings |
| `GEMINI_API_KEY` | Gemini access |
| `GEMINI_MODEL` | Model name. Note: `settings.py` defaults to `gemini-2.5-flash` but `llm_reviewer.py` defaults to `gemini-3.8-flash`; set this explicitly. `check_pipeline` verifies it exists |
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Redis/Memurai, default `redis://localhost:6379/0` |
| `CELERY_TASK_ALWAYS_EAGER` | Now defaults to `False`. Leave unset in normal use |
| `WEBHOOK_URL` | Public tunnel URL ending in `/api/webhook/` |
| `SYNC_MAX_PRS_PER_REPO` | Optional, default 500 |

## GitHub App permissions

Repository permissions: **Pull requests: Read and write** (read PRs, post reviews), **Contents: Read-only** (file contents for Tree-sitter), **Metadata: Read-only**. Subscribe to the **Pull request** event. The App must be **installed on every connected repository** (the repository owner does this). Without "Pull requests: write" the analysis is still saved and the dashboard shows the post error.

## Run

```
# 1. Redis/Memurai running
cd backend
python manage.py migrate                       # REQUIRED: adds the missing webhook column and the sync fields
python manage.py check_pipeline                # tells you which link is broken
python manage.py runserver
celery -A config worker -l info -P solo        # second terminal (Windows: -P solo)
ngrok http 8000                                # optional, only for live webhooks
cd ../frontend && npm install && npm run dev
```

Then open the dashboard and click **Sync Pull Requests**.

## Tests

```
cd backend  && python -m pytest -q             # Django, Celery and API tests (GitHub and Gemini are mocked)
cd frontend && npm test && npm run lint && npm run build
```
