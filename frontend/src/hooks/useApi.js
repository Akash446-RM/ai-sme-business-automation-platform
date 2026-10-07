import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Run an async loader and expose { data, loading, error, reload }.
 * Results arriving after a newer request are discarded, so fast filter
 * changes can never render stale data.
 */
export function useApi(loader, dependencies = [], { skip = false } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(!skip);
  const [error, setError] = useState(null);
  const requestId = useRef(0);

  const execute = useCallback(async () => {
    const current = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const result = await loader();
      if (current === requestId.current) setData(result);
      return result;
    } catch (err) {
      if (current === requestId.current) {
        setError(err.message || 'Could not load data.');
      }
      return null;
    } finally {
      if (current === requestId.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);

  useEffect(() => {
    if (skip) {
      setLoading(false);
      return;
    }
    execute();
  }, [execute, skip]);

  return { data, loading, error, reload: execute, setData };
}

/** Debounce a rapidly changing value, used for search inputs. */
export function useDebounced(value, delay = 350) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

/** Standard paginated list state shared by every table screen. */
export function usePaginatedList(fetcher, filters = {}, pageSize = 15) {
  const [page, setPage] = useState(1);
  const serialised = JSON.stringify(filters);

  useEffect(() => {
    setPage(1);
  }, [serialised]);

  const { data, loading, error, reload } = useApi(
    () => fetcher({ ...filters, page, page_size: pageSize }),
    [serialised, page, pageSize],
  );

  return {
    items: data?.items ?? [],
    total: data?.total ?? 0,
    totalPages: data?.total_pages ?? 0,
    page,
    setPage,
    loading,
    error,
    reload,
  };
}
