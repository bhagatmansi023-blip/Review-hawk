import { Search, X, Filter } from 'lucide-react';

export default function PRSearchFilter({
  searchQuery = '',
  onSearchChange = null,
  statusFilter = 'all',
  onStatusFilterChange = null,
  reviewFilter = 'all',
  onReviewFilterChange = null,
  totalCount = 0,
  filteredCount = 0,
}) {
  const statusOptions = [
    { id: 'all', label: 'All Statuses' },
    { id: 'open', label: 'Open' },
    { id: 'closed', label: 'Closed' },
    { id: 'merged', label: 'Merged' },
  ];

  const reviewOptions = [
    { id: 'all', label: 'All Reviews' },
    { id: 'completed', label: 'Review Completed' },
    { id: 'pending', label: 'Review Pending' },
    { id: 'failed', label: 'Review Failed' },
    { id: 'none', label: 'No Review Yet' },
  ];

  const hasActiveFilters = searchQuery.trim() !== '' || statusFilter !== 'all' || reviewFilter !== 'all';

  const handleClearAll = () => {
    if (onSearchChange) onSearchChange('');
    if (onStatusFilterChange) onStatusFilterChange('all');
    if (onReviewFilterChange) onReviewFilterChange('all');
  };

  return (
    <div className="repo-search-container" aria-label="Pull Request Search and Filters">
      <div className="repo-search-row">
        {/* Search input with live clear button */}
        <div className="repo-search-input-wrapper">
          <Search size={16} className="search-icon" aria-hidden="true" />
          <input
            type="text"
            className="repo-search-input"
            placeholder="Search by pull request title, #number, or author..."
            value={searchQuery}
            onChange={(e) => onSearchChange && onSearchChange(e.target.value)}
            aria-label="Search pull requests"
          />
          {searchQuery && (
            <button
              type="button"
              className="search-clear-btn"
              onClick={() => onSearchChange && onSearchChange('')}
              aria-label="Clear search query"
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* Status Count and Reset */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className="repo-count-badge">
            Showing <strong>{filteredCount}</strong> of {totalCount} PR{totalCount === 1 ? '' : 's'}
          </span>
          {hasActiveFilters && (
            <button
              type="button"
              className="btn-text-action"
              onClick={handleClearAll}
              style={{ fontSize: '0.8rem' }}
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Filter Pills Groups */}
      <div className="repo-filters-row">
        {/* GitHub Status Filter */}
        <div className="filter-group-container">
          <span className="filter-group-label">GitHub State:</span>
          <div className="filter-pill-group" role="radiogroup" aria-label="Filter by GitHub PR State">
            {statusOptions.map((opt) => (
              <button
                key={opt.id}
                type="button"
                className={`filter-pill ${statusFilter === opt.id ? 'active' : ''}`}
                onClick={() => onStatusFilterChange && onStatusFilterChange(opt.id)}
                role="radio"
                aria-checked={statusFilter === opt.id}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* CodeHawk Review Status Filter */}
        <div className="filter-group-container">
          <span className="filter-group-label">
            <Filter size={12} style={{ display: 'inline', marginRight: '4px' }} />
            Review Verdict:
          </span>
          <div className="filter-pill-group" role="radiogroup" aria-label="Filter by CodeHawk Review Status">
            {reviewOptions.map((opt) => (
              <button
                key={opt.id}
                type="button"
                className={`filter-pill ${reviewFilter === opt.id ? 'active' : ''}`}
                onClick={() => onReviewFilterChange && onReviewFilterChange(opt.id)}
                role="radio"
                aria-checked={reviewFilter === opt.id}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
