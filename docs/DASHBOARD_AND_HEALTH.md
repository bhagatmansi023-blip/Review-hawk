# Dashboard, review history and PR health scoring

This document covers the Phase 4 / 5 work: charts, real review history, Tree-sitter
findings next to AI findings, and the rule-based health score.

## 1. What the user sees

| Page | What it shows |
|---|---|
| Dashboard | Headline stats, issues-over-time chart, severity donut, AI-vs-Tree-sitter split, health grades, recent reviews |
| Analytics | The same charts plus category breakdown and a per-repository table, with a 7/30/90-day range and repo filter |
| Reviews | Full review history with search, status/repo filters and pagination |
| Pull request details | Health score ring with the reason for every point, and all findings grouped by file with filters for AI review / Tree-sitter / severity |

Every finding shows where it came from: an **AI review** badge, or a **Tree-sitter** badge with the rule name.

## 2. API (all read-only, login required, scoped to the logged-in user's repos)

| Endpoint | Purpose |
|---|---|
| `GET /api/repos/<repo_id>/pulls/?state=&search=&page=` | PRs of one repo with their latest review (accepts the local id or GitHub's repo id) |
| `GET /api/pull-requests/<id>/` | One PR: latest review with every finding, health breakdown, review history |
| `GET /api/reviews/?repo=&status=&q=&page=` | Review history |
| `GET /api/reviews/<id>/` | One review with every finding |
| `GET /api/stats/?days=30&repo=<id>` | Totals and chart series (see below) |

`/api/stats/` returns: `totals`, `severity_breakdown`, `category_breakdown`, `source_breakdown`
(AI vs Tree-sitter), `top_rules`, `health_distribution`, `issues_over_time` (one row per day,
zero-filled), `per_repository` and `recent_reviews`.

Findings carry: `severity` (error / warning / info), `category`, `source` (`llm` / `static`),
`source_label`, `rule_id` and `rule_label` (Tree-sitter only), `message`, `suggestion`.

## 3. PR health score (`backend/reviews/health_scorer.py`)

Rule-based, no machine learning. The score starts at **100** and each signal adds or removes points.
The result is clamped to 0-100 and mapped to a grade. It is calculated for every review after the
AI and Tree-sitter findings are merged, saved on the review (`health_score`, `health_grade`,
`health_report`) and appended to the GitHub review summary.

| Signal | Rule | Points |
|---|---|---|
| Size | 100 lines or fewer changed | +5 |
| | 301-600 / 601-1000 / over 1000 lines | -8 / -18 / -30 (see config for exact bands) |
| File sprawl | 6-15 files / over 15 files | -4 / -12 |
| Tests | a test file is touched | +5 |
| | over 50 source lines changed and no test file touched | -15 |
| Description | under 20 characters / 100 characters or more | -8 / +3 |
| Tree-sitter | unused import (each, max -10) | -2 |
| | long function (each, max -15) | -5 |
| | bare or empty `except` (each, max -24) | -8 |
| | deep nesting (each, max -24) | -8 |
| | hardcoded secret (each, max -60) | -30 |
| AI review | error (each, max -50) / warning (each, max -30) / info (each, max -10) | -20 / -8 / -2 |

Grades: **A+** 90+, **A** 80+, **B** 70+, **C** 60+, **D** 40+, **F** below 40.

Caps matter: without them, 40 unused imports would erase a PR's score.

### Tuning

Every weight and threshold is in `HealthScorerConfig`. To tune:

1. Change a value (for example `static_rules["TS-PY-005"]["per"]`).
2. Run `pytest reviews/tests/test_health_scorer.py`. The `SCENARIOS` table lists realistic PRs and the
   grade each should get, so you can see which ones moved.
3. Add or edit a scenario to record the behaviour you want.

## 4. Running the tests

```bash
# backend (no Postgres, Redis or network needed: tests use in-memory SQLite)
cd backend
pytest

# frontend
cd frontend
npm test
npm run lint
npm run build
```

`backend/config/test_settings.py` forces SQLite so the suite runs on any machine, even when
`backend/.env` points at a real Postgres server.

## 5. Migration

```bash
cd backend
python manage.py migrate     # applies reviews/0003_review_health
```

Existing reviews keep an empty health score; new reviews get one.

## 6. Known limits

- Tree-sitter rules and the scorer's rule ids cover Python only.
- `source_branch` is `null` in the API because the webhook handler does not store it yet.
- Scores depend on the thresholds above; they are a guide for reviewers, not a verdict.
