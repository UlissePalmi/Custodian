/**
 * One statement (income / balance / cash flow) as a dense, section-banded
 * grid matching the prototype: navy band rows for REVENUE/OPERATING
 * EXPENSES/PROFITABILITY etc., bold computed subtotals, +/- controls on the
 * first/last year column to extend or shrink the range. Historical (actual)
 * columns are read-only; projected columns are click-to-edit — the prototype
 * itself has no inline editing to copy (confirmed by testing it directly), so
 * this interaction is this component's own design.
 */

import { useState } from 'react'
import { Minus, Plus } from 'lucide-react'
import { upsertStockPeriod, deleteStockPeriod, type StockModel, type StockPeriod } from '../../api'
import {
  balanceSheetSubtotals,
  incomeStatementSubtotals,
  linkedEndingCash,
  cashFlowSubtotals,
} from '../../utils/dcf'
import { formatQuantity, formatUSD, formatUSDCompact } from '../../utils/money'

type StatementKey = 'incomeStatement' | 'balanceSheet' | 'cashFlow'
export type StatementId = 'income' | 'balance' | 'cashflow'

/** The "add an earlier year" control never goes back further than this. */
const MIN_HISTORICAL_YEAR = 2020

interface RowContext {
  period: StockPeriod
  resolvedCash: number
}

interface Row {
  key: string
  label: string
  kind: 'section' | 'line' | 'subtotal'
  indent?: boolean
  gold?: boolean
  field?: { statement: StatementKey; key: string }
  editableWhen?: (period: StockPeriod, isEarliest: boolean) => boolean
  value: (ctx: RowContext) => number | null
  format?: (value: number | null) => string
}

const money = (value: number | null) => (value == null ? '—' : formatUSDCompact(value))
const moneyPrecise = (value: number | null) => (value == null ? '—' : formatUSD(value))
const quantity = (value: number | null) => (value == null ? '—' : formatQuantity(value))
const percent = (value: number | null) => (value == null ? '—' : `${value.toFixed(1)}%`)

