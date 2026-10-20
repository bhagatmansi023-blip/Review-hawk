/**
 * Pull Requests Service for CodeHawk
 * 
 * Handles interaction with Django REST Framework endpoints for GitHub pull requests
 * and their associated automated review records.
 */

import apiService from './api';

export const pullRequestsService = {
  /**
   * Retrieves pull requests for a given repository.
   * Calls GET /api/repos/{repoId}/pulls/ with optional fallback to /api/pull-requests/?repository={repoId}
   * Supports query parameters: state, search, page
   * 
   * @param {number|string} repoId - The local repository ID or github_repo_id
   * @param {Object} [params={}] - Optional filters (state, search, page)
   * @returns {Promise<{results: Array, count: number, next: string|null, previous: string|null}>}
   */
  async getPullRequests(repoId, params = {}) {
    if (!repoId) {
      return { results: [], count: 0, next: null, previous: null };
    }

    const query = new URLSearchParams();
    if (params.state && params.state !== 'all') {
      query.set('state', params.state);
    }
    if (params.search && params.search.trim()) {
      query.set('search', params.search.trim());
    }
    if (params.page && params.page > 1) {
      query.set('page', params.page);
    }

    const queryString = query.toString() ? `?${query.toString()}` : '';

    try {
      // Primary standard endpoint: nested under repository
      const endpoint = `/api/repos/${repoId}/pulls/${queryString}`;
      const response = await apiService.get(endpoint);

      // Normalize pagination if DRF returns PageNumberPagination { count, results } or plain array
      if (response && Array.isArray(response.results)) {
        return {
          results: response.results,
          count: response.count ?? response.results.length,
          next: response.next || null,
          previous: response.previous || null,
        };
      }

      if (Array.isArray(response)) {
        return {
          results: response,
          count: response.length,
          next: null,
          previous: null,
        };
      }

      return { results: [], count: 0, next: null, previous: null };
    } catch (error) {
      // Fallback: If nested endpoint is 404, try top-level /api/pull-requests/?repository={repoId}
      if (error.status === 404) {
        try {
          const fallbackQuery = new URLSearchParams(query);
          fallbackQuery.set('repository', repoId);
          const fallbackEndpoint = `/api/pull-requests/?${fallbackQuery.toString()}`;
          const fallbackResponse = await apiService.get(fallbackEndpoint);

          if (fallbackResponse && Array.isArray(fallbackResponse.results)) {
            return {
              results: fallbackResponse.results,
              count: fallbackResponse.count ?? fallbackResponse.results.length,
              next: fallbackResponse.next || null,
              previous: fallbackResponse.previous || null,
            };
          }
          if (Array.isArray(fallbackResponse)) {
            return {
              results: fallbackResponse,
              count: fallbackResponse.length,
              next: null,
              previous: null,
            };
          }
        } catch (fallbackError) {
          // If fallback is also 404, mark as missing endpoint for teammate guide
          if (fallbackError.status === 404) {
            error.isMissingEndpoint = true;
            error.message = `The pull requests endpoint (GET /api/repos/${repoId}/pulls/) is awaiting implementation by the Django backend teammate.`;
          }
        }
      }

      if (error.status === 401) {
        error.isUnauthorized = true;
        error.message = 'Authentication session expired. Please re-authenticate with GitHub.';
      } else if (error.status === 403) {
        error.isForbidden = true;
        error.message = 'Insufficient permissions to view pull requests for this repository.';
      }

      throw error;
    }
  },

  /**
   * Retrieves full details for a specific pull request by ID or Number.
   * Calls GET /api/pull-requests/{id}/ with optional fallback to /api/repos/{repoId}/pulls/{id}/
   * 
   * @param {number|string} prId - The pull request ID or number
   * @param {number|string} [repoId=null] - Optional repository ID context
   * @returns {Promise<Object>} The pull request data including review status
   */
  async getPullRequestDetails(prId, repoId = null) {
    if (!prId) {
      throw new Error('Pull request ID is required');
    }

    try {
      // Primary standard endpoint: /api/pull-requests/{id}/
      const response = await apiService.get(`/api/pull-requests/${prId}/`);
      return response;
    } catch (error) {
      // Fallback: If repoId is available, try nested /api/repos/{repoId}/pulls/{prId}/
      if (error.status === 404 && repoId) {
        try {
          const fallbackResponse = await apiService.get(`/api/repos/${repoId}/pulls/${prId}/`);
          return fallbackResponse;
        } catch (fallbackError) {
          if (fallbackError.status === 404) {
            error.isMissingEndpoint = true;
            error.message = `The pull request details endpoint (GET /api/pull-requests/${prId}/) is awaiting implementation by the Django backend teammate.`;
          }
        }
      }

      if (error.status === 404) {
        error.isNotFound = true;
        error.message = `Pull request #${prId} could not be found.`;
      } else if (error.status === 401) {
        error.isUnauthorized = true;
        error.message = 'Authentication session expired. Please sign in again.';
      } else if (error.status === 403) {
        error.isForbidden = true;
        error.message = 'You do not have permission to view this pull request.';
      }

      throw error;
    }
  }
};

export default pullRequestsService;
