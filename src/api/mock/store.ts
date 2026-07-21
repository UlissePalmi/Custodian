/**
 * In-memory data store backing the mock API, mirrored to localStorage so edits
 * and imports survive a page refresh.
 *
 * Everything derived (month totals, the yearly table, net worth) is computed
 * from the stored transactions/holdings/balances on read. Nothing aggregate is
 * stored, which is the same invariant the real backend must hold: the monthly
 * ledger is the single source of truth and the yearly table can never disagree
 * with it.
 */

import {
  ApiError,
  type AllocationSlice,
  type Category,
  type Holding,
  type MonthInfo,
  type MonthLedger,
  type NetWorthPoint,
  type NetWorthSummary,
  type Transaction,
  type TransactionInput,
  type YearlyTable,
  type YearlyTableRow,
} from '../types'
import {
  CURRENT_SNAPSHOT_MONTH,
  SEED_BONDS_BALANCE,
  SEED_CASH_BALANCE,
  SEED_CATEGORIES,
  SEED_HOLDINGS,
  SEED_NET_WORTH_HISTORY,
  SEED_TRANSACTIONS,
} from './seed'
import { roundCents } from '../../utils/money'
import {
  LEDGER_START,
  compareMonthKeys,
  monthKeyFromDate,
  monthKeyRange,
  monthKeysInYear,
} from '../../utils/months'

/** Transaction as stored: no denormalised category fields, so renaming a
 *  category updates every historical entry for free. */
type StoredTransaction = Omit<Transaction, 'categoryName' | 'kind'>

type StoredHolding = (typeof SEED_HOLDINGS)[number]

interface StoreState {
  categories: Category[]
  transactions: StoredTransaction[]
  holdings: StoredHolding[]
  cashBalance: number
  bondsBalance: number
  /** Snapshots strictly before `CURRENT_SNAPSHOT_MONTH`. */
  pastNetWorthHistory: NetWorthPoint[]
  /** Batch ids already applied, so re-confirming cannot double-count. */
  appliedImportBatches: string[]
  nextTransactionSeq: number
}

const STORAGE_KEY = 'custodian.mock.v1'

function initialState(): StoreState {
  return {
    categories: SEED_CATEGORIES.map((c) => ({ ...c })),
    transactions: SEED_TRANSACTIONS.map((t) => ({ ...t })),
    holdings: SEED_HOLDINGS.map((h) => ({ ...h })),
    cashBalance: SEED_CASH_BALANCE,
    bondsBalance: SEED_BONDS_BALANCE,
    pastNetWorthHistory: SEED_NET_WORTH_HISTORY.map((p) => ({ ...p })),
    appliedImportBatches: [],
    nextTransactionSeq: SEED_TRANSACTIONS.length + 1,
  }
}

function load(): StoreState {
  if (typeof localStorage === 'undefined') return initialState()
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return initialState()
    const parsed = JSON.parse(raw) as StoreState
    // Shallow sanity check — a shape change bumps STORAGE_KEY, but guard anyway.
    if (!Array.isArray(parsed.transactions) || !Array.isArray(parsed.categories)) {
      return initialState()
    }
    return parsed
  } catch {
    return initialState()
  }
}

let state: StoreState = load()

function persist(): void {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // Storage full or unavailable — the in-memory store still works.
  }
}

/** Wipes persisted mock data and returns to the seed. Exposed for debugging. */
export function resetStore(): void {
  state = initialState()
  persist()
}

// ---------------------------------------------------------------------------
// Lookups
// ---------------------------------------------------------------------------

function categoryById(id: string): Category | undefined {
  return state.categories.find((c) => c.id === id)
}

function requireCategory(id: string): Category {
  const category = categoryById(id)
  if (!category) throw new ApiError(`Unknown category: ${id}`, 422)
  return category
}

/** Attaches the display fields the API contract promises. */
function hydrate(txn: StoredTransaction): Transaction {
  const category = categoryById(txn.categoryId)
  return {
    ...txn,
    categoryName: category?.name ?? 'Uncategorised',
    kind: category?.kind ?? 'expense',
  }
}

function sortByDate(a: StoredTransaction, b: StoredTransaction): number {
  if (a.date !== b.date) return a.date.localeCompare(b.date)
  return a.id.localeCompare(b.id)
}

