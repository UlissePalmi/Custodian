import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Info } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { useDataVersion } from '../context/DataVersion'
import { getYearlyTable } from '../api'
import { Card } from '../components/ui/Card'
import { ErrorState, Skeleton } from '../components/ui/States'
import { formatMonthShort, ledgerYears } from '../utils/months'
import { formatUSD, signColor } from '../utils/money'

const YEARS = ledgerYears()

/**
 * Pinned columns.
 *
 * The month column pins left at every width (a scrolling row is unreadable
 * without its label). The three computed columns pin right only from `lg` up:
 * at 360px of fixed width they would fill a phone screen entirely and push the
 * month column off, so on mobile they simply scroll with everything else.
 * Their widths are fixed because the right-hand offsets have to match them.
 */
const PIN_MONTH = 'sticky left-0 z-20 bg-white dark:bg-slate-900'
const PIN_TOTALS = 'lg:sticky z-20 bg-white dark:bg-slate-900'
const PIN_HOVER = 'group-hover:bg-slate-50 dark:group-hover:bg-slate-800'
/** Soft edge marking where pinned columns float above the scrolling ones. */
const EDGE_RIGHT = 'shadow-[8px_0_8px_-8px_rgba(15,23,42,0.15)] dark:shadow-[8px_0_8px_-8px_rgba(0,0,0,0.6)]'
const EDGE_LEFT =
  'lg:shadow-[-8px_0_8px_-8px_rgba(15,23,42,0.15)] dark:lg:shadow-[-8px_0_8px_-8px_rgba(0,0,0,0.6)]'
const MONTH_COL = `${PIN_MONTH} ${EDGE_RIGHT} w-28 min-w-28 px-4`
const TOTAL_COL = 'w-30 min-w-30 px-3'

/** Blank rather than `$0.00`, so months with real activity stand out. */
function Cell({ value }: { value: number | undefined }) {
  if (!value) return <span className="text-slate-300 dark:text-slate-700">—</span>
  return <span className="tnum">{formatUSD(value)}</span>
}

export default function YearlyTablePage() {
  const { version } = useDataVersion()
  const [year, setYear] = useState(YEARS[0])
  const { data, loading, error, refetch } = useApi(() => getYearlyTable(year), [year, version])

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Yearly table</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Every category, month by month.
          </p>
        </div>

        <div className="flex gap-1 rounded-lg border border-slate-300 p-0.5 dark:border-slate-700">
          {YEARS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setYear(option)}
              aria-pressed={option === year}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                option === year
                  ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
                  : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
              }`}
            >
              {option}
            </button>
          ))}
        </div>
      </header>

      <p className="flex items-start gap-2 rounded-lg bg-slate-100 px-3 py-2.5 text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-400">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        <span>
          This table is read-only. Every figure is computed from the monthly ledgers — edit a{' '}
          <Link to="/months" className="underline underline-offset-2">
            month page
          </Link>{' '}
          and the totals here follow.
        </span>
      </p>

      {error ? (
        <Card>
          <ErrorState error={error} onRetry={refetch} />
        </Card>
      ) : loading || !data ? (
        <Skeleton className="h-96 w-full rounded-2xl" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            {/* border-separate, not border-collapse: collapsed borders belong to
                the table rather than the cell, so Chrome drops them under
                position:sticky. Borders are set per cell below instead. */}
            <table className="w-full border-separate border-spacing-0 text-sm whitespace-nowrap">
              <caption className="sr-only">
                Income and expenses by category for each month of {year}. Derived from the monthly
                ledgers.
              </caption>

              <thead>
                <tr className="text-xs text-slate-500 [&>*]:border-b [&>*]:border-slate-200 dark:text-slate-400 dark:[&>*]:border-slate-800">
                  <th scope="col" className={`${MONTH_COL} py-3 text-left font-medium`}>
                    Month
                  </th>
                  {data.columns.map((column) => (
                    <th key={column.id} scope="col" className="px-3 py-3 text-right font-medium">
                      {column.name}
                    </th>
                  ))}
                  <th
                    scope="col"
                    className={`${PIN_TOTALS} ${TOTAL_COL} lg:right-60 ${EDGE_LEFT} py-3 text-right font-medium`}
                  >
                    Total income
                  </th>
                  <th scope="col" className={`${PIN_TOTALS} ${TOTAL_COL} lg:right-30 py-3 text-right font-medium`}>
                    Total expenses
                  </th>
                  <th scope="col" className={`${PIN_TOTALS} ${TOTAL_COL} lg:right-0 py-3 text-right font-medium`}>
                    Net
                  </th>
                </tr>
              </thead>

              <tbody>
                {data.rows.map((row) => (
                  <tr
                    key={row.monthKey}
                    className="group [&>*]:border-b [&>*]:border-slate-100 dark:[&>*]:border-slate-800"
                  >
                    <th
                      scope="row"
                      className={`${MONTH_COL} ${PIN_HOVER} py-3 text-left font-medium text-slate-900 dark:text-slate-100`}
                    >
                      <Link to={`/months/${row.monthKey}`} className="hover:underline">
                        {formatMonthShort(row.monthKey)}
                      </Link>
                    </th>

                    {data.columns.map((column) => (
                      <td
                        key={column.id}
                        className="px-3 py-3 text-right text-slate-600 group-hover:bg-slate-50 dark:text-slate-300 dark:group-hover:bg-slate-800/40"
                      >
                        <Cell value={row.cells[column.id]} />
                      </td>
                    ))}

                    <td
                      className={`${PIN_TOTALS} ${TOTAL_COL} ${PIN_HOVER} lg:right-60 ${EDGE_LEFT} py-3 text-right text-slate-900 dark:text-slate-100`}
                    >
                      <Cell value={row.totalIncome} />
                    </td>
                    <td
                      className={`${PIN_TOTALS} ${TOTAL_COL} ${PIN_HOVER} lg:right-30 py-3 text-right text-slate-900 dark:text-slate-100`}
                    >
                      <Cell value={row.totalExpenses} />
                    </td>
                    <td
                      className={`${PIN_TOTALS} ${TOTAL_COL} ${PIN_HOVER} lg:right-0 py-3 text-right font-medium ${signColor(row.net)}`}
                    >
                      {row.totalIncome || row.totalExpenses ? (
                        <span className="tnum">{formatUSD(row.net)}</span>
                      ) : (
                        <span className="text-slate-300 dark:text-slate-700">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>

              <tfoot>
                <tr className="font-semibold [&>*]:border-t-2 [&>*]:border-slate-200 dark:[&>*]:border-slate-700">
                  <th scope="row" className={`${MONTH_COL} py-3 text-left`}>
                    Total
                  </th>
                  {data.columns.map((column) => (
                    <td key={column.id} className="px-3 py-3 text-right">
                      <Cell value={data.totals.cells[column.id]} />
                    </td>
                  ))}
                  <td
                    className={`${PIN_TOTALS} ${TOTAL_COL} lg:right-60 ${EDGE_LEFT} py-3 text-right`}
                  >
                    <Cell value={data.totals.totalIncome} />
                  </td>
                  <td className={`${PIN_TOTALS} ${TOTAL_COL} lg:right-30 py-3 text-right`}>
                    <Cell value={data.totals.totalExpenses} />
                  </td>
                  <td className={`${PIN_TOTALS} ${TOTAL_COL} lg:right-0 py-3 text-right ${signColor(data.totals.net)}`}>
                    <span className="tnum">{formatUSD(data.totals.net)}</span>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
