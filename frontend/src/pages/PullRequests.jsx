import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useRepos } from '../context/useRepos';
import pullRequestsService from '../services/pullRequests';
import PRHeader from '../components/pullRequests/PRHeader';
import PRSearchFilter from '../components/pullRequests/PRSearchFilter';
import PRTable from '../components/pullRequests/PRTable';
import PREmptyState from '../components/pullRequests/PREmptyState';
import PRContractModal from '../components/pullRequests/PRContractModal';

export default function PullRequests() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { connectedRepos, activeRepo, setActiveRepo } = useRepos();

  // Pull request list state
  const [pullRequests, setPullRequests] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Filters state
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // 'all' | 'open' | 'closed' | 'merged'
  const [reviewFilter, setReviewFilter] = useState('all'); // 'all' | 'completed' | 'pending' | 'failed' | 'none'

  // Contract modal
  const [isContractModalOpen, setIsContractModalOpen] = useState(false);

  // Synchronize repo from URL query param ?repo= if present
  useEffect(() => {
    const repoParam = searchParams.get('repo');
    if (repoParam && connectedRepos.length > 0) {
      const match = connectedRepos.find(
        (r) => String(r.id) === repoParam || String(r.github_repo_id) === repoParam
      );
      if (match && (!activeRepo || (activeRepo.id !== match.id && activeRepo.github_repo_id !== match.github_repo_id))) {
        setActiveRepo(match);
      }
    }
  }, [searchParams, connectedRepos, activeRepo, setActiveRepo]);

  // Fetch pull requests from backend
  const fetchPullRequests = useCallback(async () => {
    if (!activeRepo) {
      setPullRequests([]);
      return;
    }

    const repoId = activeRepo.id || activeRepo.github_repo_id;
    setIsLoading(true);
    setError(null);

    try {
      const response = await pullRequestsService.getPullRequests(repoId, {
        state: statusFilter !== 'all' ? statusFilter : undefined,
      });
      setPullRequests(response.results || []);
    } catch (err) {
      setError(err);
      setPullRequests([]);
    } finally {
      setIsLoading(false);
    }
  }, [activeRepo, statusFilter]);

  // Re-fetch when active repo or status filter changes
  useEffect(() => {
    let isMounted = true;
    Promise.resolve().then(() => {
      if (isMounted) {
        fetchPullRequests();
      }
    });
    return () => {
      isMounted = false;
    };
  }, [fetchPullRequests]);

  // Client-side search and review filter refinement
  const filteredPullRequests = useMemo(() => {
    return pullRequests.filter((pr) => {
      // 1. Text Search Filter (matches title, #number, author)
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        const title = (pr.title || '').toLowerCase();
        const number = String(pr.number || pr.id || '');
        const numberTag = `#${number}`;
        const author = (pr.author || pr.user?.login || '').toLowerCase();

        if (
          !title.includes(query) &&
          !number.includes(query) &&
          !numberTag.includes(query) &&
          !author.includes(query)
        ) {
          return false;
        }
      }

      // 2. Status Filter (if not already handled by server)
      if (statusFilter !== 'all') {
        const prState = (pr.state || '').toLowerCase();
        if (prState !== statusFilter) return false;
      }

      // 3. Review Verdict Filter
      if (reviewFilter !== 'all') {
        const review = pr.latest_review || (typeof pr.review === 'object' ? pr.review : null);
        const reviewStatus = (review?.status || pr.review_status || '').toLowerCase();

        if (reviewFilter === 'none') {
          if (reviewStatus && reviewStatus !== 'none') return false;
        } else {
          if (reviewStatus !== reviewFilter) return false;
        }
      }

      return true;
    });
  }, [pullRequests, searchQuery, statusFilter, reviewFilter]);

  const handleSelectRepo = (repo) => {
    setActiveRepo(repo);
    const repoId = repo.id || repo.github_repo_id;
    setSearchParams({ repo: String(repoId) });
  };

  const handleClearFilters = () => {
    setSearchQuery('');
    setStatusFilter('all');
    setReviewFilter('all');
  };

  const renderContent = () => {
    // State 1: No repository connected or selected
    if (!activeRepo) {
      return <PREmptyState type="no_repo_selected" />;
    }

    // State 2: Pull requests loading
    if (isLoading) {
      return <PREmptyState type="loading" />;
    }

    // Missing Endpoint (Backend contract guide)
    if (error && error.isMissingEndpoint) {
      return (
        <PREmptyState
          type="missing_endpoint"
          activeRepo={activeRepo}
          error={error}
          onRetry={fetchPullRequests}
          onOpenContract={() => setIsContractModalOpen(true)}
        />
      );
    }

    // State 7: Unauthorized
    if (error && error.isUnauthorized) {
      return <PREmptyState type="unauthorized" error={error} />;
    }

    // State 8: Forbidden
    if (error && error.isForbidden) {
      return (
        <PREmptyState
          type="forbidden"
          activeRepo={activeRepo}
          error={error}
          onRetry={fetchPullRequests}
        />
      );
    }

    // State 6: Request failed error
    if (error) {
      return (
        <PREmptyState
          type="request_failed"
          activeRepo={activeRepo}
          error={error}
          onRetry={fetchPullRequests}
        />
      );
    }

    // State 4: Connected repository has zero pull requests
    if (pullRequests.length === 0) {
      return (
        <PREmptyState
          type="no_prs"
          activeRepo={activeRepo}
        />
      );
    }

    // State 5: Search & filter returned no results
    if (filteredPullRequests.length === 0) {
      return (
        <PREmptyState
          type="search_no_match"
          onClearFilters={handleClearFilters}
        />
      );
    }

    // State 3: Pull requests loaded successfully
    return (
      <PRTable
        pullRequests={filteredPullRequests}
        activeRepo={activeRepo}
      />
    );
  };

  return (
    <div className="repo-page-container" aria-label="Pull Requests Page">
      {/* Header with Title, Description, Active Repo, and Switcher */}
      <PRHeader
        activeRepo={activeRepo}
        connectedRepos={connectedRepos}
        onSelectRepo={handleSelectRepo}
        onRefresh={fetchPullRequests}
        isLoading={isLoading}
      />

      {/* Search and Filters Bar (rendered when active repo exists) */}
      {activeRepo && (
        <PRSearchFilter
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          reviewFilter={reviewFilter}
          onReviewFilterChange={setReviewFilter}
          totalCount={pullRequests.length}
          filteredCount={filteredPullRequests.length}
        />
      )}

      {/* Main Pull Requests Content or Empty/Error State */}
      <section className="repo-list-section" aria-label="Pull Requests List">
        {renderContent()}
      </section>

      {/* Backend Contract Modal */}
      <PRContractModal
        isOpen={isContractModalOpen}
        onClose={() => setIsContractModalOpen(false)}
      />
    </div>
  );
}
