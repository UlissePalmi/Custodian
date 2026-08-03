import type { ReactNode } from 'react'

interface PageHeaderProps {
  eyebrow?: string
  title: string
  subtitle?: ReactNode
  action?: ReactNode
}

/**
 * Navy header band every page opens with — eyebrow label, serif title,
 * optional subtitle and right-aligned action — matching the stock detail
 * page's terminal look. Sits flush against `AppLayout`'s sidebar/top edge, so
 * pages render this first, before any padded content.
 */
export function PageHeader({ eyebrow, title, subtitle, action }: PageHeaderProps) {
  return (
    <div className="bg-terminal-navy px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          {eyebrow && (
            <p className="text-xs font-semibold tracking-widest text-terminal-gold uppercase">{eyebrow}</p>
          )}
          <h1 className={`font-terminal-serif text-3xl font-bold text-white ${eyebrow ? 'mt-1' : ''}`}>
            {title}
          </h1>
          {subtitle && <p className="mt-1 text-sm text-slate-400">{subtitle}</p>}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
    </div>
  )
}

/** Padded content area below a `PageHeader` — bottom padding clears the fixed
 *  mobile nav, matching what `AppLayout`'s old shared wrapper used to provide. */
export function PageBody({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`space-y-6 px-4 py-6 pb-28 sm:px-6 lg:px-8 lg:pb-8 ${className}`}>{children}</div>
  )
}
