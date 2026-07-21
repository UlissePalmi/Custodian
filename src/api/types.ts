/**
 * Custodian API contract.
 *
 * These types are the agreement between the front end and the (not yet built)
 * FastAPI backend. Every shape here is expected to have a matching Pydantic
 * schema server-side. Change them deliberately — the mock client in
 * `./mock/client.ts` and the eventual HTTP client must both satisfy them.
 *
 * Conventions:
 *  - Money is a plain `number` of US dollars (not cents). The backend should
 *    serialise Decimal as a JSON number rounded to 2 dp.
 *  - Percentages are whole numbers, i.e. `12.5` means 12.5%, not 0.125.
 *  - Dates are ISO `YYYY-MM-DD` strings. Timestamps are ISO 8601 with timezone.
 *  - Month keys are `YYYY-MM`.
 *  - Transaction `amount` is always POSITIVE; direction comes from `kind`.
 */

// ---------------------------------------------------------------------------
// Categories
// ---------------------------------------------------------------------------

export type CategoryKind = 'income' | 'expense'

export interface Category {
  id: string
  name: string
  kind: CategoryKind
  /** Display order within its kind. */
  sortOrder: number
  /** Archived categories stay attached to historical transactions but are
   *  hidden from the "add entry" pickers. */
  archived?: boolean
}

// ---------------------------------------------------------------------------
// Transactions / monthly ledger
// ---------------------------------------------------------------------------

export type TransactionSource = 'manual' | 'chase_import'

export interface Transaction {
  id: string
  /** ISO `YYYY-MM-DD`. Must be on or after the ledger start month. */
  date: string
  /** Positive dollar amount. `kind` determines income vs. expense. */
  amount: number
  description: string
  categoryId: string
  /** Denormalised for display so lists don't need a second lookup. */
  categoryName: string
  kind: CategoryKind
  source: TransactionSource
  /** Set when the transaction came from a confirmed Chase import batch. */
  importBatchId?: string
}

/** Payload for creating or updating a transaction. */
export interface TransactionInput {
  date: string
  amount: number
  description: string
  categoryId: string
}

export interface MonthLedger {
  monthKey: string
  totalIncome: number
  totalExpenses: number
  /** `totalIncome - totalExpenses`. */
  net: number
  income: Transaction[]
  expenses: Transaction[]
}

/** One entry in the month picker. */
export interface MonthInfo {
  monthKey: string
  /** False when the month has no transactions at all — drives the empty state. */
  hasData: boolean
  totalIncome: number
  totalExpenses: number
  net: number
}

// ---------------------------------------------------------------------------
// Net worth / holdings
// ---------------------------------------------------------------------------

/**
 * Open union: `stocks | cash | bonds` today, but the backend may return more
 * (crypto, real estate, ...) and the dashboard renders whatever it receives.
 */
export type AssetClass = 'stocks' | 'cash' | 'bonds' | (string & {})

export interface AllocationSlice {
  assetClass: AssetClass
  /** Human-readable label; the UI never hardcodes asset class names. */
  label: string
  value: number
  /** Share of total net worth, e.g. `62.4`. */
  percent: number
}

export interface NetWorthPoint {
  monthKey: string
  total: number
}

export interface NetWorthChange {
  amount: number
  percent: number
}

export interface NetWorthSummary {
  total: number
  /** ISO date of the most recent snapshot. */
  asOf: string
  /** Null when there is no prior month to compare against. */
  changeVsPrevMonth: NetWorthChange | null
  /** Monthly snapshots, oldest first. */
  history: NetWorthPoint[]
  allocation: AllocationSlice[]
}

export interface Holding {
  id: string
  ticker: string
  name: string
  quantity: number
  /** Cost basis per share. */
  costBasisPerShare: number
  /** Delayed quote from the price feed. */
  currentPrice: number
  /** ISO timestamp of the quote — shown so a stale/offline feed is visible. */
  quoteAsOf: string
  /** `quantity * currentPrice`. */
  marketValue: number
  /** Gain/loss against cost basis, in dollars and percent. */
  totalReturn: NetWorthChange
  /** Year-to-date price return, percent. */
  ytdReturnPercent: number
}

// ---------------------------------------------------------------------------
// Yearly table (derived — never stored)
// ---------------------------------------------------------------------------

export interface YearlyTableRow {
  monthKey: string
  /** Total per category id for this month. Missing key means zero. */
  cells: Record<string, number>
  totalIncome: number
  totalExpenses: number
  net: number
}

export interface YearlyTable {
  year: number
  /** Column definitions in display order: income categories, then expense. */
  columns: Category[]
  rows: YearlyTableRow[]
  /** Column-wise totals across all rows, keyed by category id. */
  totals: {
    cells: Record<string, number>
    totalIncome: number
    totalExpenses: number
    net: number
  }
}

// ---------------------------------------------------------------------------
// Chase import
// ---------------------------------------------------------------------------

export interface ProposedTransaction {
  /** Client-side id for the preview row; not a persisted transaction id. */
  id: string
  date: string
  amount: number
  description: string
  /** Raw category string from the Chase export, kept for context. */
  chaseCategory: string
  /** Custodian category the mapper chose. */
  categoryId: string
  kind: CategoryKind
  /** True when the Chase category had no mapping and fell through to "Other". */
  flaggedForReview: boolean
  /** Unchecked rows are skipped on confirm. */
  include: boolean
}

export interface ImportPreview {
  batchId: string
  fileName: string
  /** Month inferred from the parsed transaction dates. */
  detectedMonthKey: string
  transactions: ProposedTransaction[]
}

export interface ImportResult {
  batchId: string
  monthKey: string
  importedCount: number
  /**
   * Net cash movement of the batch (income − expenses). Applied to the cash
   * account balance and rolled into the month's net worth snapshot.
   */
  cashDelta: number
  /** Net worth total after the roll-forward, so the UI can confirm the effect. */
  newNetWorthTotal: number
}

// ---------------------------------------------------------------------------
// Client surface
// ---------------------------------------------------------------------------

/**
 * The full API surface. Both the mock client and the future HTTP client
 * implement this, so swapping them cannot silently drop a method.
 */
export interface CustodianApi {
  getNetWorth(): Promise<NetWorthSummary>
  getHoldings(): Promise<Holding[]>
  getCategories(): Promise<Category[]>
  getMonths(): Promise<MonthInfo[]>
  getMonth(year: number, month: number): Promise<MonthLedger>
  createTransaction(monthKey: string, input: TransactionInput): Promise<Transaction>
  updateTransaction(id: string, input: TransactionInput): Promise<Transaction>
  deleteTransaction(id: string): Promise<void>
  getYearlyTable(year: number): Promise<YearlyTable>
  /**
   * `hintMonthKey` is the month the upload was started from. The backend still
   * decides `detectedMonthKey` from the parsed rows; the hint only helps when
   * the file itself is ambiguous.
   */
  uploadChaseFile(file: File, hintMonthKey?: string): Promise<ImportPreview>
  confirmImport(preview: ImportPreview): Promise<ImportResult>
}

/** Thrown by the API layer for expected, user-facing failures. */
export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status = 400) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}
