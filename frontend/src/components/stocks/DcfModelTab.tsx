import type { ReactNode } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import type { StockModel } from '../../api/types'
import { computeDcf, dcfBuildRows, latestDilutedShares } from '../../utils/dcf'
import { formatPercentSigned, formatUSDCompact } from '../../utils/money'
import { ChartTooltip } from '../charts/ChartTooltip'
import { useChartTheme } from '../charts/theme'

function tnum(value: string) {
  return <span className="tnum">{value}</span>
}

function money(value: number | null): string {
  return value == null ? '—' : formatUSDCompact(value)
}

function percent(value: number | null, decimals = 1): string {
  if (value == null) return '—'
  return `${value.toFixed(decimals)}%`
}

function SidebarCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-terminal-navy/10 bg-white p-5 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold text-terminal-navy">{title}</h3>
      {children}
    </div>
  )
}

function SidebarRow({ label, value, gold = false }: { label: string; value: string; gold?: boolean }) {
  return (
    <div className="flex items-center justify-between border-t border-slate-100 py-2 first:border-0 first:pt-0">
      <span className="text-xs text-slate-500">{label}</span>
      <span className={`tnum text-sm font-semibold ${gold ? 'text-terminal-gold' : 'text-terminal-navy'}`}>
        {value}
      </span>
    </div>
  )
}

