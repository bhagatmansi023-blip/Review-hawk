/**
 * Repository Service for CodeHawk
 * 
 * Handles interaction with Django REST Framework endpoints for GitHub repository
 * discovery, selection, and connection to CodeHawk's review bot.
 * 
 * Backed by Django endpoints:
 * - GET  /api/repos/                                → List GitHub repos for authenticated user
 * - POST /api/repos/register/                       → Register webhook on repo(s)
 * - DELETE /api/repos/<github_repo_id>/unregister/  → Unregister webhook and disable repo
 */

import apiService from './api';

export const repoService = {
  /**
   * Retrieves the list of GitHub repositories accessible to the authenticated user.
   * Calls GET /api/repos/
   */
  async getRepositories() {
    try {
      const response = await apiService.get('/api/repos/');
      
      // Standardize pagination: if wrapped in DRF PageNumberPagination { count, results }
      if (response && Array.isArray(response.results)) {
        return response.results;
      }
      if (Array.isArray(response)) {
        return response;
      }
      return [];
    } catch (error) {
      // Annotate endpoint status for UI messaging
      if (error.status === 404) {
        error.isMissingEndpoint = true;
        error.message = 'The repository list endpoint (GET /api/repos/) is awaiting implementation by the Django backend teammate.';
      } else if (error.status === 401) {
        error.isUnauthorized = true;
        error.message = 'Authentication session expired or unauthorized. Please re-authenticate with GitHub.';
      } else if (error.status === 403) {
        error.isForbidden = true;
        error.message = 'Insufficient GitHub repository permissions. Additional access scopes are required.';
      } else if (error.status === 400 && error.data?.detail) {
        error.message = error.data.detail;
      } else if (error.status === 502 && error.data?.detail) {
        error.message = error.data.detail;
      }
      throw error;
    }
  },

  /**
   * Registers webhook on the specified repository to connect it to CodeHawk.
   * Calls POST /api/repos/register/
   * Expected backend request format:
   * { "repos": [{ "github_repo_id": <int>, "owner": "<str>", "name": "<str>" }] }
   */
  async connectRepository(repoData) {
    const ownerName = typeof repoData.owner === 'object' ? (repoData.owner?.login || repoData.owner?.name) : repoData.owner;
    const repoId = Number(repoData.github_repo_id || repoData.id);

    const payload = {
      repos: [
        {
          github_repo_id: repoId,
          owner: ownerName,
          name: repoData.name,
        }
      ]
    };

    try {
      const response = await apiService.post('/api/repos/register/', payload);
      // Backend returns { results: [{ full_name, success, detail, repo }] }
      if (response && Array.isArray(response.results) && response.results.length > 0) {
        const item = response.results[0];
        if (!item.success) {
          throw new Error(item.detail || `Failed to register webhook on ${item.full_name || repoData.name}`);
        }
        return item.repo || item;
      }
      return response;
    } catch (error) {
      if (error.status === 404) {
        error.isMissingEndpoint = true;
        error.message = 'The repository registration endpoint (POST /api/repos/register/) was not found on the backend.';
      } else if (error.data?.detail) {
        error.message = error.data.detail;
      }
      throw error;
    }
  },

  /**
   * Disconnects a repository from CodeHawk by unregistering its webhook.
   * Calls DELETE /api/repos/<github_repo_id>/unregister/
   */
  async disconnectRepository(repoId) {
    const githubRepoId = Number(repoId);
    try {
      return await apiService.delete(`/api/repos/${githubRepoId}/unregister/`);
    } catch (error) {
      if (error.status === 404) {
        error.isMissingEndpoint = true;
        error.message = `The repository unregister endpoint (DELETE /api/repos/${githubRepoId}/unregister/) was not found on the backend.`;
      } else if (error.data?.detail) {
        error.message = error.data.detail;
      }
      throw error;
    }
  },

  /**
   * Returns GitHub settings URL where user can review or grant additional organization
   * or repository access permissions.
   */
  getGitHubPermissionsUrl() {
    return 'https://github.com/settings/connections/applications';
  }
};

export default repoService;
