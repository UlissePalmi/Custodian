import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

interface DataVersionValue {
  /** Include in a `useApi` dependency array to refetch on global data changes. */
  version: number
  /** Call after a write that can affect more than the current page (e.g. an import). */
  invalidate: () => void
}

const DataVersionContext = createContext<DataVersionValue>({ version: 0, invalidate: () => {} })

/**
 * A global "data changed" counter.
 *
 * A Chase import touches the month ledger, the yearly table and net worth at
 * once, so pages watch this counter rather than trying to track which specific
 * queries an action invalidated. With a real backend this is the seam where a
 * proper query cache would slot in.
 */
export function DataVersionProvider({ children }: { children: ReactNode }) {
  const [version, setVersion] = useState(0)
  const invalidate = useCallback(() => setVersion((n) => n + 1), [])
  const value = useMemo(() => ({ version, invalidate }), [version, invalidate])

  return <DataVersionContext.Provider value={value}>{children}</DataVersionContext.Provider>
}

export function useDataVersion(): DataVersionValue {
  return useContext(DataVersionContext)
}
