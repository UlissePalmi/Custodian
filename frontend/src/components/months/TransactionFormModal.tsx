import { useState, type FormEvent } from 'react'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { SelectField, TextField } from '../ui/Field'
import { Spinner } from '../ui/States'
import { useApi } from '../../hooks/useApi'
import {
  createTransaction,
  getCategories,
  updateTransaction,
  type CategoryKind,
  type Transaction,
} from '../../api'
import { daysInMonth, formatMonthLong, isoDateIn } from '../../utils/months'

interface TransactionFormModalProps {
  monthKey: string
  kind: CategoryKind
  /** Present when editing; absent when adding. */
  transaction?: Transaction
  onClose: () => void
  onSaved: () => void
}

export default function TransactionFormModal({
  monthKey,
  kind,
  transaction,
  onClose,
  onSaved,
}: TransactionFormModalProps) {
  const { data: categories } = useApi(getCategories, [])
  const options = (categories ?? []).filter((category) => category.kind === kind)

  const [date, setDate] = useState(transaction?.date ?? isoDateIn(monthKey, 1))
  const [amount, setAmount] = useState(transaction ? String(transaction.amount) : '')
  const [description, setDescription] = useState(transaction?.description ?? '')
  const [categoryId, setCategoryId] = useState(transaction?.categoryId ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Default to the first category once the list arrives.
  const resolvedCategoryId = categoryId || options[0]?.id || ''

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)

    const input = {
      date,
      amount: Number(amount),
      description,
      categoryId: resolvedCategoryId,
    }

    try {
      if (transaction) await updateTransaction(transaction.id, input)
      else await createTransaction(monthKey, input)
      onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save that entry.')
      setSaving(false)
    }
  }

  const noun = kind === 'income' ? 'income' : 'expense'

  return (
    <Modal
      open
      onClose={onClose}
      title={transaction ? `Edit ${noun}` : `Add ${noun}`}
      description={formatMonthLong(monthKey)}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="transaction-form" disabled={saving}>
            {saving && <Spinner className="size-4" />}
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </>
      }
    >
      <form id="transaction-form" onSubmit={handleSubmit} className="space-y-4">
        <SelectField
          id="txn-category"
          label="Category"
          value={resolvedCategoryId}
          onChange={(event) => setCategoryId(event.target.value)}
          required
        >
          {options.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </SelectField>

        <TextField
          id="txn-description"
          label="Description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder={kind === 'income' ? 'Paycheck' : 'Groceries'}
          required
        />

        <div className="grid grid-cols-2 gap-3">
          <TextField
            id="txn-date"
            label="Date"
            type="date"
            value={date}
            // Confine the picker to the month being edited.
            min={isoDateIn(monthKey, 1)}
            max={isoDateIn(monthKey, daysInMonth(monthKey))}
            onChange={(event) => setDate(event.target.value)}
            required
          />
          <TextField
            id="txn-amount"
            label="Amount (USD)"
            type="number"
            inputMode="decimal"
            step="0.01"
            min="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            placeholder="0.00"
            required
          />
        </div>

        {error && <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>}
      </form>
    </Modal>
  )
}
