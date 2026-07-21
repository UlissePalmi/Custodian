import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { Card, CardBody, CardHeader } from '../ui/Card'
import { EmptyState, Skeleton } from '../ui/States'
import { ChartTooltip } from '../charts/ChartTooltip'
import { useChartTheme } from '../charts/theme'
import type { AllocationSlice } from '../../api'
import { formatPercent, formatUSD } from '../../utils/money'

export function AllocationCardSkeleton() {
  return (
    <Card>
      <CardHeader title="Asset allocation" />
      <CardBody>
        <Skeleton className="mx-auto size-44 rounded-full" />
        <Skeleton className="mt-5 h-24 w-full" />
      </CardBody>
    </Card>
  )
}

interface AllocationCardProps {
  allocation: AllocationSlice[]
  total: number
}

/**
 * Donut plus a legend table. The table is not decoration: it carries the values
 * for slices whose hue sits below the 3:1 contrast bar in light mode, which is
 * what makes that palette choice legal.
 */
export default function AllocationCard({ allocation, total }: AllocationCardProps) {
  const theme = useChartTheme()
  const slices = allocation.filter((slice) => slice.value > 0)

  if (slices.length === 0) {
    return (
      <Card>
        <CardHeader title="Asset allocation" />
        <EmptyState
          title="No assets recorded"
          description="Add holdings or account balances to see your allocation."
        />
      </Card>
    )
  }

  const colorFor = (index: number) => theme.series[index % theme.series.length]

  return (
    <Card className="flex flex-col">
      <CardHeader title="Asset allocation" subtitle={`${formatUSD(total)} total`} />
      <CardBody className="flex flex-1 flex-col">
        <div className="mx-auto h-48 w-full max-w-64">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={slices}
                dataKey="value"
                nameKey="label"
                innerRadius="62%"
                outerRadius="100%"
                // 2px separation drawn in the surface colour, per mark spec.
                stroke={theme.surface}
                strokeWidth={2}
                isAnimationActive={false}
              >
                {slices.map((slice, index) => (
                  <Cell key={slice.assetClass} fill={colorFor(index)} />
                ))}
              </Pie>
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const slice = payload[0].payload as AllocationSlice
                  const index = slices.findIndex((s) => s.assetClass === slice.assetClass)
                  return (
                    <ChartTooltip
                      theme={theme}
                      label={slice.label}
                      rows={[
                        {
                          key: 'value',
                          label: formatPercent(slice.percent),
                          value: formatUSD(slice.value),
                          color: colorFor(index),
                        },
                      ]}
                    />
                  )
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Legend table — identity by swatch, values in text tokens. */}
        <table className="mt-5 w-full text-sm">
          <caption className="sr-only">Net worth by asset class</caption>
          <thead>
            <tr className="text-xs text-slate-500 dark:text-slate-400">
              <th scope="col" className="pb-2 text-left font-medium">
                Asset class
              </th>
              <th scope="col" className="pb-2 text-right font-medium">
                Value
              </th>
              <th scope="col" className="pb-2 text-right font-medium">
                Share
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {slices.map((slice, index) => (
              <tr key={slice.assetClass}>
                <th scope="row" className="py-2 text-left font-normal">
                  <span className="flex items-center gap-2">
                    <span
                      className="size-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: colorFor(index) }}
                      aria-hidden
                    />
                    <span className="text-slate-700 dark:text-slate-300">{slice.label}</span>
                  </span>
                </th>
                <td className="tnum py-2 text-right text-slate-900 dark:text-slate-100">
                  {formatUSD(slice.value)}
                </td>
                <td className="tnum py-2 text-right text-slate-500 dark:text-slate-400">
                  {formatPercent(slice.percent)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  )
}
