import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { useDataVersion } from '../context/DataVersion'
import { getMonth, type ImportResult } from '../api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { ErrorState, Skeleton } from '../components/ui/States'
import { Amount } from '../components/ui/Amount'
import MonthSummary from '../components/months/MonthSummary'
import TransactionList from '../components/months/TransactionList'
import UploadButton from '../components/import/UploadButton'
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
        className="inline-flex size-9 items-center justify-center rounded-lg text-slate-300 dark:text-slate-700"
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
      className="inline-flex size-9 items-center justify-center rounded-lg border border-slate-300 text-slate-600 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
    >
      <Icon className="size-5" aria-hidden />
    </Link>
  )
}

export default function MonthDetailPage() {
  const { monthKey = '' } = useParams()
  const { invalidate } = useDataVersion()
  const [importNotice, setImportNotice] = useState<ImportResult | null>(null)

  const valid = isWithinLedgerRange(monthKey)
  const { year, month } = valid ? parseMonthKey(monthKey) : { year: 0, month: 0 }

  const { data, loading, error, refetch } = useApi(
    () => getMonth(year, month),
    [monthKey],
  )

  if (!valid) {
    return (
      <Card>
        <div className="p-8 text-center">
          <h1 className="text-lg font-semibold">Month not available</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Custodian's ledger runs from July 2026 onward.
          </p>
          <Link to="/months" className="mt-4 inline-block">
            <Button>Back to months</Button>
          </Link>
        </div>
      </Card>
    )
  }

  function handleChanged() {
    refetch()
    // Net worth and the yearly table read the same ledger.
    invalidate()
  }

  function handleImported(result: ImportResult) {
    setImportNotice(result)
    handleChanged()
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <MonthNavLink monthKey={shiftMonthKey(monthKey, -1)} direction="prev" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{formatMonthLong(monthKey)}</h1>
            <Link
              to="/months"
              className="text-sm text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
            >
              All months
            </Link>
          </div>
          <MonthNavLink monthKey={shiftMonthKey(monthKey, 1)} direction="next" />
        </div>

        <UploadButton monthKey={monthKey} onImported={handleImported} />
      </header>

      {importNotice && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm dark:border-emerald-800 dark:bg-emerald-950/40">
          <p className="text-emerald-900 dark:text-emerald-200">
            Imported {importNotice.importedCount} transactions. Cash changed by{' '}
            <Amount value={importNotice.cashDelta} signed className="font-semibold" /> — net worth is
            now <Amount value={importNotice.newNetWorthTotal} className="font-semibold" />.
          </p>
          <Button variant="ghost" size="sm" onClick={() => setImportNotice(null)}>
            Dismiss
          </Button>
        </div>
      )}

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
    </div>
  )
}
