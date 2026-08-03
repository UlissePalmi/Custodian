import type { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
}

export function Card({ children, className = '' }: CardProps) {
  return (
    <section className={`rounded-2xl border border-terminal-navy/10 bg-white shadow-sm ${className}`}>
      {children}
    </section>
  )
}

interface CardHeaderProps {
  title: string
  subtitle?: ReactNode
  action?: ReactNode
}

export function CardHeader({ title, subtitle, action }: CardHeaderProps) {
  return (
    <header className="flex items-start justify-between gap-4 border-b border-terminal-navy/10 px-5 py-4">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold tracking-wide text-terminal-navy uppercase">{title}</h2>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  )
}

export function CardBody({ children, className = '' }: CardProps) {
  return <div className={`p-5 ${className}`}>{children}</div>
}
