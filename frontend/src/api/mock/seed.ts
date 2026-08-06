/**
 * Seed data for the mock API.
 *
 * Numbers are chosen to be internally consistent: net worth is derived from
 * holdings + cash + bonds rather than hardcoded, so a Chase import that moves
 * cash also moves the dashboard total.
 */

import type { Category, Holding, NetWorthPoint, StockModel, StockPeriod, Transaction } from '../types'

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
// ---------------------------------------------------------------------------
// Stock models (3-statement + DCF)
// ---------------------------------------------------------------------------

/**
 * Fixed operating/balance-sheet ratios (percent of revenue, unless noted) used
 * to fabricate a full, internally-consistent statement grid for one company
 * across several years from just a revenue path. Real historicals will come
 * from a data pull once the backend exists; this is a stand-in. Flat
 * percent-of-revenue ratios mean margins hold constant year over year — the
 * same simplification the prototype itself uses (its EBITDA margin is flat
 * across every projected year too).
 */
interface CompanyProfile {
  grossMarginPercent: number
  researchAndDevelopmentPercent: number
  salesAndMarketingPercent: number
  generalAndAdministrativePercent: number
  daPercent: number
  sbcPercent: number
  interestIncomePercent: number
  interestExpensePercent: number
  taxRateOnPretaxPercent: number
  accountsReceivablePercent: number
  otherCurrentAssetsPercent: number
  ppePercent: number
  deferredRevenuePercent: number
  accountsPayablePercent: number
  accruedLiabilitiesPercent: number
  longTermDebt: number
  capexPercent: number
  /** Positive = net source of cash (e.g. growing deferred revenue). */
  changeInWorkingCapitalPercent: number
  /** Negative = net cash out (buybacks, dividends). */
  cashFromFinancingPercent: number
  /** Anchors the earliest period's balance-sheet cash; every later period
   *  computes cash from the cash-flow chain instead (see `linkedEndingCash`). */
  startingCashPercent: number
}

interface YearPlan {
  year: number
  isProjected: boolean
  revenue: number
  dilutedShares: number
}

const pct = (base: number, percent: number) => Math.round((base * percent) / 100)

function buildPeriods(years: YearPlan[], profile: CompanyProfile): StockPeriod[] {
  return years.map(({ year, isProjected, revenue, dilutedShares }, index) => {
    const costOfRevenue = revenue - pct(revenue, profile.grossMarginPercent)
    const researchAndDevelopment = pct(revenue, profile.researchAndDevelopmentPercent)
    const salesAndMarketing = pct(revenue, profile.salesAndMarketingPercent)
    const generalAndAdministrative = pct(revenue, profile.generalAndAdministrativePercent)
    const depreciationAmortization = pct(revenue, profile.daPercent)
    const stockBasedComp = pct(revenue, profile.sbcPercent)
    const interestIncome = pct(revenue, profile.interestIncomePercent)
    const interestExpense = pct(revenue, profile.interestExpensePercent)

    const grossProfit = revenue - costOfRevenue
    const ebit =
      grossProfit -
      researchAndDevelopment -
      salesAndMarketing -
      generalAndAdministrative -
      depreciationAmortization -
      stockBasedComp
    const pretaxIncome = ebit - interestExpense + interestIncome
    const incomeTax = Math.max(0, pct(pretaxIncome, profile.taxRateOnPretaxPercent))
    const netIncome = pretaxIncome - incomeTax

    const changeInWorkingCapital = pct(revenue, profile.changeInWorkingCapitalPercent)
    const capex = pct(revenue, profile.capexPercent)
    const cashFromOperations = netIncome + depreciationAmortization + stockBasedComp + changeInWorkingCapital
    const cashFromFinancing = pct(revenue, profile.cashFromFinancingPercent)

    return {
      year,
      isProjected,
      incomeStatement: {
        revenue,
        costOfRevenue,
        researchAndDevelopment,
        salesAndMarketing,
        generalAndAdministrative,
        depreciationAmortization,
        stockBasedComp,
        interestIncome,
        interestExpense,
        incomeTax,
        dilutedShares,
      },
      balanceSheet: {
        cash: index === 0 ? pct(revenue, profile.startingCashPercent) : null,
        accountsReceivable: pct(revenue, profile.accountsReceivablePercent),
        otherCurrentAssets: pct(revenue, profile.otherCurrentAssetsPercent),
        ppeNet: pct(revenue, profile.ppePercent),
        deferredRevenue: pct(revenue, profile.deferredRevenuePercent),
        accountsPayable: pct(revenue, profile.accountsPayablePercent),
        accruedLiabilities: pct(revenue, profile.accruedLiabilitiesPercent),
        longTermDebt: profile.longTermDebt,
      },
      cashFlow: {
        cashFromOperations,
        capex,
        cashFromFinancing,
        changeInWorkingCapital,
      },
    }
  })
}

