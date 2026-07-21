import { CalendarDays, LayoutDashboard, Table2, type LucideIcon } from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** Sub-routes that should keep this item highlighted (e.g. /months/2026-07). */
  matchPrefix?: string
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/months', label: 'Months', icon: CalendarDays, matchPrefix: '/months' },
  { to: '/yearly', label: 'Yearly Table', icon: Table2, matchPrefix: '/yearly' },
]

export function isNavItemActive(item: NavItem, pathname: string): boolean {
  if (item.matchPrefix) return pathname.startsWith(item.matchPrefix)
  return pathname === item.to
}
