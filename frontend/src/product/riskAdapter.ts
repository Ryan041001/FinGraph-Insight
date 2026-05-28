import type { CompanyProfile, GraphEdge, GraphNode } from '../api/types'
import type { EvidenceItem, ProductCompany, RelationPath, RiskFactor, RiskLevel, RiskWorkbenchModel } from './types'

const WEAK_CONFIDENCE_THRESHOLD = 0.65
// Conservative high-risk relation allowlist. Benign types like NO_RISK are intentionally excluded.
const HIGH_RISK_EDGE_TYPES = new Set(['risk_event'])
const READABLE_EVIDENCE_SOURCE_FIELDS = [
  'source_title',
  'source_name',
  'publisher',
  'publication',
  'document_title',
  'doc_title',
  'media_name',
  'provider',
  'source'
]
const RELATION_TYPE_DISPLAY_LABELS: Record<string, string> = {
  risk_event: '风险事件',
  invested_in: '投资',
  received_funding: '获得融资'
}
const FALLBACK_RELATION_LABEL = '关联关系'

function stringValue(value: unknown, fallback = '-'): string {
  if (value === null || value === undefined) {
    return fallback
  }

  if (typeof value === 'string') {
    const trimmedValue = value.trim()

    return trimmedValue.length > 0 ? trimmedValue : fallback
  }

  if (typeof value === 'number') {
    return Number.isFinite(value) ? String(value) : fallback
  }

  if (typeof value === 'boolean' || typeof value === 'bigint' || typeof value === 'symbol') {
    return String(value)
  }

  return fallback
}

function normalizedValue(value: string): string {
  return value.trim().toLowerCase().replace(/[\s-]+/g, '_')
}

function isRawDocumentId(value: string): boolean {
  const normalizedSource = value.trim().toLowerCase()

  return (
    /^(?:doc|document)[-_][a-z0-9]+$/.test(normalizedSource) ||
    /^(?:doc|document)\d+$/.test(normalizedSource) ||
    /^source[-_](?:doc|document)(?:[-_][a-z0-9]+|\d+)$/.test(normalizedSource) ||
    /^(?:source|news|file|report|record|article|citation|evidence)[-_][a-z0-9][a-z0-9_-]*$/.test(normalizedSource) ||
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(normalizedSource) ||
    /^[0-9a-f]{16,}$/.test(normalizedSource)
  )
}

function isFallbackRelationLabel(value: string): boolean {
  const label = value.trim()

  return (
    label.length === 0 ||
    /^[A-Z0-9]+(?:_[A-Z0-9]+)+$/.test(label) ||
    /^[a-z0-9]+(?:_[a-z0-9]+)+$/.test(label)
  )
}

function relationDisplayLabel(edge: GraphEdge): string {
  const label = stringValue(edge.label, '')
  const labelDisplay = RELATION_TYPE_DISPLAY_LABELS[normalizedValue(label)]

  if (labelDisplay) {
    return labelDisplay
  }
  if (label && !isFallbackRelationLabel(label)) {
    return label
  }

  return RELATION_TYPE_DISPLAY_LABELS[normalizedValue(edge.type)] ?? FALLBACK_RELATION_LABEL
}

function isHighRiskNode(node: GraphNode): boolean {
  return normalizedValue(node.risk_level) === 'high'
}

function isRiskEdge(edge: GraphEdge): boolean {
  return HIGH_RISK_EDGE_TYPES.has(normalizedValue(edge.type))
}

function isReviewStatus(status: string): boolean {
  const normalizedStatus = normalizedValue(status)

  return normalizedStatus.length > 0 && normalizedStatus !== 'confirmed'
}

function isWeakRelation(edge: GraphEdge): boolean {
  return edge.confidence < WEAK_CONFIDENCE_THRESHOLD || isReviewStatus(edge.status)
}

function resolveEdgeRiskLevel(edge: GraphEdge): RiskLevel {
  if (isRiskEdge(edge)) {
    return 'high'
  }
  if (isWeakRelation(edge)) {
    return 'medium'
  }
  return 'low'
}

function resolveRiskLevel(nodes: GraphNode[], edges: GraphEdge[]): RiskLevel {
  if (nodes.some(isHighRiskNode) || edges.some((edge) => resolveEdgeRiskLevel(edge) === 'high')) {
    return 'high'
  }
  if (edges.some((edge) => resolveEdgeRiskLevel(edge) === 'medium')) {
    return 'medium'
  }
  return edges.length > 0 ? 'low' : 'unknown'
}

function riskScore(level: RiskLevel): number {
  const scoreMap: Record<RiskLevel, number> = {
    high: 86,
    medium: 61,
    low: 28,
    unknown: 0
  }
  return scoreMap[level]
}

function buildCompany(profile: CompanyProfile): ProductCompany {
  const companyNode = profile.graph.nodes.find((node) => node.type === 'Company')
  const company = profile.company ?? {}
  const industry = stringValue(company.industry ?? companyNode?.properties.industry)
  const legalRepresentative = stringValue(company.legal_representative ?? companyNode?.properties.legal_representative)
  const fallbackId = stringValue(companyNode?.id, stringValue(company.name, 'company_unknown'))

  return {
    id: stringValue(company.id, fallbackId),
    name: stringValue(company.name ?? companyNode?.label, '未知企业'),
    industry,
    legalRepresentative,
    tags: [industry, legalRepresentative === '-' ? '法人信息不足' : `法人 ${legalRepresentative}`]
  }
}

