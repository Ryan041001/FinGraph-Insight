import { apiPost } from './client'
import type { ExtractionPayload, GraphImportResponse } from './types'

export interface ExtractOptions {
  self_refine?: boolean
  judge?: boolean
  mock?: boolean
}

export function extractText(text: string, options: ExtractOptions = { self_refine: false, judge: false, mock: false }) {
  return apiPost<ExtractionPayload>('/extract', { text, options })
}

export function importGraph(payload: unknown) {
  return apiPost<GraphImportResponse>('/graph/import', payload)
}
