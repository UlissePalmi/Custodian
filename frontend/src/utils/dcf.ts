/**
 * 3-statement subtotals and DCF valuation, computed from a `StockModel`'s raw
 * inputs. Pure functions, no I/O — this is the mock's twin of the (not yet
 * built) `backend/app/services/dcf.py`, same duplication-on-purpose pattern as
 * `months.ts`/`months.py`. Nothing here is persisted; a stored model's numbers
 * are recomputed on every read.
 */

import type {
  BalanceSheetInputs,
  DcfResult,
  DcfYearProjection,
  IncomeStatementInputs,
  SensitivityGrid,
  StockModel,
  StockPeriod,
} from '../api/types'
import { roundCents } from './money'

const n = (value: number | null): number => value ?? 0

// ---------------------------------------------------------------------------
// Statement subtotals
// ---------------------------------------------------------------------------

export interface IncomeStatementSubtotals {
  grossProfit: number
  ebitda: number
  ebit: number
  pretaxIncome: number
  netIncome: number
}

export function incomeStatementSubtotals(inputs: IncomeStatementInputs): IncomeStatementSubtotals {
  const grossProfit = n(inputs.revenue) - n(inputs.costOfRevenue)
  const totalOpex =
    n(inputs.researchAndDevelopment) +
    n(inputs.salesAndMarketing) +
    n(inputs.generalAndAdministrative) +
    n(inputs.depreciationAmortization) +
    n(inputs.stockBasedComp)
  const ebit = grossProfit - totalOpex
  const ebitda = ebit + n(inputs.depreciationAmortization)
  const pretaxIncome = ebit - n(inputs.interestExpense) + n(inputs.interestIncome)
  const netIncome = pretaxIncome - n(inputs.incomeTax)
  return { grossProfit, ebitda, ebit, pretaxIncome, netIncome }
}

export interface BalanceSheetSubtotals {
  totalAssets: number
  totalLiabilities: number
  totalEquity: number
}

/** `resolvedCash` comes from `linkedEndingCash` — balance-sheet cash is never a
 *  raw input past a model's earliest period. */
export function balanceSheetSubtotals(inputs: BalanceSheetInputs, resolvedCash: number): BalanceSheetSubtotals {
  const totalAssets = resolvedCash + n(inputs.accountsReceivable) + n(inputs.otherCurrentAssets) + n(inputs.ppeNet)
  const totalLiabilities =
    n(inputs.deferredRevenue) + n(inputs.accountsPayable) + n(inputs.accruedLiabilities) + n(inputs.longTermDebt)
  return { totalAssets, totalLiabilities, totalEquity: totalAssets - totalLiabilities }
}

function sortedByYear(periods: StockPeriod[]): StockPeriod[] {
  return [...periods].sort((a, b) => a.year - b.year)
}

export interface CashFlowSubtotals {
  cashFromInvesting: number
  netChangeInCash: number
}

export function cashFlowSubtotals(period: StockPeriod): CashFlowSubtotals {
  const cashFromInvesting = -n(period.cashFlow.capex)
  const netChangeInCash = n(period.cashFlow.cashFromOperations) + cashFromInvesting + n(period.cashFlow.cashFromFinancing)
  return { cashFromInvesting, netChangeInCash }
}

/**
 * Each period's ending cash balance, linked year over year: the earliest
 * period's `balanceSheet.cash` is the only raw anchor, every later period is
 * `previous ending cash + this period's net change in cash` — so the balance
 * sheet's cash line always ties to the cash flow statement, the way the
 * prototype's does.
 */
export function linkedEndingCash(model: Pick<StockModel, 'periods'>): Map<number, number> {
  const sorted = sortedByYear(model.periods)
  const byYear = new Map<number, number>()
  let running = 0
  sorted.forEach((period, index) => {
    running = index === 0 ? n(period.balanceSheet.cash) : running + cashFlowSubtotals(period).netChangeInCash
    byYear.set(period.year, running)
  })
  return byYear
}

/**
 * Unlevered free cash flow for one period: EBIT after tax (at the model's
 * assumed rate, not the period's own tax line — that's the DCF convention),
 * plus D&A back out, less capex, plus/minus the period's working-capital swing.
 */
