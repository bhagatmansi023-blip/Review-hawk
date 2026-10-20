import { Link, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  FolderGit2, 
  GitPullRequest, 
  CheckCircle2, 
  BarChart3, 
  Settings, 
  LogIn,
  LogOut,
  User as UserIcon
} from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import hawkLogo from '../../assets/hawk-logo.jpg';
import { useAuth } from '../../context/useAuth';

export default function Navbar() {
  const location = useLocation();
  const { user, isAuthenticated, logout } = useAuth();

  const navItems = [
    { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { name: 'Repositories', path: '/repositories', icon: FolderGit2 },
    { name: 'Pull Requests', path: '/pull-requests', icon: GitPullRequest },
    { name: 'Reviews', path: '/reviews', icon: CheckCircle2 },
    { name: 'Analytics', path: '/analytics', icon: BarChart3 },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  return (
    <header className="app-header">
      <Link to="/dashboard" className="header-brand">
        <div className="header-logo">
          <img src={hawkLogo} alt="CodeHawk Logo" />
        </div>
        <span>CodeHawk</span>
      </Link>

      <nav className="nav-links">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={16} />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      <div className="header-right">
        <ThemeToggle />

        {isAuthenticated ? (
          <div className="user-nav-profile">
            {user?.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user?.username || 'User avatar'}
                className="user-nav-avatar"
              />
            ) : (
              <div className="user-nav-avatar-placeholder">
                <UserIcon size={14} />
              </div>
            )}
            <span className="user-nav-username">
              {user?.username || user?.email || 'Developer'}
            </span>
            <button
              type="button"
              className="btn-nav-signout"
              onClick={logout}
              title="Sign out of CodeHawk"
              aria-label="Sign out"
            >
              <LogOut size={15} />
              <span>Sign Out</span>
            </button>
          </div>
        ) : (
          <Link to="/login" className="nav-item" style={{ border: '1px solid var(--border-subtle)' }}>
            <LogIn size={16} />
            <span>Sign In</span>
          </Link>
        )}
      </div>
    </header>
  );
}
