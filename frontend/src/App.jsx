import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import { RepoProvider } from './context/RepoContext';
import AuthLayout from './layouts/AuthLayout';
import AppLayout from './layouts/AppLayout';
import ProtectedRoute from './components/common/ProtectedRoute';

import Login from './pages/Login';
import AuthCallback from './pages/AuthCallback';
import Dashboard from './pages/Dashboard';
import Repositories from './pages/Repositories';
import RepositoryDetails from './pages/RepositoryDetails';
import PullRequests from './pages/PullRequests';
import PullRequestDetails from './pages/PullRequestDetails';
import Reviews from './pages/Reviews';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <RepoProvider>
          <BrowserRouter>
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
                  <Route path="/repositories/:repoId" element={<RepositoryDetails />} />
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
          </BrowserRouter>
        </RepoProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
