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

/** Survives Chase's OAuth redirect round trip — Link tokens are single-use
 *  and the page navigates away and back during that flow. */
const LINK_TOKEN_STORAGE_KEY = 'custodian.plaid.linkToken'

function isOAuthRedirectReturn(): boolean {
  return typeof window !== 'undefined' && window.location.search.includes('oauth_state_id=')
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
  const [linkToken, setLinkToken] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getPlaidStatus()
      .then(setConnections)
      .catch(() => setConnections([]))
  }, [])

  // Resume an in-flight Link session after Chase's OAuth redirect returns.
  useEffect(() => {
    if (!isOAuthRedirectReturn()) return
    const stored = sessionStorage.getItem(LINK_TOKEN_STORAGE_KEY)
    if (stored) setLinkToken(stored)
  }, [])

  const onSuccess = useCallback(
    async (publicToken: string, metadata: PlaidLinkOnSuccessMetadata) => {
      sessionStorage.removeItem(LINK_TOKEN_STORAGE_KEY)
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
    token: linkToken ?? '',
    onSuccess,
    receivedRedirectUri: isOAuthRedirectReturn() ? window.location.href : undefined,
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
      sessionStorage.setItem(LINK_TOKEN_STORAGE_KEY, token)
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

  const active = connections.find((c) => c.status !== 'disconnected')

  if (compact) {
    return (
      <div className={className}>
        {active ? (
          <button
            type="button"
            onClick={() => void disconnect(active.itemId)}
            disabled={busy}
            title={`${active.institutionName} — tap to disconnect`}
            className="flex items-center justify-center rounded-lg p-2 text-terminal-gold transition-colors hover:bg-terminal-navy-light disabled:opacity-50"
          >
            <Landmark className="size-5" aria-hidden />
            {active.status === 'error' && <span className="sr-only">Sync error</span>}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => void startConnect()}
            disabled={busy}
            title="Connect Chase"
            className="flex items-center justify-center rounded-lg p-2 text-slate-400 transition-colors hover:bg-terminal-navy-light hover:text-white disabled:opacity-50"
          >
            {busy ? <Spinner className="size-5" /> : <Landmark className="size-5" aria-hidden />}
          </button>
        )}
      </div>
    )
  }

  return (
    <div className={className}>
      {active ? (
        <div className="flex items-center justify-between gap-2 text-xs text-slate-400">
          <span className="truncate">
            {active.institutionName}
            {active.status === 'error' && <span className="ml-1 text-rose-400">· sync error</span>}
          </span>
          <button
            type="button"
            onClick={() => void disconnect(active.itemId)}
            disabled={busy}
            className="shrink-0 text-slate-500 underline decoration-dotted hover:text-white disabled:opacity-50"
          >
            Disconnect
          </button>
        </div>
      ) : (
        <Button variant="secondary" size="md" className="w-full" disabled={busy} onClick={() => void startConnect()}>
          {busy ? <Spinner className="size-4" /> : <Landmark className="size-4" aria-hidden />}
          {busy ? 'Connecting…' : 'Connect Chase'}
        </Button>
      )}
      {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}
    </div>
  )
}
