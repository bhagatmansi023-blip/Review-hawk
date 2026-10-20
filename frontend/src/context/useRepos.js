import { useContext } from 'react';
import { RepoContext } from './repoContextDef';

export function useRepos() {
  const context = useContext(RepoContext);
  if (!context) {
    throw new Error('useRepos must be used within a RepoProvider');
  }
  return context;
}

export default useRepos;