function incomeRows(): Row[] {
  return [
    { key: 'sec-revenue', label: 'Revenue', kind: 'section', value: () => null },
    {
      key: 'revenue',
      label: 'Revenue',
      kind: 'line',
      field: { statement: 'incomeStatement', key: 'revenue' },
      value: (c) => c.period.incomeStatement.revenue,
    },
    {
      key: 'costOfRevenue',
      label: 'Cost of Revenue',
      kind: 'line',
      indent: true,
      field: { statement: 'incomeStatement', key: 'costOfRevenue' },
      value: (c) => c.period.incomeStatement.costOfRevenue,
    },
    {
      key: 'grossProfit',
      label: 'Gross Profit',
      kind: 'subtotal',
      value: (c) => incomeStatementSubtotals(c.period.incomeStatement).grossProfit,
    },
    {
      key: 'grossMargin',
      label: 'Gross Margin %',
      kind: 'line',
      indent: true,
      value: (c) => {
        const revenue = c.period.incomeStatement.revenue
        if (!revenue) return null
        return (incomeStatementSubtotals(c.period.incomeStatement).grossProfit / revenue) * 100
      },
      format: percent,
    },
    { key: 'sec-opex', label: 'Operating Expenses', kind: 'section', value: () => null },
    {
      key: 'rd',
      label: 'Research and Development',
      kind: 'line',
      indent: true,
      field: { statement: 'incomeStatement', key: 'researchAndDevelopment' },
      value: (c) => c.period.incomeStatement.researchAndDevelopment,
    },
    {
      key: 'sm',
      label: 'Sales and Marketing',
      kind: 'line',
      indent: true,
      field: { statement: 'incomeStatement', key: 'salesAndMarketing' },
      value: (c) => c.period.incomeStatement.salesAndMarketing,
    },
    {
      key: 'ga',
      label: 'General and Administrative',
      kind: 'line',
      indent: true,
      field: { statement: 'incomeStatement', key: 'generalAndAdministrative' },
      value: (c) => c.period.incomeStatement.generalAndAdministrative,
    },
    {
      key: 'da',
      label: 'Depreciation and Amortization',
      kind: 'line',
      indent: true,
      field: { statement: 'incomeStatement', key: 'depreciationAmortization' },
      value: (c) => c.period.incomeStatement.depreciationAmortization,
    },
    {
      key: 'sbc',
      label: 'Stock-Based Compensation',
      kind: 'line',
      indent: true,
      field: { statement: 'incomeStatement', key: 'stockBasedComp' },
      value: (c) => c.period.incomeStatement.stockBasedComp,
    },
    { key: 'sec-profitability', label: 'Profitability', kind: 'section', value: () => null },
    {
      key: 'ebit',
      label: 'EBIT',
      kind: 'subtotal',
      value: (c) => incomeStatementSubtotals(c.period.incomeStatement).ebit,
    },
    {
      key: 'ebitda',
      label: 'EBITDA',
      kind: 'subtotal',
      gold: true,
      value: (c) => incomeStatementSubtotals(c.period.incomeStatement).ebitda,
    },
    {
      key: 'interestIncome',
      label: 'Interest Income',
      kind: 'line',
      indent: true,
      field: { statement: 'incomeStatement', key: 'interestIncome' },
      value: (c) => c.period.incomeStatement.interestIncome,
    },
    {
      key: 'interestExpense',
      label: 'Interest Expense',
      kind: 'line',
      indent: true,
      field: { statement: 'incomeStatement', key: 'interestExpense' },
      value: (c) => c.period.incomeStatement.interestExpense,
    },
    {
      key: 'pretax',
      label: 'Pre-tax Income',
      kind: 'subtotal',
      value: (c) => incomeStatementSubtotals(c.period.incomeStatement).pretaxIncome,
    },
    {
      key: 'incomeTax',
      label: 'Income Tax',
      kind: 'line',
      indent: true,
      field: { statement: 'incomeStatement', key: 'incomeTax' },
      value: (c) => c.period.incomeStatement.incomeTax,
    },
    {
      key: 'netIncome',
      label: 'Net Income',
      kind: 'subtotal',
      value: (c) => incomeStatementSubtotals(c.period.incomeStatement).netIncome,
    },
    {
      key: 'netMargin',
      label: 'Net Margin %',
      kind: 'line',
      indent: true,
      value: (c) => {
        const revenue = c.period.incomeStatement.revenue
        if (!revenue) return null
        return (incomeStatementSubtotals(c.period.incomeStatement).netIncome / revenue) * 100
      },
      format: percent,
    },
    {
      key: 'dilutedShares',
      label: 'Diluted Shares Outstanding',
      kind: 'line',
      indent: true,
      field: { statement: 'incomeStatement', key: 'dilutedShares' },
      value: (c) => c.period.incomeStatement.dilutedShares,
      format: quantity,
    },
    {
      key: 'eps',
      label: 'EPS (diluted)',
      kind: 'line',
      indent: true,
      value: (c) => {
        const shares = c.period.incomeStatement.dilutedShares
        if (!shares) return null
        return incomeStatementSubtotals(c.period.incomeStatement).netIncome / shares
      },
      format: moneyPrecise,
    },
  ]
}

