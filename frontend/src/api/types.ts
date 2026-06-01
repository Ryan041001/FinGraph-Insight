export interface GraphNode {
  id: string
  label: string
  type: string
  properties: Record<string, unknown>
  risk_level: string
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
  label: string
  confidence: number
  status: string
  properties: Record<string, unknown>
  provenance: Record<string, unknown>
}

export interface GraphPayload {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface CompanyProfile {
  company: Record<string, unknown>
  profile: Record<string, unknown>
  graph: GraphPayload
  found?: boolean
}

export interface CompanySearchItem {
  id: string
  name: string
  industry: string
}

export interface CompanySearchResponse {
  query: string
  total: number
  companies: CompanySearchItem[]
}

export interface HealthResponse {
  status: string
  neo4j: string
  scheduler: string
}

export interface PreloadState {
  dataset_status: 'skipped' | 'running' | 'ready' | 'failed'
  dataset_started_at: string | null
  dataset_finished_at: string | null
  dataset_nodes: number
  dataset_relationships: number
  akshare_status: string
  akshare_job_run_id: string | null
  error: string | null
}

export interface DatasetImportResponse {
  import_run_id: string
  nodes_created: number
  relationships_created: number
  nodes_skipped: number
  relationships_skipped: number
  status: string
}

export interface ExtractionEntity {
  temp_id?: string
  name: string
  type: string
  resolved_id?: string
  resolved_name?: string
  normalized_name?: string
  resolution_match_type?: string
  resolution_confidence?: number
  evidence?: string
}

export interface ExtractionRelationship {
  temp_id?: string
  head_temp_id?: string
  relation: string
  tail_temp_id?: string
  attributes?: Record<string, unknown>
  evidence?: string
  confidence?: number
  status?: string
}

export interface ExtractionPayload {
  document?: Record<string, unknown>
  entities: ExtractionEntity[]
  relationships: ExtractionRelationship[]
  warnings?: string[]
}

export interface GraphImportResponse {
  nodes_created: number
  nodes_matched: number
  relationships_created: number
  relationships_skipped: number
  status: string
}

export interface Text2CypherResponse {
  cypher: string
  safety: Record<string, unknown>
  table: {
    columns: string[]
    rows: unknown[]
  }
  graph: GraphPayload
  note?: string
}

export interface GraphRagResponse {
  answer?: string
  entities?: string[]
  supporting_graph?: GraphPayload
  citations?: unknown[]
  document_context?: unknown[]
  retrieval?: Record<string, unknown>
  [key: string]: unknown
}

export interface JobRun {
  job_run_id: string
  status: 'running' | 'success' | 'failed'
  started_at: string
  finished_at: string | null
  new_documents: number
  new_entities: number
  new_relationships: number
  failed_items: number
}

export interface JobListResponse {
  jobs: JobRun[]
}

export interface ExtractionMetrics {
  sample_count: number
  entity_precision: number
  entity_recall: number
  entity_f1: number
  relation_precision: number
  relation_recall: number
  relation_f1: number
  hallucination_rate: number
  effective_import_rate: number
}
