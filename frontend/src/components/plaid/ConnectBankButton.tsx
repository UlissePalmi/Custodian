import { useCallback, useEffect, useState } from 'react'
import { usePlaidLink, type PlaidLinkOnSuccessMetadata } from 'react-plaid-link'
import { Landmark } from 'lucide-react'
import { Button } from '../ui/Button'
import { Spinner } from '../ui/States'
import {
  disconnectPlaid,
  exchangePlaidToken,
  getPlaidLinkToken,
  getPlaidStatus,
  type PlaidConnection,
} from '../../api'
import { useDataVersion } from '../../context/DataVersion'

const IS_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

/**
 * Survives the bank's OAuth redirect round trip — Link tokens are single-use
 * and the page navigates away to the bank and back during that flow.
 *
 * localStorage rather than sessionStorage: the bank can return the user in a
 * *different tab* (routine on mobile), and sessionStorage is per-tab, so the
 * token would be missing exactly when Link needs it to resume — which strands
 * the flow on a blank page. Plaid's OAuth guide calls for localStorage or a
 * cookie for this reason.
 */
const LINK_TOKEN_STORAGE_KEY = 'custodian.plaid.linkToken'

function isOAuthRedirectReturn(): boolean {
  if (typeof window === 'undefined') return false
  return new URLSearchParams(window.location.search).has('oauth_state_id')
}

function readStoredLinkToken(): string | null {
  try {
    return localStorage.getItem(LINK_TOKEN_STORAGE_KEY)
  } catch {
    return null // Private-mode or storage-disabled browsers.
  }
}

function writeStoredLinkToken(token: string): void {
  try {
    localStorage.setItem(LINK_TOKEN_STORAGE_KEY, token)
  } catch {
    // Non-fatal: only the OAuth resume depends on it.
  }
}

function clearStoredLinkToken(): void {
  try {
    localStorage.removeItem(LINK_TOKEN_STORAGE_KEY)
  } catch {
    // Ignore.
  }
}

interface ConnectBankButtonProps {
  className?: string
  /** Tight layout for the mobile header — icon-only button, no institution
   *  name row, since there's no room for either there. */
  compact?: boolean
}

/**
 * "Connect Chase" entry point for Plaid bank sync, plus the connected state
 * (institution name, disconnect). Rendered twice: full in the desktop
 * sidebar, `compact` in the mobile header — there's no settings page yet, so
 * this is the only place either layout can reach it.
 */
