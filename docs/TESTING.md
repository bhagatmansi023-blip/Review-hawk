# Review-hawk — Manual Testing Checklist

Use this checklist to verify end-to-end behaviour against a **real GitHub repository**.
All automated tests run without network; this document covers what only a live integration can confirm.

---

## Prerequisites

| Item | Where |
|------|--------|
| GitHub App installed on your test repo | GitHub → Settings → GitHub Apps |
| `GITHUB_APP_ID` in `.env` | App settings → "App ID" |
| `GITHUB_PRIVATE_KEY_PATH` in `.env` | Downloaded `.pem` path |
| `GITHUB_WEBHOOK_SECRET` in `.env` | App settings → Webhooks |
| `GEMINI_API_KEY` in `.env` | Google AI Studio |
| Postgres DB running + migrated | `python manage.py migrate` |
| Celery worker running | `celery -A config worker -l info` |
| Django dev server running | `python manage.py runserver` |
| `ngrok` or equivalent tunnel for webhook | `ngrok http 8000` |

---

## 1. Webhook delivery

- [ ] Open (or push to) a PR in the test repo.
- [ ] In GitHub → App settings → Recent Deliveries, confirm a `pull_request.opened` or `pull_request.synchronize` event was received with **HTTP 200**.
- [ ] In Django logs, verify: `"Webhook received: event=pull_request action=opened"`.
- [ ] In the DB, confirm a `reviews_webhookevent` row with `processed=true`.

## 2. Duplicate delivery (idempotency)

- [ ] In GitHub → App settings → Recent Deliveries, redeliver the same webhook.
- [ ] Confirm the second delivery also returns **200** with `{"status": "skipped"}`.
- [ ] Confirm no duplicate `reviews_review` row was created.

## 3. Review posted as GitHub App

- [ ] In the PR timeline on GitHub, the review comment should appear posted by your **App name** (e.g. `Review-hawk[bot]`), **not** by your personal account.
- [ ] In Django logs, verify: `"Using GitHub App auth (installation_id=…)"`.
- [ ] No `"Using user OAuth token"` warning should appear unless you deliberately break App config.

## 4. Inline comments visible

- [ ] Open the PR's **Files changed** tab.
- [ ] Inline comments should appear on the exact lines that were added in the diff.
- [ ] At most 20 inline comments are posted per review (cap enforced).

## 5. DB rows after a successful review

Run in `python manage.py shell`:

```python
from reviews.models import Review, ReviewComment

r = Review.objects.latest("created_at")
print(r.status, r.github_review_id, r.posted_at, r.installation_id)
# Expect: completed  <non-null>  <non-null>  <your installation_id>

print(ReviewComment.objects.filter(review=r).count())
# At least 1 row expected for a non-trivial diff
```

## 6. Static analysis (tree-sitter)

- [ ] Open a PR that adds a `.py` file with at least one bare `except:` clause.
- [ ] In Django logs, verify: `"Running tree-sitter on 1 Python file(s)"`.
- [ ] In GitHub, verify a 🟡 inline comment with `[TS-PY-003]` appears on the bare-except line.

## 7. 422 fallback

To simulate a 422 (stale diff position):
- [ ] Temporarily patch `_post_github_review` to always raise `GithubException(422, …)` on the first call.
- [ ] Confirm the review is still posted (as summary-only) and `Review.status = completed`.
- [ ] Remove the patch.

## 8. Transient retry

To simulate a Gemini rate-limit:
- [ ] Temporarily patch `_call_gemini` to raise a Google API `ResourceExhausted` exception.
- [ ] Confirm `Review.status = running` (not failed) and Celery logs show a retry.
- [ ] After 3 retries, confirm `Review.status = failed` and `error_message` is set.
- [ ] Remove the patch.

## 9. Permanent failure

- [ ] Temporarily set `GEMINI_API_KEY` to an invalid value.
- [ ] Open a PR.
- [ ] Confirm `Review.status = failed` and `Review.error_message` contains a useful message.
- [ ] No Celery retry should appear (permanent failure).
- [ ] Restore the key.

## 10. Security: invalid webhook signature

- [ ] Use curl to send a fake webhook with a wrong signature:

```bash
curl -X POST http://localhost:8000/api/webhook/webhook/ \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: sha256=badbadbadbad" \
  -d '{"action":"opened"}'
```

- [ ] Confirm HTTP 403 is returned.
- [ ] Confirm no DB rows were created.

---

## Running the automated test suite

```bash
cd backend

# All tests (tree-sitter + pipeline)
.\\venv\\Scripts\\pytest reviews/tests/ -v

# Just pipeline tests
.\\venv\\Scripts\\pytest reviews/tests/test_pipeline.py -v

# Just tree-sitter tests
.\\venv\\Scripts\\pytest reviews/tests/test_tree_sitter_analyzer.py -v
```

Expected: **all tests pass with no network calls**.

---

## Suggested commit messages

After verifying all items above, use these commit messages:

```
feat(auth): use GitHub App installation token for posting reviews

feat(reviews): cap inline PR comments at 20, fallback on 422

feat(reviews): classify transient vs permanent errors, exponential retry

feat(db): add installation_id and posted_at to Review model (migration 0002)

test(pipeline): add integration tests for webhook, posting, retry, and DB rows

docs: add TESTING.md manual checklist
```
