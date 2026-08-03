import type { DcfResult } from '../../api/types'
import { formatUSDCompact } from '../../utils/money'

interface BridgeRow {
  label: string
  value: number
  color: string
}

/** Horizontal bar chart, hand-rolled rather than recharts — three plain bars
 *  scaled to the largest magnitude, matching the prototype's simple layout. */
export default function ValuationBridgeCard({ dcf }: { dcf: DcfResult }) {
  const pvOfFcfs = dcf.projections.reduce((sum, p) => sum + p.presentValue, 0)

  const rows: BridgeRow[] = [
    { label: 'PV of FCFs', value: pvOfFcfs, color: '#1b2640' },
    { label: 'PV Terminal Value', value: dcf.presentValueOfTerminalValue, color: '#d4af37' },
    { label: '(−) Net Debt', value: dcf.netDebt, color: '#8b3a3a' },
  ]
  const maxMagnitude = Math.max(1, ...rows.map((r) => Math.abs(r.value)))

  return (
    <div className="rounded-lg border border-terminal-navy/10 bg-white p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-terminal-navy">Valuation Bridge</h3>

      <div className="mt-4 space-y-3">
        {rows.map((row) => (
          <div key={row.label}>
            <div className="mb-1 flex items-baseline justify-between text-xs">
              <span className="text-slate-500">{row.label}</span>
              <span className="tnum font-semibold text-terminal-navy">{formatUSDCompact(row.value)}</span>
            </div>
            <div className="h-2 w-full rounded-full bg-slate-100">
              <div
                className="h-2 rounded-full"
                style={{
                  width: `${(Math.abs(row.value) / maxMagnitude) * 100}%`,
                  backgroundColor: row.color,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3">
        <span className="text-sm font-semibold text-terminal-navy">Equity Value</span>
        <span className="tnum text-lg font-bold text-terminal-gold">{formatUSDCompact(dcf.equityValue)}</span>
      </div>
    </div>
  )
}