function transactionsForMonth(monthKey: string): StoredTransaction[] {
  return state.transactions
    .filter((t) => monthKeyFromDate(t.date) === monthKey)
    .sort(sortByDate)
}

function nextTransactionId(): string {
  const id = `txn-${String(state.nextTransactionSeq).padStart(4, '0')}`
  state.nextTransactionSeq += 1
  return id
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

function validateInput(input: TransactionInput): void {
  if (!ISO_DATE.test(input.date)) {
    throw new ApiError('Date must be a valid calendar date.', 422)
  }
  if (compareMonthKeys(monthKeyFromDate(input.date), LEDGER_START) < 0) {
    throw new ApiError(`Custodian's ledger starts in ${LEDGER_START}. Earlier dates are not accepted.`, 422)
  }
  if (!Number.isFinite(input.amount) || input.amount <= 0) {
    throw new ApiError('Amount must be greater than zero.', 422)
  }
  if (!input.description.trim()) {
    throw new ApiError('Description is required.', 422)
  }
  requireCategory(input.categoryId)
}

// ---------------------------------------------------------------------------
// Derived reads
// ---------------------------------------------------------------------------

export function readCategories(): Category[] {
  return [...state.categories]
    .filter((c) => !c.archived)
    .sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === 'income' ? -1 : 1
      return a.sortOrder - b.sortOrder
    })
}

export function readMonthLedger(monthKey: string): MonthLedger {
  const entries = transactionsForMonth(monthKey).map(hydrate)
  const income = entries.filter((t) => t.kind === 'income')
  const expenses = entries.filter((t) => t.kind === 'expense')
  const totalIncome = roundCents(income.reduce((sum, t) => sum + t.amount, 0))
  const totalExpenses = roundCents(expenses.reduce((sum, t) => sum + t.amount, 0))

  return {
    monthKey,
    totalIncome,
    totalExpenses,
    net: roundCents(totalIncome - totalExpenses),
    income,
    expenses,
  }
}

export function readMonths(): MonthInfo[] {
  return monthKeyRange().map((monthKey) => {
    const ledger = readMonthLedger(monthKey)
    return {
      monthKey,
      hasData: ledger.income.length > 0 || ledger.expenses.length > 0,
      totalIncome: ledger.totalIncome,
      totalExpenses: ledger.totalExpenses,
      net: ledger.net,
    }
  })
}

export function readYearlyTable(year: number): YearlyTable {
  const columns = readCategories()
  const rows: YearlyTableRow[] = monthKeysInYear(year).map((monthKey) => {
    const cells: Record<string, number> = {}
    let totalIncome = 0
    let totalExpenses = 0

    for (const txn of transactionsForMonth(monthKey)) {
      const category = categoryById(txn.categoryId)
      if (!category) continue
      cells[category.id] = roundCents((cells[category.id] ?? 0) + txn.amount)
      if (category.kind === 'income') totalIncome += txn.amount
      else totalExpenses += txn.amount
    }

    totalIncome = roundCents(totalIncome)
    totalExpenses = roundCents(totalExpenses)
    return { monthKey, cells, totalIncome, totalExpenses, net: roundCents(totalIncome - totalExpenses) }
  })

  const totals = {
    cells: {} as Record<string, number>,
    totalIncome: 0,
    totalExpenses: 0,
    net: 0,
  }
  for (const row of rows) {
    for (const [categoryId, value] of Object.entries(row.cells)) {
      totals.cells[categoryId] = roundCents((totals.cells[categoryId] ?? 0) + value)
    }
    totals.totalIncome += row.totalIncome
    totals.totalExpenses += row.totalExpenses
  }
  totals.totalIncome = roundCents(totals.totalIncome)
  totals.totalExpenses = roundCents(totals.totalExpenses)
  totals.net = roundCents(totals.totalIncome - totals.totalExpenses)

  return { year, columns, rows, totals }
}

export function readHoldings(): Holding[] {
  // A real feed timestamp; ~15 minutes delayed, as the backend's cache will be.
  const quoteAsOf = new Date(Date.now() - 15 * 60 * 1000).toISOString()

  return state.holdings.map((h) => {
    const marketValue = roundCents(h.quantity * h.currentPrice)
    const costBasis = h.quantity * h.costBasisPerShare
    const gain = roundCents(marketValue - costBasis)
    return {
      id: h.id,
      ticker: h.ticker,
      name: h.name,
      quantity: h.quantity,
      costBasisPerShare: h.costBasisPerShare,
      currentPrice: h.currentPrice,
      quoteAsOf,
      marketValue,
      totalReturn: {
        amount: gain,
        percent: costBasis === 0 ? 0 : roundCents((gain / costBasis) * 100),
      },
      ytdReturnPercent: h.ytdReturnPercent,
    }
  })
}

