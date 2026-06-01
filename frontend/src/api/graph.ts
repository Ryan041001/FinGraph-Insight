import { apiGet } from './client'
import type { CompanyProfile, CompanySearchResponse, GraphPayload } from './types'

export function getCompanyProfile(name: string) {
  return apiGet<CompanyProfile>(`/graph/company/${encodeURIComponent(name)}`)
}

export function getSubgraph(entity: string) {
  return apiGet<GraphPayload>(`/graph/subgraph?entity=${encodeURIComponent(entity)}`)
}

export function searchCompanies(query: string, limit = 8) {
  const params = new URLSearchParams({ q: query, limit: String(limit) })
  return apiGet<CompanySearchResponse>(`/graph/companies?${params.toString()}`)
}
