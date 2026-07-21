/**
 * Seed data for the mock API.
 *
 * Numbers are chosen to be internally consistent: net worth is derived from
 * holdings + cash + bonds rather than hardcoded, so a Chase import that moves
 * cash also moves the dashboard total.
 */

import type { Category, Holding, NetWorthPoint, Transaction } from '../types'

/** The month the latest net worth snapshot belongs to. */
export const CURRENT_SNAPSHOT_MONTH = '2026-07'

export const SEED_CATEGORIES: Category[] = [
  { id: 'cat-main-income', name: 'Main income', kind: 'income', sortOrder: 0 },
  { id: 'cat-secondary-income', name: 'Secondary income', kind: 'income', sortOrder: 1 },
  { id: 'cat-rent', name: 'Rent', kind: 'expense', sortOrder: 0 },
  { id: 'cat-utilities', name: 'Utilities', kind: 'expense', sortOrder: 1 },
  { id: 'cat-phone', name: 'Phone', kind: 'expense', sortOrder: 2 },
  { id: 'cat-groceries', name: 'Groceries', kind: 'expense', sortOrder: 3 },
  { id: 'cat-dining', name: 'Dining', kind: 'expense', sortOrder: 4 },
  { id: 'cat-transport', name: 'Transport', kind: 'expense', sortOrder: 5 },
  { id: 'cat-subscriptions', name: 'Subscriptions', kind: 'expense', sortOrder: 6 },
  { id: 'cat-other', name: 'Other', kind: 'expense', sortOrder: 7 },
]

/** Category every unmapped import row falls through to. */
export const FALLBACK_EXPENSE_CATEGORY_ID = 'cat-other'

type SeedTransaction = Omit<Transaction, 'categoryName' | 'kind'>

const seedTransactions: SeedTransaction[] = [
  // --- Income -------------------------------------------------------------
  {
    id: 'txn-0001',
    date: '2026-07-01',
    amount: 3200,
    description: 'Paycheck — first half',
    categoryId: 'cat-main-income',
    source: 'manual',
  },
  {
    id: 'txn-0002',
    date: '2026-07-15',
    amount: 3200,
    description: 'Paycheck — second half',
    categoryId: 'cat-main-income',
    source: 'manual',
  },
  {
    id: 'txn-0003',
    date: '2026-07-08',
    amount: 850,
    description: 'Freelance — landing page build',
    categoryId: 'cat-secondary-income',
    source: 'manual',
  },
  // --- Expenses -----------------------------------------------------------
  {
    id: 'txn-0004',
    date: '2026-07-01',
    amount: 1850,
    description: 'July rent',
    categoryId: 'cat-rent',
    source: 'manual',
  },
  {
    id: 'txn-0005',
    date: '2026-07-03',
    amount: 92.4,
    description: 'Con Edison — electric',
    categoryId: 'cat-utilities',
    source: 'manual',
  },
  {
    id: 'txn-0006',
    date: '2026-07-05',
    amount: 65,
    description: 'Verizon',
    categoryId: 'cat-phone',
    source: 'manual',
  },
  {
    id: 'txn-0007',
    date: '2026-07-04',
    amount: 128.75,
    description: "Trader Joe's",
    categoryId: 'cat-groceries',
    source: 'manual',
  },
  {
    id: 'txn-0008',
    date: '2026-07-11',
    amount: 94.2,
    description: 'Whole Foods',
    categoryId: 'cat-groceries',
    source: 'manual',
  },
  {
    id: 'txn-0009',
    date: '2026-07-18',
    amount: 112.6,
    description: "Trader Joe's",
    categoryId: 'cat-groceries',
    source: 'manual',
  },
  {
    id: 'txn-0010',
    date: '2026-07-06',
    amount: 78,
    description: 'Sushi with M.',
    categoryId: 'cat-dining',
    source: 'manual',
  },
  {
    id: 'txn-0011',
    date: '2026-07-12',
    amount: 42.3,
    description: 'Coffee + brunch',
    categoryId: 'cat-dining',
    source: 'manual',
  },
  {
    id: 'txn-0012',
    date: '2026-07-19',
    amount: 31.5,
    description: 'Thai takeout',
    categoryId: 'cat-dining',
    source: 'manual',
  },
  {
    id: 'txn-0013',
    date: '2026-07-02',
    amount: 132,
    description: 'MTA monthly',
    categoryId: 'cat-transport',
    source: 'manual',
  },
  {
    id: 'txn-0014',
    date: '2026-07-14',
    amount: 23.8,
    description: 'Uber — airport',
    categoryId: 'cat-transport',
    source: 'manual',
  },
  {
    id: 'txn-0015',
    date: '2026-07-01',
    amount: 11.99,
    description: 'Spotify',
    categoryId: 'cat-subscriptions',
    source: 'manual',
  },
  {
    id: 'txn-0016',
    date: '2026-07-02',
    amount: 9.99,
    description: 'iCloud 2TB',
    categoryId: 'cat-subscriptions',
    source: 'manual',
  },
  {
    id: 'txn-0017',
    date: '2026-07-07',
    amount: 15.49,
    description: 'Netflix',
    categoryId: 'cat-subscriptions',
    source: 'manual',
  },
  {
    id: 'txn-0018',
    date: '2026-07-09',
    amount: 45,
    description: 'Dentist copay',
    categoryId: 'cat-other',
    source: 'manual',
  },
  {
    id: 'txn-0019',
    date: '2026-07-16',
    amount: 60,
    description: 'Birthday gift',
    categoryId: 'cat-other',
    source: 'manual',
  },
]

