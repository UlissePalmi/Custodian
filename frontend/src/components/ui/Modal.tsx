import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  /** Wider variant for the import preview table. */
  size?: 'md' | 'lg'
}

/**
 * Centred dialog on desktop, bottom sheet on mobile.
 * Closes on Escape and backdrop click; locks body scroll while open.
 *
 * Portaled to `document.body` rather than rendered in place: a page with its
 * own `position: sticky` + `z-index` elements (e.g. the yearly table's pinned
 * columns) can otherwise composite above this modal despite its higher
 * z-index, since sticky layers inside a scrolling ancestor aren't guaranteed
 * to stack correctly against a later, unrelated element's z-index.
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    // Move focus into the dialog so keyboard users start inside it.
    panelRef.current?.focus()

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <button
        type="button"
        className="absolute inset-0 bg-terminal-navy/50 backdrop-blur-sm"
        onClick={onClose}
        aria-label="Close dialog"
        tabIndex={-1}
      />
      <div
        ref={panelRef}
        tabIndex={-1}
        className={`relative flex max-h-[92vh] w-full flex-col rounded-t-2xl bg-white shadow-xl sm:rounded-2xl ${
          size === 'lg' ? 'sm:max-w-3xl' : 'sm:max-w-md'
        }`}
      >
        <header className="flex items-start justify-between gap-4 border-b border-terminal-navy/10 px-5 py-4">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-terminal-navy">{title}</h2>
            {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="-m-1 rounded-lg p-1 text-slate-400 transition-colors hover:bg-terminal-cream hover:text-terminal-navy"
            aria-label="Close"
          >
            <X className="size-5" aria-hidden />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>

        {footer && (
          <footer className="flex items-center justify-end gap-2 border-t border-terminal-navy/10 px-5 py-4 pb-safe sm:pb-4">
            {footer}
          </footer>
        )}
      </div>
    </div>,
    document.body,
  )
}
