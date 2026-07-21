import type { ReactNode } from 'react'
import { AlertCircle, Loader2 } from 'lucide-react'
import { Button } from './Button'

export function Spinner({ className = '' }: { className?: string }) {
  return <Loader2 className={`animate-spin ${className}`} aria-hidden />
}

/** Full-panel loading state. `label` is announced to screen readers. */
export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div
      className="flex min-h-48 flex-col items-center justify-center gap-3 p-8 text-slate-400"
      role="status"
    >
      <Spinner className="size-6" />
      <span className="text-sm">{label}</span>
    </div>
  )
}

/** Grey placeholder block used inside cards while their data loads. */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-slate-200 dark:bg-slate-800 ${className}`} />
}

interface ErrorStateProps {
  error: Error
  onRetry?: () => void
}

export function ErrorState({ error, onRetry }: ErrorStateProps) {
  return (
    <div className="flex min-h-48 flex-col items-center justify-center gap-3 p-8 text-center">
      <AlertCircle className="size-6 text-rose-500" aria-hidden />
      <div>
        <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
          Something went wrong
        </p>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{error.message}</p>
      </div>
      {onRetry && (
        <Button size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center gap-2 p-8 text-center">
      {icon && <div className="text-slate-300 dark:text-slate-600">{icon}</div>}
      <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{title}</p>
      {description && (
        <p className="max-w-sm text-sm text-slate-500 dark:text-slate-400">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
