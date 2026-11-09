/**
 * Dashboard data + synchronisation service.
 * Talks to the real backend: no sample data anywhere.
 */
import apiService from './api';
import { toQuery } from './reviews';

export const syncService = {
  /** POST /api/sync/ — fetch open PRs from GitHub for every connected repo and queue reviews. */
  syncAll({ review = true } = {}) {
    return apiService.post('/api/sync/', { review });
  },

  /** GET /api/sync/status/ — last sync per repository and review progress for open PRs. */
  getStatus({ celery = false } = {}) {
    return apiService.get(`/api/sync/status/${celery ? '?celery=1' : ''}`);
  },

  /** GET /api/pull-requests/ — pull requests across all connected repositories. */
  listPullRequests({ page = 1, state, repository, search } = {}) {
    return apiService.get(`/api/pull-requests/${toQuery({ page, state, repository, search })}`);
  },
};

export default syncService;
