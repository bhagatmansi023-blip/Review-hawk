"""
python manage.py check_pipeline [--skip-network]

Checks every link of the review pipeline and says which one is broken:

  GitHub -> tunnel (ngrok/smee) -> Django webhook -> Redis -> Celery -> Gemini -> GitHub comment -> dashboard

Run it whenever "nothing is being reviewed". It never prints secret values.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from decouple import config
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

OK, BAD, WARN = "  [ OK ]", "  [FAIL]", "  [WARN]"


class Command(BaseCommand):
    help = "Diagnose why pull requests are not being reviewed."

    def add_arguments(self, parser):
        parser.add_argument("--skip-network", action="store_true",
                            help="Skip the Redis, Celery, GitHub and Gemini checks (used by the tests).")

    # -- helpers -------------------------------------------------------------
    def out(self, mark, text):
        style = {OK: self.style.SUCCESS, BAD: self.style.ERROR, WARN: self.style.WARNING}[mark]
        self.stdout.write(style(f"{mark} {text}"))
        if mark == BAD:
            self.problems.append(text)

    def title(self, text):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{text}"))

    # -- main ----------------------------------------------------------------
    def handle(self, *args, **opts):
        self.problems: list[str] = []
        self.check_config()
        self.check_models_and_db()
        if not opts["skip_network"]:
            self.check_redis_and_celery()
            self.check_github_app()
            self.check_gemini()
        else:
            self.check_celery_mode()
        self.check_data()

        self.stdout.write("")
        if self.problems:
            self.stdout.write(self.style.ERROR(f"{len(self.problems)} problem(s) found. Fix them from the top down:"))
            for i, p in enumerate(self.problems, 1):
                self.stdout.write(self.style.ERROR(f"  {i}. {p}"))
        else:
            self.stdout.write(self.style.SUCCESS("No problems found."))

    # -- 1. configuration ----------------------------------------------------
    def check_config(self):
        self.title("1. Configuration (.env)")
        for key in ("GITHUB_WEBHOOK_SECRET", "GITHUB_APP_ID", "GITHUB_PRIVATE_KEY_PATH", "GEMINI_API_KEY"):
            if config(key, default=""):
                self.out(OK, f"{key} is set")
            else:
                self.out(BAD, f"{key} is empty or missing in backend/.env")
        key_path = config("GITHUB_PRIVATE_KEY_PATH", default="")
        if key_path and not Path(key_path).is_file():
            self.out(BAD, "GITHUB_PRIVATE_KEY_PATH points to a file that does not exist")
        url = config("WEBHOOK_URL", default="")
        if url:
            path = urlparse(url).path.rstrip("/")
            if path in ("/api/webhook", "/api/webhook/webhook"):
                self.out(OK, f"WEBHOOK_URL host is {urlparse(url).netloc}; it must equal the Webhook URL in the GitHub App settings")
            else:
                self.out(WARN, "WEBHOOK_URL should end with /api/webhook/ (what GitHub calls)")
        else:
            self.out(WARN, "WEBHOOK_URL is not set (only needed to create per-repository webhooks)")

    # -- 2. models and database ---------------------------------------------
    def check_models_and_db(self):
        self.title("2. Models and database")
        from reviews.models import Review
        have = {f.name for f in Review._meta.get_fields()}
        missing = {"pull_request", "head_sha", "status", "summary"} - have
        if missing:
            self.out(BAD, "The Review model is missing fields " + ", ".join(sorted(missing)) +
                     ". reviews/models.py probably defines 'class Review' twice. Every webhook will crash.")
        else:
            self.out(OK, "Review model has all required fields")
        try:
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if plan:
                names = ", ".join(f"{m.app_label}.{m.name}" for m, _ in plan[:4])
                self.out(BAD, f"{len(plan)} migration(s) not applied ({names}). Run: python manage.py migrate "
                              "(an unapplied migration makes every webhook fail with a database error)")
            else:
                self.out(OK, "Database is reachable and all migrations are applied")
        except Exception as exc:  # noqa: BLE001
            self.out(BAD, f"Cannot reach the database: {exc.__class__.__name__}")

    # -- 3. redis + celery ---------------------------------------------------
    def check_celery_mode(self):
        if settings.CELERY_TASK_ALWAYS_EAGER:
            self.out(WARN, "Celery is in eager mode: reviews run inside the web request and no worker is used. "
                           "Set CELERY_TASK_ALWAYS_EAGER=False in .env.")

    def check_redis_and_celery(self):
        self.title("3. Redis and Celery worker")
        self.check_celery_mode()
        from config.celery import app
        try:
            with app.connection_for_write() as conn:
                conn.ensure_connection(max_retries=1, timeout=3)
            self.out(OK, "Redis broker is reachable")
        except Exception as exc:  # noqa: BLE001
            self.out(BAD, f"Redis is not reachable ({exc.__class__.__name__}). Start Redis/Memurai, "
                          "otherwise reviews can never be queued.")
            return
        try:
            workers = app.control.inspect(timeout=2).ping() or {}
        except Exception:  # noqa: BLE001
            workers = {}
        if workers:
            self.out(OK, f"{len(workers)} Celery worker(s) online")
        else:
            self.out(BAD, "No Celery worker is running. Start one: celery -A config worker -l info -P solo")

    # -- 4. github app -------------------------------------------------------
    def check_github_app(self):
        self.title("4. GitHub App")
        app_id, key_path = config("GITHUB_APP_ID", default=""), config("GITHUB_PRIVATE_KEY_PATH", default="")
        if not (app_id and key_path and Path(key_path).is_file()):
            self.out(WARN, "Skipped (app id or private key missing)")
            return
        from repos.models import Repository
        from reviews.github_app import GitHubAccessError, installation_for_repo
        try:
            from github import Auth, GithubIntegration
            auth = Auth.AppAuth(int(app_id), Path(key_path).read_text())
            installs = list(GithubIntegration(auth=auth).get_installations())
        except Exception as exc:  # noqa: BLE001
            self.out(BAD, f"Could not authenticate as the GitHub App ({exc.__class__.__name__}). "
                          "Check GITHUB_APP_ID and the .pem file.")
            return
        if not installs:
            self.out(BAD, "The GitHub App is not installed on any account. Open the app page -> Install App.")
        for inst in installs:
            self.out(OK, f"Installed on {inst.account.login} (installation {inst.id}, repos: {inst.repository_selection})")
        for repo in Repository.objects.filter(is_enabled=True):
            try:
                installation_id, _ = installation_for_repo(repo.owner, repo.name)
                self.out(OK, f"{repo.full_name}: App installed (installation {installation_id})")
            except GitHubAccessError as exc:
                self.out(BAD, f"{repo.full_name}: {exc}")

    # -- 5. gemini -----------------------------------------------------------
    def check_gemini(self):
        self.title("5. Gemini")
        key, model = config("GEMINI_API_KEY", default=""), config("GEMINI_MODEL", default="")
        from reviews import llm_reviewer
        model = model or llm_reviewer.GEMINI_MODEL
        if not key or llm_reviewer.genai is None:
            self.out(WARN, "Skipped (no API key, or google-generativeai is not installed)")
            return
        try:
            llm_reviewer.genai.configure(api_key=key)
            names = {m.name.removeprefix("models/") for m in llm_reviewer.genai.list_models()
                     if "generateContent" in getattr(m, "supported_generation_methods", [])}
        except Exception as exc:  # noqa: BLE001
            self.out(BAD, f"Could not reach Gemini ({exc.__class__.__name__}): check GEMINI_API_KEY and your network")
            return
        if model in names:
            self.out(OK, f"Gemini model '{model}' exists and supports generateContent")
        else:
            flash = ", ".join(sorted(n for n in names if "flash" in n)[:6]) or "none found"
            self.out(BAD, f"Gemini model '{model}' is not available to this API key. Set GEMINI_MODEL to one of: {flash}")

    # -- 6. data -------------------------------------------------------------
    def check_data(self):
        self.title("6. What the database has seen")
        from django.contrib.auth import get_user_model
        from repos.models import PullRequest, Repository
        from reviews.models import Review, WebhookEvent

        repos = list(Repository.objects.select_related("user"))
        if not repos:
            self.out(BAD, "No repository is connected. Open Repositories in the dashboard and connect one.")
        for r in repos:
            state = "enabled" if r.is_enabled else "DISABLED"
            self.out(OK if r.is_enabled else WARN, f"{r.full_name} (github id {r.github_repo_id}) {state}, "
                                                    f"connected by user '{r.user.username}'")
            if r.last_sync_status == "error":
                self.out(WARN, f"{r.full_name}: last sync failed: {r.last_sync_error[:160]}")
            elif r.last_sync_status == "ok":
                self.stdout.write(f"       last sync: {r.last_sync_count} open PR(s) fetched at {r.last_synced_at:%Y-%m-%d %H:%M}")
            else:
                self.stdout.write("       never synced: use 'Sync Pull Requests' on the dashboard")
        self.stdout.write(f"       users: {get_user_model().objects.count()}, "
                          f"pull requests: {PullRequest.objects.count()}, reviews: {Review.objects.count()}")
        statuses = Counter(Review.objects.values_list("status", flat=True))
        if statuses:
            self.stdout.write("       review statuses: " + ", ".join(f"{k}={v}" for k, v in statuses.items()))
            for rev in Review.objects.filter(status="failed").exclude(error_message="")[:3]:
                self.out(WARN, f"Review {rev.pk} failed: {rev.error_message[:160]}")
            for rev in Review.objects.exclude(github_post_error="")[:3]:
                self.out(WARN, f"Review {rev.pk} analysed but not posted to GitHub: {rev.github_post_error[:160]}")
            if statuses.get("pending"):
                self.out(WARN, "Reviews stuck in 'pending' mean the Celery worker is not picking them up.")

        total_events = WebhookEvent.objects.count()
        if total_events == 0:
            self.out(WARN, "No webhook from GitHub has arrived yet (fine if you rely on 'Sync Pull Requests'). "
                           "For live updates: keep the tunnel running, set the GitHub App Webhook URL to "
                           "https://<tunnel>/api/webhook/ with the same secret as GITHUB_WEBHOOK_SECRET, and "
                           "subscribe to 'Pull request' (GitHub App -> Advanced -> Recent deliveries shows errors).")
        else:
            self.out(OK, f"{total_events} webhook event(s) received. Latest:")
            for e in WebhookEvent.objects.all()[:5]:
                detail = f"ERROR {e.error[:90]}" if e.error else (e.outcome or ("repo matched" if e.repository_id else "repo NOT registered"))
                self.stdout.write(f"       {e.received_at:%Y-%m-%d %H:%M} {e.event_type}.{e.action} processed={e.processed} {detail}")
            if WebhookEvent.objects.exclude(error="").exists():
                self.out(WARN, "Some webhook deliveries crashed while being processed (see ERROR above). Redeliver them from GitHub after fixing.")
            if not WebhookEvent.objects.filter(event_type="pull_request").exists():
                self.out(WARN, "Webhooks arrived but none were pull_request events. Subscribe the app to 'Pull request'.")
