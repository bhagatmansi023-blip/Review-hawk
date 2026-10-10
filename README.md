<<<<<<< HEAD
# Review-hawk

An AI-powered code review bot for GitHub. When a pull request is opened, it
analyzes the diff with an LLM and tree-sitter static checks, then posts review
comments automatically. A dashboard shows review history and stats.

## Tech stack

- **Backend:** Django, Django REST Framework, PyGithub
- **Database:** PostgreSQL
- **Background jobs:** Celery + Redis
- **Analysis:** LLM API, tree-sitter
- **Auth:** GitHub OAuth (django-allauth)
- **Frontend:** React

## Project structure

```
Review-hawk/
├── backend/    # Django project (config, accounts, repos, reviews)
└── frontend/   # React dashboard
```

## Getting started (backend)

1. Clone the repo and open the `backend/` folder.
2. Create and activate a virtual environment:
```
   python -m venv venv
   venv\Scripts\activate
```
3. Install dependencies:
```
   pip install -r requirements.txt
```
4. Create a PostgreSQL database and user.
5. Copy `.env.example` to `.env` and fill in your values.
6. Run migrations and start the server:
```
   python manage.py migrate
   python manage.py createsuperuser
   python manage.py runserver
```
7. Open http://127.0.0.1:8000/admin/

## Status

Work in progress. See the build plan below.

- [x] Project setup
- [ ] Initial database models
- [ ] GitHub OAuth login
- [ ] Webhook endpoint
- [ ] LLM review and static checks
- [ ] Dashboard
=======
# Review Hawk — Sharp Eyes. Cleaner Code.

> **AI-powered automated code review platform for GitHub repositories.**

Review Hawk automatically analyzes GitHub Pull Requests (PRs) using AI and static analysis to identify bugs, security vulnerabilities, and code-quality issues.

---

## 📁 Repository Structure

```text
Review-hawk/
├── frontend/        # React + Vite application (Phase 1 complete)
└── backend/         # Django REST Framework backend (In development)
```

---

## 🚀 Frontend Quickstart

1. Navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Copy environment configuration:
   ```bash
   cp .env.example .env
   ```
4. Start development server:
   ```bash
   npm run dev
   ```
   Open [http://localhost:5173](http://localhost:5173) in your browser.

5. Build for production:
   ```bash
   npm run build
   ```

For detailed frontend integration contracts and component details, see [frontend/README.md](file:///d:/Review%20hawk/frontend/README.md).
>>>>>>> f085f03 (Review hawk frontend foundation and login page)