export default function DcfModelTab({ model }: { model: StockModel }) {
  const CHART_THEME = useChartTheme()
  const dcf = computeDcf(model)
  const rows = dcfBuildRows(model)
  const shares = latestDilutedShares(model.periods)
  const marketCap = model.currentPrice != null && shares ? model.currentPrice * shares : null

  const pvOfFcfs = dcf.projections.reduce((sum, p) => sum + p.presentValue, 0)
  const pvComposition = [
    { key: 'fcf', label: 'PV of FCFs', value: pvOfFcfs, color: CHART_THEME.series[0] },
    { key: 'terminal', label: 'PV Terminal Value', value: dcf.presentValueOfTerminalValue, color: CHART_THEME.series[1] },
  ].filter((slice) => slice.value > 0)
  const pvTotal = pvComposition.reduce((sum, s) => sum + s.value, 0)

  const upsideLabel = dcf.upsidePercent == null ? '' : dcf.upsidePercent >= 0 ? 'UPSIDE' : 'DOWNSIDE'

  return (
    <div>
      {/* Flush against the tab bar above — see StockModelPage's comment on why
          this page bypasses AppLayout's normal padding. */}
      <div className="bg-terminal-navy px-4 py-6 sm:px-6 lg:px-8">
        <p className="text-xs font-semibold tracking-widest text-terminal-gold uppercase">
          Discounted cash flow analysis
        </p>
        <div className="mt-1 flex flex-wrap items-end justify-between gap-6">
          <div>
            <h1 className="font-terminal-serif text-3xl font-bold text-white">{model.name}</h1>
            <p className="mt-1 text-sm text-slate-400">
              {[model.exchange && `${model.exchange}: ${model.ticker}`, model.sector, 'DCF Base']
                .filter(Boolean)
                .join(' · ')}
            </p>
          </div>
          <div className="flex gap-8">
            <div className="text-right">
              <p className="tnum text-2xl font-semibold text-white">{money(dcf.fairValuePerShare)}</p>
              <p className="text-[11px] tracking-wide text-slate-400 uppercase">Intrinsic value</p>
            </div>
            <div className="text-right">
              <p className="tnum text-2xl font-semibold text-white">{money(model.currentPrice)}</p>
              <p className="text-[11px] tracking-wide text-slate-400 uppercase">Market</p>
            </div>
            {dcf.upsidePercent != null && (
              <div className="text-right">
                <p className="tnum text-2xl font-semibold text-white">
                  {formatPercentSigned(dcf.upsidePercent)}
                </p>
                <p className="text-[11px] tracking-wide text-slate-400 uppercase">{upsideLabel}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[1fr_320px] lg:px-8">
        <div className="overflow-x-auto rounded-lg border border-terminal-navy/10 bg-white shadow-sm">
          <table className="w-full min-w-max text-sm">
            <thead>
              <tr className="bg-terminal-navy text-white">
                <th className="px-4 py-2 text-left text-xs font-semibold tracking-wide uppercase">
                  Line item
                </th>
                {rows.map((row) => (
                  <th
                    key={row.year}
                    className={`px-4 py-2 text-right text-xs font-semibold ${
                      row.isProjected ? 'text-white' : 'text-slate-400'
                    }`}
                  >
                    {row.year}
                    {row.isProjected ? 'E' : 'A'}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-slate-100">
                <td className="px-4 py-1.5 font-semibold text-terminal-navy">Net Revenue</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1.5 text-right font-semibold text-terminal-navy">
                    {tnum(money(row.revenue))}
                  </td>
                ))}
              </tr>
              <tr className="border-b border-slate-100">
                <td className="pl-6 text-xs text-slate-400 italic">Growth</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1 text-right text-xs text-slate-400 italic">
                    {tnum(percent(row.revenueGrowthPercent))}
                  </td>
                ))}
              </tr>

              <tr className="border-b border-slate-100">
                <td className="px-4 py-1.5 font-semibold text-terminal-gold">EBITDA</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1.5 text-right font-semibold text-terminal-gold">
                    {tnum(money(row.ebitda))}
                  </td>
                ))}
              </tr>
              <tr className="border-b border-slate-100">
                <td className="pl-6 text-xs text-slate-400 italic">Margin</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1 text-right text-xs text-slate-400 italic">
                    {tnum(percent(row.ebitdaMarginPercent))}
                  </td>
                ))}
              </tr>
              <tr className="border-b border-slate-100">
                <td className="pl-6 text-xs text-slate-400 italic">Growth</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1 text-right text-xs text-slate-400 italic">
                    {tnum(percent(row.ebitdaGrowthPercent))}
                  </td>
                ))}
              </tr>

              <tr className="border-b border-slate-100">
                <td className="px-4 py-1.5 font-semibold text-terminal-navy">Net Income</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1.5 text-right font-semibold text-terminal-navy">
                    {tnum(money(row.netIncome))}
                  </td>
                ))}
              </tr>
              <tr className="border-b border-slate-100">
                <td className="pl-6 text-xs text-slate-400 italic">Margin</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1 text-right text-xs text-slate-400 italic">
                    {tnum(percent(row.netIncomeMarginPercent))}
                  </td>
                ))}
              </tr>
              <tr className="border-b border-slate-100">
                <td className="pl-6 text-xs text-slate-400 italic">Growth</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1 text-right text-xs text-slate-400 italic">
                    {tnum(percent(row.netIncomeGrowthPercent))}
                  </td>
                ))}
              </tr>

              <tr className="border-b border-slate-100">
                <td className="px-4 py-1.5 font-semibold text-terminal-navy italic">EBIAT</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1.5 text-right font-semibold text-terminal-navy italic">
                    {tnum(money(row.ebiat))}
                  </td>
                ))}
              </tr>
              <tr className="border-b border-slate-100">
                <td className="pl-6 text-xs text-slate-400 italic">Growth</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1 text-right text-xs text-slate-400 italic">
                    {tnum(percent(row.ebiatGrowthPercent))}
                  </td>
                ))}
              </tr>

              <tr className="border-b border-slate-100">
                <td className="px-4 py-1.5 text-slate-600">D&amp;A</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1.5 text-right text-slate-600">
                    {tnum(money(row.depreciationAmortization))}
                  </td>
                ))}
              </tr>
              <tr className="border-b border-slate-100">
                <td className="px-4 py-1.5 text-slate-600">Capex</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1.5 text-right text-rose-700">
                    {tnum(money(-row.capex))}
                  </td>
                ))}
              </tr>
              <tr className="border-b border-slate-100">
                <td className="px-4 py-1.5 text-slate-600">NWC</td>
                {rows.map((row) => (
                  <td
                    key={row.year}
                    className={`px-4 py-1.5 text-right ${row.changeInWorkingCapital < 0 ? 'text-rose-700' : 'text-slate-600'}`}
                  >
                    {tnum(money(row.changeInWorkingCapital))}
                  </td>
                ))}
              </tr>

              <tr className="border-t-2 border-terminal-gold">
                <td className="px-4 py-1.5 font-semibold text-terminal-navy">Unlevered FCFF</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1.5 text-right font-semibold text-terminal-navy">
                    {row.isProjected ? tnum(money(row.unleveredFcf)) : '—'}
                  </td>
                ))}
              </tr>
              <tr className="border-b border-slate-100">
                <td className="px-4 py-1 text-xs text-slate-400">Discount Period</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1 text-right text-xs text-slate-400">
                    {tnum(row.discountPeriod?.toString() ?? '—')}
                  </td>
                ))}
              </tr>
              <tr className="border-b border-slate-100">
                <td className="px-4 py-1 text-xs text-slate-400">Discount Factor</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1 text-right text-xs text-slate-400">
                    {tnum(row.discountFactor != null ? row.discountFactor.toFixed(3) : '—')}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-4 py-1.5 font-semibold text-terminal-gold">Present Value of FCF</td>
                {rows.map((row) => (
                  <td key={row.year} className="px-4 py-1.5 text-right font-semibold text-terminal-gold">
                    {tnum(money(row.presentValue))}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>

        <div className="space-y-4">
          <SidebarCard title="Key Inputs">
            <SidebarRow label="WACC" value={percent(model.waccPercent)} />
            <SidebarRow label="Terminal Growth Rate" value={percent(model.terminalGrowthPercent)} />
          </SidebarCard>

          <SidebarCard title="PV Composition">
            {pvComposition.length === 0 ? (
              <p className="text-sm text-slate-400">Add a projected year to see the split.</p>
            ) : (
              <>
                <div className="mx-auto h-40 w-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pvComposition}
                        dataKey="value"
                        nameKey="label"
                        innerRadius="60%"
                        outerRadius="100%"
                        stroke={CHART_THEME.surface}
                        strokeWidth={2}
                        isAnimationActive={false}
                      >
                        {pvComposition.map((slice) => (
                          <Cell key={slice.key} fill={slice.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        content={({ active, payload }) => {
                          if (!active || !payload?.length) return null
                          const slice = payload[0].payload as (typeof pvComposition)[number]
                          return (
                            <ChartTooltip
                              theme={CHART_THEME}
                              label={slice.label}
                              rows={[{ key: slice.key, label: formatUSDCompact(slice.value), value: '', color: slice.color }]}
                            />
                          )
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <ul className="mt-3 space-y-1.5">
                  {pvComposition.map((slice) => (
                    <li key={slice.key} className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-1.5 text-slate-500">
                        <span
                          className="size-2 shrink-0 rounded-full"
                          style={{ backgroundColor: slice.color }}
                          aria-hidden
                        />
                        {slice.label}
                      </span>
                      <span className="tnum font-medium text-terminal-navy">
                        {percent(pvTotal ? (slice.value / pvTotal) * 100 : null, 0)}
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            )}
            <div className="mt-4 space-y-1 border-t border-slate-100 pt-3">
              <SidebarRow label="Enterprise Value" value={money(dcf.enterpriseValue)} gold />
              <SidebarRow label="Equity Value" value={money(dcf.equityValue)} gold />
            </div>
          </SidebarCard>

          <SidebarCard title="Current Market">
            <SidebarRow label="Market Cap" value={money(marketCap)} />
            <SidebarRow label="Enterprise Value" value={money(dcf.enterpriseValue)} />
          </SidebarCard>
        </div>
      </div>
    </div>
  )
}