function balanceRows(): Row[] {
  return [
    { key: 'sec-assets', label: 'Assets', kind: 'section', value: () => null },
    {
      key: 'cash',
      label: 'Cash and Equivalents',
      kind: 'line',
      field: { statement: 'balanceSheet', key: 'cash' },
      editableWhen: (_period, isEarliest) => isEarliest,
      value: (c) => c.resolvedCash,
    },
    {
      key: 'ar',
      label: 'Accounts Receivable',
      kind: 'line',
      indent: true,
      field: { statement: 'balanceSheet', key: 'accountsReceivable' },
      value: (c) => c.period.balanceSheet.accountsReceivable,
    },
    {
      key: 'otherCurrentAssets',
      label: 'Other Current Assets',
      kind: 'line',
      indent: true,
      field: { statement: 'balanceSheet', key: 'otherCurrentAssets' },
      value: (c) => c.period.balanceSheet.otherCurrentAssets,
    },
    {
      key: 'ppe',
      label: 'PP&E, net',
      kind: 'line',
      indent: true,
      field: { statement: 'balanceSheet', key: 'ppeNet' },
      value: (c) => c.period.balanceSheet.ppeNet,
    },
    {
      key: 'totalAssets',
      label: 'Total Assets',
      kind: 'subtotal',
      value: (c) => balanceSheetSubtotals(c.period.balanceSheet, c.resolvedCash).totalAssets,
    },
    { key: 'sec-liabilities', label: 'Liabilities', kind: 'section', value: () => null },
    {
      key: 'deferredRevenue',
      label: 'Deferred Revenue',
      kind: 'line',
      indent: true,
      field: { statement: 'balanceSheet', key: 'deferredRevenue' },
      value: (c) => c.period.balanceSheet.deferredRevenue,
    },
    {
      key: 'ap',
      label: 'Accounts Payable',
      kind: 'line',
      indent: true,
      field: { statement: 'balanceSheet', key: 'accountsPayable' },
      value: (c) => c.period.balanceSheet.accountsPayable,
    },
    {
      key: 'accrued',
      label: 'Accrued Liabilities',
      kind: 'line',
      indent: true,
      field: { statement: 'balanceSheet', key: 'accruedLiabilities' },
      value: (c) => c.period.balanceSheet.accruedLiabilities,
    },
    {
      key: 'longTermDebt',
      label: 'Long-Term Debt',
      kind: 'line',
      indent: true,
      field: { statement: 'balanceSheet', key: 'longTermDebt' },
      value: (c) => c.period.balanceSheet.longTermDebt,
    },
    {
      key: 'totalLiabilities',
      label: 'Total Liabilities',
      kind: 'subtotal',
      value: (c) => balanceSheetSubtotals(c.period.balanceSheet, c.resolvedCash).totalLiabilities,
    },
    { key: 'sec-equity', label: 'Equity', kind: 'section', value: () => null },
    {
      key: 'totalEquity',
      label: 'Total Equity',
      kind: 'subtotal',
      gold: true,
      value: (c) => balanceSheetSubtotals(c.period.balanceSheet, c.resolvedCash).totalEquity,
    },
  ]
}

function cashFlowRows(): Row[] {
  return [
    { key: 'sec-operating', label: 'Operating Activities', kind: 'section', value: () => null },
    {
      key: 'cfo',
      label: 'Cash from Operations',
      kind: 'line',
      field: { statement: 'cashFlow', key: 'cashFromOperations' },
      value: (c) => c.period.cashFlow.cashFromOperations,
    },
    { key: 'sec-investing', label: 'Investing Activities', kind: 'section', value: () => null },
    {
      key: 'capex',
      label: 'Capital Expenditures',
      kind: 'line',
      indent: true,
      field: { statement: 'cashFlow', key: 'capex' },
      value: (c) => (c.period.cashFlow.capex == null ? null : -c.period.cashFlow.capex),
    },
    {
      key: 'cfi',
      label: 'Cash from Investing',
      kind: 'subtotal',
      value: (c) => cashFlowSubtotals(c.period).cashFromInvesting,
    },
    { key: 'sec-financing', label: 'Financing Activities', kind: 'section', value: () => null },
    {
      key: 'cff',
      label: 'Cash from Financing',
      kind: 'line',
      field: { statement: 'cashFlow', key: 'cashFromFinancing' },
      value: (c) => c.period.cashFlow.cashFromFinancing,
    },
    { key: 'sec-summary', label: 'Summary', kind: 'section', value: () => null },
    {
      key: 'netChange',
      label: 'Net Change in Cash',
      kind: 'subtotal',
      value: (c) => cashFlowSubtotals(c.period).netChangeInCash,
    },
    {
      key: 'endingCash',
      label: 'Ending Cash Balance',
      kind: 'subtotal',
      gold: true,
      value: (c) => c.resolvedCash,
    },
  ]
}

