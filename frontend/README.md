# CodeHawk — Sharp Eyes. Cleaner Code.

> **AI-Powered Automated Code Review Bot for GitHub.**

CodeHawk automatically analyzes GitHub Pull Requests (PRs) using AI and static analysis to help developers identify bugs, security concerns, and code-quality issues before merging.

---

## 🚀 Phase 2: GitHub Authentication & Login Integration

Phase 2 builds upon the Phase 1 UI foundation to connect CodeHawk to the real GitHub OAuth authentication flow supported by our Django REST Framework and Django Allauth backend.

### Features Implemented:

- **Branded CodeHawk Identity:** Updated branding, hawk emblem logo, tagline (*"Sharp Eyes. Cleaner Code."*), and clear value proposition.
- **Polished Login Experience:**
  - Clear heading: *"Review code smarter."*
  - Concise description of automated pull request reviews.
  - Prominent **"Continue with GitHub"** button with official GitHub icon.
  - Granular access explanation: *GitHub access is required to connect repositories and review pull requests.*
  - Security/privacy note: *Access is limited strictly to authorized repositories and can be revoked at any time via GitHub.*
  - Interactive states: loading spinner during initiation, error banners with retry triggers, and duplicate-click prevention.
- **Backend Flow Integration:**
  - Direct connection to Django Allauth initiation endpoint: `GET /accounts/github/login/?process=login`.
  - Fallback and direct OAuth URL generator with CSRF state protection.
  - Dedicated `/auth/callback` route for handling callback query parameters (`code`, `state`, `error`, `error_description`), network errors, and denied authorization.
- **Authentication State Management:**
  - Centralized `AuthContext` and `useAuth` hook providing `user`, `isAuthenticated`, `isLoading`, `login`, and `logout`.
  - Session verification with `credentials: 'include'` supporting Django `sessionid` cookies and `csrftoken`.
  - Minimal user metadata caching without trusting client flags as security controls.
- **Protected Routing (`ProtectedRoute`):**
  - All application routes (`/dashboard`, `/repositories`, `/pull-requests`, `/reviews`, `/analytics`, `/settings`) require authentication.
  - Unauthenticated access redirects smoothly to `/login` preserving target location.
  - Authenticated visitors to `/login` are automatically directed to `/dashboard`.
  - Clean non-flashing loading state while verifying sessions.
- **Navbar Profile & Sign Out:**
  - Shows developer avatar / username when authenticated and a dedicated **Sign Out** button.
  - Shows **Sign In** action when unauthenticated.

---

## 🛠️ Getting Started Locally

### Prerequisites
- Node.js (v18+)
- npm or yarn

### Installation & Run

1. Navigate into the `frontend/` directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   ```

4. Start development server:
   ```bash
   npm run dev
   ```
   The application will be live at `http://localhost:5173`.

5. Build and validate for production:
   ```bash
   npm run build
   npm run lint
   ```

---

## 🔌 Django Backend Flow & Teammate Integration Guide

### Discovered Backend Architecture:
The Django backend (`backend/config/settings.py` & `backend/config/urls.py`) uses **`django-allauth`** with the GitHub social provider:
- **Initiation URL:** `GET /accounts/github/login/?process=login` (Redirects user to GitHub OAuth authorize).
- **Callback URL:** `GET /accounts/github/login/callback/?code=...&state=...` (Managed by Django Allauth using server-side client secret).
- **Post-Login Redirect:** `LOGIN_REDIRECT_URL = "http://localhost:5173/dashboard"`.
- **Post-Logout Redirect:** `ACCOUNT_LOGOUT_REDIRECT_URL = "http://localhost:5173/login"`.

### Outstanding Action Items for Backend Teammate:

1. **User Profile / Session REST Endpoint:**
   - Expose `GET /api/auth/user/` returning authenticated user JSON:
     ```json
     {
       "id": 1,
       "username": "developer",
       "email": "dev@example.com",
       "avatar_url": "https://avatars.githubusercontent.com/u/12345"
     }
     ```
   - Returns `401 Unauthorized` when the session is invalid or expired.

