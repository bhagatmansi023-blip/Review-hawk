import { useState, useEffect, useCallback, useRef } from 'react';
import { Database, RefreshCw, CheckCircle2, AlertCircle, Clock, Loader } from 'lucide-react';
import ragService from '../../services/ragService';

/**
 * RAGIndexStatus
 * Shows the RAG codebase index status for a repository and allows triggering reindexing.
 *
 * Props:
 *   repoId {number|string} - Django DB primary key of the repository
 */
export default function RAGIndexStatus({ repoId }) {
  const [indexStatus, setIndexStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isReindexing, setIsReindexing] = useState(false);
  const [reindexMessage, setReindexMessage] = useState('');
  const pollRef = useRef(null);

  const fetchStatus = useCallback(async () => {
    if (!repoId) return;
    try {
      const data = await ragService.getIndexStatus(repoId);
      setIndexStatus(data);
    } catch (err) {
      // Non-fatal: RAG may not be available
      setIndexStatus({ status: 'never', error: '' });
    } finally {
      setIsLoading(false);
    }
  }, [repoId]);

  // Auto-poll while indexing
  useEffect(() => {
    fetchStatus();

    // Clear any existing poll
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(() => {
      fetchStatus();
    }, 10000);

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchStatus]);

  // Stop polling when no longer in progress
  useEffect(() => {
    if (indexStatus && indexStatus.status !== 'indexing' && indexStatus.status !== 'pending') {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }
  }, [indexStatus]);

  const handleReindex = async () => {
    if (!repoId || isReindexing) return;
    setIsReindexing(true);
    setReindexMessage('');
    try {
      await ragService.triggerReindex(repoId);
      setReindexMessage('Reindexing started!');
      setIndexStatus(prev => ({ ...prev, status: 'indexing' }));
      // Resume polling
      if (!pollRef.current) {
        pollRef.current = setInterval(fetchStatus, 10000);
      }
      setTimeout(() => setReindexMessage(''), 4000);
    } catch (err) {
      setReindexMessage('Failed to start reindex.');
      setTimeout(() => setReindexMessage(''), 4000);
    } finally {
      setIsReindexing(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'ready':
        return (
          <span className="badge-status badge-status-active" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <CheckCircle2 size={12} />
            <span>Indexed</span>
          </span>
        );
      case 'indexing':
      case 'pending':
        return (
          <span className="badge-status" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: 'var(--accent-warning, #f59e0b)', borderColor: 'var(--accent-warning, #f59e0b)' }}>
            <Loader size={12} className="spin-icon" />
            <span>Indexing…</span>
          </span>
        );
      case 'failed':
        return (
          <span className="badge-status" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: 'var(--accent-error, #ef4444)', borderColor: 'var(--accent-error, #ef4444)' }}>
            <AlertCircle size={12} />
            <span>Failed</span>
          </span>
        );
      default: // 'never' or unknown
        return (
          <span className="badge-status" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: 'var(--text-muted, #6b7280)', borderColor: 'var(--text-muted, #6b7280)' }}>
            <Clock size={12} />
            <span>Not Indexed</span>
          </span>
        );
    }
  };

  if (isLoading) {
    return null; // Don't flash a loading state for a secondary panel
  }

  const status = indexStatus?.status || 'never';
  const isInProgress = status === 'indexing' || status === 'pending';

  return (
    <div className="rd-meta-item" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: '6px' }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%' }}>
        <span className="rd-meta-label" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Database size={12} />
          <span>RAG Index</span>
        </span>
        {getStatusBadge(status)}
        <button
          type="button"
          className="btn-repo-refresh"
          onClick={handleReindex}
          disabled={isReindexing || isInProgress}
          title={isInProgress ? 'Indexing in progress…' : 'Reindex this repository'}
          style={{ marginLeft: 'auto', fontSize: '0.75rem' }}
        >
          <RefreshCw size={11} className={isReindexing || isInProgress ? 'spin-icon' : ''} />
          <span>{isInProgress ? 'Indexing…' : 'Reindex'}</span>
        </button>
      </div>

      {/* Stats row (only when indexed) */}
      {status === 'ready' && indexStatus && (
        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted, #6b7280)', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          {indexStatus.indexed_files > 0 && (
            <span>{indexStatus.indexed_files} files</span>
          )}
          {indexStatus.indexed_chunks > 0 && (
            <span>{indexStatus.indexed_chunks} chunks</span>
          )}
          {indexStatus.indexed_at && (
            <span>Last indexed: {new Date(indexStatus.indexed_at).toLocaleDateString()}</span>
          )}
          {indexStatus.indexed_commit_sha && (
            <span>@ {indexStatus.indexed_commit_sha.slice(0, 7)}</span>
          )}
        </div>
      )}

      {/* Error */}
      {status === 'failed' && indexStatus?.error && (
        <div style={{ fontSize: '0.78rem', color: 'var(--accent-error, #ef4444)' }}>
          {indexStatus.error.slice(0, 200)}
        </div>
      )}

      {/* Success/failure message */}
      {reindexMessage && (
        <div style={{ fontSize: '0.78rem', color: reindexMessage.includes('Failed') ? 'var(--accent-error, #ef4444)' : 'var(--accent-success, #22c55e)' }}>
          {reindexMessage}
        </div>
      )}
    </div>
  );
}
