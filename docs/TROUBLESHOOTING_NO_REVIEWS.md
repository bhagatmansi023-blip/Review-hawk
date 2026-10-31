# Nothing is being reviewed / no pull requests show up

## Start here

```bash
cd backend
python manage.py check_pipeline
```

It checks every link and prints `[ OK ]`, `[WARN]` or `[FAIL]` with the fix. It never prints secrets.

## The pipeline (a break at any link means nothing shows up)

```
GitHub  ->  tunnel (ngrok / smee)  ->  Django webhook  ->  Redis  ->  Celery worker  ->  Gemini  ->  comment on the PR  ->  dashboard
```

Start order: **Redis, Django, Celery worker, tunnel, frontend**.

| Process | Command |
|---|---|
| Redis | `docker run -p 6379:6379 redis` (or Memurai / WSL on Windows) |
| Django | `python manage.py runserver` |
| Celery | `celery -A config worker -l info -P solo` (`-P solo` on Windows) |
| Tunnel | `ngrok http 8000` |

## GitHub App settings that must match

- **Webhook URL** = `https://<your-tunnel>/api/webhook/webhook/` (free ngrok URLs change every restart, so update it each time)
- **Webhook secret** = `GITHUB_WEBHOOK_SECRET` in `backend/.env`
- **Subscribe to events**: *Pull request*
- The app must be **installed** on the repository (the repo owner does this)
- Check **GitHub App -> Advanced -> Recent deliveries**: `403` = secret mismatch, `404` = wrong URL path, no entries = GitHub cannot reach your tunnel

## Use the dashboard without waiting for webhooks

- **Pull Requests -> Sync from GitHub** imports the repo's existing PRs and queues reviews for open ones.
- **Pull request page -> Review now / Retry review / Re-run review** reviews that PR's latest commit. The page updates by itself while the review runs.

## Reading the symptoms

| What you see | Cause |
|---|---|
| Dashboard shows 0 reviews and 0 PRs | No webhook ever created a review (see the pipeline above), or the Review model was broken |
| Review stuck on "pending" | Celery worker is not running |
| Review "failed" with "Is Redis running?" | Redis is not running |
| Webhook log says "NOT registered" | Connect that repository on the Repositories page |
| Webhook log says signature rejected | Secret in `.env` differs from the GitHub App secret |

## History: two bugs fixed in this change

1. `reviews/models.py` defined `class Review` twice (a pasted snippet), so `Review` had no `pull_request`, `head_sha` or `status` fields and every webhook crashed. `test_review_model_has_the_fields_the_webhook_needs` now guards against it.
2. `merge_and_dedupe` in `llm_reviewer.py` had been overwritten by an older version, so its tests failed. The newer version is restored.