const DUOL_PROFILE: CompanyProfile = {
  grossMarginPercent: 72,
  researchAndDevelopmentPercent: 17,
  salesAndMarketingPercent: 18,
  generalAndAdministrativePercent: 12,
  daPercent: 2.5,
  sbcPercent: 9,
  interestIncomePercent: 2,
  interestExpensePercent: 0,
  taxRateOnPretaxPercent: 22,
  accountsReceivablePercent: 3,
  otherCurrentAssetsPercent: 2,
  ppePercent: 4,
  deferredRevenuePercent: 12,
  accountsPayablePercent: 3,
  accruedLiabilitiesPercent: 3,
  longTermDebt: 0,
  capexPercent: 3,
  changeInWorkingCapitalPercent: 2,
  cashFromFinancingPercent: -1,
  startingCashPercent: 40,
}

// Historical revenue (2022A-2024A) and growth-rate path (2025E-2031E, 30% down
// to 10%) both match the prototype; the resulting figures are the same for the
// parts that are internally consistent to reproduce (revenue), not the parts
// that weren't (the prototype's own EBIT/net income don't tie to its stated
// opex ratios, so those are this seed's own consistent numbers instead).
const DUOL_YEARS: YearPlan[] = [
  { year: 2022, isProjected: false, revenue: 369, dilutedShares: 40 },
  { year: 2023, isProjected: false, revenue: 531, dilutedShares: 41 },
  { year: 2024, isProjected: false, revenue: 748, dilutedShares: 42 },
  { year: 2025, isProjected: true, revenue: 972, dilutedShares: 43 },
  { year: 2026, isProjected: true, revenue: 1216, dilutedShares: 44 },
  { year: 2027, isProjected: true, revenue: 1483, dilutedShares: 45 },
  { year: 2028, isProjected: true, revenue: 1750, dilutedShares: 46 },
  { year: 2029, isProjected: true, revenue: 2012, dilutedShares: 47 },
  { year: 2030, isProjected: true, revenue: 2254, dilutedShares: 48 },
  { year: 2031, isProjected: true, revenue: 2479, dilutedShares: 49 },
]

const AAPL_PROFILE: CompanyProfile = {
  grossMarginPercent: 45,
  researchAndDevelopmentPercent: 8,
  salesAndMarketingPercent: 5,
  generalAndAdministrativePercent: 2,
  daPercent: 2.7,
  sbcPercent: 3,
  interestIncomePercent: 1.5,
  interestExpensePercent: 0.8,
  taxRateOnPretaxPercent: 15,
  accountsReceivablePercent: 4,
  otherCurrentAssetsPercent: 3,
  ppePercent: 9,
  deferredRevenuePercent: 3,
  accountsPayablePercent: 15,
  accruedLiabilitiesPercent: 8,
  longTermDebt: 95000,
  capexPercent: 3,
  changeInWorkingCapitalPercent: -1,
  cashFromFinancingPercent: -12,
  startingCashPercent: 5,
}

const AAPL_YEARS: YearPlan[] = [
  { year: 2022, isProjected: false, revenue: 365000, dilutedShares: 16000 },
  { year: 2023, isProjected: false, revenue: 383000, dilutedShares: 15700 },
  { year: 2024, isProjected: false, revenue: 400000, dilutedShares: 15400 },
  { year: 2025, isProjected: true, revenue: 416000, dilutedShares: 15100 },
  { year: 2026, isProjected: true, revenue: 433000, dilutedShares: 14800 },
  { year: 2027, isProjected: true, revenue: 450000, dilutedShares: 14500 },
  { year: 2028, isProjected: true, revenue: 468000, dilutedShares: 14200 },
  { year: 2029, isProjected: true, revenue: 487000, dilutedShares: 13900 },
  { year: 2030, isProjected: true, revenue: 507000, dilutedShares: 13600 },
  { year: 2031, isProjected: true, revenue: 527000, dilutedShares: 13300 },
]

export const SEED_STOCK_MODELS: StockModel[] = [
  {
    id: 'stock-duol',
    ticker: 'DUOL',
    name: 'Duolingo, Inc.',
    notes: 'Research only — not currently held. Watching engagement and pricing power.',
    exchange: 'NASDAQ',
    sector: 'EdTech',
    waccPercent: 11,
    terminalGrowthPercent: 3,
    taxRatePercent: 22,
    netDebt: -650,
    currentPrice: 185.4,
    quoteAsOf: null,
    periods: buildPeriods(DUOL_YEARS, DUOL_PROFILE),
  },
  {
    id: 'stock-aapl',
    ticker: 'AAPL',
    name: 'Apple Inc.',
    notes: 'Existing core holding — tracking services mix and buyback pace.',
    exchange: 'NASDAQ',
    sector: 'Technology',
    waccPercent: 8,
    terminalGrowthPercent: 2.5,
    taxRatePercent: 15,
    netDebt: 15000,
    currentPrice: SEED_HOLDINGS.find((h) => h.ticker === 'AAPL')!.currentPrice,
    quoteAsOf: null,
    periods: buildPeriods(AAPL_YEARS, AAPL_PROFILE),
  },
]
