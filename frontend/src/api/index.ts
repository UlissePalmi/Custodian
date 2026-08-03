/**
 * The app's only data-access entry point. Components import from here and
 * never from `./mock/*` directly.
 *
 * Talks to the FastAPI backend over `/api`. Set `VITE_USE_MOCK=true` to run
 * against the in-memory mock instead — useful for front-end work without the
 * backend or database running.
 */

import type { CustodianApi, ImportPreview, StockModelInput, StockPeriod, TransactionInput } from './types'
import { mockApi } from './mock/client'
import { httpApi } from './http/client'

export const api: CustodianApi = import.meta.env.VITE_USE_MOCK === 'true' ? mockApi : httpApi

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

export const getStockModels = () => api.getStockModels()
export const getStockModel = (id: string) => api.getStockModel(id)
export const createStockModel = (input: StockModelInput) => api.createStockModel(input)
export const updateStockModel = (id: string, input: StockModelInput) => api.updateStockModel(id, input)
export const deleteStockModel = (id: string) => api.deleteStockModel(id)
export const upsertStockPeriod = (stockModelId: string, period: StockPeriod) =>
  api.upsertStockPeriod(stockModelId, period)
export const deleteStockPeriod = (stockModelId: string, year: number) =>
  api.deleteStockPeriod(stockModelId, year)

export { resetStore } from './mock/store'
export * from './types'
