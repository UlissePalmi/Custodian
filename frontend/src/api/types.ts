/**
 * Custodian API contract.
 *
 * These types are the agreement between the front end and the FastAPI
 * backend. Every shape here has a matching Pydantic schema server-side.
 * Change them deliberately — the mock client in `./mock/client.ts` and the
 * HTTP client in `./http/client.ts` must both satisfy them.
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

/** 'chase_import' is legacy: the file importer it came from has been removed,
 *  but historical rows may still carry it. */
export type TransactionSource = 'manual' | 'chase_import' | 'plaid'

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
  /** Set when the transaction came from a sync batch. */
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

/** Net worth at the end of one day. */
export interface DailyNetWorth {
  /** ISO `YYYY-MM-DD`. */
  day: string
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
// Accounts
// ---------------------------------------------------------------------------

/** One position, as listed beneath the account holding it. */
export interface AccountHoldingLine {
  id: number
  ticker: string
  name: string
  quantity: number
  currentPrice: number
  marketValue: number
  quoteAsOf: string
  source: 'plaid' | 'manual'
}

export interface AccountBreakdown {
  id: number
  name: string
  /** The account's own kind: cash, stocks, bonds, credit. */
  type: AssetClass | 'credit' | (string & {})
  /** Where this row counts in the allocation, which is not always `type`: a
   *  card's debt and a brokerage's uninvested cash both count as cash. A
   *  brokerage with idle cash yields two rows, so group by this, not `type`. */
  assetClass: AssetClass | (string & {})
  currency: string
  /** In the account's own currency; `value` is the USD figure net worth uses. */
  balance: number
  /** Contribution to net worth under `assetClass`: negative for a credit
   *  account, positions only for a brokerage's stocks row. Summing every row
   *  gives the net worth total. */
  value: number
  percent: number
  /** False for accounts Plaid cannot see, which are maintained by hand. */
  isConnected: boolean
  /** When the bank last reported; null for unconnected accounts. */
  balanceAsOf: string | null
  holdings: AccountHoldingLine[]
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
// Bank sync (Plaid)
// ---------------------------------------------------------------------------

/** What one sync run did to the ledger. */
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

export interface LinkTokenResponse {
  /** Passed straight to `usePlaidLink` — short-lived, fetch fresh per attempt. */
  linkToken: string
}

export interface PlaidConnection {
  itemId: string
  institutionName: string
  status: 'active' | 'error' | 'disconnected'
  /** Null until the first sync has run. */
  lastSyncedAt: string | null
  /** Set when `status === 'error'`; the last sync failure, if any. */
  lastError: string | null
}

// ---------------------------------------------------------------------------
// Stock models (3-statement + DCF)
// ---------------------------------------------------------------------------

/**
 * Raw statement inputs. Every field is nullable — a period starts blank (or
 * partially filled from a historical-data pull) and is edited cell by cell;
 * subtotals (gross profit, EBITDA, FCF, ...) are always computed, never
 * stored, same "derive don't store" rule as the yearly table.
 */
export interface IncomeStatementInputs {
  revenue: number | null
  costOfRevenue: number | null
  researchAndDevelopment: number | null
  salesAndMarketing: number | null
  generalAndAdministrative: number | null
  depreciationAmortization: number | null
  stockBasedComp: number | null
  interestIncome: number | null
  interestExpense: number | null
  incomeTax: number | null
  dilutedShares: number | null
}

export interface BalanceSheetInputs {
  /** Raw input only on a model's earliest period — every later period computes
   *  this as `previous period's cash + this period's net change in cash`, so it
   *  always ties to the cash flow statement's ending balance. */
  cash: number | null
  accountsReceivable: number | null
  otherCurrentAssets: number | null
  ppeNet: number | null
  deferredRevenue: number | null
  accountsPayable: number | null
  accruedLiabilities: number | null
  longTermDebt: number | null
}

export interface CashFlowInputs {
  cashFromOperations: number | null
  capex: number | null
  cashFromFinancing: number | null
  /** DCF-only working-capital swing, feeding `freeCashFlow()` — kept separate
   *  from `cashFromOperations` above rather than decomposing that figure, since
   *  the two aren't meant to reconcile to each other. */
  changeInWorkingCapital: number | null
}

export interface StockPeriod {
  year: number
  /** False for a historical actual, true for a forecast year. */
  isProjected: boolean
  incomeStatement: IncomeStatementInputs
  balanceSheet: BalanceSheetInputs
  cashFlow: CashFlowInputs
}

export interface StockModelInput {
  ticker: string
  name: string
  notes?: string
  exchange?: string
  sector?: string
  waccPercent: number
  terminalGrowthPercent: number
  taxRatePercent: number
  /** Total debt minus cash & equivalents — a standalone assumption for the
   *  valuation bridge, not derived from any period's balance sheet. */
  netDebt: number
}

export interface StockModel {
  id: string
  ticker: string
  name: string
  notes?: string
  exchange?: string
  sector?: string
  waccPercent: number
  terminalGrowthPercent: number
  taxRatePercent: number
  netDebt: number
  /** Delayed quote, same feed as `Holding.currentPrice` — null until fetched
   *  (e.g. an unrecognised ticker). */
  currentPrice: number | null
  quoteAsOf: string | null
  /** Historical + projected years, in no particular order. */
  periods: StockPeriod[]
}

/** One projected year's discounted cash flow. */
export interface DcfYearProjection {
  year: number
  freeCashFlow: number
  discountFactor: number
  presentValue: number
}

export interface DcfResult {
  projections: DcfYearProjection[]
  terminalValue: number
  presentValueOfTerminalValue: number
  enterpriseValue: number
  /** Total debt minus cash & short-term investments, from the latest period. */
  netDebt: number
  equityValue: number
  /** Null when diluted shares aren't set on any period. */
  fairValuePerShare: number | null
  currentPrice: number | null
  /** `(fairValuePerShare / currentPrice - 1) * 100`, null if either is missing. */
  upsidePercent: number | null
}

/** WACC (rows) × terminal growth (columns) grid of implied fair value per share. */
export interface SensitivityGrid {
  waccPercentSteps: number[]
  terminalGrowthPercentSteps: number[]
  /** `fairValuePerShare[waccIndex][growthIndex]`; null where WACC <= growth. */
  fairValuePerShare: (number | null)[][]
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
  /** Every account, its USD value and share, and the positions it holds. */
  getAccountsBreakdown(): Promise<AccountBreakdown[]>
  /** End-of-day net worth, oldest first. Missing days are reconstructed
   *  server-side on read, so a gap while the Pi was off fills itself. */
  getDailyNetWorth(): Promise<DailyNetWorth[]>
  /** Server-issued token for `usePlaidLink`'s Link flow. */
  getPlaidLinkToken(): Promise<LinkTokenResponse>
  /**
   * Exchanges Link's `public_token` for a stored connection and runs the
   * first sync immediately, so newly imported transactions show up without
   * waiting for the next scheduled run.
   */
  exchangePlaidToken(
    publicToken: string,
    institutionId?: string,
    institutionName?: string,
  ): Promise<PlaidConnection>
  /** Runs a sync for every linked connection right now. */
  syncPlaidNow(): Promise<ImportResult[]>
  getPlaidStatus(): Promise<PlaidConnection[]>
  /** Unlinks the connection. Past transactions/batches are untouched. */
  disconnectPlaid(itemId: string): Promise<void>

  getStockModels(): Promise<StockModel[]>
  getStockModel(id: string): Promise<StockModel>
  createStockModel(input: StockModelInput): Promise<StockModel>
  updateStockModel(id: string, input: StockModelInput): Promise<StockModel>
  deleteStockModel(id: string): Promise<void>
  upsertStockPeriod(stockModelId: string, period: StockPeriod): Promise<StockPeriod>
  deleteStockPeriod(stockModelId: string, year: number): Promise<void>
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