export function freeCashFlow(period: StockPeriod, taxRatePercent: number): number {
  const { ebit } = incomeStatementSubtotals(period.incomeStatement)
  const afterTax = ebit * (1 - taxRatePercent / 100)
  return (
    afterTax +
    n(period.incomeStatement.depreciationAmortization) -
    n(period.cashFlow.capex) +
    n(period.cashFlow.changeInWorkingCapital)
  )
}

// ---------------------------------------------------------------------------
// DCF Model tab build table
// ---------------------------------------------------------------------------

export interface DcfBuildRow {
  year: number
  isProjected: boolean
  revenue: number
  revenueGrowthPercent: number | null
  ebitda: number
  ebitdaMarginPercent: number | null
  ebitdaGrowthPercent: number | null
  netIncome: number
  netIncomeMarginPercent: number | null
  netIncomeGrowthPercent: number | null
  /** EBIT after tax at the model's assumed rate — the DCF's starting point. */
  ebiat: number
  ebiatGrowthPercent: number | null
  depreciationAmortization: number
  capex: number
  changeInWorkingCapital: number
  unleveredFcf: number
  /** Null for actual years — only projected years get discounted. */
  discountPeriod: number | null
  discountFactor: number | null
  presentValue: number | null
}

function percentChange(current: number, previous: number): number | null {
  if (previous === 0) return null
  return roundCents(((current - previous) / previous) * 100)
}

export function dcfBuildRows(model: StockModel): DcfBuildRow[] {
  const sorted = sortedByYear(model.periods)
  const wacc = model.waccPercent / 100
  let projectedIndex = 0

  return sorted.map((period, index) => {
    const { ebitda, ebit, netIncome } = incomeStatementSubtotals(period.incomeStatement)
    const revenue = n(period.incomeStatement.revenue)
    const ebiat = ebit * (1 - model.taxRatePercent / 100)
    const depreciationAmortization = n(period.incomeStatement.depreciationAmortization)
    const capex = n(period.cashFlow.capex)
    const changeInWorkingCapital = n(period.cashFlow.changeInWorkingCapital)
    const unleveredFcf = freeCashFlow(period, model.taxRatePercent)

    const previous = index > 0 ? sorted[index - 1] : undefined
    const previousSubtotals = previous ? incomeStatementSubtotals(previous.incomeStatement) : undefined
    const previousEbiat = previous ? previousSubtotals!.ebit * (1 - model.taxRatePercent / 100) : undefined

    let discountPeriod: number | null = null
    let discountFactor: number | null = null
    let presentValue: number | null = null
    if (period.isProjected) {
      projectedIndex += 1
      discountPeriod = projectedIndex
      discountFactor = 1 / (1 + wacc) ** projectedIndex
      presentValue = roundCents(unleveredFcf * discountFactor)
    }

    return {
      year: period.year,
      isProjected: period.isProjected,
      revenue,
      revenueGrowthPercent: previous ? percentChange(revenue, n(previous.incomeStatement.revenue)) : null,
      ebitda,
      ebitdaMarginPercent: revenue !== 0 ? roundCents((ebitda / revenue) * 100) : null,
      ebitdaGrowthPercent: previous ? percentChange(ebitda, previousSubtotals!.ebitda) : null,
      netIncome,
      netIncomeMarginPercent: revenue !== 0 ? roundCents((netIncome / revenue) * 100) : null,
      netIncomeGrowthPercent: previous ? percentChange(netIncome, previousSubtotals!.netIncome) : null,
      ebiat,
      ebiatGrowthPercent: previous ? percentChange(ebiat, previousEbiat!) : null,
      depreciationAmortization,
      capex,
      changeInWorkingCapital,
      unleveredFcf: roundCents(unleveredFcf),
      discountPeriod,
      discountFactor,
      presentValue,
    }
  })
}

// ---------------------------------------------------------------------------
// DCF
// ---------------------------------------------------------------------------

export function latestDilutedShares(periods: StockPeriod[]): number | null {
  for (const period of sortedByYear(periods).reverse()) {
    if (period.incomeStatement.dilutedShares != null) {
      return period.incomeStatement.dilutedShares
    }
  }
  return null
}

/**
 * Fair value per share for one WACC/terminal-growth pair, or null if the pair
 * is invalid (WACC must exceed terminal growth or the perpetuity blows up).
 */