const ROW_BUILDERS: Record<StatementId, () => Row[]> = {
  income: incomeRows,
  balance: balanceRows,
  cashflow: cashFlowRows,
}

const STATEMENT_TITLES: Record<StatementId, string> = {
  income: 'Income Statement',
  balance: 'Balance Sheet',
  cashflow: 'Cash Flow Statement',
}

function updatePeriodField(period: StockPeriod, statement: StatementKey, field: string, value: number | null): StockPeriod {
  return {
    ...period,
    [statement]: { ...(period[statement] as unknown as Record<string, number | null>), [field]: value },
  }
}

interface EditableCellProps {
  value: number | null
  format: (value: number | null) => string
  editable: boolean
  onCommit: (value: number | null) => void
}

function EditableCell({ value, format, editable, onCommit }: EditableCellProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')

  if (!editable) {
    return <span className="tnum">{format(value)}</span>
  }

  if (!editing) {
    return (
      <button
        type="button"
        className="tnum -mx-2 w-full rounded px-2 py-0.5 text-right hover:bg-terminal-gold/10"
        onClick={() => {
          setDraft(value == null ? '' : String(value))
          setEditing(true)
        }}
      >
        {format(value)}
      </button>
    )
  }

  function commit() {
    const trimmed = draft.trim()
    onCommit(trimmed === '' ? null : Number(trimmed))
    setEditing(false)
  }

  return (
    <input
      autoFocus
      type="number"
      inputMode="decimal"
      className="tnum w-full rounded border border-terminal-gold bg-white px-2 py-0.5 text-right outline-none"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') commit()
        if (e.key === 'Escape') setEditing(false)
      }}
    />
  )
}

interface StatementGridProps {
  model: StockModel
  statement: StatementId
  onChanged: () => void
}

