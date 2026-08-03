import { useState } from 'react'
import type { StockModel } from '../../api/types'
import StatementGrid, { type StatementId } from './StatementGrid'

const SUB_TABS: Array<{ id: StatementId; label: string }> = [
  { id: 'income', label: 'Income Statement' },
  { id: 'balance', label: 'Balance Sheet' },
  { id: 'cashflow', label: 'Cash Flow' },
]

export default function ThreeStatementTab({ model, onChanged }: { model: StockModel; onChanged: () => void }) {
  const [sub, setSub] = useState<StatementId>('income')

  return (
    <div className="space-y-4">
      <div className="flex gap-6 border-b border-terminal-navy/10">
        {SUB_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setSub(t.id)}
            className={`-mb-px border-b-2 px-1 py-2 text-sm font-medium transition-colors ${
              sub === t.id
                ? 'border-terminal-gold text-terminal-navy'
                : 'border-transparent text-slate-400 hover:text-slate-600'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <StatementGrid model={model} statement={sub} onChanged={onChanged} />
    </div>
  )
}