function nodeLabel(nodes: GraphNode[], id: string): string {
  const node = nodes.find((candidate) => candidate.id === id)

  return node ? stringValue(node.label, '未识别对象') : '未知关联方'
}

function edgesTouchingNode(edges: GraphEdge[], nodeId: string): string[] {
  return edges
    .filter((edge) => edge.source === nodeId || edge.target === nodeId)
    .map((edge) => edge.id)
}

function buildRiskFactors(nodes: GraphNode[], edges: GraphEdge[], level: RiskLevel): RiskFactor[] {
  if (level === 'low') {
    return [{
      id: 'stable-relations',
      level: 'low',
      title: '暂未发现高风险路径',
      description: '当前关系数据中主要为已确认关系，可继续查看证据链验证来源。',
      relationIds: edges.map((edge) => edge.id)
    }]
  }

  if (level === 'unknown') {
    return []
  }

  const nodeFactors: RiskFactor[] = nodes
    .filter(isHighRiskNode)
    .map((node) => ({
      id: `factor-node-${node.id}`,
      level: 'high',
      title: `${stringValue(node.label, '未识别对象')} 标记为高风险节点`,
      description: '该节点已被图谱标记为高风险，建议结合关联关系和外部来源复核。',
      relationIds: edgesTouchingNode(edges, node.id)
    }))

  const edgeFactors: RiskFactor[] = edges
    .map((edge) => ({
      edge,
      level: resolveEdgeRiskLevel(edge)
    }))
    .filter((item) => item.level !== 'low')
    .map((edge) => ({
      id: `factor-${edge.edge.id}`,
      level: edge.level,
      title: `${nodeLabel(nodes, edge.edge.source)} 与 ${nodeLabel(nodes, edge.edge.target)} 存在${relationDisplayLabel(edge.edge)}`,
      description: `该关系置信度为 ${(edge.edge.confidence * 100).toFixed(0)}%，建议结合证据来源复核。`,
      relationIds: [edge.edge.id]
    }))

  return [...nodeFactors, ...edgeFactors]
}

function resolveEvidenceSource(provenance: Record<string, unknown>): string {
  for (const field of READABLE_EVIDENCE_SOURCE_FIELDS) {
    const source = stringValue(provenance[field], '')

    if (source && !isRawDocumentId(source)) {
      return source
    }
  }

  return '图谱来源'
}

function buildEvidence(edges: GraphEdge[]): EvidenceItem[] {
  return edges.map((edge) => ({
    id: `evidence-${edge.id}`,
    relationId: edge.id,
    title: relationDisplayLabel(edge),
    text: stringValue(edge.provenance.source_text, '暂无可展示证据文本'),
    source: resolveEvidenceSource(edge.provenance),
    confidence: edge.confidence,
    date: stringValue(edge.properties.date ?? edge.provenance.date, '未标注日期')
  }))
}

function buildRelationPaths(nodes: GraphNode[], edges: GraphEdge[]): RelationPath[] {
  return edges.map((edge) => ({
    id: `path-${edge.id}`,
    label: `${nodeLabel(nodes, edge.source)} -> ${nodeLabel(nodes, edge.target)}`,
    relationIds: [edge.id],
    riskLevel: resolveEdgeRiskLevel(edge)
  }))
}

function buildDisplayGraph(profile: CompanyProfile) {
  return {
    nodes: profile.graph.nodes,
    edges: profile.graph.edges.map((edge) => ({
      ...edge,
      label: relationDisplayLabel(edge)
    }))
  }
}

function buildRiskSummary(company: ProductCompany, level: RiskLevel): string {
  const summaryMap: Record<RiskLevel, string> = {
    high: `${company.name} 存在高风险节点或关系，请优先查看高亮路径和证据链并复核来源。`,
    medium: `${company.name} 存在置信度较低或待复核关系，建议补充证据后再做风险判断。`,
    low: `${company.name} 当前关系数据暂未发现高风险路径，建议继续关注融资、股权和关键人员变化。`,
    unknown: `${company.name} 暂无足够图谱关系判断风险，请补充工商、投融资、司法和舆情数据。`
  }

  return summaryMap[level]
}

export function buildRiskWorkbenchModel(profile: CompanyProfile): RiskWorkbenchModel {
  const company = buildCompany(profile)
  const level = resolveRiskLevel(profile.graph.nodes, profile.graph.edges)
  const factors = buildRiskFactors(profile.graph.nodes, profile.graph.edges, level)

  return {
    company,
    risk: {
      level,
      score: riskScore(level),
      summary: buildRiskSummary(company, level),
      factors
    },
    graph: buildDisplayGraph(profile),
    evidence: buildEvidence(profile.graph.edges),
    paths: buildRelationPaths(profile.graph.nodes, profile.graph.edges)
  }
}
