import { Link, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  FolderGit2, 
  GitPullRequest, 
  CheckCircle2, 
  BarChart3, 
  Settings, 
  LogIn 
} from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import hawkLogo from '../../assets/hawk-logo.jpg';

export default function Navbar() {
  const location = useLocation();

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
      <Link to="/login" className="header-brand">
        <div className="header-logo">
          <img src={hawkLogo} alt="Review Hawk Logo" />
        </div>
        <span>Review Hawk</span>
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
        <Link to="/login" className="nav-item" style={{ border: '1px solid var(--border-subtle)' }}>
          <LogIn size={16} />
          <span>Login</span>
        </Link>
      </div>
    </header>
  );
}
