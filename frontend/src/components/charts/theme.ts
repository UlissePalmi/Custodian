/**
 * Chart colour tokens — fixed to the app's navy/cream/gold terminal palette,
 * not OS light/dark aware (the app no longer adapts to system theme). Recharts
 * needs real colour values in JS, so this can't live in Tailwind classes alone.
 */
export interface ChartTheme {
  /** Categorical slots, in fixed assignment order — never cycled. */
  series: [string, string, string]
  surface: string
  grid: string
  axis: string
  /** Tooltip container. */
  tooltipBg: string
  tooltipBorder: string
  tooltipText: string
}

const TERMINAL_THEME: ChartTheme = {
  series: ['#1b2640', '#d4af37', '#8b3a3a'],
  surface: '#ffffff',
  grid: '#e5dfd0',
  axis: '#6b6459',
  tooltipBg: '#1b2640',
  tooltipBorder: '#2a3a5c',
  tooltipText: '#f5f0e6',
}

export function useChartTheme(): ChartTheme {
  return TERMINAL_THEME
}

/** Shared Recharts axis styling: recessive, hairline, never dashed. */
export function axisProps(theme: ChartTheme) {
  return {
    stroke: theme.axis,
    tick: { fill: theme.axis, fontSize: 12 },
    tickLine: false as const,
    axisLine: false as const,
  }
}
