import { AlertCircle, RotateCw } from 'lucide-react';

/** Inline error with a retry button, used when an API call fails. */
export default function ErrorNotice({ error, onRetry, title = 'Could not load data' }) {
  if (!error) return null;
  const message =
    error.status === 401 || error.status === 403
      ? 'Your session has expired. Please sign in again.'
      : error.message || 'Something went wrong while contacting the server.';
  return (
    <div className="error-notice" role="alert">
      <AlertCircle size={18} />
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
      {onRetry && (
        <button type="button" className="btn-secondary-sm" onClick={onRetry}>
          <RotateCw size={14} /> Retry
        </button>
      )}
    </div>
  );
}
