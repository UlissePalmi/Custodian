import { Link, useParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { useDataVersion } from '../context/DataVersion'
import { getMonth } from '../api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { ErrorState, Skeleton } from '../components/ui/States'
import { PageBody, PageHeader } from '../components/ui/PageHeader'
import MonthSummary from '../components/months/MonthSummary'
import TransactionList from '../components/months/TransactionList'
import {
  formatMonthLong,
  isWithinLedgerRange,
  parseMonthKey,
  shiftMonthKey,
} from '../utils/months'

function MonthNavLink({ monthKey, direction }: { monthKey: string | null; direction: 'prev' | 'next' }) {
  const Icon = direction === 'prev' ? ChevronLeft : ChevronRight
  const label = direction === 'prev' ? 'Previous month' : 'Next month'

  if (!monthKey) {
    return (
      <span
        className="inline-flex size-9 items-center justify-center rounded-lg text-white/20"
        aria-hidden
      >
        <Icon className="size-5" />
      </span>
    )
  }

  return (
    <Link
      to={`/months/${monthKey}`}
      aria-label={label}
      className="inline-flex size-9 items-center justify-center rounded-lg border border-white/20 text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
    >
      <Icon className="size-5" aria-hidden />
    </Link>
  )
}

export default function MonthDetailPage() {
  const { monthKey = '' } = useParams()
  const { invalidate } = useDataVersion()

  const valid = isWithinLedgerRange(monthKey)
  const { year, month } = valid ? parseMonthKey(monthKey) : { year: 0, month: 0 }

  const { data, loading, error, refetch } = useApi(
    () => getMonth(year, month),
    [monthKey],
  )

  if (!valid) {
    return (
      <>
        <PageHeader eyebrow="Ledger" title="Month not available" />
        <PageBody>
          <Card>
            <div className="p-8 text-center">
              <p className="text-sm text-slate-500">Custodian's ledger runs from July 2026 onward.</p>
              <Link to="/months" className="mt-4 inline-block">
                <Button>Back to months</Button>
              </Link>
            </div>
          </Card>
        </PageBody>
      </>
    )
  }

  function handleChanged() {
    refetch()
    // Net worth and the yearly table read the same ledger.
    invalidate()
  }

  return (
    <>
      <PageHeader
        eyebrow="Ledger"
        title={formatMonthLong(monthKey)}
        subtitle={
          <Link to="/months" className="hover:text-white">
            All months
          </Link>
        }
        action={
          <div className="flex items-center gap-2">
            <MonthNavLink monthKey={shiftMonthKey(monthKey, -1)} direction="prev" />
            <MonthNavLink monthKey={shiftMonthKey(monthKey, 1)} direction="next" />
          </div>
        }
      />
      <PageBody>

        {error ? (
          <Card>
            <ErrorState error={error} onRetry={refetch} />
          </Card>
        ) : loading || !data ? (
          <>
            <Skeleton className="h-48 w-full rounded-2xl" />
            <div className="grid gap-6 lg:grid-cols-2">
              <Skeleton className="h-72 w-full rounded-2xl" />
              <Skeleton className="h-72 w-full rounded-2xl" />
            </div>
          </>
        ) : (
          <>
            <MonthSummary ledger={data} />

            {/* Mobile stacks income above expenses; desktop shows them side by side. */}
            <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
              <TransactionList
                monthKey={monthKey}
                kind="income"
                transactions={data.income}
                total={data.totalIncome}
                onChanged={handleChanged}
              />
              <TransactionList
                monthKey={monthKey}
                kind="expense"
                transactions={data.expenses}
                total={data.totalExpenses}
                onChanged={handleChanged}
              />
            </div>
          </>
        )}
      </PageBody>
    </>
  )
}
