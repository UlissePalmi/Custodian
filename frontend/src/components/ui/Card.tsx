import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'

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
  /** Makes the title a link to this route, with a chevron so it reads as one.
   *  Narrower than accepting a ReactNode title: every existing call site keeps
   *  passing a plain string and renders exactly as before. */
  titleTo?: string
}

export function CardHeader({ title, subtitle, action, titleTo }: CardHeaderProps) {
  const heading = (
    <h2 className="text-sm font-semibold tracking-wide text-terminal-navy uppercase">{title}</h2>
  )

  return (
    <header className="flex items-start justify-between gap-4 border-b border-terminal-navy/10 px-5 py-4">
      <div className="min-w-0">
        {titleTo ? (
          <Link
            to={titleTo}
            className="group inline-flex items-center gap-1 rounded transition-colors hover:text-terminal-gold"
          >
            {heading}
            <ChevronRight
              className="size-4 shrink-0 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:text-terminal-gold"
              aria-hidden
            />
          </Link>
        ) : (
          heading
        )}
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  )
}

export function CardBody({ children, className = '' }: CardProps) {
  return <div className={`p-5 ${className}`}>{children}</div>
}
