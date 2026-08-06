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
 *  across both views. */
const ASSET_CLASS_ORDER = ['stocks', 'bonds', 'cash']

const GROUP_LABEL: Record<string, string> = {
  cash: 'Cash',
  stocks: 'Stocks',
  bonds: 'Bonds',
}

function groupOrder(assetClass: string): number {
  const index = ASSET_CLASS_ORDER.indexOf(assetClass)
  return index >= 0 ? index : ASSET_CLASS_ORDER.length
}

/** Grouped by `assetClass`, not by account type — a card's debt and a
 *  brokerage's idle cash both count as cash, so grouping by what holds the
 *  money would disagree with the dashboard's slices. */
function groupBy(rows: AccountBreakdown[]): [string, AccountBreakdown[]][] {
  const groups = new Map<string, AccountBreakdown[]>()
  for (const row of rows) {
    groups.set(row.assetClass, [...(groups.get(row.assetClass) ?? []), row])
  }
  return [...groups.entries()].sort(([a], [b]) => groupOrder(a) - groupOrder(b))
}

function AccountRow({ account, color }: { account: AccountBreakdown; color: string }) {
  const foreign = account.currency !== 'usd'

  return (
    <li className="px-5 py-3">
      <div className="flex items-baseline justify-between gap-3">
        <div className="flex min-w-0 items-baseline gap-2">
          <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: color }} aria-hidden />
          <span className="truncate font-medium text-terminal-navy">{account.name}</span>
          {account.type === 'stocks' && account.assetClass === 'cash' && (
            <span className="shrink-0 text-xs text-slate-400">uninvested</span>
          )}
          {account.type === 'credit' && (
            <span className="shrink-0 text-xs text-slate-400">owed</span>
          )}
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
        subtitle={
          data
            ? `${formatUSD(total)} across ${new Set(data.map((r) => r.id)).size} accounts`
            : undefined
        }
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
                    subtitle={`${formatUSD(subtotal)} total`}
                  />
                  <ul className="divide-y divide-terminal-navy/10">
                    {accounts.map((account) => (
                      <AccountRow
                        key={`${account.id}-${account.assetClass}`}
                        account={account}
                        color={colorFor(type)}
                      />
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
