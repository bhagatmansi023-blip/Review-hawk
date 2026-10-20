import { Search, X, RotateCw, Filter } from 'lucide-react';
import { useRepos } from '../../context/useRepos';

export default function RepoSearchFilter() {
  const {
    searchQuery,
    setSearchQuery,
    filterVisibility,
    setFilterVisibility,
    filterConnected,
    setFilterConnected,
    filteredRepositories,
    repositories,
    fetchRepositories,
    isLoading,
  } = useRepos();

  const handleClearSearch = () => {
    setSearchQuery('');
  };

  return (
    <div className="repo-search-filter-card">
      <div className="repo-search-row">
        {/* Search input field */}
        <div className="repo-search-input-wrapper">
          <Search size={16} className="search-icon" aria-hidden="true" />
          <input
            type="text"
            id="repo-search-input"
            className="repo-search-input"
            placeholder="Search repositories by name or owner..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search repositories"
          />
          {searchQuery && (
            <button
              type="button"
              className="btn-search-clear"
              onClick={handleClearSearch}
              aria-label="Clear search query"
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* Refresh action */}
        <button
          type="button"
          className="btn-repo-refresh"
          onClick={fetchRepositories}
          disabled={isLoading}
          title="Refresh repository list from backend"
          aria-label="Refresh repositories"
        >
          <RotateCw size={14} className={isLoading ? 'spin-icon' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      <div className="repo-filter-row">
        {/* Visibility filter pills */}
        <div className="filter-pill-group">
          <span className="filter-label">
            <Filter size={13} />
            <span>Visibility:</span>
          </span>
          <button
            type="button"
            className={`filter-pill ${filterVisibility === 'all' ? 'active' : ''}`}
            onClick={() => setFilterVisibility('all')}
          >
            All
          </button>
          <button
            type="button"
            className={`filter-pill ${filterVisibility === 'public' ? 'active' : ''}`}
            onClick={() => setFilterVisibility('public')}
          >
            Public
          </button>
          <button
            type="button"
            className={`filter-pill ${filterVisibility === 'private' ? 'active' : ''}`}
            onClick={() => setFilterVisibility('private')}
          >
            Private
          </button>
        </div>

        {/* Connection status filter pills */}
        <div className="filter-pill-group">
          <span className="filter-label">Status:</span>
          <button
            type="button"
            className={`filter-pill ${filterConnected === 'all' ? 'active' : ''}`}
            onClick={() => setFilterConnected('all')}
          >
            All
          </button>
          <button
            type="button"
            className={`filter-pill ${filterConnected === 'connected' ? 'active' : ''}`}
            onClick={() => setFilterConnected('connected')}
          >
            Connected
          </button>
          <button
            type="button"
            className={`filter-pill ${filterConnected === 'unconnected' ? 'active' : ''}`}
            onClick={() => setFilterConnected('unconnected')}
          >
            Available
          </button>
        </div>

        {/* Count summary */}
        <div className="repo-count-badge">
          <span>
            {repositories.length > 0 ? (
              <>Showing <strong>{filteredRepositories.length}</strong> of {repositories.length}</>
            ) : (
              '0 repositories'
            )}
          </span>
        </div>
      </div>
    </div>
  );
}
