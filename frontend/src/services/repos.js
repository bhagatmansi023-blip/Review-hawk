/**
 * Repository Service for CodeHawk
 * 
 * Handles interaction with Django REST Framework endpoints for GitHub repository
 * discovery, selection, and connection to CodeHawk's review bot.
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
      }
      throw error;
    }
  },

  /**
   * Retrieves currently connected repositories saved in Django's Repository model.
   * Calls GET /api/repos/connected/
   */
  async getConnectedRepositories() {
    try {
      const response = await apiService.get('/api/repos/connected/');
      if (response && Array.isArray(response.results)) {
        return response.results;
      }
      if (Array.isArray(response)) {
        return response;
      }
      return [];
    } catch (error) {
      // Non-fatal fallback: if connected-specific endpoint isn't wired yet
      if (error.status === 404) {
        return [];
      }
      throw error;
    }
  },

  /**
   * Connects a repository to CodeHawk to enable automated PR reviews.
   * Calls POST /api/repos/connect/
   */
  async connectRepository(repoData) {
    const payload = {
      github_repo_id: repoData.github_repo_id || repoData.id,
      owner: repoData.owner?.login || repoData.owner,
      name: repoData.name,
      default_branch: repoData.default_branch || 'main',
      is_private: Boolean(repoData.is_private || repoData.private),
    };

    try {
      const response = await apiService.post('/api/repos/connect/', payload);
      return response;
    } catch (error) {
      if (error.status === 404) {
        error.isMissingEndpoint = true;
        error.message = 'The repository connection endpoint (POST /api/repos/connect/) is awaiting implementation by the Django backend teammate.';
      }
      throw error;
    }
  },

  /**
   * Disconnects a repository from CodeHawk.
   * Calls DELETE /api/repos/{id}/
   */
  async disconnectRepository(repoId) {
    try {
      return await apiService.delete(`/api/repos/${repoId}/`);
    } catch (error) {
      if (error.status === 404) {
        // Fallback to POST disconnect action if DELETE is not supported
        return await apiService.post(`/api/repos/${repoId}/disconnect/`);
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
