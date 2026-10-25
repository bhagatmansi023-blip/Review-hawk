import { Search, X, RotateCw, Filter, FolderGit2 } from 'lucide-react';
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
    selectedRepo,
    selectRepo,
    clearSelection,
    fetchRepositories,
    isLoading,
  } = useRepos();

  const handleClearSearch = () => {
    setSearchQuery('');
  };

  const currentSelectedId = selectedRepo ? String(selectedRepo.github_repo_id || selectedRepo.id) : '';

  const handleDropdownSelect = (e) => {
    const val = e.target.value;
    if (!val) {
      clearSelection();
    } else {
      const match = repositories.find((r) => String(r.github_repo_id || r.id) === String(val));
      if (match) {
        selectRepo(match);
      }
    }
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

        {/* Dropdown selector for repositories on page */}
        {repositories.length > 0 && (
          <div className="repo-page-select-wrapper">
            <FolderGit2 size={15} className="repo-select-icon" aria-hidden="true" />
            <select
              id="repo-page-selector"
              className="repo-page-select-dropdown"
              value={currentSelectedId}
              onChange={handleDropdownSelect}
              aria-label="Select from repositories on my page"
            >
              <option value="">-- Select from repositories on page --</option>
              {repositories.map((repo) => {
                const rId = String(repo.github_repo_id || repo.id);
                const owner = typeof repo.owner === 'object' ? repo.owner?.login : repo.owner;
                const fName = repo.full_name || `${owner}/${repo.name}`;
                const isConn = Boolean(repo.registered || repo.is_connected || repo.is_enabled);
                return (
                  <option key={rId} value={rId}>
                    {fName} {isConn ? '✓ (Connected)' : ''}
                  </option>
                );
              })}
            </select>
          </div>
        )}

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

        {/* Results Count Counter */}
        <div className="filter-results-counter">
          <span>
            Showing <strong>{filteredRepositories.length}</strong> of {repositories.length} repositories
          </span>
        </div>
      </div>
    </div>
  );
}
