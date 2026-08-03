import { useState, type FormEvent } from 'react'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { TextField } from '../ui/Field'
import { Spinner } from '../ui/States'
import { createStockModel } from '../../api'

interface AddStockModalProps {
  onClose: () => void
  onSaved: () => void
}

export default function AddStockModal({ onClose, onSaved }: AddStockModalProps) {
  const [ticker, setTicker] = useState('')
  const [name, setName] = useState('')
  const [notes, setNotes] = useState('')
  const [exchange, setExchange] = useState('')
  const [sector, setSector] = useState('')
  const [waccPercent, setWaccPercent] = useState('9')
  const [terminalGrowthPercent, setTerminalGrowthPercent] = useState('3')
  const [taxRatePercent, setTaxRatePercent] = useState('21')
  const [netDebt, setNetDebt] = useState('0')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)

    try {
      await createStockModel({
        ticker,
        name,
        notes: notes || undefined,
        exchange: exchange || undefined,
        sector: sector || undefined,
        waccPercent: Number(waccPercent),
        terminalGrowthPercent: Number(terminalGrowthPercent),
        taxRatePercent: Number(taxRatePercent),
        netDebt: Number(netDebt),
      })
      onSaved()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add that stock.')
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Track a stock"
      description="Held or research-only — either works."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="add-stock-form" disabled={saving}>
            {saving && <Spinner className="size-4" />}
            {saving ? 'Adding…' : 'Add stock'}
          </Button>
        </>
      }
    >
      <form id="add-stock-form" onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <TextField
            id="stock-ticker"
            label="Ticker"
            value={ticker}
            onChange={(event) => setTicker(event.target.value.toUpperCase())}
            placeholder="DUOL"
            required
          />
          <TextField
            id="stock-name"
            label="Company name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Duolingo, Inc."
            required
          />
        </div>

        <TextField
          id="stock-notes"
          label="Notes (optional)"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Why you're tracking it"
        />

        <div className="grid grid-cols-2 gap-3">
          <TextField
            id="stock-exchange"
            label="Exchange (optional)"
            value={exchange}
            onChange={(event) => setExchange(event.target.value.toUpperCase())}
            placeholder="NASDAQ"
          />
          <TextField
            id="stock-sector"
            label="Sector (optional)"
            value={sector}
            onChange={(event) => setSector(event.target.value)}
            placeholder="EdTech"
          />
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <TextField
            id="stock-wacc"
            label="WACC (%)"
            type="number"
            inputMode="decimal"
            step="0.1"
            value={waccPercent}
            onChange={(event) => setWaccPercent(event.target.value)}
            required
          />
          <TextField
            id="stock-terminal-growth"
            label="Terminal growth (%)"
            type="number"
            inputMode="decimal"
            step="0.1"
            value={terminalGrowthPercent}
            onChange={(event) => setTerminalGrowthPercent(event.target.value)}
            required
          />
          <TextField
            id="stock-tax-rate"
            label="Tax rate (%)"
            type="number"
            inputMode="decimal"
            step="0.1"
            value={taxRatePercent}
            onChange={(event) => setTaxRatePercent(event.target.value)}
            required
          />
          <TextField
            id="stock-net-debt"
            label="Net debt ($M)"
            type="number"
            inputMode="decimal"
            step="1"
            value={netDebt}
            onChange={(event) => setNetDebt(event.target.value)}
            required
          />
        </div>

        <p className="text-xs text-slate-500">
          Statement years get added on the next screen — this just creates the model.
        </p>

        {error && <p className="text-sm text-rose-600">{error}</p>}
      </form>
    </Modal>
  )
}
