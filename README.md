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