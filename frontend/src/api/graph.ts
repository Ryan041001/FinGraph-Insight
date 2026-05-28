import { apiGet } from './client'
import type { CompanyProfile, GraphPayload } from './types'

export function getCompanyProfile(name: string) {
  return apiGet<CompanyProfile>(`/graph/company/${encodeURIComponent(name)}`)
}

export function getSubgraph(entity: string) {
  return apiGet<GraphPayload>(`/graph/subgraph?entity=${encodeURIComponent(entity)}`)
}
