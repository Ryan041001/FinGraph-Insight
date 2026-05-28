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
}
