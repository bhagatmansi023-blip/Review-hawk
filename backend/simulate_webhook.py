"""
simulate_webhook.py
====================
Sends a fake `pull_request.opened` webhook to YOUR OWN running Django server
so you can test the full pipeline (webhook → Celery → Gemini → GitHub review)
without needing GitHub to actually deliver the event.

Usage (from backend/ directory, with Django server + Celery running):
    python simulate_webhook.py

It will:
1. Pick the first enabled repository from the DB
2. Use the real GITHUB_WEBHOOK_SECRET to sign the payload
3. POST to http://127.0.0.1:8000/api/webhook/webhook/
4. Print the response so you know if it worked
"""
import hashlib
import hmac
import json
import os
import sys
import urllib.request
import urllib.error

# ── Setup Django ─────────────────────────────────────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from decouple import config
from repos.models import Repository
from reviews.models import PullRequest, Review

# ── Config ───────────────────────────────────────────────────────────────────
WEBHOOK_URL = "http://127.0.0.1:8000/api/webhook/webhook/"
WEBHOOK_SECRET = config("GITHUB_WEBHOOK_SECRET", default="")

if not WEBHOOK_SECRET:
    print("❌  GITHUB_WEBHOOK_SECRET is not set in .env — cannot sign the payload.")
    sys.exit(1)

# ── Pick a repo ───────────────────────────────────────────────────────────────
repo = Repository.objects.filter(is_enabled=True).first()
if not repo:
    print("❌  No enabled repository found in DB. Connect a repo first.")
    sys.exit(1)

print(f"✅  Using repository: {repo.owner}/{repo.name} (github_id={repo.github_repo_id})")

# Use a fake PR number unlikely to clash with real ones
fake_pr_number = 9999
fake_sha = "deadbeef" * 5  # 40 chars

# ── Build payload ─────────────────────────────────────────────────────────────
payload = {
    "action": "opened",
    "installation": {"id": 12345678},        # fake installation id
    "repository": {
        "id": repo.github_repo_id,
        "full_name": f"{repo.owner}/{repo.name}",
    },
    "pull_request": {
        "number": fake_pr_number,
        "title": "[TEST] Simulated PR — pipeline smoke test",
        "head": {"sha": fake_sha},
        "user": {"login": "simulate-webhook-script"},
        "html_url": f"https://github.com/{repo.owner}/{repo.name}/pull/{fake_pr_number}",
        "state": "open",
        "body": "This is a simulated pull request to test the CodeHawk review pipeline end-to-end.",
    },
}

body = json.dumps(payload).encode("utf-8")

# ── Sign the payload ──────────────────────────────────────────────────────────
sig = "sha256=" + hmac.new(
    WEBHOOK_SECRET.encode("utf-8"), msg=body, digestmod=hashlib.sha256
).hexdigest()

print(f"📦  Payload size: {len(body)} bytes")
print(f"🔐  Signature: {sig[:30]}...")

# ── POST to the webhook endpoint ──────────────────────────────────────────────
req = urllib.request.Request(
    WEBHOOK_URL,
    data=body,
    headers={
        "Content-Type": "application/json",
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": "simulate-001",
        "X-Hub-Signature-256": sig,
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        response_body = resp.read().decode()
        print(f"\n✅  HTTP {resp.status} — {response_body}")
except urllib.error.HTTPError as e:
    print(f"\n❌  HTTP {e.code} — {e.read().decode()}")
except urllib.error.URLError as e:
    print(f"\n❌  Could not connect to {WEBHOOK_URL}: {e.reason}")
    print("    Make sure Django is running: python manage.py runserver")

# ── Show DB state after ───────────────────────────────────────────────────────
print("\n── DB state after simulation ─────────────────────────────────────────")
pr_count = PullRequest.objects.count()
rev_count = Review.objects.count()
print(f"  PullRequest rows: {pr_count}")
print(f"  Review rows:      {rev_count}")

latest = Review.objects.order_by("-created_at").first()
if latest:
    print(f"  Latest review: id={latest.id} status={latest.status} pr=#{latest.pull_request.number}")
    print(f"  Comments:      {latest.comments.count()}")
    print(f"\n  → Open http://localhost:5173/pull-requests and look for PR #{fake_pr_number}")
