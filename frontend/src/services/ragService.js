/**
 * RAG (Repository-Aware Generation) Service
 * Handles interaction with the RAG indexing API endpoints.
 * GET  /api/rag/repos/<repo_id>/index-status/
 * POST /api/rag/repos/<repo_id>/reindex/
 */
import apiService from './api';

export const ragService = {
  /**
   * Get the RAG index status for a connected repository.
   * @param {number|string} repoId - Django DB primary key of the repository
   * @returns {Promise<{status, indexed_at, indexed_files, indexed_chunks, indexed_commit_sha, error}>}
   */
  async getIndexStatus(repoId) {
    try {
      return await apiService.get(`/api/rag/repos/${repoId}/index-status/`);
    } catch (error) {
      if (error.status === 404) {
        return {
          status: 'never',
          indexed_at: null,
          indexed_files: 0,
          indexed_chunks: 0,
          indexed_commit_sha: '',
          error: '',
        };
      }
      throw error;
    }
  },

  /**
   * Trigger reindexing of a repository.
   * @param {number|string} repoId - Django DB primary key of the repository
   * @returns {Promise<{detail: string}>}
   */
  async triggerReindex(repoId) {
    return await apiService.post(`/api/rag/repos/${repoId}/reindex/`, {});
  },
};

export default ragService;
