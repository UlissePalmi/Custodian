import { useState } from 'react'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { Card, CardHeader } from '../ui/Card'
import { Button } from '../ui/Button'
import { Amount } from '../ui/Amount'
import { EmptyState } from '../ui/States'
import TransactionFormModal from './TransactionFormModal'
import { deleteTransaction, type CategoryKind, type Transaction } from '../../api'
import { formatDayShort } from '../../utils/months'
import { formatUSD } from '../../utils/money'

interface TransactionListProps {
  monthKey: string
  kind: CategoryKind
  transactions: Transaction[]
  total: number
  onChanged: () => void
}

export default function TransactionList({
  monthKey,
  kind,
  transactions,
  total,
  onChanged,
}: TransactionListProps) {
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState<Transaction | null>(null)
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const title = kind === 'income' ? 'Income' : 'Expenses'

  async function handleDelete(id: string) {
    setDeletingId(id)
    try {
      await deleteTransaction(id)
      onChanged()
    } finally {
      setDeletingId(null)
      setConfirmingDelete(null)
    }
  }

  return (
    <>
      {/* min-w-0 lets the card shrink below its content's min-content width,
          which otherwise pushes past the grid track on narrow screens. */}
      <Card className="flex min-w-0 flex-col">
        <CardHeader
          title={title}
          subtitle={
            <span className="tnum">
              {formatUSD(total)} · {transactions.length}{' '}
              {transactions.length === 1 ? 'entry' : 'entries'}
            </span>
          }
          action={
            <Button size="sm" onClick={() => setAdding(true)}>
              <Plus className="size-4" aria-hidden />
              Add
            </Button>
          }
        />

        {transactions.length === 0 ? (
          <EmptyState
            title={`No ${title.toLowerCase()} yet`}
            description={`Entries you add for this month will be listed here.`}
            action={
              <Button size="sm" onClick={() => setAdding(true)}>
                <Plus className="size-4" aria-hidden />
                Add {kind === 'income' ? 'income' : 'expense'}
              </Button>
            }
          />
        ) : (
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {transactions.map((transaction) => (
              <li key={transaction.id} className="group px-5 py-3">
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-900 dark:text-slate-100">
                      {transaction.description}
                    </p>
                    <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-slate-500 dark:text-slate-400">
                      <span>{transaction.categoryName}</span>
                      <span aria-hidden>·</span>
                      <span>{formatDayShort(transaction.date)}</span>
                      {transaction.source === 'chase_import' && (
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                          Imported
                        </span>
                      )}
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center gap-1">
                    <span className="tnum text-sm font-medium text-slate-900 dark:text-slate-100">
                      {formatUSD(transaction.amount)}
                    </span>
                    <div className="flex opacity-100 transition-opacity lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-within:opacity-100">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="px-1.5"
                        onClick={() => setEditing(transaction)}
                        aria-label={`Edit ${transaction.description}`}
                      >
                        <Pencil className="size-3.5" aria-hidden />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="px-1.5"
                        onClick={() => setConfirmingDelete(transaction.id)}
                        aria-label={`Delete ${transaction.description}`}
                      >
                        <Trash2 className="size-3.5" aria-hidden />
                      </Button>
                    </div>
                  </div>
                </div>

                {confirmingDelete === transaction.id && (
                  <div className="mt-2 flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/60">
                    <span className="text-xs text-slate-600 dark:text-slate-300">
                      Delete this entry?
                    </span>
                    <span className="flex gap-1.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setConfirmingDelete(null)}
                        disabled={deletingId === transaction.id}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => void handleDelete(transaction.id)}
                        disabled={deletingId === transaction.id}
                      >
                        {deletingId === transaction.id ? 'Deleting…' : 'Delete'}
                      </Button>
                    </span>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}

        {transactions.length > 0 && (
          <footer className="mt-auto flex items-center justify-between border-t border-slate-200 px-5 py-3 text-sm dark:border-slate-800">
            <span className="font-medium text-slate-600 dark:text-slate-400">Total</span>
            <Amount value={total} className="font-semibold" />
          </footer>
        )}
      </Card>

      {adding && (
        <TransactionFormModal
          monthKey={monthKey}
          kind={kind}
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false)
            onChanged()
          }}
        />
      )}

      {editing && (
        <TransactionFormModal
          monthKey={monthKey}
          kind={kind}
          transaction={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            onChanged()
          }}
        />
      )}
    </>
  )
}