2. **CORS Headers & Cookie Middleware:**
   - In `backend/config/settings.py`, add `corsheaders.middleware.CorsMiddleware` to `MIDDLEWARE`:
     ```python
     MIDDLEWARE = [
         'django.middleware.security.SecurityMiddleware',
         'django.contrib.sessions.middleware.SessionMiddleware',
         'corsheaders.middleware.CorsMiddleware', # Add here
         'django.middleware.common.CommonMiddleware',
         ...
     ]
     ```
   - Configure allowed origins and credentials:
     ```python
     CORS_ALLOWED_ORIGINS = [
         "http://localhost:5173",
         "http://127.0.0.1:5173",
     ]
     CORS_ALLOW_CREDENTIALS = True
     CSRF_TRUSTED_ORIGINS = [
         "http://localhost:5173",
         "http://127.0.0.1:5173",
     ]
     ```

3. **GitHub OAuth App Settings on GitHub:**
   - Homepage URL: `http://localhost:5173`
   - Authorization callback URL: `http://localhost:8000/accounts/github/login/callback/`

---

## 📦 Phase 3: GitHub Repository Connection & Selection

Phase 3 implements repository management, search, selection, and connection for automated CodeHawk pull request reviews.

### Features Implemented:
- **Repository Management View (`/repositories`):**
  - Page title: *"Connect a Repository"*.
  - Description: *"Choose a GitHub repository to enable automated pull request reviews."*
  - Real GitHub connection status banner (*"GitHub Connected: @username"* or unauthenticated prompt).
  - Search input with clear action matching repository names, owners, or full names.
  - Filter pills for repository visibility (*All*, *Public*, *Private*) and connection state (*All*, *Connected*, *Available*).
  - Responsive repository list table displaying owner/name, GitHub link, visibility badges, default branch, language tag, and action triggers.
  - Selection confirmation action banner highlighting selected repo with *"Connect Repository"* action, duplicate submission prevention (`isConnecting`), and cancellation.
  - Comprehensive states: loading indicators, search with zero matches, empty state, missing backend endpoints, permission guide, and error/success alerts.
- **Repository Context & Service (`RepoContext`, `repoService`):**
  - Centralized state for available and connected repositories.
  - Parallel queries to `GET /api/repos/` and `GET /api/repos/connected/`.
  - Confirms connection with backend before updating connected status.
  - Handles permission explanations and DRF contract modal viewers.
- **Dashboard Integration (`/dashboard`):**
  - Keeps the dashboard part in `Dashboard.jsx`.
  - When a repository is connected: displays the **Active Connected Repository** card with bot review status, default branch, and repository management shortcut, plus live summary stats.
  - When no repository is connected: displays a **Connect Your Repository** call-to-action card linking directly to `/repositories`.

### 🔌 Django Backend Repository API Contract for Backend Teammate:

| Method | Endpoint | Description | Expected Payload / Response |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/repos/` | Retrieves repositories accessible to user from GitHub | Response: `200 OK`<br>`[{ "id": 101, "github_repo_id": 89234120, "name": "core-api", "full_name": "acme/core-api", "owner": "acme", "is_private": false, "default_branch": "main", "language": "Python", "is_connected": false }]` |
| `POST` | `/api/repos/connect/` | Connects repository to CodeHawk and activates webhook | Request: `{ "github_repo_id": 89234120, "owner": "acme", "name": "core-api", "default_branch": "main", "is_private": false }`<br>Response: `201 Created`<br>`{ "id": 1, "github_repo_id": 89234120, "full_name": "acme/core-api", "is_enabled": true }` |
| `GET` | `/api/repos/connected/` | Retrieves user's connected repositories from Django DB | Response: `200 OK`<br>`[{ "id": 1, "github_repo_id": 89234120, "full_name": "acme/core-api", "is_enabled": true }]` |
| `DELETE` | `/api/repos/{id}/` | Disconnects repository and disables bot reviews | Response: `204 No Content` |

---

## 🔍 Phase 4: Pull Request Listing & Details

Phase 4 implements pull request monitoring and dedicated details views for connected repositories, displaying real GitHub PR metadata alongside CodeHawk automated review statuses.

### Features Implemented:
- **Pull Request Listing (`/pull-requests`):**
  - Page title: *"Pull Requests"*.
  - Description: *"Track pull requests and their automated code review status."*
  - Active connected repository indicator displaying full repository name, default branch, visibility badge, and bot status.
  - Repository switcher dropdown allowing users with multiple connected repositories to seamlessly switch views.
  - Live search input matching pull request title, `#number`, and author with instant clear trigger.
  - Filter pills for GitHub state (*All*, *Open*, *Closed*, *Merged*) and CodeHawk review verdict (*All*, *Review Completed*, *Review Pending*, *Review Failed*, *No Review Yet*).
  - Explicit refresh action querying latest data from the backend.
  - Desktop table view with columns: *Pull Request*, *Author*, *Source Branch*, *Target Branch*, *Status*, *Review Status*, *Updated*, *Actions*.
  - Mobile/tablet responsive card layout with touch-friendly elements.
