/**
 * Mock implementation of the Custodian API.
 *
 * Every function here has the exact signature and return shape the real
 * FastAPI backend serves, so `src/api/index.ts` can swap between this and the
 * HTTP client with no component changes. Run with VITE_USE_MOCK=true.
 */

import {
  ApiError,
  type Category,
  type CustodianApi,
  type Holding,
  type ImportResult,
  type LinkTokenResponse,
  type MonthInfo,
  type MonthLedger,
  type NetWorthSummary,
  type PlaidConnection,
  type StockModel,
  type StockModelInput,
  type StockPeriod,
  type Transaction,
  type TransactionInput,
  type YearlyTable,
} from '../types'
import {
  insertStockModel,
  insertTransaction,
  linkPlaidConnection,
  modifyStockModel,
  modifyTransaction,
  readCategories,
  readHoldings,
  readMonthLedger,
  readMonths,
  readNetWorth,
  readPlaidConnections,
  readStockModel,
  readStockModels,
  readYearlyTable,
  removePlaidConnection,
  removeStockModel,
  removeStockModelPeriod,
  removeTransaction,
  upsertStockModelPeriod,
} from './store'
import { isValidMonthKey, isWithinLedgerRange, toMonthKey } from '../../utils/months'

/** Simulated network latency, so loading states are real during development. */
function delay(min = 250, max = 500): Promise<void> {
  const ms = min + Math.random() * (max - min)
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// ---------------------------------------------------------------------------
// Plaid sync mock
// ---------------------------------------------------------------------------

/** A fabricated first batch of "bank" transactions for a newly linked connection. */
const FAKE_PLAID_ROWS: Array<{
  day: number
  description: string
  categoryId: string
  amount: number
  kind: 'income' | 'expense'
}> = [
  { day: 1, description: 'ACME CORP PAYROLL', categoryId: 'cat-main-income', amount: 3200, kind: 'income' },
  { day: 4, description: 'TRADER JOE\'S #112', categoryId: 'cat-groceries', amount: 71.8, kind: 'expense' },
  { day: 9, description: 'CHEVRON GAS STATION', categoryId: 'cat-transport', amount: 44.1, kind: 'expense' },
  { day: 13, description: 'SPOTIFY USA', categoryId: 'cat-subscriptions', amount: 11.99, kind: 'expense' },
  { day: 17, description: 'CHIPOTLE ONLINE', categoryId: 'cat-dining', amount: 14.35, kind: 'expense' },
]

function currentMonthDate(day: number): string {
  const now = new Date()
  const monthKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
  return `${monthKey}-${String(day).padStart(2, '0')}`
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

  async getPlaidLinkToken(): Promise<LinkTokenResponse> {
    await delay(150, 300)
    // Never actually handed to a real Link widget in mock mode — see
    // ConnectBankButton, which skips Link entirely when VITE_USE_MOCK is set.
    return { linkToken: `link-mock-${Date.now().toString(36)}` }
  },

  async exchangePlaidToken(
    _publicToken: string,
    institutionId?: string,
    institutionName?: string,
  ): Promise<PlaidConnection> {
    await delay(500, 900) // Stands in for the real backend's token exchange + first sync.

    const itemId = institutionId ? `item-${institutionId}` : `item-${Date.now().toString(36)}`
    const rows = FAKE_PLAID_ROWS.map((row) => ({
      date: currentMonthDate(row.day),
      amount: row.amount,
      description: row.description,
      categoryId: row.categoryId,
      kind: row.kind,
    }))
    const { connection } = linkPlaidConnection(itemId, institutionName ?? 'Connected bank', rows)
    return connection
  },

  async syncPlaidNow(): Promise<ImportResult[]> {
    await delay(400, 700)
    // The mock's fabricated transactions are all inserted at link time; a
    // manual "sync now" has nothing further to fetch.
    return []
  },

  async getPlaidStatus(): Promise<PlaidConnection[]> {
    await delay(120, 240)
    return readPlaidConnections()
  },

  async disconnectPlaid(itemId: string): Promise<void> {
    await delay(200, 400)
    removePlaidConnection(itemId)
  },

  async getStockModels(): Promise<StockModel[]> {
    await delay()
    return readStockModels()
  },

  async getStockModel(id: string): Promise<StockModel> {
    await delay()
    return readStockModel(id)
  },

  async createStockModel(input: StockModelInput): Promise<StockModel> {
    await delay(200, 400)
    return insertStockModel(input)
  },

  async updateStockModel(id: string, input: StockModelInput): Promise<StockModel> {
    await delay(200, 400)
    return modifyStockModel(id, input)
  },

  async deleteStockModel(id: string): Promise<void> {
    await delay(200, 400)
    removeStockModel(id)
  },

  async upsertStockPeriod(stockModelId: string, period: StockPeriod): Promise<StockPeriod> {
    await delay(150, 300)
    return upsertStockModelPeriod(stockModelId, period)
  },

  async deleteStockPeriod(stockModelId: string, year: number): Promise<void> {
    await delay(150, 300)
    removeStockModelPeriod(stockModelId, year)
  },
}