export const SEED_TRANSACTIONS = seedTransactions

export const SEED_HOLDINGS: Array<
  Pick<Holding, 'id' | 'ticker' | 'name' | 'quantity' | 'costBasisPerShare' | 'currentPrice'> & {
    ytdReturnPercent: number
  }
> = [
  {
    id: 'hold-voo',
    ticker: 'VOO',
    name: 'Vanguard S&P 500 ETF',
    quantity: 42,
    costBasisPerShare: 465.2,
    currentPrice: 528.4,
    ytdReturnPercent: 8.4,
  },
  {
    id: 'hold-aapl',
    ticker: 'AAPL',
    name: 'Apple Inc.',
    quantity: 60,
    costBasisPerShare: 178.5,
    currentPrice: 231.15,
    ytdReturnPercent: 12.7,
  },
  {
    id: 'hold-msft',
    ticker: 'MSFT',
    name: 'Microsoft Corp.',
    quantity: 25,
    costBasisPerShare: 372.8,
    currentPrice: 448.6,
    ytdReturnPercent: 9.1,
  },
  {
    id: 'hold-nvda',
    ticker: 'NVDA',
    name: 'NVIDIA Corp.',
    quantity: 30,
    costBasisPerShare: 118.4,
    currentPrice: 172.9,
    ytdReturnPercent: 21.3,
  },
  {
    id: 'hold-vxus',
    ticker: 'VXUS',
    name: 'Vanguard Total International Stock ETF',
    quantity: 85,
    costBasisPerShare: 61.3,
    currentPrice: 68.75,
    ytdReturnPercent: 5.2,
  },
  {
    id: 'hold-schd',
    ticker: 'SCHD',
    name: 'Schwab US Dividend Equity ETF',
    quantity: 70,
    costBasisPerShare: 79.1,
    currentPrice: 84.25,
    ytdReturnPercent: -1.8,
  },
]

export const SEED_CASH_BALANCE = 28450
export const SEED_BONDS_BALANCE = 12300

/**
 * Snapshots for months before `CURRENT_SNAPSHOT_MONTH`. The current month's
 * point is computed live from holdings + cash + bonds, so imports move it.
 *
 * Net worth history predates the ledger start on purpose — snapshots and
 * transactions are independent records.
 */
export const SEED_NET_WORTH_HISTORY: NetWorthPoint[] = [
  { monthKey: '2026-01', total: 88420 },
  { monthKey: '2026-02', total: 90150 },
  { monthKey: '2026-03', total: 89280 },
  { monthKey: '2026-04', total: 93640 },
  { monthKey: '2026-05', total: 96910 },
  { monthKey: '2026-06', total: 99780 },
]

/**
 * Chase export category -> Custodian category id. The backend will hold this
 * in a configurable table; anything missing falls through to "Other" and is
 * flagged for review in the import preview.
 */
export const CHASE_CATEGORY_MAP: Record<string, string> = {
  'Bills & Utilities': 'cat-utilities',
  Groceries: 'cat-groceries',
  'Food & Drink': 'cat-dining',
  Travel: 'cat-transport',
  Gas: 'cat-transport',
  Automotive: 'cat-transport',
  Entertainment: 'cat-subscriptions',
  Shopping: 'cat-other',
  Health: 'cat-other',
  Rent: 'cat-rent',
}
