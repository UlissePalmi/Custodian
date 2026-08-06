import { useApi } from '../hooks/useApi'
import { useDataVersion } from '../context/DataVersion'
import { getAccountsBreakdown, type AccountBreakdown } from '../api'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { ErrorState, Skeleton } from '../components/ui/States'
import { Amount } from '../components/ui/Amount'
import { PageBody, PageHeader } from '../components/ui/PageHeader'
import { useChartTheme } from '../components/charts/theme'
import { formatPercent, formatQuantity, formatUSD, roundCents } from '../utils/money'

/** Same fixed assignment the dashboard donut uses, so a class keeps its colour
 *  across both views. 'credit' is a liability rather than an asset class and
 *  falls past the end deliberately. */
const ASSET_CLASS_ORDER = ['stocks', 'bonds', 'cash']

const GROUP_LABEL: Record<string, string> = {
  cash: 'Cash',
  stocks: 'Stocks',
  bonds: 'Bonds',
  credit: 'Credit',
}

/** Display order: assets by size, debts last — they read as a footnote to the
 *  assets rather than a peer of them. */
function groupOrder(type: string): number {
  if (type === 'credit') return ASSET_CLASS_ORDER.length + 1
  const index = ASSET_CLASS_ORDER.indexOf(type)
  return index >= 0 ? index : ASSET_CLASS_ORDER.length
}

function groupBy(accounts: AccountBreakdown[]): [string, AccountBreakdown[]][] {
  const groups = new Map<string, AccountBreakdown[]>()
  for (const account of accounts) {
    groups.set(account.type, [...(groups.get(account.type) ?? []), account])
  }
  return [...groups.entries()].sort(([a], [b]) => groupOrder(a) - groupOrder(b))
}

function AccountRow({ account, color }: { account: AccountBreakdown; color: string }) {
  const foreign = account.currency !== 'usd'

  // Whatever the account is worth beyond its positions — uninvested cash in a
  // brokerage. Derived from `value` rather than `balance` so it is already in
  // USD and the rows always reconcile with the account total, which is the
  // whole point of showing it.
  const positions = roundCents(account.holdings.reduce((sum, h) => sum + h.marketValue, 0))
  const uninvested = roundCents(account.value - positions)

  return (
    <li className="px-5 py-3">
      <div className="flex items-baseline justify-between gap-3">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: color }} aria-hidden />
          <span className="truncate font-medium text-terminal-navy">{account.name}</span>
          {!account.isConnected && (
            <span className="shrink-0 text-xs text-slate-400" title="Not linked to a bank — maintained by hand">
              manual
            </span>
          )}
        </div>
        <div className="shrink-0 text-right">
          <Amount value={account.value} className="font-semibold" />
          <p className="text-xs text-slate-500">{formatPercent(account.percent)}</p>
        </div>
      </div>

      {foreign && (
        <p className="mt-0.5 pl-4 text-xs text-slate-500">
          {formatQuantity(account.balance)} {account.currency.toUpperCase()}
        </p>
      )}

      {account.holdings.length > 0 && (
        <ul className="mt-2 space-y-1 pl-4">
          {uninvested !== 0 && (
            <li className="flex items-baseline justify-between gap-3 text-sm">
              <span className="truncate text-slate-600">
                <span className="font-medium text-terminal-navy">Cash</span>
                <span className="ml-2 text-xs text-slate-400">uninvested</span>
              </span>
              <span className="shrink-0 tabular-nums text-slate-600">{formatUSD(uninvested)}</span>
            </li>
          )}
          {account.holdings.map((holding) => (
            <li key={holding.id} className="flex items-baseline justify-between gap-3 text-sm">
              <span className="truncate text-slate-600">
                <span className="font-medium text-terminal-navy">{holding.ticker}</span>
                <span className="ml-2 text-xs text-slate-400">
                  {formatQuantity(holding.quantity)} @ {formatUSD(holding.currentPrice)}
                </span>
              </span>
              <span className="shrink-0 tabular-nums text-slate-600">
                {formatUSD(holding.marketValue)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

export default function AllocationPage() {
  const { version } = useDataVersion()
  const { data, loading, error, refetch } = useApi(getAccountsBreakdown, [version])
  const theme = useChartTheme()

  const colorFor = (type: string) => {
    const fixedIndex = ASSET_CLASS_ORDER.indexOf(type)
    const index = fixedIndex >= 0 ? fixedIndex : ASSET_CLASS_ORDER.length
    return theme.series[index % theme.series.length]
  }

  const total = data ? roundCents(data.reduce((sum, a) => sum + a.value, 0)) : 0

  return (
    <>
      <PageHeader
        eyebrow="Net worth"
        title="Where it sits"
        subtitle={data ? `${formatUSD(total)} across ${data.length} accounts` : undefined}
      />
      <PageBody>
        {error ? (
          <Card>
            <ErrorState error={error} onRetry={refetch} />
          </Card>
        ) : loading || !data ? (
          <div className="space-y-6">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-40 w-full rounded-2xl" />
            ))}
          </div>
        ) : (
          <div className="space-y-6">
            {groupBy(data).map(([type, accounts]) => {
              const subtotal = roundCents(accounts.reduce((sum, a) => sum + a.value, 0))
              return (
                <Card key={type}>
                  <CardHeader
                    title={GROUP_LABEL[type] ?? type}
                    subtitle={
                      type === 'credit'
                        ? `${formatUSD(Math.abs(subtotal))} owed`
                        : `${formatUSD(subtotal)} total`
                    }
                  />
                  <ul className="divide-y divide-terminal-navy/10">
                    {accounts.map((account) => (
                      <AccountRow key={account.id} account={account} color={colorFor(type)} />
                    ))}
                  </ul>
                </Card>
              )
            })}

            <Card>
              <CardBody className="flex items-baseline justify-between">
                <span className="text-sm font-semibold tracking-wide text-terminal-navy uppercase">
                  Net worth
                </span>
                <Amount value={total} className="text-lg font-semibold" />
              </CardBody>
            </Card>
          </div>
        )}
      </PageBody>
    </>
  )
}
