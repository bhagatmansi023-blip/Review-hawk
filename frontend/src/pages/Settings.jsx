import { Settings as SettingsIcon, Clock, Sliders, Bell, Key } from 'lucide-react';

export default function Settings() {
  return (
    <div className="placeholder-page">
      <div className="placeholder-header">
        <div>
          <h1 className="placeholder-title">Settings</h1>
          <p className="placeholder-desc">
            Configure Review Hawk workspace preferences, GitHub tokens, webhook secrets, and notifications.
          </p>
        </div>
        <span className="placeholder-badge">
          <Clock size={14} />
          <span>Scheduled for Next Phase</span>
        </span>
      </div>

      <div className="placeholder-card">
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          Workspace & Integration Settings
        </h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.5 }}>
          Once the authenticated session is established with Django REST Framework, developers can adjust review parameters, manage AI model preferences, and configure notification channels.
        </p>

        <div className="roadmap-list">
          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-primary)', marginBottom: '4px' }}>
              <Key size={18} />
              <h5>GitHub App & OAuth Tokens</h5>
            </div>
            <p>Inspect token expiration, revoke access, or re-authorize with extended organization scopes.</p>
          </div>

          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-secondary)', marginBottom: '4px' }}>
              <Sliders size={18} />
              <h5>Review Sensitivity Settings</h5>
            </div>
            <p>Customize AI review aggressiveness, strictness thresholds, and comment formatting.</p>
          </div>

          <div className="roadmap-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#eab308', marginBottom: '4px' }}>
              <Bell size={18} />
              <h5>Notifications & Integrations</h5>
            </div>
            <p>Receive Slack, Discord, or email summaries when PR reviews complete or critical CVEs are flagged.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
