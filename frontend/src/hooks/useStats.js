import { useCallback, useEffect, useState } from 'react';
import reviewsService from '../services/reviews';

/**
 * Loads dashboard statistics for a date range (and optionally one repository).
 * Returns { data, isLoading, error, reload }.
 */
export function useStats({ days = 30, repo } = {}) {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let active = true;
    Promise.resolve().then(async () => {
      if (!active) return;
      setIsLoading(true);
      setError(null);
      try {
        const stats = await reviewsService.getStats({ days, repo });
        if (active) setData(stats);
      } catch (err) {
        if (active) setError(err);
      } finally {
        if (active) setIsLoading(false);
      }
    });
    return () => {
      active = false;
    };
  }, [days, repo, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, isLoading, error, reload };
}

export default useStats;
