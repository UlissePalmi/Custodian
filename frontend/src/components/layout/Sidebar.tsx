import { Link, useLocation } from 'react-router-dom'
import { NAV_ITEMS, isNavItemActive } from './navItems'
import UploadButton from '../import/UploadButton'

/** Persistent left navigation, desktop only (>= lg). */
export default function Sidebar({ onImported }: { onImported?: () => void }) {
  const { pathname } = useLocation()

  return (
    <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col bg-terminal-navy lg:flex">
      <div className="px-6 py-6">
        <Link to="/" className="font-terminal-serif text-lg font-bold tracking-tight text-white">
          Custodian
        </Link>
        <p className="mt-0.5 text-xs text-slate-400">Wealth management</p>
      </div>

      <nav className="flex-1 px-3">
        <ul className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const active = isNavItemActive(item, pathname)
            const Icon = item.icon
            return (
              <li key={item.to}>
                <Link
                  to={item.to}
                  aria-current={active ? 'page' : undefined}
                  className={`flex items-center gap-3 rounded-lg border-l-2 px-3 py-2 text-sm font-medium transition-colors ${
                    active
                      ? 'border-terminal-gold bg-terminal-navy-light text-white'
                      : 'border-transparent text-slate-400 hover:bg-terminal-navy-light hover:text-white'
                  }`}
                >
                  <Icon className="size-4.5 shrink-0" aria-hidden />
                  {item.label}
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

      <div className="border-t border-white/10 p-3">
        <UploadButton onImported={onImported} className="w-full" />
      </div>
    </aside>
  )
}
