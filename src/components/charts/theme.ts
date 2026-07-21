import { useEffect, useState } from 'react'

/**
 * Chart colour tokens.
 *
 * Recharts needs real colour values in JS, so the palette can't live in Tailwind
 * classes. Both columns are the same hues stepped for their own surface, and the
 * set was validated (lightness band, chroma floor, CVD separation, normal-vision
 * floor, contrast) against the card surfaces below — `#ffffff` light and
 * `#0f172a` dark. Re-run the validator if you change any of these.
 *
 * Note: in light mode `aqua` sits at 2.82:1 against white, under the 3:1 bar.
 * That is allowed only because every chart using it ships visible value labels
 * or an adjacent table (the allocation legend). Don't use it bare.
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

const LIGHT: ChartTheme = {
  series: ['#2a78d6', '#eb6834', '#1baf7a'],
  surface: '#ffffff',
  grid: '#e2e8f0',
  axis: '#64748b',
  tooltipBg: '#ffffff',
  tooltipBorder: '#e2e8f0',
  tooltipText: '#0f172a',
}

const DARK: ChartTheme = {
  series: ['#3987e5', '#d95926', '#199e70'],
  surface: '#0f172a',
  grid: '#1e293b',
  axis: '#94a3b8',
  tooltipBg: '#1e293b',
  tooltipBorder: '#334155',
  tooltipText: '#f1f5f9',
}

/** Tracks the OS colour scheme so charts restep rather than flip. */
export function useChartTheme(): ChartTheme {
  const [dark, setDark] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-color-scheme: dark)').matches,
  )

  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (event: MediaQueryListEvent) => setDark(event.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  return dark ? DARK : LIGHT
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