function stocksValue(): number {
  return roundCents(state.holdings.reduce((sum, h) => sum + h.quantity * h.currentPrice, 0))
}

export function readNetWorth(): NetWorthSummary {
  const stocks = stocksValue()
  const cash = roundCents(state.cashBalance)
  const bonds = roundCents(state.bondsBalance)
  const total = roundCents(stocks + cash + bonds)

  const rawAllocation: Array<{ assetClass: string; label: string; value: number }> = [
    { assetClass: 'stocks', label: 'Stocks', value: stocks },
    { assetClass: 'cash', label: 'Cash', value: cash },
    { assetClass: 'bonds', label: 'Bonds', value: bonds },
  ]
  const allocation: AllocationSlice[] = rawAllocation.map((slice) => ({
    ...slice,
    percent: total === 0 ? 0 : roundCents((slice.value / total) * 100),
  }))

  // The current month's snapshot is live, so a confirmed import moves both the
  // headline total and the last point on the chart.
  const history: NetWorthPoint[] = [
    ...state.pastNetWorthHistory,
    { monthKey: CURRENT_SNAPSHOT_MONTH, total },
  ].sort((a, b) => compareMonthKeys(a.monthKey, b.monthKey))

  const previous = history.length > 1 ? history[history.length - 2] : null
  const changeVsPrevMonth =
    previous && previous.total !== 0
      ? {
          amount: roundCents(total - previous.total),
          percent: roundCents(((total - previous.total) / previous.total) * 100),
        }
      : null

  return {
    total,
    asOf: new Date().toISOString().slice(0, 10),
    changeVsPrevMonth,
    history,
    allocation,
  }
}

// ---------------------------------------------------------------------------
// Writes
// ---------------------------------------------------------------------------

export function insertTransaction(
  input: TransactionInput,
  options: { source?: Transaction['source']; importBatchId?: string } = {},
): Transaction {
  validateInput(input)
  const stored: StoredTransaction = {
    id: nextTransactionId(),
    date: input.date,
    amount: roundCents(input.amount),
    description: input.description.trim(),
    categoryId: input.categoryId,
    source: options.source ?? 'manual',
    ...(options.importBatchId ? { importBatchId: options.importBatchId } : {}),
  }
  state.transactions.push(stored)
  persist()
  return hydrate(stored)
}

export function modifyTransaction(id: string, input: TransactionInput): Transaction {
  validateInput(input)
  const existing = state.transactions.find((t) => t.id === id)
  if (!existing) throw new ApiError('Transaction not found.', 404)

  existing.date = input.date
  existing.amount = roundCents(input.amount)
  existing.description = input.description.trim()
  existing.categoryId = input.categoryId
  persist()
  return hydrate(existing)
}

export function removeTransaction(id: string): void {
  const index = state.transactions.findIndex((t) => t.id === id)
  if (index === -1) throw new ApiError('Transaction not found.', 404)
  state.transactions.splice(index, 1)
  persist()
}

/**
 * Applies a confirmed import batch's cash movement to net worth.
 *
 * This is the behaviour the real backend owns: the cash delta (income −
 * expenses of the batch) is added to the cash account balance, which rolls
 * forward into the month's net worth snapshot. Guarded by batch id so
 * re-confirming the same batch cannot double-count.
 *
 * Returns the new net worth total.
 */
export function applyCashDelta(batchId: string, cashDelta: number): number {
  if (!state.appliedImportBatches.includes(batchId)) {
    state.cashBalance = roundCents(state.cashBalance + cashDelta)
    state.appliedImportBatches.push(batchId)
    persist()
  }
  return readNetWorth().total
}

export function hasAppliedBatch(batchId: string): boolean {
  return state.appliedImportBatches.includes(batchId)
}

export function categoryIdsByKind(kind: Category['kind']): string[] {
  return readCategories()
    .filter((c) => c.kind === kind)
    .map((c) => c.id)
}
