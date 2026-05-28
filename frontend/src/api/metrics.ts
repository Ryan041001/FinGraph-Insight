import { apiGet } from './client'

export function getExtractionMetrics() {
  return apiGet<Record<string, number>>('/metrics/extraction')
}
