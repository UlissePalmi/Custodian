/**
 * The app's only data-access entry point. Components import from here and
 * never from `./mock/*` directly.
 *
 * Swapping to the real backend:
 *   1. Add `./http/client.ts` exporting an object typed `CustodianApi` whose
 *      methods `fetch('/api/...')` and return the same shapes.
 *   2. Change the `api` binding below to point at it.
 * Nothing else in `src/` needs to change — that's the whole point of this file.
 */

import type { CustodianApi, ImportPreview, TransactionInput } from './types'
import { mockApi } from './mock/client'

export const api: CustodianApi = mockApi

export const getNetWorth = () => api.getNetWorth()
export const getHoldings = () => api.getHoldings()
export const getCategories = () => api.getCategories()
export const getMonths = () => api.getMonths()
export const getMonth = (year: number, month: number) => api.getMonth(year, month)
export const getYearlyTable = (year: number) => api.getYearlyTable(year)

export const createTransaction = (monthKey: string, input: TransactionInput) =>
  api.createTransaction(monthKey, input)
export const updateTransaction = (id: string, input: TransactionInput) =>
  api.updateTransaction(id, input)
export const deleteTransaction = (id: string) => api.deleteTransaction(id)

export const uploadChaseFile = (file: File, hintMonthKey?: string) =>
  api.uploadChaseFile(file, hintMonthKey)
export const confirmImport = (preview: ImportPreview) => api.confirmImport(preview)

export { resetStore } from './mock/store'
export * from './types'
