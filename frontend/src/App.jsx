import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import { RepoProvider } from './context/RepoContext';
import AuthLayout from './layouts/AuthLayout';
import AppLayout from './layouts/AppLayout';
import ProtectedRoute from './components/common/ProtectedRoute';
import ErrorBoundary from './components/common/ErrorBoundary';

import Login from './pages/Login';
import AuthCallback from './pages/AuthCallback';
import Repositories from './pages/Repositories';
import PullRequests from './pages/PullRequests';
import PullRequestDetails from './pages/PullRequestDetails';
import Reviews from './pages/Reviews';
import Settings from './pages/Settings';

// Chart pages are loaded on demand so the login screen stays light (recharts is large).
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Analytics = lazy(() => import('./pages/Analytics'));

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <RepoProvider>
          <BrowserRouter>
            <Suspense fallback={<div className="chart-skeleton" style={{ height: 240, margin: 32 }} role="status" aria-label="Loading page" />}>
              <ErrorBoundary>
                <Routes>
              {/* Root route redirects to dashboard (protected route will gate unauthenticated users to /login) */}
              <Route path="/" element={<Navigate to="/dashboard" replace />} />

              {/* Public Authentication Routes */}
              <Route element={<AuthLayout />}>
                <Route path="/login" element={<Login />} />
                <Route path="/auth/callback" element={<AuthCallback />} />
              </Route>

              {/* Protected Application Routes */}
              <Route element={<ProtectedRoute />}>
                <Route element={<AppLayout />}>
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/repositories" element={<Repositories />} />
                  <Route path="/pull-requests" element={<PullRequests />} />
                  <Route path="/pull-requests/:id" element={<PullRequestDetails />} />
                  <Route path="/reviews" element={<Reviews />} />
                  <Route path="/analytics" element={<Analytics />} />
                  <Route path="/settings" element={<Settings />} />
                </Route>
              </Route>

              {/* Catch-all route redirects to /dashboard */}
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
              </ErrorBoundary>
            </Suspense>
          </BrowserRouter>
        </RepoProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