export default function StatementGrid({ model, statement, onChanged }: StatementGridProps) {
  const periods = [...model.periods].sort((a, b) => a.year - b.year)
  const rows = ROW_BUILDERS[statement]()
  const cashByYear = linkedEndingCash(model)

  if (periods.length === 0) {
    return (
      <div className="rounded-lg border border-terminal-navy/10 bg-white p-6 text-sm text-slate-500 shadow-sm">
        No years added yet.
      </div>
    )
  }

  async function commitField(period: StockPeriod, field: { statement: StatementKey; key: string }, value: number | null) {
    await upsertStockPeriod(model.id, updatePeriodField(period, field.statement, field.key, value))
    onChanged()
  }

  async function addYear(direction: 'earlier' | 'later') {
    const edge = direction === 'earlier' ? periods[0] : periods[periods.length - 1]
    if (direction === 'earlier' && edge.year <= MIN_HISTORICAL_YEAR) return
    const year = direction === 'earlier' ? edge.year - 1 : edge.year + 1
    const newPeriod: StockPeriod = {
      year,
      isProjected: direction === 'later' ? true : edge.isProjected,
      incomeStatement: { ...edge.incomeStatement },
      balanceSheet: { ...edge.balanceSheet, cash: null },
      cashFlow: { ...edge.cashFlow },
    }
    await upsertStockPeriod(model.id, newPeriod)
    onChanged()
  }

  async function removeYear(direction: 'earlier' | 'later') {
    if (periods.length <= 1) return
    const edge = direction === 'earlier' ? periods[0] : periods[periods.length - 1]
    await deleteStockPeriod(model.id, edge.year)
    onChanged()
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-terminal-navy/10 bg-white shadow-sm">
      <table className="w-full min-w-max text-sm">
        <thead>
          <tr className="bg-terminal-navy">
            <th className="px-4 py-2 text-left text-xs font-semibold tracking-wide text-white uppercase">
              {STATEMENT_TITLES[statement]}
            </th>
            {periods.map((period, index) => {
              const isFirst = index === 0
              const isLast = index === periods.length - 1
              return (
                <th
                  key={period.year}
                  className={`px-4 py-2 text-right text-xs font-semibold ${
                    period.isProjected ? 'text-white' : 'text-slate-400'
                  }`}
                >
                  <span className="inline-flex items-center gap-1">
                    {isFirst && (
                      <>
                        <button
                          type="button"
                          aria-label="Add an earlier year"
                          onClick={() => addYear('earlier')}
                          disabled={period.year <= MIN_HISTORICAL_YEAR}
                          title={period.year <= MIN_HISTORICAL_YEAR ? `Can't go back further than ${MIN_HISTORICAL_YEAR}` : undefined}
                          className="rounded-full p-0.5 text-slate-400 hover:bg-white/10 hover:text-white disabled:pointer-events-none disabled:opacity-30"
                        >
                          <Plus className="size-3" aria-hidden />
                        </button>
                        {periods.length > 1 && (
                          <button
                            type="button"
                            aria-label="Remove this year"
                            onClick={() => removeYear('earlier')}
                            className="rounded-full p-0.5 text-slate-400 hover:bg-white/10 hover:text-white"
                          >
                            <Minus className="size-3" aria-hidden />
                          </button>
                        )}
                      </>
                    )}
                    <span>
                      {period.year}
                      {period.isProjected ? 'E' : 'A'}
                    </span>
                    {isLast && periods.length > 1 && (
                      <>
                        {isLast && (
                          <button
                            type="button"
                            aria-label="Remove this year"
                            onClick={() => removeYear('later')}
                            className="rounded-full p-0.5 text-slate-400 hover:bg-white/10 hover:text-white"
                          >
                            <Minus className="size-3" aria-hidden />
                          </button>
                        )}
                      </>
                    )}
                    {isLast && (
                      <button
                        type="button"
                        aria-label="Add a later year"
                        onClick={() => addYear('later')}
                        className="rounded-full p-0.5 text-slate-400 hover:bg-white/10 hover:text-white"
                      >
                        <Plus className="size-3" aria-hidden />
                      </button>
                    )}
                  </span>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            if (row.kind === 'section') {
              return (
                <tr key={row.key} className="bg-terminal-navy">
                  <td
                    colSpan={periods.length + 1}
                    className="px-4 py-1 text-[11px] font-semibold tracking-wide text-terminal-gold uppercase"
                  >
                    {row.label}
                  </td>
                </tr>
              )
            }

            const format = row.format ?? money
            return (
              <tr
                key={row.key}
                className={`border-b border-slate-100 last:border-0 ${row.kind === 'subtotal' ? 'font-semibold' : ''}`}
              >
                <td
                  className={`px-4 py-1.5 whitespace-nowrap ${row.indent ? 'pl-8 text-slate-600' : ''} ${
                    row.gold ? 'text-terminal-gold' : 'text-terminal-navy'
                  }`}
                >
                  {row.label}
                </td>
                {periods.map((period, index) => {
                  const resolvedCash = cashByYear.get(period.year) ?? 0
                  const ctx: RowContext = { period, resolvedCash }
                  const value = row.value(ctx)
                  const editable =
                    row.field != null && (row.editableWhen ? row.editableWhen(period, index === 0) : period.isProjected)

                  return (
                    <td key={period.year} className={`px-4 py-1.5 text-right ${row.gold ? 'text-terminal-gold' : 'text-terminal-navy'}`}>
                      {row.field ? (
                        <EditableCell
                          value={value}
                          format={format}
                          editable={editable}
                          onCommit={(next) => {
                            if (!row.field) return
                            void commitField(period, row.field, next)
                          }}
                        />
                      ) : (
                        <span className="tnum">{format(value)}</span>
                      )}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
