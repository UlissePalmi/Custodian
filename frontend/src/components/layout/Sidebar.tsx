import { Link, useLocation } from 'react-router-dom'
import { NAV_ITEMS, isNavItemActive } from './navItems'
import UploadButton from '../import/UploadButton'

/** Persistent left navigation, desktop only (>= lg). */
export default function Sidebar({ onImported }: { onImported?: () => void }) {
  const { pathname } = useLocation()

  return (
    <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r border-slate-200 bg-white lg:flex dark:border-slate-800 dark:bg-slate-900">
      <div className="px-6 py-6">
        <Link to="/" className="text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Custodian
        </Link>
        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">Wealth management</p>
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
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    active
                      ? 'bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-100'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/60 dark:hover:text-slate-100'
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

      <div className="border-t border-slate-200 p-3 dark:border-slate-800">
        <UploadButton onImported={onImported} className="w-full" />
      </div>
    </aside>
  )
}
