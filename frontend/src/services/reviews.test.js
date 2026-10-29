import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./api', () => ({ default: { get: vi.fn(() => Promise.resolve({})) } }));

import apiService from './api';
import reviewsService, { toQuery } from './reviews';

describe('toQuery', () => {
  it('skips empty, null and "all" values', () => {
    expect(toQuery({ a: 1, b: '', c: null, d: undefined, e: 'all' })).toBe('?a=1');
    expect(toQuery({})).toBe('');
  });
});

describe('reviewsService', () => {
  beforeEach(() => apiService.get.mockClear());

  it('requests stats with the range and optional repo', async () => {
    await reviewsService.getStats({ days: 7 });
    expect(apiService.get).toHaveBeenCalledWith('/api/stats/?days=7');
    await reviewsService.getStats({ days: 90, repo: 4 });
    expect(apiService.get).toHaveBeenLastCalledWith('/api/stats/?days=90&repo=4');
  });

  it('defaults to 30 days', async () => {
    await reviewsService.getStats();
    expect(apiService.get).toHaveBeenCalledWith('/api/stats/?days=30');
  });

  it('requests review lists with filters and one review by id', async () => {
    await reviewsService.getReviews({ page: 2, status: 'failed', repo: 'all', q: 'login' });
    expect(apiService.get).toHaveBeenCalledWith('/api/reviews/?page=2&status=failed&q=login');
    await reviewsService.getReview(12);
    expect(apiService.get).toHaveBeenLastCalledWith('/api/reviews/12/');
  });
});
