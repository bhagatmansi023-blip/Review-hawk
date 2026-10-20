/**
 * Authentication Service for CodeHawk
 * 
 * Supports the backend Django Allauth GitHub OAuth flow:
 * 1. Initiation via GET /accounts/github/login/?process=login
 * 2. Server-side code exchange via /accounts/github/login/callback/
 * 3. Session checking via GET /api/auth/user/
 * 4. Logout via /accounts/logout/ or /api/auth/logout/
 */

import apiService from './api';

export const AUTH_STORAGE_KEY = 'codehawk_token';
export const USER_STORAGE_KEY = 'codehawk_user';

// Fallback legacy keys for migration
const LEGACY_AUTH_STORAGE_KEY = 'review_hawk_token';
const LEGACY_USER_STORAGE_KEY = 'review_hawk_user';

export const authService = {
  /**
   * Retrieves the backend GitHub OAuth initiation URL.
   * Based on Django Allauth configuration discovered in backend/config/settings.py:
   * SOCIALACCOUNT_LOGIN_ON_GET = True
   * Endpoint: /accounts/github/login/
   */
  getAuthInitiationUrl() {
    const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');
    return `${apiBaseUrl}/accounts/github/login/?process=login`;
  },

  /**
   * Generates direct GitHub OAuth authorization URL as a fallback if the frontend
   * is configured to initiate client-side OAuth.
   */
  getDirectGitHubAuthorizeUrl(redirectUri = null) {
    const clientId = import.meta.env.VITE_GITHUB_CLIENT_ID;
    if (!clientId) return null;

    const appUrl = (import.meta.env.VITE_APP_URL || window.location.origin).replace(/\/+$/, '');
    const targetRedirect = redirectUri || `${appUrl}/auth/callback`;
    const scope = encodeURIComponent('read:user user:email repo');
    const state = Math.random().toString(36).substring(2, 15);

    sessionStorage.setItem('codehawk_oauth_state', state);

    return `https://github.com/login/oauth/authorize?client_id=${encodeURIComponent(
      clientId
    )}&redirect_uri=${encodeURIComponent(targetRedirect)}&scope=${scope}&state=${encodeURIComponent(state)}`;
  },

  /**
   * Initiates the real GitHub sign-in flow.
   * Performs a connectivity check before full-page redirect to prevent unhandled
   * browser ERR_CONNECTION_REFUSED crashes if the Django backend is offline.
   */
  async initiateGitHubLogin() {
    const initiationUrl = this.getAuthInitiationUrl();
    const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');

    // Pre-flight check: verify backend server is listening before navigating away from SPA
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2500);

      await fetch(initiationUrl, {
        method: 'HEAD',
        mode: 'no-cors',
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
    } catch {
      throw new Error(
        `Could not connect to the authentication server at ${apiBaseUrl}. Ensure the Django backend is running and accessible.`
      );
    }

    // Backend is reachable - proceed with browser navigation to Django Allauth GitHub flow
    if (typeof window !== 'undefined') {
      window.location.href = initiationUrl;
    }

    return {
      status: 'redirecting',
      url: initiationUrl,
    };
  },

  /**
   * Exchanges GitHub callback code for user session.
   * Used if GitHub redirects back to frontend route /auth/callback.
   */
  async handleOAuthCallback(code, state = null) {
    try {
      const response = await apiService.post('/api/auth/github/callback/', { code, state });
      if (response?.token) {
        localStorage.setItem(AUTH_STORAGE_KEY, response.token);
      }
      if (response?.user) {
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(response.user));
      }
      return response;
    } catch (error) {
      console.warn('[CodeHawk Auth] OAuth callback code exchange failed:', error.message);
      throw error;
    }
  },

  /**
   * Retrieves the current user's profile from the Django backend.
   * Leverages HttpOnly session cookies (credentials: include) or Bearer token.
   */
  async getCurrentUser() {
    try {
      // First attempt the standard REST user profile endpoint
      const user = await apiService.get('/api/auth/user/');
      if (user) {
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
        return user;
      }
      return null;
    } catch (error) {
      // If 401 Unauthorized or 404 (endpoint not yet created by backend teammate):
      // Clean up cached user info and return null (unauthenticated).
      if (error.status === 401 || error.status === 404) {
        this.clearSession();
        return null;
      }

      // If backend is not running or network fails, check if we have a locally stored user
      const stored = this.getStoredUser();
      if (stored) {
        return stored;
      }

      return null;
    }
  },

  /**
   * Retrieves stored user metadata from localStorage if previously authenticated
   */
  getStoredUser() {
    try {
      const raw = localStorage.getItem(USER_STORAGE_KEY) || localStorage.getItem(LEGACY_USER_STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },

  /**
   * Retrieves stored token if token-based auth is used
   */
  getStoredToken() {
    return localStorage.getItem(AUTH_STORAGE_KEY) || localStorage.getItem(LEGACY_AUTH_STORAGE_KEY);
  },

  /**
   * Checks if an authentication credential or session is stored
   */
  isAuthenticated() {
    return Boolean(this.getStoredToken() || this.getStoredUser());
  },

  /**
   * Clears stored client credentials and user session
   */
  clearSession() {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    localStorage.removeItem(USER_STORAGE_KEY);
    localStorage.removeItem(LEGACY_AUTH_STORAGE_KEY);
    localStorage.removeItem(LEGACY_USER_STORAGE_KEY);
    sessionStorage.removeItem('codehawk_oauth_state');
  },

  /**
   * Logs out user by clearing frontend state and calling backend logout endpoint
   */
  async logout() {
    const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');
    try {
      await apiService.post('/api/auth/logout/');
    } catch {
      // Fallback: If REST logout endpoint doesn't exist, we can ping /accounts/logout/
      try {
        await fetch(`${apiBaseUrl}/accounts/logout/`, {
          method: 'POST',
          credentials: 'include',
        });
      } catch {
        // Ignore network errors on logout
      }
    } finally {
      this.clearSession();
    }
  }
};

export default authService;
