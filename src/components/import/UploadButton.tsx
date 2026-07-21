import { useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { Button } from '../ui/Button'
import { Spinner } from '../ui/States'
import ImportConfirmModal from './ImportConfirmModal'
import { uploadChaseFile, type ImportPreview, type ImportResult } from '../../api'

interface UploadButtonProps {
  /** Month the upload was started from, used as a hint when the file is ambiguous. */
  monthKey?: string
  /** Called after a successful confirm so the caller can refetch. */
  onImported?: (result: ImportResult) => void
  label?: string
  size?: 'sm' | 'md'
  variant?: 'primary' | 'secondary'
  className?: string
}

/**
 * Opens a file picker for a Chase export, parses it through the API layer,
 * then hands the preview to the confirmation modal.
 */
export default function UploadButton({
  monthKey,
  onImported,
  label = 'Import Chase file',
  size = 'md',
  variant = 'secondary',
  className = '',
}: UploadButtonProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [parsing, setParsing] = useState(false)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleFile(file: File) {
    setParsing(true)
    setError(null)
    try {
      setPreview(await uploadChaseFile(file, monthKey))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not read that file.')
    } finally {
      setParsing(false)
    }
  }

  return (
    <>
      <div className={className}>
        <Button
          variant={variant}
          size={size}
          className={className}
          disabled={parsing}
          onClick={() => inputRef.current?.click()}
        >
          {parsing ? <Spinner className="size-4" /> : <Upload className="size-4" aria-hidden />}
          {parsing ? 'Parsing…' : label}
        </Button>
        {error && <p className="mt-2 text-xs text-rose-600 dark:text-rose-400">{error}</p>}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xls,.xlsx"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0]
          // Reset so re-selecting the same file fires change again.
          event.target.value = ''
          if (file) void handleFile(file)
        }}
      />

      {preview && (
        <ImportConfirmModal
          preview={preview}
          onClose={() => setPreview(null)}
          onConfirmed={(result) => {
            setPreview(null)
            onImported?.(result)
          }}
        />
      )}
    </>
  )
}
