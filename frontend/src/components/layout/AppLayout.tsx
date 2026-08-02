import { Link, Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import BottomNav from './BottomNav'
import { DataVersionProvider, useDataVersion } from '../../context/DataVersion'

function Shell() {
  const { invalidate } = useDataVersion()

  return (
    <div className="min-h-dvh">
      <Sidebar onImported={invalidate} />

      {/* Mobile header — the app name lives here since there is no sidebar.
          Import is deliberately not repeated here: it is a month-scoped action
          and both the Months index and each month page carry their own button. */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur-sm lg:hidden dark:border-slate-800 dark:bg-slate-900/95">
        <Link to="/" className="text-base font-semibold tracking-tight">
          Custodian
        </Link>
      </header>

      <main className="lg:pl-60">
        {/* Bottom padding clears the fixed mobile nav. */}
        <div className="mx-auto w-full max-w-6xl px-4 py-6 pb-28 sm:px-6 lg:px-8 lg:py-8 lg:pb-8">
          <Outlet />
        </div>
      </main>

      <BottomNav />
    </div>
  )
}

export default function AppLayout() {
  return (
    <DataVersionProvider>
      <Shell />
    </DataVersionProvider>
  )
}
