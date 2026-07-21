/**
 * Mock implementation of the Custodian API.
 *
 * Every function here has the exact signature and return shape the real
 * FastAPI backend must serve. To go live, write an HTTP client against the same
 * `CustodianApi` interface and swap the export in `src/api/index.ts` — no
 * component changes.
 */

import {
  ApiError,
  type Category,
  type CustodianApi,
  type Holding,
  type ImportPreview,
  type ImportResult,
  type MonthInfo,
  type MonthLedger,
  type NetWorthSummary,
  type ProposedTransaction,
  type Transaction,
  type TransactionInput,
  type YearlyTable,
} from '../types'
import {
  applyCashDelta,
  hasAppliedBatch,
  insertTransaction,
  modifyTransaction,
  readCategories,
  readHoldings,
  readMonthLedger,
  readMonths,
  readNetWorth,
  readYearlyTable,
  removeTransaction,
} from './store'
import { CHASE_CATEGORY_MAP, CURRENT_SNAPSHOT_MONTH, FALLBACK_EXPENSE_CATEGORY_ID } from './seed'
import { roundCents } from '../../utils/money'
import { isValidMonthKey, isWithinLedgerRange, isoDateIn, toMonthKey } from '../../utils/months'

/** Simulated network latency, so loading states are real during development. */
function delay(min = 250, max = 500): Promise<void> {
  const ms = min + Math.random() * (max - min)
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// ---------------------------------------------------------------------------
// Chase import mock
// ---------------------------------------------------------------------------

const ACCEPTED_EXTENSIONS = ['.csv', '.xls', '.xlsx']

/**
 * Rows a Chase export might contain. The real parser reads these off the
 * uploaded file; the mock fabricates a plausible statement instead.
 */
const FAKE_CHASE_ROWS: Array<{
  day: number
  description: string
  chaseCategory: string
  amount: number
  kind: 'income' | 'expense'
}> = [
  { day: 2, description: 'WHOLEFDS MKT #10259', chaseCategory: 'Groceries', amount: 86.42, kind: 'expense' },
  { day: 3, description: 'STARBUCKS STORE 08812', chaseCategory: 'Food & Drink', amount: 7.85, kind: 'expense' },
  { day: 5, description: 'CON EDISON WEB PMT', chaseCategory: 'Bills & Utilities', amount: 88.15, kind: 'expense' },
  { day: 6, description: 'UBER *TRIP', chaseCategory: 'Travel', amount: 18.4, kind: 'expense' },
  { day: 8, description: 'AMAZON MKTPL*RT4Y2', chaseCategory: 'Shopping', amount: 64.99, kind: 'expense' },
  { day: 10, description: "TRADER JOE'S #542", chaseCategory: 'Groceries', amount: 103.27, kind: 'expense' },
  { day: 12, description: 'NETFLIX.COM', chaseCategory: 'Entertainment', amount: 15.49, kind: 'expense' },
  { day: 14, description: 'PAYROLL DIRECT DEP - ACME CORP', chaseCategory: 'Payroll', amount: 3200, kind: 'income' },
  { day: 16, description: 'CVS/PHARMACY #04913', chaseCategory: 'Health', amount: 32.6, kind: 'expense' },
  { day: 18, description: 'SQ *THE COFFEE PROJECT', chaseCategory: 'Food & Drink', amount: 12.75, kind: 'expense' },
  { day: 20, description: 'VENMO PAYMENT', chaseCategory: 'Personal', amount: 45, kind: 'expense' },
  { day: 22, description: 'COURSERA.ORG', chaseCategory: 'Education', amount: 49, kind: 'expense' },
]

/** Pulls a `YYYY-MM` out of a filename like `Chase_activity_2026-08.csv`. */
function monthFromFileName(fileName: string): string | null {
  const match = fileName.match(/(20\d{2})[-_.]?(0[1-9]|1[0-2])/)
  if (!match) return null
  const key = toMonthKey(Number(match[1]), Number(match[2]))
  return isWithinLedgerRange(key) ? key : null
}

function mapChaseCategory(
  row: (typeof FAKE_CHASE_ROWS)[number],
): { categoryId: string; flaggedForReview: boolean } {
  if (row.kind === 'income') {
    return { categoryId: 'cat-main-income', flaggedForReview: false }
  }
  const mapped = CHASE_CATEGORY_MAP[row.chaseCategory]
  return mapped
    ? { categoryId: mapped, flaggedForReview: false }
    : { categoryId: FALLBACK_EXPENSE_CATEGORY_ID, flaggedForReview: true }
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

export const mockApi: CustodianApi = {
  async getNetWorth(): Promise<NetWorthSummary> {
    await delay()
    return readNetWorth()
  },

  async getHoldings(): Promise<Holding[]> {
    await delay()
    return readHoldings()
  },

  async getCategories(): Promise<Category[]> {
    await delay(120, 240)
    return readCategories()
  },

  async getMonths(): Promise<MonthInfo[]> {
    await delay()
    return readMonths()
  },

  async getMonth(year: number, month: number): Promise<MonthLedger> {
    await delay()
    const monthKey = toMonthKey(year, month)
    if (!isValidMonthKey(monthKey)) {
      throw new ApiError(`Invalid month: ${monthKey}`, 422)
    }
    if (!isWithinLedgerRange(monthKey)) {
      throw new ApiError(`${monthKey} is outside the ledger range.`, 404)
    }
    return readMonthLedger(monthKey)
  },

  async createTransaction(monthKey: string, input: TransactionInput): Promise<Transaction> {
    await delay(200, 400)
    if (input.date.slice(0, 7) !== monthKey) {
      throw new ApiError(`Date ${input.date} does not fall in ${monthKey}.`, 422)
    }
    return insertTransaction(input)
  },

  async updateTransaction(id: string, input: TransactionInput): Promise<Transaction> {
    await delay(200, 400)
    return modifyTransaction(id, input)
  },

  async deleteTransaction(id: string): Promise<void> {
    await delay(200, 400)
    removeTransaction(id)
  },

  async getYearlyTable(year: number): Promise<YearlyTable> {
    await delay()
    return readYearlyTable(year)
  },

  async uploadChaseFile(file: File, hintMonthKey?: string): Promise<ImportPreview> {
    await delay(700, 1200) // Parsing a spreadsheet is slower than a plain read.

    const lowerName = file.name.toLowerCase()
    if (!ACCEPTED_EXTENSIONS.some((ext) => lowerName.endsWith(ext))) {
      throw new ApiError('Please upload a Chase export as .csv, .xls or .xlsx.', 415)
    }
    if (file.size === 0) {
      throw new ApiError('That file is empty.', 422)
    }

    const detectedMonthKey =
      monthFromFileName(file.name) ??
      (hintMonthKey && isWithinLedgerRange(hintMonthKey) ? hintMonthKey : CURRENT_SNAPSHOT_MONTH)

    const transactions: ProposedTransaction[] = FAKE_CHASE_ROWS.map((row, index) => {
      const { categoryId, flaggedForReview } = mapChaseCategory(row)
      return {
        id: `preview-${index + 1}`,
        date: isoDateIn(detectedMonthKey, row.day),
        amount: row.amount,
        description: row.description,
        chaseCategory: row.chaseCategory,
        categoryId,
        kind: row.kind,
        flaggedForReview,
        include: true,
      }
    })

    return {
      batchId: `batch-${Date.now().toString(36)}`,
      fileName: file.name,
      detectedMonthKey,
      transactions,
    }
  },

  /**
   * Writes the confirmed rows into the ledger, then applies the batch's cash
   * delta to net worth.
   *
   * The cash-delta roll-forward is a core product behaviour, not a UI
   * convenience: confirming an import must move the cash account balance by
   * (income − expenses) of the batch and update that month's net worth
   * snapshot. The real backend implements this in the same step, idempotently
   * — re-confirming the same `batchId` must not double-count.
   */
  async confirmImport(preview: ImportPreview): Promise<ImportResult> {
    await delay(600, 1000)

    if (hasAppliedBatch(preview.batchId)) {
      throw new ApiError('This import has already been confirmed.', 409)
    }
    if (!isWithinLedgerRange(preview.detectedMonthKey)) {
      throw new ApiError(`${preview.detectedMonthKey} is outside the ledger range.`, 422)
    }

    const included = preview.transactions.filter((t) => t.include)
    if (included.length === 0) {
      throw new ApiError('No transactions selected to import.', 422)
    }

    let cashDelta = 0
    for (const row of included) {
      insertTransaction(
        {
          date: row.date,
          amount: row.amount,
          description: row.description,
          categoryId: row.categoryId,
        },
        { source: 'chase_import', importBatchId: preview.batchId },
      )
      cashDelta += row.kind === 'income' ? row.amount : -row.amount
    }
    cashDelta = roundCents(cashDelta)

    const newNetWorthTotal = applyCashDelta(preview.batchId, cashDelta)

    return {
      batchId: preview.batchId,
      monthKey: preview.detectedMonthKey,
      importedCount: included.length,
      cashDelta,
      newNetWorthTotal,
    }
  },
}
