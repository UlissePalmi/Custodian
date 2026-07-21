import { useMemo, useState } from 'react'
import { AlertTriangle, Check } from 'lucide-react'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { InlineSelect } from '../ui/Field'
import { Amount } from '../ui/Amount'
import { Spinner } from '../ui/States'
import { useApi } from '../../hooks/useApi'
import { getCategories, confirmImport, type ImportPreview, type ImportResult } from '../../api'
import { formatDayShort, formatMonthLong } from '../../utils/months'
import { roundCents } from '../../utils/money'

interface ImportConfirmModalProps {
  preview: ImportPreview
  onClose: () => void
  onConfirmed: (result: ImportResult) => void
}

/**
 * Review step for a parsed Chase file. Every row's category is editable and
 * rows can be excluded before anything is written to the ledger.
 */
export default function ImportConfirmModal({
  preview,
  onClose,
  onConfirmed,
}: ImportConfirmModalProps) {
  const { data: categories } = useApi(getCategories, [])
  const [rows, setRows] = useState(preview.transactions)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const included = rows.filter((row) => row.include)

  const cashDelta = useMemo(
    () =>
      roundCents(
        included.reduce((sum, row) => sum + (row.kind === 'income' ? row.amount : -row.amount), 0),
      ),
    [included],
  )

  const flaggedCount = included.filter((row) => row.flaggedForReview).length

  function updateRow(id: string, patch: Partial<(typeof rows)[number]>) {
    setRows((current) => current.map((row) => (row.id === id ? { ...row, ...patch } : row)))
  }

  async function handleConfirm() {
    setSubmitting(true)
    setError(null)
    try {
      onConfirmed(await confirmImport({ ...preview, transactions: rows }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed.')
      setSubmitting(false)
    }
  }

  const monthLabel = formatMonthLong(preview.detectedMonthKey)

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={`Are these all your transactions for ${monthLabel}?`}
      description={`Parsed ${preview.transactions.length} rows from ${preview.fileName}. Adjust categories or uncheck anything that shouldn't be imported.`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleConfirm} disabled={submitting || included.length === 0}>
            {submitting ? <Spinner className="size-4" /> : <Check className="size-4" aria-hidden />}
            {submitting ? 'Importing…' : `Import ${included.length}`}
          </Button>
        </>
      }
    >
      {flaggedCount > 0 && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2.5 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <p>
            {flaggedCount} {flaggedCount === 1 ? 'transaction' : 'transactions'} had no category
            mapping and defaulted to <strong>Other</strong>. Review the highlighted rows.
          </p>
        </div>
      )}

      <ul className="space-y-2">
        {rows.map((row) => (
          <li
            key={row.id}
            className={`rounded-lg border px-3 py-2.5 transition-opacity ${
              row.include ? '' : 'opacity-45'
            } ${
              row.flaggedForReview && row.include
                ? 'border-amber-300 bg-amber-50/60 dark:border-amber-800/70 dark:bg-amber-950/20'
                : 'border-slate-200 dark:border-slate-800'
            }`}
          >
            <div className="flex items-start gap-3">
              <input
                type="checkbox"
                checked={row.include}
                onChange={(event) => updateRow(row.id, { include: event.target.checked })}
                className="mt-1 size-4 shrink-0 rounded border-slate-300 accent-slate-900 dark:accent-slate-100"
                aria-label={`Include ${row.description}`}
              />

              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">
                      {row.description}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                      {formatDayShort(row.date)} · Chase: {row.chaseCategory || '—'}
                    </p>
                  </div>
                  <Amount
                    value={row.kind === 'income' ? row.amount : -row.amount}
                    signed
                    className="shrink-0 text-sm font-medium"
                  />
                </div>

                <div className="mt-2 max-w-64">
                  <InlineSelect
                    value={row.categoryId}
                    disabled={!row.include}
                    aria-label={`Category for ${row.description}`}
                    onChange={(event) =>
                      updateRow(row.id, {
                        categoryId: event.target.value,
                        // Choosing a category by hand clears the review flag.
                        flaggedForReview: false,
                      })
                    }
                  >
                    {(categories ?? [])
                      .filter((category) => category.kind === row.kind)
                      .map((category) => (
                        <option key={category.id} value={category.id}>
                          {category.name}
                        </option>
                      ))}
                  </InlineSelect>
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>

      <div className="mt-4 rounded-lg bg-slate-50 px-3 py-3 text-sm dark:bg-slate-800/50">
        <div className="flex items-center justify-between">
          <span className="text-slate-600 dark:text-slate-400">Cash impact on net worth</span>
          <Amount value={cashDelta} signed className="font-semibold" />
        </div>
        <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
          Confirming writes these entries to {monthLabel} and applies this delta to your cash
          balance, updating net worth.
        </p>
      </div>

      {error && <p className="mt-3 text-sm text-rose-600 dark:text-rose-400">{error}</p>}
    </Modal>
  )
}
