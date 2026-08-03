import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ChevronLeft, Trash2 } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { useDataVersion } from '../context/DataVersion'
import { deleteStockModel, getStockModel } from '../api'
import { Card } from '../components/ui/Card'
import { ErrorState, LoadingState } from '../components/ui/States'
import DcfModelTab from '../components/stocks/DcfModelTab'
import ThreeStatementTab from '../components/stocks/ThreeStatementTab'
import SensitivityTab from '../components/stocks/SensitivityTab'

type TabId = 'dcf' | 'statements' | 'sensitivity'

const TABS: Array<{ id: TabId; label: string }> = [
  { id: 'dcf', label: 'DCF Model' },
  { id: 'statements', label: '3-Statement Model' },
  { id: 'sensitivity', label: 'Sensitivity' },
]

/**
 * This page originated the app's "analyst terminal" look — navy/cream/gold,
 * serif headline type, matching the Claude-designed prototype (`Duolingo DCF
 * Model (Standalone).html`) — since adopted everywhere. Unlike other pages it
 * has its own tabbed navy header (not the shared `PageHeader`) since it needs
 * tabs and per-stock stats, not just a title. `pb-28 lg:pb-8` supplies the
 * bottom clearance for the fixed mobile bottom nav, same as `PageBody`.
 */
export default function StockModelPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const { version, invalidate } = useDataVersion()
  const { data: model, loading, error, refetch } = useApi(() => getStockModel(id), [id, version])
  const [tab, setTab] = useState<TabId>('dcf')

  async function handleDelete() {
    if (!model) return
    if (!window.confirm(`Stop tracking ${model.ticker}? This removes its whole model.`)) return
    await deleteStockModel(model.id)
    invalidate()
    navigate('/stocks')
  }

  if (error) {
    return (
      <Card>
        <ErrorState error={error} onRetry={refetch} />
      </Card>
    )
  }

  // Only the *first* load blanks the page — a refetch after an edit (e.g. a
  // statement-grid cell commit) keeps the current tab showing stale data
  // rather than flashing a full-page spinner on every keystroke's commit.
  if (!model) {
    return (
      <Card>
        <LoadingState label={loading ? 'Loading model…' : 'Stock model not found.'} />
      </Card>
    )
  }

  return (
    <div className="pb-28 lg:pb-8">
      <div className="bg-terminal-navy">
        <div className="flex items-center gap-1 px-4 pt-3 sm:px-6 lg:px-8">
          <button
            type="button"
            onClick={() => navigate('/stocks')}
            aria-label="Back to Stocks"
            className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
          >
            <ChevronLeft className="size-3.5" aria-hidden />
            Stocks
          </button>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 px-4 pb-1 sm:px-6 lg:px-8">
          <span className="font-terminal-serif text-xl font-bold tracking-wide text-white">
            {model.ticker}
          </span>
          <div className="flex items-center gap-4">
            <nav className="flex">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTab(t.id)}
                  className={`border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                    tab === t.id
                      ? 'border-terminal-gold text-white'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </nav>
            <button
              type="button"
              onClick={handleDelete}
              aria-label="Stop tracking"
              title="Stop tracking"
              className="inline-flex size-8 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
            >
              <Trash2 className="size-4" aria-hidden />
            </button>
          </div>
        </div>
      </div>

      {tab === 'dcf' && <DcfModelTab model={model} />}
      {tab === 'statements' && (
        <div className="px-4 py-6 sm:px-6 lg:px-8">
          <ThreeStatementTab model={model} onChanged={refetch} />
        </div>
      )}
      {tab === 'sensitivity' && (
        <div className="px-4 py-6 sm:px-6 lg:px-8">
          <SensitivityTab model={model} />
        </div>
      )}
    </div>
  )
}
