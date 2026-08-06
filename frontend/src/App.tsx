import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import DashboardPage from './pages/DashboardPage'
import AllocationPage from './pages/AllocationPage'
import MonthsPage from './pages/MonthsPage'
import MonthDetailPage from './pages/MonthDetailPage'
import YearlyTablePage from './pages/YearlyTablePage'
import StocksPage from './pages/StocksPage'
import StockModelPage from './pages/StockModelPage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<DashboardPage />} />
        {/* Reached from the dashboard's Asset allocation card, not the nav —
            a sixth bottom-nav item would crowd the phone layout. */}
        <Route path="/allocation" element={<AllocationPage />} />
        <Route path="/months" element={<MonthsPage />} />
        <Route path="/months/:monthKey" element={<MonthDetailPage />} />
        <Route path="/yearly" element={<YearlyTablePage />} />
        <Route path="/stocks" element={<StocksPage />} />
        <Route path="/stocks/:id" element={<StockModelPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
