import { apiPost } from './client'

export function extractText(text: string) {
  return apiPost<Record<string, unknown>>('/extract', { text })
}

export function importGraph(payload: unknown) {
  return apiPost<Record<string, unknown>>('/graph/import', payload)
}
