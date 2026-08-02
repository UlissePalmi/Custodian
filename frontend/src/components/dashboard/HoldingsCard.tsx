import { Card, CardBody, CardHeader } from '../ui/Card'
import { EmptyState, Skeleton } from '../ui/States'
import { Amount } from '../ui/Amount'
import type { Holding } from '../../api'
import { formatPercentSigned, formatQuantity, formatUSD, signColor } from '../../utils/money'

export function HoldingsCardSkeleton() {
  return (
    <Card>
      <CardHeader title="Holdings" />
      <CardBody className="space-y-3">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-12 w-full" />
        ))}
      </CardBody>
    </Card>
  )
}

function quoteLabel(holdings: Holding[]): string | undefined {
  if (holdings.length === 0) return undefined
  const asOf = new Date(holdings[0].quoteAsOf)
  return `Prices delayed · as of ${asOf.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`
}

/**
 * Individual positions. Full table from `lg` up; below that each holding
 * becomes its own card, which stays readable at 390px without side-scrolling.
 */
export default function HoldingsCard({ holdings }: { holdings: Holding[] }) {
  if (holdings.length === 0) {
    return (
      <Card>
        <CardHeader title="Holdings" />
        <EmptyState
          title="No holdings yet"
          description="Positions you add will appear here with live market values."
        />
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader title="Holdings" subtitle={quoteLabel(holdings)} />

      {/* Desktop: full table */}
      <div className="hidden overflow-x-auto lg:block">
        <table className="w-full text-sm">
          <caption className="sr-only">Individual holdings and their returns</caption>
          <thead>
            <tr className="border-b border-slate-200 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
              <th scope="col" className="px-5 py-2.5 text-left font-medium">
                Ticker
              </th>
              <th scope="col" className="px-3 py-2.5 text-right font-medium">
                Qty
              </th>
              <th scope="col" className="px-3 py-2.5 text-right font-medium">
                Cost basis
              </th>
              <th scope="col" className="px-3 py-2.5 text-right font-medium">
                Price
              </th>
              <th scope="col" className="px-3 py-2.5 text-right font-medium">
                Market value
              </th>
              <th scope="col" className="px-3 py-2.5 text-right font-medium">
                Total return
              </th>
              <th scope="col" className="px-5 py-2.5 text-right font-medium">
                YTD
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {holdings.map((holding) => (
              <tr key={holding.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                <th scope="row" className="px-5 py-3 text-left font-normal">
                  <span className="block font-semibold text-slate-900 dark:text-slate-100">
                    {holding.ticker}
                  </span>
                  <span className="block max-w-52 truncate text-xs text-slate-500 dark:text-slate-400">
                    {holding.name}
                  </span>
                </th>
                <td className="tnum px-3 py-3 text-right text-slate-600 dark:text-slate-300">
                  {formatQuantity(holding.quantity)}
                </td>
                <td className="tnum px-3 py-3 text-right text-slate-600 dark:text-slate-300">
                  {formatUSD(holding.costBasisPerShare)}
                </td>
                <td className="tnum px-3 py-3 text-right text-slate-600 dark:text-slate-300">
                  {formatUSD(holding.currentPrice)}
                </td>
                <td className="tnum px-3 py-3 text-right font-medium text-slate-900 dark:text-slate-100">
                  {formatUSD(holding.marketValue)}
                </td>
                <td className="px-3 py-3 text-right">
                  <Amount value={holding.totalReturn.amount} signed className="block font-medium" />
                  <span className={`tnum block text-xs ${signColor(holding.totalReturn.percent)}`}>
                    {formatPercentSigned(holding.totalReturn.percent)}
                  </span>
                </td>
                <td
                  className={`tnum px-5 py-3 text-right font-medium ${signColor(holding.ytdReturnPercent)}`}
                >
                  {formatPercentSigned(holding.ytdReturnPercent)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile / tablet: one card per holding */}
      <ul className="divide-y divide-slate-100 lg:hidden dark:divide-slate-800">
        {holdings.map((holding) => (
          <li key={holding.id} className="px-5 py-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-semibold text-slate-900 dark:text-slate-100">{holding.ticker}</p>
                <p className="truncate text-xs text-slate-500 dark:text-slate-400">{holding.name}</p>
              </div>
              <div className="shrink-0 text-right">
                <p className="tnum font-medium text-slate-900 dark:text-slate-100">
                  {formatUSD(holding.marketValue)}
                </p>
                <p className={`tnum text-xs ${signColor(holding.totalReturn.percent)}`}>
                  {formatPercentSigned(holding.totalReturn.percent)} all time
                </p>
              </div>
            </div>

            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs sm:grid-cols-4">
              <div className="flex justify-between sm:block">
                <dt className="text-slate-500 dark:text-slate-400">Qty</dt>
                <dd className="tnum text-slate-700 sm:mt-0.5 dark:text-slate-300">
                  {formatQuantity(holding.quantity)}
                </dd>
              </div>
              <div className="flex justify-between sm:block">
                <dt className="text-slate-500 dark:text-slate-400">Cost basis</dt>
                <dd className="tnum text-slate-700 sm:mt-0.5 dark:text-slate-300">
                  {formatUSD(holding.costBasisPerShare)}
                </dd>
              </div>
              <div className="flex justify-between sm:block">
                <dt className="text-slate-500 dark:text-slate-400">Price</dt>
                <dd className="tnum text-slate-700 sm:mt-0.5 dark:text-slate-300">
                  {formatUSD(holding.currentPrice)}
                </dd>
              </div>
              <div className="flex justify-between sm:block">
                <dt className="text-slate-500 dark:text-slate-400">YTD</dt>
                <dd className={`tnum sm:mt-0.5 ${signColor(holding.ytdReturnPercent)}`}>
                  {formatPercentSigned(holding.ytdReturnPercent)}
                </dd>
              </div>
            </dl>

            <p className="mt-2 flex justify-between text-xs">
              <span className="text-slate-500 dark:text-slate-400">Total return</span>
              <Amount value={holding.totalReturn.amount} signed className="font-medium" />
            </p>
          </li>
        ))}
      </ul>
    </Card>
  )
}