- **Pull Request Details View (`/pull-requests/:id`):**
  - Dedicated details route supporting direct navigation, bookmarking, and link sharing.
  - Top breadcrumb navigation (*"← Back to Pull Requests"*) and external GitHub link (*"Open on GitHub ↗"*).
  - Pull request header with `#number`, title, author, GitHub state badge, and associated repository tag.
  - Branch topology card displaying source (head) branch, target (base) branch, and head commit SHA.
  - Timeline card displaying creation and last-updated timestamps.
  - Pull request description/summary body when available.
  - Dedicated **CodeHawk Automated Review Verdict** section clearly distinguishing GitHub PR state from CodeHawk review state.
  - Honest status rendering: displays review summary, model name, tokens, and files reviewed only when confirmed by the backend; renders clear neutral state (*"No review recorded yet"*) when no review exists.
- **Navigation & Integration:**
  - Added *"View PRs"* shortcut on connected repositories in `RepoTable`.
  - Added *"View Pull Requests"* shortcut in `Dashboard` active repository card.
  - Preserved shared layouts (`AppLayout`, `Navbar`, `ProtectedRoute`).
- **Comprehensive State Handling (All 10 States):**
  1. *No repository selected*: Guided card directing user to `/repositories`.
  2. *Pull requests loading*: Skeleton loading indicator.
  3. *Pull requests loaded successfully*: Table and card layout.
  4. *No pull requests available*: Neutral notice for repositories with zero PRs.
  5. *Search returns no results*: Zero-match notice with *"Reset All Filters"* action.
  6. *API request fails*: Network error alert with *"Retry"* action.
  7. *Authentication expires*: Session expiration prompt with GitHub sign-in redirect.
  8. *User lacks repository access*: Permissions notice linking to GitHub settings.
  9. *Pull request details cannot be found*: 404 state with return navigation.
  10. *Review information not yet available*: Neutral *"No review recorded yet"* banner.
  - *Missing backend endpoint*: Informational card with modal contract viewer for backend teammate.

### 🔌 Django Backend Pull Request API Contract for Backend Teammate:

| Method | Endpoint | Description | Expected Payload / Response |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/repos/{repo_id}/pulls/` | Retrieves pull requests for a connected repository | Query params: `?state=open|closed|merged`, `?search=keyword`, `?page=1`<br>Response: `200 OK`<br>`{ "count": 1, "next": null, "previous": null, "results": [{ "id": 1, "number": 42, "title": "Add OAuth callback", "author": "octocat", "state": "open", "html_url": "https://github.com/...", "source_branch": "feature/auth", "target_branch": "main", "latest_head_sha": "a1b2...", "created_at": "...", "updated_at": "...", "latest_review": { "status": "completed", "summary": "..." } }] }` |
| `GET` | `/api/pull-requests/{id}/` | Retrieves details and review record for specific PR | Response: `200 OK`<br>`{ "id": 1, "number": 42, "title": "...", "author": "...", "state": "open", "description": "...", "html_url": "...", "source_branch": "...", "target_branch": "...", "latest_head_sha": "...", "created_at": "...", "updated_at": "...", "repository": { "id": 101, "full_name": "acme/core-api" }, "latest_review": { "id": 10, "status": "completed", "summary": "...", "llm_model": "gemini-1.5-pro", "input_tokens": 1420, "output_tokens": 340, "files_reviewed": 4 } }` |


