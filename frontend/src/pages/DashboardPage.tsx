import { useApi } from '../hooks/useApi'
import { useDataVersion } from '../context/DataVersion'
import { getDailyNetWorth, getHoldings, getNetWorth } from '../api'
import NetWorthCard, { NetWorthCardSkeleton } from '../components/dashboard/NetWorthCard'
import AllocationCard, { AllocationCardSkeleton } from '../components/dashboard/AllocationCard'
import HoldingsCard, { HoldingsCardSkeleton } from '../components/dashboard/HoldingsCard'
import { ErrorState } from '../components/ui/States'
import { Card } from '../components/ui/Card'
import { PageBody, PageHeader } from '../components/ui/PageHeader'

export default function DashboardPage() {
  const { version } = useDataVersion()
  const netWorth = useApi(getNetWorth, [version])
  // Separate call: filling any missed day happens server-side on read, so
  // this is also what catches the chart up after the Pi has been off.
  const daily = useApi(getDailyNetWorth, [version])
  const holdings = useApi(getHoldings, [version])

  return (
    <>
      <PageHeader eyebrow="Custodian" title="Dashboard" subtitle="Where your money stands today." />
      <PageBody>
        {netWorth.error ? (
          <Card>
            <ErrorState error={netWorth.error} onRetry={netWorth.refetch} />
          </Card>
        ) : netWorth.loading || !netWorth.data || daily.loading || !daily.data ? (
          <NetWorthCardSkeleton />
        ) : (
          <NetWorthCard data={netWorth.data} daily={daily.data} />
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
      </PageBody>
    </>
  )
}
