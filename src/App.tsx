import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import DashboardPage from './pages/DashboardPage'
import MonthsPage from './pages/MonthsPage'
import MonthDetailPage from './pages/MonthDetailPage'
import YearlyTablePage from './pages/YearlyTablePage'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/months" element={<MonthsPage />} />
        <Route path="/months/:monthKey" element={<MonthDetailPage />} />
        <Route path="/yearly" element={<YearlyTablePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
