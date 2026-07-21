import { useCallback, useEffect, useRef, useState } from 'react'

export interface UseApiResult<T> {
  data: T | null
  loading: boolean
  error: Error | null
  /** Re-runs the fetcher; used after every mutation. */
  refetch: () => void
}

/**
 * Runs an async API call and tracks loading/error/data.
 *
 * `deps` behaves like a `useEffect` dependency array — change it to refetch
 * (e.g. when the route's month key changes). The fetcher itself is held in a
 * ref so an inline arrow function doesn't cause a refetch loop.
 */
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    fetcherRef
      .current()
      .then((result) => {
        if (cancelled) return
        setData(result)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err : new Error(String(err)))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadToken])

  const refetch = useCallback(() => setReloadToken((n) => n + 1), [])

  return { data, loading, error, refetch }
}
