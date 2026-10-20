/**
 * Base API Service for CodeHawk
 * 
 * Provides centralized HTTP communication with the Django REST Framework backend.
 * Includes credentials handling for Django session cookies and CSRF tokens.
 */

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');

class ApiService {
  constructor() {
    this.baseUrl = API_BASE_URL;
  }

  /**
   * Helper to retrieve CSRF token from browser cookies if set by Django
   */
  getCsrfToken() {
    if (typeof document === 'undefined') return null;
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : null;
  }

  /**
   * Helper to retrieve auth headers (JWT, Bearer token, and CSRF)
   */
  getHeaders(customHeaders = {}) {
    const headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...customHeaders,
    };

    // Check for Bearer token if token-based auth is in use
    const token = localStorage.getItem('codehawk_token') || localStorage.getItem('review_hawk_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // Include Django CSRF token if present
    const csrfToken = this.getCsrfToken();
    if (csrfToken && !headers['X-CSRFToken']) {
      headers['X-CSRFToken'] = csrfToken;
    }

    return headers;
  }

  /**
   * Generic request handler with credentials support for Django session cookies
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
    
    const config = {
      credentials: options.credentials || 'include',
      ...options,
      headers: this.getHeaders(options.headers),
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        let errorData = null;
        try {
          errorData = await response.json();
        } catch {
          errorData = { detail: response.statusText };
        }
        const error = new Error(errorData?.detail || errorData?.message || `API error (${response.status})`);
        error.status = response.status;
        error.data = errorData;
        throw error;
      }

      if (response.status === 204) {
        return null;
      }

      return await response.json();
    } catch (error) {
      // Avoid spamming warnings for expected unauthenticated 401/404 session checks
      if (error.status !== 401 && error.status !== 404) {
        console.warn(`[CodeHawk API] Request failed for ${url}:`, error.message);
      }
      throw error;
    }
  }

  get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  post(endpoint, body, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'POST',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  }

  delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'DELETE' });
  }
}

export const apiService = new ApiService();
export default apiService;
