import { useApi } from '../hooks/useApi'
import { useDataVersion } from '../context/DataVersion'
import { getHoldings, getNetWorth } from '../api'
import NetWorthCard, { NetWorthCardSkeleton } from '../components/dashboard/NetWorthCard'
import AllocationCard, { AllocationCardSkeleton } from '../components/dashboard/AllocationCard'
import HoldingsCard, { HoldingsCardSkeleton } from '../components/dashboard/HoldingsCard'
import { ErrorState } from '../components/ui/States'
import { Card } from '../components/ui/Card'

export default function DashboardPage() {
  const { version } = useDataVersion()
  const netWorth = useApi(getNetWorth, [version])
  const holdings = useApi(getHoldings, [version])

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Where your money stands today.
        </p>
      </header>

      {netWorth.error ? (
        <Card>
          <ErrorState error={netWorth.error} onRetry={netWorth.refetch} />
        </Card>
      ) : netWorth.loading || !netWorth.data ? (
        <NetWorthCardSkeleton />
      ) : (
        <NetWorthCard data={netWorth.data} />
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          {netWorth.error ? null : netWorth.loading || !netWorth.data ? (
            <AllocationCardSkeleton />
          ) : (
            <AllocationCard allocation={netWorth.data.allocation} total={netWorth.data.total} />
          )}
        </div>

        <div className="lg:col-span-2">
          {holdings.error ? (
            <Card>
              <ErrorState error={holdings.error} onRetry={holdings.refetch} />
            </Card>
          ) : holdings.loading || !holdings.data ? (
            <HoldingsCardSkeleton />
          ) : (
            <HoldingsCard holdings={holdings.data} />
          )}
        </div>
      </div>
    </div>
  )
}
