import { formatUSD } from '../../utils/money'
import type { SensitivityGrid } from '../../api/types'

const LOW = [252, 226, 226] as const // soft rose
const HIGH = [209, 236, 219] as const // soft green

function heatColor(value: number, min: number, max: number): string {
  const t = max === min ? 0.5 : (value - min) / (max - min)
  const [r, g, b] = LOW.map((low, i) => Math.round(low + (HIGH[i] - low) * t))
  return `rgb(${r}, ${g}, ${b})`
}

/**
 * WACC (rows) × terminal growth (columns) heatmap of implied fair value per
 * share, matching the prototype's Sensitivity tab. The current assumptions'
 * cell is highlighted navy/bold so it reads as the centre of the grid.
 */
export default function SensitivityTable({
  grid,
  waccPercent,
  terminalGrowthPercent,
}: {
  grid: SensitivityGrid
  waccPercent: number
  terminalGrowthPercent: number
}) {
  const values = grid.fairValuePerShare.flat().filter((v): v is number => v != null)
  const min = values.length ? Math.min(...values) : 0
  const max = values.length ? Math.max(...values) : 0

  return (
    <div className="rounded-lg border border-terminal-navy/10 bg-white p-5 shadow-sm">
      <h3 className="text-sm font-semibold text-terminal-navy">Sensitivity — Share Price ($)</h3>
      <p className="mt-0.5 text-xs text-slate-500">WACC (rows) vs. Terminal Growth Rate (columns)</p>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-max text-sm">
          <thead>
            <tr>
              <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">WACC \ TGR</th>
              {grid.terminalGrowthPercentSteps.map((growth) => (
                <th
                  key={growth}
                  className={`tnum px-3 py-2 text-right text-xs font-medium ${
                    growth === terminalGrowthPercent ? 'text-terminal-gold' : 'text-slate-400'
                  }`}
                >
                  {growth.toFixed(1)}%
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grid.waccPercentSteps.map((wacc, rowIndex) => (
              <tr key={wacc}>
                <td
                  className={`tnum px-3 py-1.5 text-xs font-medium ${
                    wacc === waccPercent ? 'text-terminal-gold' : 'text-slate-400'
                  }`}
                >
                  {wacc.toFixed(1)}%
                </td>
                {grid.terminalGrowthPercentSteps.map((growth, colIndex) => {
                  const value = grid.fairValuePerShare[rowIndex][colIndex]
                  const isCurrent = wacc === waccPercent && growth === terminalGrowthPercent
                  return (
                    <td
                      key={growth}
                      className={`tnum px-3 py-1.5 text-right ${isCurrent ? 'rounded bg-terminal-navy font-semibold text-white' : 'text-terminal-navy'}`}
                      style={!isCurrent && value != null ? { backgroundColor: heatColor(value, min, max) } : undefined}
                    >
                      {value != null ? formatUSD(value) : '—'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
