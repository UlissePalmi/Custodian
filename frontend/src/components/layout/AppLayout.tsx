import { Link, Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import BottomNav from './BottomNav'
import ConnectBankButton from '../plaid/ConnectBankButton'
import { DataVersionProvider, useDataVersion } from '../../context/DataVersion'

function Shell() {
  const { invalidate } = useDataVersion()

  return (
    <div className="min-h-dvh bg-terminal-cream">
      <Sidebar onImported={invalidate} />

      {/* Mobile header — the app name lives here since there is no sidebar.
          Import is deliberately not repeated here: it is a month-scoped action
          and both the Months index and each month page carry their own button.
          Connect Chase isn't month-scoped, so unlike Import it has no other
          mobile home — it gets a compact icon-only slot here instead. */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-white/10 bg-terminal-navy px-4 py-3 lg:hidden">
        <Link to="/" className="font-terminal-serif text-base font-bold text-white">
          Custodian
        </Link>
        <ConnectBankButton compact />
      </header>

      {/* Every page renders its own navy header band flush against this edge,
          then manages its own padding — there is no shared padded/max-width
          wrapper, so each page reaches the full width of the content column
          the way the stock detail page's terminal look always has. */}
      <main className="lg:pl-60">
        <Outlet />
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
