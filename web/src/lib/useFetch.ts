import { useEffect, useState, useRef, useCallback } from 'react';
import { ApiError, apiGet } from './api';

export interface FetchState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useFetch<T>(path: string | null, deps: unknown[] = []): FetchState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(path !== null);
  const [error, setError] = useState<string | null>(null);
  // Track the latest call so an old slow response doesn't overwrite a new one.
  const callId = useRef(0);

  const run = useCallback(async () => {
    if (path === null) return;
    const id = ++callId.current;
    setLoading(true);
    setError(null);
    try {
      const result = await apiGet<T>(path);
      if (callId.current === id) {
        setData(result);
        setLoading(false);
      }
    } catch (e) {
      if (callId.current === id) {
        const msg =
          e instanceof ApiError ? `${e.status}: ${e.message}` :
          e instanceof Error ? e.message :
          'Request failed.';
        setError(msg);
        setLoading(false);
      }
    }
  }, [path]);

  useEffect(() => { run(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [path, ...deps]);

  return { data, loading, error, refresh: run };
}
