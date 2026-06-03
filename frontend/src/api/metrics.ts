import { apiGet } from './client'
import type { ExtractionMetrics } from './types'

export function getExtractionMetrics() {
  return apiGet<ExtractionMetrics>('/metrics/extraction')
}
