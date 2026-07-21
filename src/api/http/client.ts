/**
 * HTTP client for the FastAPI backend.
 *
 * Implements the same `CustodianApi` interface as the mock, so the two are
 * interchangeable at the binding in `../index.ts`. The backend runs as a
 * separate service on its own port, so these are cross-origin requests — see
 * `VITE_API_BASE_URL` in the repo root `.env`, and the matching CORS setting
 * on the backend.
 */

import {
  ApiError,
  type Category,
  type CustodianApi,
  type Holding,
  type ImportPreview,
  type ImportResult,
  type MonthInfo,
  type MonthLedger,
  type NetWorthSummary,
  type Transaction,
  type TransactionInput,
  type YearlyTable,
} from '../types'
import { toMonthKey } from '../../utils/months'

const BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

/** Pulls the backend's `{"detail": "..."}` message out of a failed response. */
async function errorFrom(response: Response): Promise<ApiError> {
  let message = response.statusText || 'Request failed.'
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') message = body.detail
  } catch {
    // Non-JSON error body (a proxy or gateway page) — keep the status text.
  }
  return new ApiError(message, response.status)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, init)
  } catch {
    // The Pi is unreachable — a distinct case from an error the API returned.
    throw new ApiError('Cannot reach Custodian. Is the server running?', 0)
  }

  if (!response.ok) throw await errorFrom(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

function jsonRequest<T>(path: string, method: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export const httpApi: CustodianApi = {
  getNetWorth: () => request<NetWorthSummary>('/networth'),

  getHoldings: () => request<Holding[]>('/holdings'),

  getCategories: () => request<Category[]>('/categories'),

  getMonths: () => request<MonthInfo[]>('/months'),

  getMonth: (year: number, month: number) =>
    request<MonthLedger>(`/months/${toMonthKey(year, month)}`),

  createTransaction: (monthKey: string, input: TransactionInput) =>
    jsonRequest<Transaction>(`/months/${monthKey}/transactions`, 'POST', input),

  updateTransaction: (id: string, input: TransactionInput) =>
    jsonRequest<Transaction>(`/transactions/${encodeURIComponent(id)}`, 'PUT', input),

  deleteTransaction: (id: string) =>
    request<void>(`/transactions/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  getYearlyTable: (year: number) => request<YearlyTable>(`/yearly-table?year=${year}`),

  uploadChaseFile: (file: File, hintMonthKey?: string) => {
    const form = new FormData()
    form.append('file', file)
    if (hintMonthKey) form.append('hintMonthKey', hintMonthKey)
    // No Content-Type header: the browser sets it with the multipart boundary.
    return request<ImportPreview>('/import/chase', { method: 'POST', body: form })
  },

  confirmImport: (preview: ImportPreview) =>
    jsonRequest<ImportResult>('/import/chase/confirm', 'POST', preview),
}
