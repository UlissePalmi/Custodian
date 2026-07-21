import type { ReactNode } from 'react'
import type { ChartTheme } from './theme'

interface ChartTooltipProps {
  theme: ChartTheme
  label: string
  rows: Array<{ key: string; label: string; value: ReactNode; color?: string }>
}

/**
 * Tooltip surface shared by every chart. Values use text tokens; identity comes
 * from the colour swatch beside the label, never from colouring the text.
 */
export function ChartTooltip({ theme, label, rows }: ChartTooltipProps) {
  return (
    <div
      className="rounded-lg border px-3 py-2 text-xs shadow-lg"
      style={{
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        color: theme.tooltipText,
      }}
    >
      <p className="font-medium">{label}</p>
      <ul className="mt-1 space-y-0.5">
        {rows.map((row) => (
          <li key={row.key} className="flex items-center gap-2">
            {row.color && (
              <span
                className="size-2 shrink-0 rounded-full"
                style={{ backgroundColor: row.color }}
                aria-hidden
              />
            )}
            <span className="opacity-70">{row.label}</span>
            <span className="tnum ml-auto font-medium">{row.value}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
