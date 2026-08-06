import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { useDataVersion } from '../context/DataVersion'
import { getYearlyTable } from '../api'
import { Card } from '../components/ui/Card'
import { ErrorState, Skeleton } from '../components/ui/States'
import { PageBody, PageHeader } from '../components/ui/PageHeader'
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
const PIN_MONTH = 'sticky left-0 z-20 bg-white'
const PIN_TOTALS = 'lg:sticky z-20 bg-white'
const PIN_HOVER = 'group-hover:bg-terminal-cream/60'
/** Soft edge marking where pinned columns float above the scrolling ones. */
const EDGE_RIGHT = 'shadow-[8px_0_8px_-8px_rgba(27,38,64,0.15)]'
const EDGE_LEFT = 'lg:shadow-[-8px_0_8px_-8px_rgba(27,38,64,0.15)]'
const MONTH_COL = `${PIN_MONTH} ${EDGE_RIGHT} w-28 min-w-28 px-4`
const TOTAL_COL = 'w-30 min-w-30 px-3'

/** Blank rather than `$0.00`, so months with real activity stand out. */
function Cell({ value }: { value: number | undefined }) {
  if (!value) return <span className="text-slate-300">—</span>
  return <span className="tnum">{formatUSD(value)}</span>
}

export default function YearlyTablePage() {
  const { version } = useDataVersion()
  const [year, setYear] = useState(YEARS[0])
  const { data, loading, error, refetch } = useApi(() => getYearlyTable(year), [year, version])

  return (
    <>
      <PageHeader
        eyebrow="Ledger"
        title="Yearly Table"
        subtitle="Every category, month by month."
        action={
          <div className="flex gap-1 rounded-lg border border-white/20 p-0.5">
            {YEARS.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setYear(option)}
                aria-pressed={option === year}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  option === year
                    ? 'bg-terminal-gold text-terminal-navy'
                    : 'text-slate-300 hover:bg-white/10 hover:text-white'
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        }
      />
      <PageBody>
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
                  <tr className="text-xs text-slate-500 [&>*]:border-b [&>*]:border-terminal-navy/10">
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
                    <tr key={row.monthKey} className="group [&>*]:border-b [&>*]:border-terminal-navy/10">
                      <th
                        scope="row"
                        className={`${MONTH_COL} ${PIN_HOVER} py-3 text-left font-medium text-terminal-navy`}
                      >
                        <Link to={`/months/${row.monthKey}`} className="hover:underline">
                          {formatMonthShort(row.monthKey)}
                        </Link>
                      </th>

                      {data.columns.map((column) => (
                        <td
                          key={column.id}
                          className="px-3 py-3 text-right text-slate-600 group-hover:bg-terminal-cream/60"
                        >
                          <Cell value={row.cells[column.id]} />
                        </td>
                      ))}

                      <td
                        className={`${PIN_TOTALS} ${TOTAL_COL} ${PIN_HOVER} lg:right-60 ${EDGE_LEFT} py-3 text-right text-terminal-navy`}
                      >
                        <Cell value={row.totalIncome} />
                      </td>
                      <td
                        className={`${PIN_TOTALS} ${TOTAL_COL} ${PIN_HOVER} lg:right-30 py-3 text-right text-terminal-navy`}
                      >
                        <Cell value={row.totalExpenses} />
                      </td>
                      <td
                        className={`${PIN_TOTALS} ${TOTAL_COL} ${PIN_HOVER} lg:right-0 py-3 text-right font-medium ${signColor(row.net)}`}
                      >
                        {row.totalIncome || row.totalExpenses ? (
                          <span className="tnum">{formatUSD(row.net)}</span>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>

                <tfoot>
                  <tr className="font-semibold [&>*]:border-t-2 [&>*]:border-terminal-navy/20">
                    <th scope="row" className={`${MONTH_COL} py-3 text-left`}>
                      Total
                    </th>
                    {data.columns.map((column) => (
                      <td key={column.id} className="px-3 py-3 text-right">
                        <Cell value={data.totals.cells[column.id]} />
                      </td>
                    ))}
                    <td className={`${PIN_TOTALS} ${TOTAL_COL} lg:right-60 ${EDGE_LEFT} py-3 text-right`}>
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
      </PageBody>
    </>
  )
}