export default function ConnectBankButton({ className = '', compact = false }: ConnectBankButtonProps) {
  const { invalidate } = useDataVersion()
  const [connections, setConnections] = useState<PlaidConnection[]>([])

  // Captured once, synchronously, on the very first render. Link has to be
  // initialised with the original token *and* the full return URL together;
  // discovering either one render late leaves Link briefly initialised with
  // nothing to resume from, which is what strands the flow.
  const [redirectHref] = useState<string | null>(() =>
    isOAuthRedirectReturn() ? window.location.href : null,
  )
  const [linkToken, setLinkToken] = useState<string | null>(() =>
    isOAuthRedirectReturn() ? readStoredLinkToken() : null,
  )
  const [busy, setBusy] = useState(() => isOAuthRedirectReturn())
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getPlaidStatus()
      .then(setConnections)
      .catch(() => setConnections([]))
  }, [])

  // Strip oauth_state_id once captured, so a refresh doesn't try to resume a
  // flow that's already been consumed. `redirectHref` keeps the original URL.
  useEffect(() => {
    if (redirectHref) {
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [redirectHref])

  // Came back from the bank but the token is gone (storage cleared, or a
  // browser that dropped it). Say so instead of sitting on a dead spinner.
  useEffect(() => {
    if (redirectHref && !linkToken) {
      setBusy(false)
      setError('Could not resume the bank connection. Please try connecting again.')
    }
  }, [redirectHref, linkToken])

  const onSuccess = useCallback(
    async (publicToken: string, metadata: PlaidLinkOnSuccessMetadata) => {
      clearStoredLinkToken()
      setBusy(true)
      setError(null)
      try {
        const connection = await exchangePlaidToken(
          publicToken,
          metadata.institution?.institution_id ?? undefined,
          metadata.institution?.name ?? undefined,
        )
        setConnections((prev) => [...prev.filter((c) => c.itemId !== connection.itemId), connection])
        invalidate()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not connect that account.')
      } finally {
        setBusy(false)
      }
    },
    [invalidate],
  )

  const { open, ready } = usePlaidLink({
    // null until there's a real token — Link stays uninitialised rather than
    // initialising against an empty string.
    token: linkToken,
    onSuccess,
    // Only meaningful alongside the token that started the flow; sending it
    // without one is what produces a dead-end blank page.
    receivedRedirectUri: redirectHref && linkToken ? redirectHref : undefined,
  })

  // Opens as soon as a token is set and Link has initialised with it — covers
  // both the first open and the OAuth-redirect resume.
  useEffect(() => {
    if (linkToken && ready) {
      open()
      setBusy(false)
    }
  }, [linkToken, ready, open])

  async function startConnect() {
    setError(null)
    setBusy(true)

    if (IS_MOCK) {
      // No real Plaid Link in mock mode — the mock's exchange endpoint
      // fabricates a connection directly, same shape the real flow ends in.
      try {
        const connection = await exchangePlaidToken('mock-public-token', 'chase', 'Chase (mock)')
        setConnections((prev) => [...prev.filter((c) => c.itemId !== connection.itemId), connection])
        invalidate()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Could not connect that account.')
      } finally {
        setBusy(false)
      }
      return
    }

    try {
      const { linkToken: token } = await getPlaidLinkToken()
      writeStoredLinkToken(token)
      setLinkToken(token)
      // `busy` stays true until the `ready`-triggered `open()` effect fires.
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start bank connection.')
      setBusy(false)
    }
  }

  async function disconnect(itemId: string) {
    setBusy(true)
    setError(null)
    try {
      await disconnectPlaid(itemId)
      setConnections((prev) => prev.filter((c) => c.itemId !== itemId))
      invalidate()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not disconnect.')
    } finally {
      setBusy(false)
    }
  }

  // Every linked institution is its own connection, and more can always be
  // added — a second card's transactions are what let its payments be
  // recognised as transfers rather than counted as spending.
  const linked = connections.filter((c) => c.status !== 'disconnected')
  const anyError = linked.some((c) => c.status === 'error')

  if (compact) {
    return (
      <div className={className}>
        <button
          type="button"
          onClick={() => void startConnect()}
          disabled={busy}
          title={linked.length ? `${linked.map((c) => c.institutionName).join(', ')} — tap to add another` : 'Connect a bank'}
          className={`flex items-center justify-center rounded-lg p-2 transition-colors hover:bg-terminal-navy-light disabled:opacity-50 ${
            anyError ? 'text-rose-400' : linked.length ? 'text-terminal-gold' : 'text-slate-400 hover:text-white'
          }`}
        >
          {busy ? <Spinner className="size-5" /> : <Landmark className="size-5" aria-hidden />}
          <span className="sr-only">
            {linked.length ? `${linked.length} bank(s) connected. Add another.` : 'Connect a bank'}
          </span>
        </button>
      </div>
    )
  }

  return (
    <div className={className}>
      {linked.length > 0 && (
        <ul className="mb-2 space-y-1">
          {linked.map((connection) => (
            <li key={connection.itemId} className="flex items-center justify-between gap-2 text-xs text-slate-400">
              <span className="truncate">
                {connection.institutionName}
                {connection.status === 'error' && <span className="ml-1 text-rose-400">· sync error</span>}
              </span>
              <button
                type="button"
                onClick={() => void disconnect(connection.itemId)}
                disabled={busy}
                className="shrink-0 text-slate-500 underline decoration-dotted hover:text-white disabled:opacity-50"
              >
                Disconnect
              </button>
            </li>
          ))}
        </ul>
      )}

      <Button variant="secondary" size="md" className="w-full" disabled={busy} onClick={() => void startConnect()}>
        {busy ? <Spinner className="size-4" /> : <Landmark className="size-4" aria-hidden />}
        {busy ? 'Connecting…' : linked.length ? 'Connect another bank' : 'Connect a bank'}
      </Button>
      {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}
    </div>
  )
}
