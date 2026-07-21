import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import { Card, CardBody } from '../ui/Card'
import { Amount } from '../ui/Amount'
import { axisProps, useChartTheme } from '../charts/theme'
import type { MonthLedger } from '../../api'
import { formatUSD, formatUSDCompact } from '../../utils/money'

interface StatProps {
  label: string
  value: number
  signed?: boolean
  emphasis?: boolean
}

function Stat({ label, value, signed = false, emphasis = false }: StatProps) {
  return (
    <div>
      <p className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</p>
      <p className={`mt-1 ${emphasis ? 'text-2xl' : 'text-xl'} font-semibold tracking-tight`}>
        <Amount value={value} signed={signed} />
      </p>
    </div>
  )
}

/**
 * Income vs. expenses for the month: three figures plus a two-bar comparison so
 * the relationship is visible, not just the totals. Both bars are directly
 * labelled, so the two categorical hues never carry meaning alone.
 */
export default function MonthSummary({ ledger }: { ledger: MonthLedger }) {
  const theme = useChartTheme()
  const hasData = ledger.totalIncome > 0 || ledger.totalExpenses > 0

  const chartData = [
    { name: 'Income', value: ledger.totalIncome, color: theme.series[0] },
    { name: 'Expenses', value: ledger.totalExpenses, color: theme.series[1] },
  ]

  return (
    <Card>
      <CardBody className="grid gap-6 sm:grid-cols-2 sm:items-center">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-1 sm:gap-5">
          <Stat label="Total income" value={ledger.totalIncome} />
          <Stat label="Total expenses" value={ledger.totalExpenses} />
          <div className="col-span-2 border-t border-slate-200 pt-4 sm:col-span-1 dark:border-slate-800">
            <Stat label="Net" value={ledger.net} signed emphasis />
          </div>
        </div>

        {hasData ? (
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 20, right: 8, bottom: 0, left: 0 }}>
                <CartesianGrid stroke={theme.grid} strokeWidth={1} vertical={false} />
                <XAxis dataKey="name" {...axisProps(theme)} />
                <YAxis
                  {...axisProps(theme)}
                  width={56}
                  tickFormatter={(value: number) => formatUSDCompact(value)}
                />
                <Bar dataKey="value" maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false}>
                  {chartData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                  <LabelList
                    dataKey="value"
                    position="top"
                    offset={8}
                    fontSize={11}
                    fill={theme.axis}
                    formatter={(value: number) => formatUSDCompact(value)}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="flex h-44 items-center justify-center rounded-lg border border-dashed border-slate-200 text-sm text-slate-400 dark:border-slate-800 dark:text-slate-500">
            Add entries to see the comparison
          </div>
        )}
      </CardBody>

      <p className="sr-only">
        Income {formatUSD(ledger.totalIncome)}, expenses {formatUSD(ledger.totalExpenses)}, net{' '}
        {formatUSD(ledger.net)}.
      </p>
    </Card>
  )
}
