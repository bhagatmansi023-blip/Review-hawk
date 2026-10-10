# Review Hawk — Sharp Eyes. Cleaner Code.

> **AI-powered automated code review platform for GitHub repositories.**

Review Hawk automatically analyzes GitHub Pull Requests (PRs) using AI and static analysis to identify bugs, security vulnerabilities, and code-quality issues.

---

## 🚀 Phase 1: Frontend Foundation & Authentication UI

This repository contains the **React + Vite** frontend foundation designed to integrate seamlessly with our Django REST Framework backend.

### Features Implemented:
- **Design System & Themes:** Polished Dark Navy/Charcoal mode with subtle blue/indigo accents, plus Light mode with soft pastel tones.
- **Brand Identity:** Review Hawk logo asset integration, tagline (*"Sharp Eyes. Cleaner Code."*), and developer SaaS value propositions.
- **Authentication UI:** Modern split-screen layout with an accessible **"Continue with GitHub"** button, interactive states, loading indicators, and permission disclaimers.
- **Backend OAuth Contract Scaffold:** Dedicated `authService` and `apiService` modules configured with environment variables (`VITE_API_BASE_URL`).
- **Phase 1 Routing Architecture:** React Router setup with `/login` as the primary entry point and dedicated placeholder routes for:
  - `/dashboard`
  - `/repositories`
  - `/pull-requests`
  - `/reviews`
  - `/analytics`
  - `/settings`
- **Security Safeguards:** Client secrets remain strictly on the backend. No server credentials or private keys are exposed in client code.

---

## 🛠️ Getting Started Locally

### Prerequisites
- Node.js (v18+)
- npm or yarn

### Installation

1. Clone and navigate into the repository:
   ```bash
   git clone https://github.com/bhagatmansi023-blip/Review-hawk.git
   cd Review-hawk
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Setup environment variables:
   ```bash
   cp .env.example .env
   ```

4. Start the development server:
   ```bash
   npm run dev
   ```
   The application will be live at `http://localhost:5173`.

5. Build for production:
   ```bash
   npm run build
   ```

---

## 🔌 Django Backend Team Integration Guide

To connect the live GitHub OAuth flow in Phase 2, the frontend needs the following endpoints from the Django REST Framework backend:

| Method | Endpoint | Description | Expected Payload / Response |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/auth/github/url/` | Generates GitHub OAuth authorization URL with CSRF state | `{ "url": "https://github.com/login/oauth/authorize?..." }` |
| `POST` | `/api/auth/github/callback/` | Exchanges temporary code with GitHub and issues app session/JWT | Request: `{ "code": "...", "state": "..." }`<br>Response: `{ "token": "...", "user": { "id": "...", "username": "...", "avatar_url": "..." } }` |
| `GET` | `/api/auth/user/` | Retrieves authenticated user profile | Response: `{ "id": "...", "username": "...", "email": "...", "avatar_url": "..." }` |
| `POST` | `/api/auth/logout/` | Revokes user session or JWT token | Response: `204 No Content` |
