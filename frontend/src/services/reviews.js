/**
 * Reviews & statistics service.
 * Wraps the read-only dashboard endpoints added in reviews/api_views.py.
 */
import apiService from './api';

function toQuery(params = {}) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '' && value !== 'all') {
      query.set(key, value);
    }
  });
  const str = query.toString();
  return str ? `?${str}` : '';
}

export const reviewsService = {
  /** GET /api/stats/?days=30&repo=<id> */
  getStats({ days = 30, repo } = {}) {
    return apiService.get(`/api/stats/${toQuery({ days, repo })}`);
  },

  /** GET /api/reviews/?page=&status=&repo=&q= -> { count, next, previous, results } */
  getReviews(params = {}) {
    return apiService.get(`/api/reviews/${toQuery(params)}`);
  },

  /** GET /api/reviews/<id>/ -> review with all findings and health breakdown */
  getReview(id) {
    return apiService.get(`/api/reviews/${id}/`);
  },
};

export { toQuery };
export default reviewsService;
