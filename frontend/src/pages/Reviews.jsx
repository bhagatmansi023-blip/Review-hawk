import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Search, GitPullRequest } from 'lucide-react';
import { useRepos } from '../context/useRepos';
import reviewsService from '../services/reviews';
import ReviewsTable from '../components/reviews/ReviewsTable';
import ErrorNotice from '../components/common/ErrorNotice';

const PAGE_SIZE = 10;

export default function Reviews() {
  const { connectedRepos } = useRepos();
  const [status, setStatus] = useState('all');
  const [repo, setRepo] = useState('all');
  const [search, setSearch] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);

  const [result, setResult] = useState({ count: 0, results: [] });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);

  // Debounce the search box so we don't call the API on every keystroke.
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(search.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    let active = true;
    Promise.resolve().then(async () => {
      if (!active) return;
      setIsLoading(true);
      setError(null);
      try {
        const data = await reviewsService.getReviews({ page, status, repo, q });
        if (active) setResult(data);
      } catch (err) {
        if (active) setError(err);
      } finally {
        if (active) setIsLoading(false);
      }
    });
    return () => {
      active = false;
    };
  }, [page, status, repo, q, tick]);

  const totalPages = Math.max(1, Math.ceil((result.count || 0) / PAGE_SIZE));

  return (
    <div className="placeholder-page analytics-page">
      <div className="placeholder-header">
        <div>
          <h1 className="placeholder-title">Review History</h1>
          <p className="placeholder-desc">Every automated review: status, findings from AI and Tree-sitter, and PR health.</p>
        </div>
      </div>

      <div className="filters-bar">
        <label className="search-box">
          <Search size={15} />
          <input type="search" placeholder="Search by title, author or #number" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search reviews" />
        </label>
        <select className="filter-select" aria-label="Status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="all">All statuses</option>
          <option value="completed">Completed</option>
          <option value="running">Running</option>
          <option value="pending">Pending</option>
          <option value="failed">Failed</option>
        </select>
        <select className="filter-select" aria-label="Repository" value={repo} onChange={(e) => { setRepo(e.target.value); setPage(1); }}>
          <option value="all">All repositories</option>
          {(connectedRepos || []).map((r) => (
            <option key={r.id} value={r.id}>
              {r.full_name || `${r.owner}/${r.name}`}
            </option>
          ))}
        </select>
      </div>

      <ErrorNotice error={error} onRetry={() => setTick((t) => t + 1)} title="Could not load reviews" />

      <section className="chart-card" aria-label="Reviews">
        {isLoading ? (
          <div className="chart-skeleton" style={{ height: 240 }} role="status" aria-label="Loading reviews" />
        ) : result.results.length === 0 ? (
          <div className="chart-empty" style={{ height: 240 }}>
            <GitPullRequest size={28} />
            <p>{q || status !== 'all' || repo !== 'all' ? 'No reviews match these filters.' : 'No reviews yet. Open a pull request on a connected repository.'}</p>
          </div>
        ) : (
          <ReviewsTable reviews={result.results} />
        )}

        {!isLoading && result.count > PAGE_SIZE && (
          <footer className="pagination-bar">
            <span>
              Page {page} of {totalPages} · {result.count} reviews
            </span>
            <div>
              <button type="button" className="btn-secondary-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                <ChevronLeft size={14} /> Previous
              </button>
              <button type="button" className="btn-secondary-sm" disabled={!result.next} onClick={() => setPage((p) => p + 1)}>
                Next <ChevronRight size={14} />
              </button>
            </div>
          </footer>
        )}
      </section>
    </div>
  );
}