function fairValueFor(
  model: Pick<StockModel, 'periods' | 'taxRatePercent' | 'netDebt'>,
  waccPercent: number,
  terminalGrowthPercent: number,
): number | null {
  if (waccPercent <= terminalGrowthPercent) return null

  const projected = sortedByYear(model.periods.filter((p) => p.isProjected))
  if (projected.length === 0) return null

  const wacc = waccPercent / 100
  const growth = terminalGrowthPercent / 100

  let presentValueSum = 0
  let lastFcf = 0
  projected.forEach((period, index) => {
    const fcf = freeCashFlow(period, model.taxRatePercent)
    const discountFactor = 1 / (1 + wacc) ** (index + 1)
    presentValueSum += fcf * discountFactor
    lastFcf = fcf
  })

  const terminalValue = (lastFcf * (1 + growth)) / (wacc - growth)
  const presentValueOfTerminalValue = terminalValue / (1 + wacc) ** projected.length
  const enterpriseValue = presentValueSum + presentValueOfTerminalValue
  const equityValue = enterpriseValue - model.netDebt

  const shares = latestDilutedShares(model.periods)
  if (!shares || shares <= 0) return null
  return equityValue / shares
}

export function computeDcf(model: StockModel): DcfResult {
  const projected = sortedByYear(model.periods.filter((p) => p.isProjected))
  const wacc = model.waccPercent / 100
  const growth = model.terminalGrowthPercent / 100

  const projections: DcfYearProjection[] = projected.map((period, index) => {
    const fcf = freeCashFlow(period, model.taxRatePercent)
    const discountFactor = 1 / (1 + wacc) ** (index + 1)
    return {
      year: period.year,
      freeCashFlow: roundCents(fcf),
      discountFactor,
      presentValue: roundCents(fcf * discountFactor),
    }
  })

  const lastFcf = projections.length > 0 ? projections[projections.length - 1].freeCashFlow : 0
  const valid = model.waccPercent > model.terminalGrowthPercent && projections.length > 0

  const terminalValue = valid ? (lastFcf * (1 + growth)) / (wacc - growth) : 0
  const presentValueOfTerminalValue = valid ? terminalValue / (1 + wacc) ** projections.length : 0
  const presentValueSum = projections.reduce((sum, p) => sum + p.presentValue, 0)
  const enterpriseValue = presentValueSum + presentValueOfTerminalValue
  const equityValue = enterpriseValue - model.netDebt

  const shares = latestDilutedShares(model.periods)
  const fairValuePerShare = valid && shares && shares > 0 ? roundCents(equityValue / shares) : null

  const upsidePercent =
    fairValuePerShare != null && model.currentPrice
      ? roundCents(((fairValuePerShare - model.currentPrice) / model.currentPrice) * 100)
      : null

  return {
    projections,
    terminalValue: roundCents(terminalValue),
    presentValueOfTerminalValue: roundCents(presentValueOfTerminalValue),
    enterpriseValue: roundCents(enterpriseValue),
    netDebt: roundCents(model.netDebt),
    equityValue: roundCents(equityValue),
    fairValuePerShare,
    currentPrice: model.currentPrice,
    upsidePercent,
  }
}

// ---------------------------------------------------------------------------
// Sensitivity
// ---------------------------------------------------------------------------

const WACC_STEP_OFFSETS = [-2, -1, 0, 1, 2]
const GROWTH_STEP_OFFSETS = [-1, -0.5, 0, 0.5, 1]

export function computeSensitivityGrid(model: StockModel): SensitivityGrid {
  const waccPercentSteps = WACC_STEP_OFFSETS.map((offset) => roundCents(model.waccPercent + offset))
  const terminalGrowthPercentSteps = GROWTH_STEP_OFFSETS.map((offset) =>
    roundCents(model.terminalGrowthPercent + offset),
  )

  const fairValuePerShare = waccPercentSteps.map((wacc) =>
    terminalGrowthPercentSteps.map((growth) => {
      const value = fairValueFor(model, wacc, growth)
      return value == null ? null : roundCents(value)
    }),
  )

  return { waccPercentSteps, terminalGrowthPercentSteps, fairValuePerShare }
}
