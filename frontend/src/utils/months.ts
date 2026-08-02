/**
 * Month-key utilities.
 *
 * A "month key" is the string `YYYY-MM` (e.g. `2026-07`). It is the identifier
 * used in routes (`/months/2026-07`) and by the API layer. The backend derives
 * the same key from a transaction's date.
 */

/** Ledger data starts here. Nothing before this month exists, ever. */
export const LEDGER_START = '2026-07'

/**
 * Last month offered by the month picker. Extend this to add more months —
 * everything (picker, yearly table year list, month navigation) derives from it.
 */
export const LEDGER_END = '2027-12'

export const MONTH_NAMES = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
] as const

export const MONTH_NAMES_SHORT = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const

const MONTH_KEY_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/

export function isValidMonthKey(key: string): boolean {
  return MONTH_KEY_PATTERN.test(key)
}

/** Splits `2026-07` into `{ year: 2026, month: 7 }` (month is 1-indexed). */
export function parseMonthKey(key: string): { year: number; month: number } {
  const [year, month] = key.split('-')
  return { year: Number(year), month: Number(month) }
}

export function toMonthKey(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, '0')}`
}

/** Converts a month key to a sortable integer, e.g. `2026-07` -> 24319. */
function monthIndex(key: string): number {
  const { year, month } = parseMonthKey(key)
  return year * 12 + (month - 1)
}

export function compareMonthKeys(a: string, b: string): number {
  return monthIndex(a) - monthIndex(b)
}

export function isWithinLedgerRange(key: string): boolean {
  return (
    isValidMonthKey(key) &&
    compareMonthKeys(key, LEDGER_START) >= 0 &&
    compareMonthKeys(key, LEDGER_END) <= 0
  )
}

/** Adds `delta` months to a key. Returns `null` if the result leaves the ledger range. */
export function shiftMonthKey(key: string, delta: number): string | null {
  const index = monthIndex(key) + delta
  const next = toMonthKey(Math.floor(index / 12), (index % 12) + 1)
  return isWithinLedgerRange(next) ? next : null
}

/** All month keys from `from` to `to` inclusive. */
export function monthKeyRange(from = LEDGER_START, to = LEDGER_END): string[] {
  const keys: string[] = []
  for (let i = monthIndex(from); i <= monthIndex(to); i++) {
    keys.push(toMonthKey(Math.floor(i / 12), (i % 12) + 1))
  }
  return keys
}

/** Every year that has at least one month in the ledger range. */
export function ledgerYears(): number[] {
  const years = new Set(monthKeyRange().map((key) => parseMonthKey(key).year))
  return [...years].sort((a, b) => a - b)
}

/** Month keys within the ledger range that fall in `year`. */
export function monthKeysInYear(year: number): string[] {
  return monthKeyRange().filter((key) => parseMonthKey(key).year === year)
}

/** `2026-07` -> `July 2026` */
export function formatMonthLong(key: string): string {
  const { year, month } = parseMonthKey(key)
  return `${MONTH_NAMES[month - 1]} ${year}`
}

/** `2026-07` -> `Jul 2026` */
export function formatMonthShort(key: string): string {
  const { year, month } = parseMonthKey(key)
  return `${MONTH_NAMES_SHORT[month - 1]} ${year}`
}

/** The month key an ISO date (`2026-07-14`) belongs to. */
export function monthKeyFromDate(isoDate: string): string {
  return isoDate.slice(0, 7)
}

/** Number of days in the given month key. */
export function daysInMonth(key: string): number {
  const { year, month } = parseMonthKey(key)
  return new Date(year, month, 0).getDate()
}

/** `2026-07-14` -> `Jul 14` */
export function formatDayShort(isoDate: string): string {
  const [, month, day] = isoDate.split('-')
  return `${MONTH_NAMES_SHORT[Number(month) - 1]} ${Number(day)}`
}

/** Builds an ISO date string inside a month, clamped to that month's length. */
export function isoDateIn(monthKey: string, day: number): string {
  const clamped = Math.min(Math.max(day, 1), daysInMonth(monthKey))
  return `${monthKey}-${String(clamped).padStart(2, '0')}`
}
