import { useState, useEffect, useCallback, useMemo } from 'react';
import { RepoContext } from './repoContextDef';
import repoService from '../services/repos';
import { useAuth } from './useAuth';

export function RepoProvider({ children }) {
  const { isAuthenticated } = useAuth();

  const [repositories, setRepositories] = useState([]);
  const [connectedRepos, setConnectedRepos] = useState([]);
  const [selectedRepo, setSelectedRepo] = useState(null);
  const [activeRepoId, setActiveRepoId] = useState(() => {
    try {
      return localStorage.getItem('codehawk_active_repo_id') || null;
    } catch {
      return null;
    }
  });
  const [isLoading, setIsLoading] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // Search & Filtering State
  const [searchQuery, setSearchQuery] = useState('');
  const [filterVisibility, setFilterVisibility] = useState('all'); // 'all' | 'public' | 'private'
  const [filterConnected, setFilterConnected] = useState('all');   // 'all' | 'connected' | 'unconnected'

  // Active connected repository for PRs and reviews
  const activeRepo = useMemo(() => {
    if (!connectedRepos || connectedRepos.length === 0) return null;
    if (activeRepoId) {
      const found = connectedRepos.find(
        (r) => String(r.id) === String(activeRepoId) || String(r.github_repo_id) === String(activeRepoId)
      );
      if (found) return found;
    }
    return connectedRepos[0];
  }, [connectedRepos, activeRepoId]);

  const setActiveRepo = useCallback((repoOrId) => {
    if (!repoOrId) {
      setActiveRepoId(null);
      try {
        localStorage.removeItem('codehawk_active_repo_id');
      } catch {
        // Ignore storage errors
      }
      return;
    }
    const id = typeof repoOrId === 'object' ? (repoOrId.id || repoOrId.github_repo_id) : repoOrId;
    setActiveRepoId(id);
    try {
      localStorage.setItem('codehawk_active_repo_id', String(id));
    } catch {
      // Ignore storage errors
    }
  }, []);

  // Modals for Contract, Permissions, and Connect
  const [isContractModalOpen, setIsContractModalOpen] = useState(false);
  const [isPermissionModalOpen, setIsPermissionModalOpen] = useState(false);
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);

  // Fetch repositories from real Django backend
  const fetchRepositories = useCallback(async () => {
    if (!isAuthenticated) {
      setRepositories([]);
      setConnectedRepos([]);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const repos = await repoService.getRepositories();
      setRepositories(repos);

      // Determine connected repos directly from backend response:
      // In DRF ListGitHubReposView, `registered` indicates tracked in database with webhook
      const connected = repos.filter(
        (r) => Boolean(r.registered || r.is_enabled || r.is_connected)
      );
      setConnectedRepos(connected);
    } catch (err) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  // Initial fetch on mount or when auth state changes
  useEffect(() => {
    if (!isAuthenticated) {
      return;
    }

    let isMounted = true;
    Promise.resolve().then(() => {
      if (isMounted) {
        fetchRepositories();
      }
    });

    return () => {
      isMounted = false;
    };
  }, [isAuthenticated, fetchRepositories]);

  // Select a repository for connection
  const selectRepo = useCallback((repo) => {
    setSelectedRepo((prev) => {
      // Toggle off if clicking the already selected repo
      if (prev && ((prev.github_repo_id && prev.github_repo_id === repo.github_repo_id) || prev.id === repo.id)) {
        return null;
      }
      return repo;
    });
    setError(null);
    setSuccessMessage(null);
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedRepo(null);
  }, []);

  // Connect the currently selected repository
  const connectSelectedRepo = useCallback(async () => {
    if (!selectedRepo || isConnecting) return;

    setIsConnecting(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const result = await repoService.connectRepository(selectedRepo);

      const targetId = Number(selectedRepo.github_repo_id || selectedRepo.id);
      const connectedItem = {
        ...selectedRepo,
        ...(typeof result === 'object' ? result : {}),
        registered: true,
        is_connected: true,
        is_enabled: true,
      };

      setConnectedRepos((prev) => {
        const exists = prev.some((r) => Number(r.github_repo_id || r.id) === targetId);
        return exists ? prev : [connectedItem, ...prev];
      });

      // Update repositories list to mark as connected/registered
      setRepositories((prev) =>
        prev.map((r) =>
          Number(r.github_repo_id || r.id) === targetId
            ? { ...r, registered: true, is_connected: true, is_enabled: true }
            : r
        )
      );

      const repoName = selectedRepo.full_name || `${typeof selectedRepo.owner === 'object' ? selectedRepo.owner?.login : selectedRepo.owner}/${selectedRepo.name}`;
      setSuccessMessage(`Repository "${repoName}" successfully connected! CodeHawk review bot is now enabled.`);
      setSelectedRepo(null);
    } catch (err) {
      setError(err);
    } finally {
      setIsConnecting(false);
    }
  }, [selectedRepo, isConnecting]);

  // Disconnect a connected repository
  const disconnectRepo = useCallback(async (repoId) => {
    setIsConnecting(true);
    setError(null);
    const targetId = Number(repoId);

    try {
      await repoService.disconnectRepository(targetId);
      setConnectedRepos((prev) => prev.filter((r) => Number(r.github_repo_id || r.id) !== targetId));
      setRepositories((prev) =>
        prev.map((r) =>
          Number(r.github_repo_id || r.id) === targetId
            ? { ...r, registered: false, is_connected: false, is_enabled: false }
            : r
        )
      );
      setSuccessMessage('Repository disconnected successfully.');
    } catch (err) {
      setError(err);
    } finally {
      setIsConnecting(false);
    }
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const clearSuccessMessage = useCallback(() => {
    setSuccessMessage(null);
  }, []);

  // Filtered repositories based on search and visibility pills
  const filteredRepositories = useMemo(() => {
    return repositories.filter((repo) => {
      // 1. Search Query filter (matches name, owner, or full_name)
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase().trim();
        const name = (repo.name || '').toLowerCase();
        const owner = (typeof repo.owner === 'object' ? repo.owner?.login || '' : repo.owner || '').toLowerCase();
        const fullName = (repo.full_name || `${owner}/${name}`).toLowerCase();
        if (!name.includes(query) && !owner.includes(query) && !fullName.includes(query)) {
          return false;
        }
      }

      // 2. Visibility filter
      const isPrivate = Boolean(repo.is_private || repo.private);
      if (filterVisibility === 'public' && isPrivate) return false;
      if (filterVisibility === 'private' && !isPrivate) return false;

      // 3. Connected status filter
      const isConnected = Boolean(
        repo.registered ||
        repo.is_connected ||
        connectedRepos.some((c) => Number(c.github_repo_id || c.id) === Number(repo.github_repo_id || repo.id))
      );
      if (filterConnected === 'connected' && !isConnected) return false;
      if (filterConnected === 'unconnected' && isConnected) return false;

      return true;
    });
  }, [repositories, connectedRepos, searchQuery, filterVisibility, filterConnected]);

  const value = {
    repositories,
    filteredRepositories,
    connectedRepos,
    selectedRepo,
    activeRepo,
    activeRepoId,
    setActiveRepo,
    isLoading,
    isConnecting,
    error,
    successMessage,
    searchQuery,
    setSearchQuery,
    filterVisibility,
    setFilterVisibility,
    filterConnected,
    setFilterConnected,
    fetchRepositories,
    selectRepo,
    clearSelection,
    connectSelectedRepo,
    disconnectRepo,
    clearError,
    clearSuccessMessage,
    isContractModalOpen,
    setIsContractModalOpen,
    isPermissionModalOpen,
    setIsPermissionModalOpen,
    isConnectModalOpen,
    setIsConnectModalOpen,
  };

  return <RepoContext.Provider value={value}>{children}</RepoContext.Provider>;
}

export default RepoProvider;
