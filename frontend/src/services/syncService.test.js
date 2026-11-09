import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./api', () => ({ default: { get: vi.fn(() => Promise.resolve({})), post: vi.fn(() => Promise.resolve({})) } }));

import apiService from './api';
import syncService from './syncService';

describe('syncService', () => {
  beforeEach(() => {
    apiService.get.mockClear();
    apiService.post.mockClear();
  });

  it('starts a synchronisation of every repository and queues reviews by default', async () => {
    await syncService.syncAll();
    expect(apiService.post).toHaveBeenCalledWith('/api/sync/', { review: true });
    await syncService.syncAll({ review: false });
    expect(apiService.post).toHaveBeenLastCalledWith('/api/sync/', { review: false });
  });

  it('reads the sync status, optionally including the Celery worker check', async () => {
    await syncService.getStatus();
    expect(apiService.get).toHaveBeenCalledWith('/api/sync/status/');
    await syncService.getStatus({ celery: true });
    expect(apiService.get).toHaveBeenLastCalledWith('/api/sync/status/?celery=1');
  });

  it('lists pull requests across all repositories with filters', async () => {
    await syncService.listPullRequests();
    expect(apiService.get).toHaveBeenCalledWith('/api/pull-requests/?page=1');
    await syncService.listPullRequests({ page: 3, state: 'open', repository: 4, search: 'login' });
    expect(apiService.get).toHaveBeenLastCalledWith('/api/pull-requests/?page=3&state=open&repository=4&search=login');
  });
});
