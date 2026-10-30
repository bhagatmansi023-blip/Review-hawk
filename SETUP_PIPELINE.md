# How to get reviews working right now

## Step 1 — Start Celery (open a NEW terminal in backend/)

```powershell
cd "d:\Claude Code VS\pr hawk\Review-hawk\backend"
.\venv\Scripts\celery -A config worker -l info -P solo
```

> **`-P solo`** is required on Windows (no fork support).  
> Keep this terminal open — it must stay running.

---

## Step 2 — Expose your backend to GitHub via ngrok (NEW terminal)

```powershell
ngrok http 8000
```

Copy the `https://xxxx.ngrok-free.app` URL shown.

---

## Step 3 — Set that URL in your GitHub App settings

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → Review-hawk (or your app name)**
2. Under **Webhook URL**, set it to:  
   `https://xxxx.ngrok-free.app/api/webhook/webhook/`
3. Ensure **Webhook secret** matches `GITHUB_WEBHOOK_SECRET` in your `.env`
4. Click **Save**

---

## Step 4 — Verify your GitHub App is installed on both repos

1. On the same App page, click **Install App**
2. Confirm it's installed on `bhagatmansi023-blip/Review-hawk` and `bawahemangi/neetcode-submissions`
3. Grant access to **All repositories** or at minimum those two

---

## Step 5 — Test with the simulator (while Django is running)

With Django running in one terminal, run in another:

```powershell
cd "d:\Claude Code VS\pr hawk\Review-hawk\backend"
.\venv\Scripts\python simulate_webhook.py
```

This injects a fake PR event **directly** into Django, bypassing GitHub entirely.  
If Celery is running, you'll see the full pipeline execute in the Celery terminal.

---

## Step 6 — Open a real PR to test end-to-end

Open a pull request on your connected GitHub repo. Within ~30 seconds you should:
- See `pull_request.opened` in Django logs
- See Celery process the task
- See a review comment appear on the GitHub PR from your App
- See data in the dashboard

---

## Step 7 — Run the migration (if not done yet)

```powershell
.\venv\Scripts\python manage.py migrate
```

This applies the `0002_review_installation_id_posted_at` migration.

---

## Quick sanity check after Step 5

```powershell
.\venv\Scripts\python manage.py shell -c "
from reviews.models import Review, ReviewComment
from repos.models import PullRequest
print('PRs:', PullRequest.objects.count())
print('Reviews:', Review.objects.count())
for r in Review.objects.all():
    print(f'  Review {r.id}: status={r.status} comments={r.comments.count()}')
"
```
