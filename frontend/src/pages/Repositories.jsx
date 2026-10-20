import { useRepos } from '../context/useRepos';
import RepoHeader from '../components/repos/RepoHeader';
import RepoSearchFilter from '../components/repos/RepoSearchFilter';
import RepoTable from '../components/repos/RepoTable';
import RepoActionBanner from '../components/repos/RepoActionBanner';
import RepoEmptyState from '../components/repos/RepoEmptyState';
import RepoPermissionNotice from '../components/repos/RepoPermissionNotice';
import RepoContractModal from '../components/repos/RepoContractModal';

export default function Repositories() {
  const {
    repositories,
    filteredRepositories,
    isLoading,
    error,
    searchQuery,
  } = useRepos();

  const renderContent = () => {
    // State 2: Loading
    if (isLoading) {
      return <RepoEmptyState type="loading" />;
    }

    // Backend missing endpoint state
    if (error && error.isMissingEndpoint) {
      return <RepoEmptyState type="missing_endpoint" />;
    }

    // State 4: No repositories returned from GitHub
    if (repositories.length === 0) {
      return <RepoEmptyState type="no_repos" />;
    }

    // State 6: Search with no matches
    if (filteredRepositories.length === 0 && searchQuery) {
      return <RepoEmptyState type="search_no_match" />;
    }

    // State 3 & 5: Repositories loaded or search with matches
    return <RepoTable />;
  };

  return (
    <div className="repo-page-container">
      {/* Page Header */}
      <RepoHeader />

      {/* Action and status notifications banner */}
      <RepoActionBanner />

      {/* Search and filters bar */}
      <RepoSearchFilter />

      {/* Main repository list or state */}
      <section className="repo-list-section" aria-label="Repository List">
        {renderContent()}
      </section>

      {/* Modals */}
      <RepoPermissionNotice />
      <RepoContractModal />
    </div>
  );
}
