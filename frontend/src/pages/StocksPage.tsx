import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, TrendingDown, TrendingUp } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import { useDataVersion } from '../context/DataVersion'
import { getStockModels, type StockModel } from '../api'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { EmptyState, ErrorState, Skeleton } from '../components/ui/States'
import { PageBody, PageHeader } from '../components/ui/PageHeader'
import AddStockModal from '../components/stocks/AddStockModal'
import { computeDcf } from '../utils/dcf'
import { formatPercentSigned, formatUSD, signColor } from '../utils/money'

function StockTile({ model }: { model: StockModel }) {
  const dcf = computeDcf(model)

  return (
    <Link
      to={`/stocks/${model.id}`}
      className="flex flex-col gap-3 rounded-xl border border-terminal-navy/10 bg-white p-4 shadow-sm transition-colors hover:border-terminal-navy/25"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <span className="font-terminal-serif text-sm font-bold text-terminal-navy">
            {model.ticker}
          </span>
          <p className="truncate text-xs text-slate-500">{model.name}</p>
        </div>
        {model.currentPrice != null && (
          <span className="tnum shrink-0 text-sm font-medium text-terminal-navy">
            {formatUSD(model.currentPrice)}
          </span>
        )}
      </div>

      <div className="flex items-end justify-between gap-3 border-t border-terminal-navy/10 pt-3">
        <div>
          <p className="text-xs text-slate-400">Fair value</p>
          <span className="tnum text-sm font-medium text-terminal-gold">
            {dcf.fairValuePerShare != null ? formatUSD(dcf.fairValuePerShare) : '—'}
          </span>
        </div>
        {dcf.upsidePercent != null && (
          <div className={`flex items-center gap-1 text-sm font-medium ${signColor(dcf.upsidePercent)}`}>
            {dcf.upsidePercent >= 0 ? (
              <TrendingUp className="size-4" aria-hidden />
            ) : (
              <TrendingDown className="size-4" aria-hidden />
            )}
            <span className="tnum">{formatPercentSigned(dcf.upsidePercent)}</span>
          </div>
        )}
      </div>
    </Link>
  )
}

export default function StocksPage() {
  const { version, invalidate } = useDataVersion()
  const { data, loading, error, refetch } = useApi(getStockModels, [version])
  const [adding, setAdding] = useState(false)

  return (
    <>
      <PageHeader
        eyebrow="Research"
        title="Stocks"
        subtitle="3-statement models and DCF valuations — held positions and research."
        action={
          <Button variant="primary" onClick={() => setAdding(true)}>
            <Plus className="size-4" aria-hidden />
            Add stock
          </Button>
        }
      />
      <PageBody>
        {error ? (
          <Card>
            <ErrorState error={error} onRetry={refetch} />
          </Card>
        ) : loading || !data ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-32 w-full rounded-xl" />
            ))}
          </div>
        ) : data.length === 0 ? (
          <Card>
            <EmptyState
              title="No stocks tracked yet"
              description="Add a ticker to start a 3-statement model and DCF for it."
              action={
                <Button variant="primary" onClick={() => setAdding(true)}>
                  <Plus className="size-4" aria-hidden />
                  Add stock
                </Button>
              }
            />
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.map((model) => (
              <StockTile key={model.id} model={model} />
            ))}
          </div>
        )}

        {adding && (
          <AddStockModal
            onClose={() => setAdding(false)}
            onSaved={() => {
              setAdding(false)
              invalidate()
            }}
          />
        )}
      </PageBody>
    </>
  )
}
