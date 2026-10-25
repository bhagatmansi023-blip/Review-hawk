import { useEffect, useState, useCallback } from 'react';
import authService from '../services/auth';
import { AuthContext } from './authContextDef';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => authService.getStoredUser());
  const [isAuthenticated, setIsAuthenticated] = useState(() => authService.isAuthenticated());
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  // Initialize and check current authentication state
  const checkAuth = useCallback(async () => {
    setIsLoading(true);
    setAuthError(null);
    try {
      const currentUser = await authService.getCurrentUser();
      if (currentUser) {
        setUser(currentUser);
        setIsAuthenticated(true);
      } else {
        setUser(null);
        setIsAuthenticated(false);
      }
    } catch (err) {
      setUser(null);
      setIsAuthenticated(false);
      if (err.status && err.status !== 401 && err.status !== 404) {
        setAuthError(err.message || 'Failed to verify session');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;

    // Check if token was provided in the OAuth redirect URL (e.g. /dashboard?token=...)
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      const urlToken = urlParams.get('token');
      if (urlToken) {
        localStorage.setItem('codehawk_token', urlToken);
        urlParams.delete('token');
        const remaining = urlParams.toString();
        const cleanPath = window.location.pathname + (remaining ? `?${remaining}` : '');
        window.history.replaceState({}, document.title, cleanPath);
      }
    }

    authService.getCurrentUser()
      .then((currentUser) => {
        if (!isMounted) return;
        if (currentUser) {
          setUser(currentUser);
          setIsAuthenticated(true);
        } else {
          setUser(null);
          setIsAuthenticated(false);
        }
        setIsLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        setUser(null);
        setIsAuthenticated(false);
        if (err.status && err.status !== 401 && err.status !== 404) {
          setAuthError(err.message || 'Failed to verify session');
        }
        setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Initiate real GitHub OAuth login flow
  const login = useCallback(async () => {
    setAuthError(null);
    try {
      await authService.initiateGitHubLogin();
    } catch (err) {
      setAuthError(err.message || 'Failed to start GitHub authentication. Please check backend connection.');
      throw err;
    }
  }, []);

  // Log out current session
  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } catch (err) {
      console.warn('[CodeHawk Auth] Logout warning:', err.message);
    } finally {
      setUser(null);
      setIsAuthenticated(false);
      setAuthError(null);
    }
  }, []);

  // Update session directly (e.g. after callback exchange)
  const setUserSession = useCallback((userData) => {
    setUser(userData);
    setIsAuthenticated(Boolean(userData));
    setAuthError(null);
  }, []);

  const clearError = useCallback(() => {
    setAuthError(null);
  }, []);

  const value = {
    user,
    isAuthenticated,
    isLoading,
    authError,
    setAuthError,
    login,
    logout,
    checkAuth,
    setUserSession,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export default AuthProvider;
