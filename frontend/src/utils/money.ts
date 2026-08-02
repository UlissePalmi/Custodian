/** USD formatting helpers. All money in the app flows through these. */

const usd = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const usdCompact = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
})

const percent = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

const quantity = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 4,
})

/** `1234.5` -> `$1,234.50` */
export function formatUSD(value: number): string {
  return usd.format(value)
}

/** `1234.5` -> `$1,235` — for axis ticks and large headline figures. */
export function formatUSDCompact(value: number): string {
  return usdCompact.format(value)
}

/** Always shows a sign: `1234.5` -> `+$1,234.50`, `-20` -> `-$20.00` */
export function formatUSDSigned(value: number): string {
  const sign = value > 0 ? '+' : value < 0 ? '-' : ''
  return `${sign}${usd.format(Math.abs(value))}`
}

/** `12.34` -> `12.3%` */
export function formatPercent(value: number): string {
  return `${percent.format(value)}%`
}

/** `12.34` -> `+12.3%` */
export function formatPercentSigned(value: number): string {
  const sign = value > 0 ? '+' : value < 0 ? '-' : ''
  return `${sign}${percent.format(Math.abs(value))}%`
}

/** `10.5` -> `10.5`, `10` -> `10` — share counts. */
export function formatQuantity(value: number): string {
  return quantity.format(value)
}

/** Rounds to cents so accumulated float error never surfaces in totals. */
export function roundCents(value: number): number {
  return Math.round(value * 100) / 100
}

/**
 * Tailwind text colour for a signed value. `neutralZero` keeps an exact zero
 * from being painted green, which reads oddly on an empty month.
 */
export function signColor(value: number, neutralZero = true): string {
  if (value > 0) return 'text-emerald-600 dark:text-emerald-400'
  if (value < 0) return 'text-rose-600 dark:text-rose-400'
  return neutralZero ? 'text-slate-500 dark:text-slate-400' : 'text-emerald-600 dark:text-emerald-400'
}
