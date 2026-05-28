import type { GraphPayload } from '../api/types'

export type RiskLevel = 'low' | 'medium' | 'high' | 'unknown'

export interface ProductCompany {
  id: string
  name: string
  industry: string
  legalRepresentative: string
  tags: string[]
}

export interface RiskFactor {
  id: string
  level: RiskLevel
  title: string
  description: string
  relationIds: string[]
}

export interface RiskSummary {
  level: RiskLevel
  score: number
  summary: string
  factors: RiskFactor[]
}

export interface EvidenceItem {
  id: string
  relationId: string
  title: string
  text: string
  source: string
  confidence: number
  date: string
}

export interface RelationPath {
  id: string
  label: string
  relationIds: string[]
  riskLevel: RiskLevel
}

export interface RiskWorkbenchModel {
  company: ProductCompany
  risk: RiskSummary
  graph: GraphPayload
  evidence: EvidenceItem[]
  paths: RelationPath[]
}

export interface WatchlistItem {
  companyName: string
  industry: string
  riskLevel: RiskLevel
  summary: string
  updatedAt: string
}

export interface DueDiligenceReport {
  id: string
  companyName: string
  riskLevel: RiskLevel
  summary: string
  factors: ReportRiskFactor[]
  evidence: ReportEvidenceItem[]
  createdAt: string
}

export interface ReportRiskFactor {
  level: RiskLevel
  title: string
  description: string
}

export interface ReportEvidenceItem {
  title: string
  text: string
  source: string
  confidence: number
  date: string
}
