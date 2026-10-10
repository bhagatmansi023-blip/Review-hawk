/**
 * Authentication Service for Review Hawk
 * 
 * PHASE 1 STATUS: Foundation & UI Scaffold.
 * Real GitHub OAuth requires the Django REST Framework backend endpoints
 * for client-secret exchange and secure session/token handling.
 * 
 * CONTRACT SPECIFICATION FOR BACKEND TEAM:
 * -------------------------------------------------------------
 * 1. GET /api/auth/github/login/ (or /api/auth/github/url/)
 *    - Returns GitHub OAuth authorize URL with state parameter.
 *    - OR frontend redirects to https://github.com/login/oauth/authorize
 *      with client_id, redirect_uri, scope="repo,read:user,user:email".
 * 
 * 2. POST /api/auth/github/callback/
 *    - Request payload: { code: string, state?: string }
 *    - Exchange temporary GitHub code with GitHub using server-side client secret.
 *    - Creates or updates user in Django DB.
 *    - Response payload: { token: string (JWT/drf token), user: { id, username, email, avatar_url } }
 * 
 * 3. GET /api/auth/user/
 *    - Authenticated endpoint to retrieve current user session.
 * 
 * 4. POST /api/auth/logout/
 *    - Invalidates session or token.
 */

import apiService from './api';

export const AUTH_STORAGE_KEY = 'review_hawk_token';
export const USER_STORAGE_KEY = 'review_hawk_user';

export const authService = {
  /**
   * Status flag indicating whether backend endpoints are currently wired
   */
  isBackendConnected: false,

  /**
   * Initiates the GitHub OAuth sign-in flow.
   * In Phase 1, returns metadata indicating integration readiness.
   */
  async initiateGitHubLogin() {
    // Check if backend API URL or Client ID is configured
    const clientId = import.meta.env.VITE_GITHUB_CLIENT_ID;
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

    return {
      status: 'pending_backend_integration',
      message: 'GitHub OAuth UI is ready. Awaiting Django REST Framework backend OAuth exchange endpoint.',
      details: {
        configuredApiUrl: apiBaseUrl,
        clientIdConfigured: Boolean(clientId),
        expectedBackendEndpoints: [
          'GET /api/auth/github/url/ (or login redirect)',
          'POST /api/auth/github/callback/',
          'GET /api/auth/user/'
        ]
      }
    };
  },

  /**
   * Exchanges GitHub callback code for user session.
   * To be invoked once the OAuth redirect handler route is built in Phase 2.
   */
  async handleOAuthCallback(code, state = null) {
    return apiService.post('/api/auth/github/callback/', { code, state });
  },

  /**
   * Retrieves the current user's profile from Django backend.
   */
  async getCurrentUser() {
    return apiService.get('/api/auth/user/');
  },

  /**
   * Checks if a local auth token exists (placeholder until session cookies or JWT are active)
   */
  isAuthenticated() {
    return Boolean(localStorage.getItem(AUTH_STORAGE_KEY));
  },

  /**
   * Clears stored credentials
   */
  logout() {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    localStorage.removeItem(USER_STORAGE_KEY);
  }
};

export default authService;
