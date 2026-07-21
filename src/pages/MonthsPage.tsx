import { Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { useDataVersion } from '../context/DataVersion'
import { getMonths, type MonthInfo } from '../api'
import { Card } from '../components/ui/Card'
import { Amount } from '../components/ui/Amount'
import { ErrorState, Skeleton } from '../components/ui/States'
import UploadButton from '../components/import/UploadButton'
import { MONTH_NAMES, parseMonthKey } from '../utils/months'

function MonthTile({ month }: { month: MonthInfo }) {
  const { year, month: monthNumber } = parseMonthKey(month.monthKey)

  return (
    <Link
      to={`/months/${month.monthKey}`}
      className="flex flex-col rounded-xl border border-slate-200 bg-white p-4 transition-colors hover:border-slate-300 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700 dark:hover:bg-slate-800/60"
    >
      <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
        {MONTH_NAMES[monthNumber - 1]}
      </span>
      <span className="text-xs text-slate-500 dark:text-slate-400">{year}</span>

      {month.hasData ? (
        <span className="mt-3">
          <Amount value={month.net} signed className="text-sm font-medium" />
          <span className="mt-0.5 block text-xs text-slate-400 dark:text-slate-500">net</span>
        </span>
      ) : (
        <span className="mt-3 text-xs text-slate-400 dark:text-slate-500">No entries</span>
      )}
    </Link>
  )
}

export default function MonthsPage() {
  const { version, invalidate } = useDataVersion()
  const { data, loading, error, refetch } = useApi(getMonths, [version])

  const byYear = new Map<number, MonthInfo[]>()
  for (const month of data ?? []) {
    const { year } = parseMonthKey(month.monthKey)
    byYear.set(year, [...(byYear.get(year) ?? []), month])
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Months</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Pick a month to view and edit its ledger.
          </p>
        </div>
        <UploadButton onImported={invalidate} />
      </header>

      {error ? (
        <Card>
          <ErrorState error={error} onRetry={refetch} />
        </Card>
      ) : loading || !data ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 12 }).map((_, index) => (
            <Skeleton key={index} className="h-28 w-full rounded-xl" />
          ))}
        </div>
      ) : (
        [...byYear.entries()].map(([year, months]) => (
          <section key={year}>
            <h2 className="mb-3 text-xs font-semibold tracking-wide text-slate-500 uppercase dark:text-slate-400">
              {year}
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {months.map((month) => (
                <MonthTile key={month.monthKey} month={month} />
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  )
}
