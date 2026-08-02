import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { TrendingDown, TrendingUp } from 'lucide-react'
import { Card } from '../ui/Card'
import { Skeleton } from '../ui/States'
import { ChartTooltip } from '../charts/ChartTooltip'
import { axisProps, useChartTheme } from '../charts/theme'
import type { NetWorthSummary } from '../../api'
import { formatMonthLong, formatMonthShort } from '../../utils/months'
import { formatPercentSigned, formatUSD, formatUSDCompact, formatUSDSigned, signColor } from '../../utils/money'

export function NetWorthCardSkeleton() {
  return (
    <Card className="p-5 sm:p-6">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="mt-3 h-12 w-56" />
      <Skeleton className="mt-6 h-48 w-full" />
    </Card>
  )
}

/**
 * Dashboard headline: total net worth, change vs. last month, and the monthly
 * snapshot history. Single series, so no legend — the card title names it.
 */
export default function NetWorthCard({ data }: { data: NetWorthSummary }) {
  const theme = useChartTheme()
  const change = data.changeVsPrevMonth
  const chartData = data.history.map((point) => ({
    ...point,
    label: formatMonthShort(point.monthKey),
  }))

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold tracking-wide text-slate-500 uppercase dark:text-slate-400">
            Net worth
          </h2>
          {/* Hero figure — proportional figures, not tabular, at display size. */}
          <p className="mt-2 text-4xl font-semibold tracking-tight text-slate-900 sm:text-5xl dark:text-slate-50">
            {formatUSD(data.total)}
          </p>

          {change ? (
            <p className={`mt-2 flex items-center gap-1.5 text-sm font-medium ${signColor(change.amount)}`}>
              {change.amount >= 0 ? (
                <TrendingUp className="size-4" aria-hidden />
              ) : (
                <TrendingDown className="size-4" aria-hidden />
              )}
              <span className="tnum">
                {formatUSDSigned(change.amount)} ({formatPercentSigned(change.percent)})
              </span>
              <span className="font-normal text-slate-500 dark:text-slate-400">vs last month</span>
            </p>
          ) : (
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              No prior month to compare against yet.
            </p>
          )}
        </div>
      </div>

      <div className="mt-6 h-52 w-full sm:h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={theme.grid} strokeWidth={1} vertical={false} />
            <XAxis dataKey="label" {...axisProps(theme)} minTickGap={16} />
            <YAxis
              {...axisProps(theme)}
              width={64}
              tickFormatter={(value: number) => formatUSDCompact(value)}
              domain={['auto', 'auto']}
            />
            <Tooltip
              cursor={{ stroke: theme.axis, strokeWidth: 1 }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null
                const point = payload[0].payload as (typeof chartData)[number]
                return (
                  <ChartTooltip
                    theme={theme}
                    label={formatMonthLong(point.monthKey)}
                    rows={[
                      {
                        key: 'total',
                        label: 'Net worth',
                        value: formatUSD(point.total),
                        color: theme.series[0],
                      },
                    ]}
                  />
                )
              }}
            />
            <Line
              type="monotone"
              dataKey="total"
              stroke={theme.series[0]}
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={false}
              // Surface ring keeps the hovered marker legible over the line.
              activeDot={{ r: 5, strokeWidth: 2, stroke: theme.surface, fill: theme.series[0] }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
