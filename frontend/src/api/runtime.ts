import { apiGet, apiPost } from './client'
import type { DatasetImportResponse, HealthResponse, PreloadState } from './types'

export function getHealth() {
  return apiGet<HealthResponse>('/health')
}

export function getPreloadState() {
  return apiGet<PreloadState>('/preload')
}

export function importFinancialDataset() {
  return apiPost<DatasetImportResponse>('/datasets/import', { dataset: 'financial_datasets' })
}
