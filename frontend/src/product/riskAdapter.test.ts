import { describe, expect, it } from 'vitest'
import type { CompanyProfile, GraphEdge, GraphNode } from '../api/types'
import { buildRiskWorkbenchModel } from './riskAdapter'

const baseCompany = {
  id: 'company_profile_id',
  name: '示例科技',
  industry: '金融科技',
  legal_representative: '张三'
}

const companyNode: GraphNode = {
  id: 'company_demo',
  label: '示例科技',
  type: 'Company',
  risk_level: 'normal',
  properties: { industry: '金融科技' }
}

const institutionNode: GraphNode = {
  id: 'institution_demo',
  label: '红杉资本',
  type: 'Institution',
  risk_level: 'normal',
  properties: { type: 'VC' }
}

const eventNode: GraphNode = {
  id: 'event_demo',
  label: 'B轮融资事件',
  type: 'Event',
  risk_level: 'normal',
  properties: { amount: '3000万元', date: '2024-03-15' }
}

const investmentEdge: GraphEdge = {
  id: 'rel_invested_demo',
  source: 'institution_demo',
  target: 'event_demo',
  type: 'INVESTED_IN',
  label: '投资',
  confidence: 0.92,
  status: 'confirmed',
  properties: { role: '领投', round: 'B轮' },
  provenance: { source_text: '红杉资本领投了示例科技B轮融资。', source_doc_id: 'doc_demo' }
}

function makeProfile(
  nodes: GraphNode[] = [companyNode, institutionNode, eventNode],
  edges: GraphEdge[] = [investmentEdge],
  companyOverrides: Record<string, unknown> = {}
): CompanyProfile {
  return {
    company: {
      ...baseCompany,
      ...companyOverrides
    },
    profile: {},
    graph: {
      nodes,
      edges
    }
  }
}

describe('buildRiskWorkbenchModel', () => {
  it('maps a company profile into business-facing risk content', () => {
    const model = buildRiskWorkbenchModel(makeProfile())

    expect(model.company.id).toBe('company_profile_id')
    expect(model.company.name).toBe('示例科技')
    expect(model.company.industry).toBe('金融科技')
    expect(model.risk.level).toBe('low')
    expect(model.risk.summary).toContain('暂未发现高风险路径')
    expect(model.risk.summary).not.toContain('当前样例数据')
    expect(model.risk.factors[0].description).not.toContain('当前样例图谱')
    expect(model.evidence).toHaveLength(1)
    expect(model.evidence[0].text).toBe('红杉资本领投了示例科技B轮融资。')
    expect(model.evidence[0].source).toBe('图谱来源')
    expect(model.evidence[0].source).not.toContain('doc_demo')
    expect(model.paths[0].label).toBe('红杉资本 -> B轮融资事件')
    expect(model.paths[0].riskLevel).toBe('low')
    expect(model.graph.nodes).toHaveLength(3)
  })

  it('stringifies numeric profile company ids before falling back to graph node ids', () => {
    const model = buildRiskWorkbenchModel(makeProfile(undefined, undefined, { id: 10001 }))

    expect(model.company.id).toBe('10001')
  })

  it('falls back to company name when profile id is absent and graph company node id is empty', () => {
    const emptyIdCompanyNode: GraphNode = {
      ...companyNode,
      id: ''
    }

    const model = buildRiskWorkbenchModel(makeProfile([emptyIdCompanyNode], [], { id: undefined }))

    expect(model.company.id).toBe('示例科技')
  })

  it('stringifies primitive evidence values from provenance and properties', () => {
    const primitiveEvidenceEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_primitive_evidence',
      properties: { date: true },
      provenance: {
        source_text: false,
        source_doc_id: 20240501
      }
    }

    const model = buildRiskWorkbenchModel(makeProfile(undefined, [primitiveEvidenceEdge]))

    expect(model.evidence[0].text).toBe('false')
    expect(model.evidence[0].source).toBe('图谱来源')
    expect(model.evidence[0].date).toBe('true')
  })

  it('prefers readable evidence provenance and hides raw document IDs', () => {
    const docOnlyEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_doc_only',
      provenance: {
        source_text: '示例科技完成B轮融资。',
        source_doc_id: 'doc_demo'
      }
    }
    const titledSourceEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_titled_source',
      provenance: {
        source_text: '示例科技披露补充融资信息。',
        source_doc_id: 'doc_abc',
        source_title: '投融资公告'
      }
    }

    const model = buildRiskWorkbenchModel(makeProfile(undefined, [docOnlyEdge, titledSourceEdge]))

    expect(model.evidence.map((item) => item.source)).toEqual(['图谱来源', '投融资公告'])
    expect(model.evidence.map((item) => item.source).join(' ')).not.toContain('doc_demo')
    expect(model.evidence.map((item) => item.source).join(' ')).not.toContain('doc_abc')
  })

  it('filters likely internal source IDs and prefers readable source fields over generic source', () => {
    const documentIdEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_document_id_source',
      provenance: {
        source_text: '示例科技披露融资进展。',
        source: 'document_123'
      }
    }
    const sourceDocIdEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_source_doc_id_source',
      provenance: {
        source_text: '示例科技补充披露融资信息。',
        source: 'source_doc_001'
      }
    }
    const compactDocIdEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_compact_doc_id_source',
      provenance: {
        source_text: '示例科技更新融资公告。',
        source: 'doc123'
      }
    }
    const readablePublisherEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_readable_publisher_source',
      provenance: {
        source_text: '示例科技公告融资完成。',
        source: 'doc123',
        publisher: '证券时报'
      }
    }

    const model = buildRiskWorkbenchModel(makeProfile(undefined, [
      documentIdEdge,
      sourceDocIdEdge,
      compactDocIdEdge,
      readablePublisherEdge
    ]))

    expect(model.evidence.map((item) => item.source)).toEqual([
      '图谱来源',
      '图谱来源',
      '图谱来源',
      '证券时报'
    ])
  })

  it('falls back instead of stringifying plain object evidence values', () => {
    const objectEvidenceEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_object_evidence',
      properties: { date: { raw: '2024-03-15' } },
      provenance: {
        source_text: { raw: 'object text' },
        source_doc_id: { id: 'doc_demo' }
      }
    }

    const model = buildRiskWorkbenchModel(makeProfile(undefined, [objectEvidenceEdge]))

    expect(model.evidence[0].text).toBe('暂无可展示证据文本')
    expect(model.evidence[0].source).toBe('图谱来源')
    expect(model.evidence[0].date).toBe('未标注日期')
  })

  it('raises high risk and creates a factor for a high-risk node only', () => {
    const highRiskNode: GraphNode = {
      id: 'risk_event',
      label: '异常担保事件',
      type: 'Event',
      risk_level: 'high',
      properties: { date: '2024-05-01' }
    }

    const model = buildRiskWorkbenchModel(makeProfile([companyNode, highRiskNode], []))

    expect(model.risk.level).toBe('high')
    expect(model.risk.summary).toContain('高风险')
    expect(model.risk.factors).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'factor-node-risk_event',
        level: 'high',
        title: expect.stringContaining('异常担保事件'),
        relationIds: []
      })
    ]))
  })

  it('raises high risk for explicit risk relations', () => {
    const riskEdge: GraphEdge = {
      id: 'rel_risk',
      source: 'company_demo',
      target: 'event_demo',
      type: 'RISK_EVENT',
      label: '涉及风险事件',
      confidence: 0.92,
      status: 'confirmed',
      properties: {},
      provenance: { source_text: '示例科技被报道涉及异常担保。' }
    }

    const model = buildRiskWorkbenchModel(makeProfile(undefined, [riskEdge]))

    expect(model.risk.level).toBe('high')
    expect(model.risk.factors).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'factor-rel_risk',
        level: 'high',
        title: expect.stringContaining('涉及风险事件')
      })
    ]))
    expect(model.paths[0].riskLevel).toBe('high')
  })

  it('uses product-safe relation labels when raw labels are enum-like or blank', () => {
    const enumLabelRiskEdge: GraphEdge = {
      id: 'rel_enum_risk',
      source: 'company_demo',
      target: 'event_demo',
      type: 'RISK_EVENT',
      label: 'RISK_EVENT',
      confidence: 0.92,
      status: 'confirmed',
      properties: {},
      provenance: { source_text: '示例科技被报道涉及异常担保。' }
    }
    const blankLabelInvestmentEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_blank_investment_label',
      label: '',
      provenance: { source_text: '红杉资本领投了示例科技B轮融资。' }
    }

    const model = buildRiskWorkbenchModel(makeProfile(undefined, [
      enumLabelRiskEdge,
      blankLabelInvestmentEdge
    ]))
    const visibleRelationText = [
      ...model.risk.factors.map((factor) => factor.title),
      ...model.risk.factors.map((factor) => factor.description),
      ...model.evidence.map((item) => item.title)
    ].join(' ')

    expect(model.evidence.map((item) => item.title)).toEqual(['风险事件', '投资'])
    expect(visibleRelationText).toContain('风险事件')
    expect(visibleRelationText).toContain('投资')
    expect(visibleRelationText).not.toContain('RISK_EVENT')
    expect(model.evidence.every((item) => item.title.trim().length > 0)).toBe(true)
  })

  it('normalizes lowercase backend relation labels before display', () => {
    const lowercaseRiskEdge: GraphEdge = {
      id: 'rel_lowercase_risk',
      source: 'company_demo',
      target: 'event_demo',
      type: 'RISK_EVENT',
      label: 'risk_event',
      confidence: 0.92,
      status: 'confirmed',
      properties: {},
      provenance: { source_text: '示例科技被报道涉及异常担保。' }
    }
    const lowercaseInvestmentEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_lowercase_investment',
      label: 'invested_in',
      provenance: { source_text: '红杉资本领投了示例科技B轮融资。' }
    }

    const model = buildRiskWorkbenchModel(makeProfile(undefined, [
      lowercaseRiskEdge,
      lowercaseInvestmentEdge
    ]))
    const visibleRelationText = [
      ...model.risk.factors.map((factor) => factor.title),
      ...model.evidence.map((item) => item.title)
    ].join(' ')

    expect(model.evidence.map((item) => item.title)).toEqual(['风险事件', '投资'])
    expect(visibleRelationText).not.toContain('risk_event')
    expect(visibleRelationText).not.toContain('invested_in')
  })

  it('uses product-safe relation labels in graph edges for visualization', () => {
    const lowercaseRiskEdge: GraphEdge = {
      id: 'rel_graph_lowercase_risk',
      source: 'company_demo',
      target: 'event_demo',
      type: 'RISK_EVENT',
      label: 'risk_event',
      confidence: 0.92,
      status: 'confirmed',
      properties: {},
      provenance: { source_text: '示例科技被报道涉及异常担保。' }
    }
    const lowercaseInvestmentEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_graph_lowercase_investment',
      label: 'invested_in',
      provenance: { source_text: '红杉资本领投了示例科技B轮融资。' }
    }

    const model = buildRiskWorkbenchModel(makeProfile(undefined, [
      lowercaseRiskEdge,
      lowercaseInvestmentEdge
    ]))

    expect(model.graph.edges.map((edge) => edge.label)).toEqual(['风险事件', '投资'])
    expect(model.graph.edges.map((edge) => edge.label).join(' ')).not.toContain('risk_event')
    expect(model.graph.edges.map((edge) => edge.label).join(' ')).not.toContain('invested_in')
  })

  it('preserves readable English relation labels instead of treating them as raw enums', () => {
    const strategicPartnerEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_strategic_partner',
      type: 'PARTNER_RELATION',
      label: 'Strategic Partner',
      provenance: { source_text: '双方披露战略合作关系。' }
    }
    const legalDisputeEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_legal_dispute',
      type: 'LEGAL_CASE',
      label: 'Legal Dispute',
      provenance: { source_text: '公开信息显示存在法律纠纷。' }
    }

    const model = buildRiskWorkbenchModel(makeProfile(undefined, [
      strategicPartnerEdge,
      legalDisputeEdge
    ]))

    expect(model.evidence.map((item) => item.title)).toEqual(['Strategic Partner', 'Legal Dispute'])
  })

  it('hides backend-like source identifiers that are not document-prefixed IDs', () => {
    const sourceIdEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_source_id',
      provenance: {
        source_text: '示例科技披露融资进展。',
        source: 'source_001'
      }
    }
    const newsIdEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_news_id',
      provenance: {
        source_text: '示例科技补充披露融资信息。',
        source: 'news_202405'
      }
    }
    const uuidSourceEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_uuid_source',
      provenance: {
        source_text: '示例科技公告融资完成。',
        source: '550e8400-e29b-41d4-a716-446655440000'
      }
    }

    const model = buildRiskWorkbenchModel(makeProfile(undefined, [
      sourceIdEdge,
      newsIdEdge,
      uuidSourceEdge
    ]))

    expect(model.evidence.map((item) => item.source)).toEqual(['图谱来源', '图谱来源', '图谱来源'])
  })

  it('uses product-safe labels for risk relations with missing endpoint nodes', () => {
    const orphanRiskEdge: GraphEdge = {
      id: 'rel_orphan_risk',
      source: 'missing_source',
      target: 'missing_target',
      type: 'RISK_EVENT',
      label: '涉及风险事件',
      confidence: 0.92,
      status: 'confirmed',
      properties: {},
      provenance: { source_text: '外部报道显示存在异常风险。' }
    }

    const model = buildRiskWorkbenchModel(makeProfile([companyNode], [orphanRiskEdge]))
    const factorLabels = model.risk.factors.map((factor) => factor.title)
    const pathLabels = model.paths.map((path) => path.label)
    const generatedLabels = [...factorLabels, ...pathLabels]

    expect(generatedLabels).toEqual(expect.arrayContaining([
      expect.stringContaining('未知关联方')
    ]))
    for (const label of generatedLabels) {
      expect(label).not.toContain('missing_source')
      expect(label).not.toContain('missing_target')
    }
  })

  it('uses product-safe fallbacks for empty graph node labels', () => {
    const blankCompanyNode: GraphNode = {
      ...companyNode,
      label: ''
    }
    const blankRiskNode: GraphNode = {
      id: 'risk_event',
      label: '',
      type: 'Event',
      risk_level: 'high',
      properties: {}
    }
    const riskEdge: GraphEdge = {
      id: 'rel_blank_label_risk',
      source: 'company_demo',
      target: 'risk_event',
      type: 'RISK_EVENT',
      label: '涉及风险事件',
      confidence: 0.92,
      status: 'confirmed',
      properties: {},
      provenance: { source_text: '外部报道显示存在异常风险。' }
    }

    const model = buildRiskWorkbenchModel(makeProfile([blankCompanyNode, blankRiskNode], [riskEdge]))
    const factorLabels = model.risk.factors.map((factor) => factor.title)
    const pathLabels = model.paths.map((path) => path.label)
    const generatedLabels = [...factorLabels, ...pathLabels]

    expect(generatedLabels).toEqual(expect.arrayContaining([
      expect.stringContaining('未识别对象')
    ]))
    for (const label of generatedLabels) {
      expect(label).not.toContain('company_demo')
      expect(label).not.toContain('risk_event')
    }
  })

  it('does not escalate benign relation types that contain risk text', () => {
    const noRiskEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_no_risk',
      type: 'NO_RISK',
      label: '无风险记录',
      confidence: 0.94,
      status: 'confirmed'
    }

    const model = buildRiskWorkbenchModel(makeProfile(undefined, [noRiskEdge]))

    expect(model.risk.level).toBe('low')
    expect(model.risk.summary).toContain('暂未发现高风险路径')
    expect(model.risk.summary).not.toContain('当前样例数据')
    expect(model.risk.factors).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'stable-relations',
        level: 'low',
        description: expect.not.stringContaining('当前样例图谱'),
        relationIds: ['rel_no_risk']
      })
    ]))
    expect(model.paths[0].riskLevel).toBe('low')
  })

  it('preserves per-edge levels when high, medium, and benign risk-like relations are mixed', () => {
    const highRiskEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_mixed_risk',
      source: 'company_demo',
      target: 'event_demo',
      type: 'RISK_EVENT',
      label: '涉及风险事件',
      confidence: 0.95,
      status: 'confirmed'
    }
    const mediumReviewEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_mixed_review',
      type: 'INVESTED_IN',
      label: '待复核投资',
      confidence: 0.9,
      status: 'under_review'
    }
    const benignRiskTextEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_mixed_no_risk',
      type: 'NO_RISK',
      label: '无风险记录',
      confidence: 0.94,
      status: 'confirmed'
    }

    const model = buildRiskWorkbenchModel(makeProfile(undefined, [
      highRiskEdge,
      mediumReviewEdge,
      benignRiskTextEdge
    ]))
    const pathLevels = Object.fromEntries(model.paths.map((path) => [path.relationIds[0], path.riskLevel]))

    expect(model.risk.level).toBe('high')
    expect(model.risk.factors).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'factor-rel_mixed_risk',
        level: 'high'
      }),
      expect.objectContaining({
        id: 'factor-rel_mixed_review',
        level: 'medium'
      })
    ]))
    expect(pathLevels).toEqual({
      rel_mixed_risk: 'high',
      rel_mixed_review: 'medium',
      rel_mixed_no_risk: 'low'
    })
  })

  it('classifies low-confidence relations as medium risk', () => {
    const weakEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_weak',
      confidence: 0.58
    }

    const model = buildRiskWorkbenchModel(makeProfile(undefined, [weakEdge]))

    expect(model.risk.level).toBe('medium')
    expect(model.risk.summary).toContain('待复核')
    expect(model.risk.factors).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'factor-rel_weak',
        level: 'medium'
      })
    ]))
    expect(model.paths[0].riskLevel).toBe('medium')
  })

  it('treats review-like non-confirmed statuses as medium risk', () => {
    const reviewEdge: GraphEdge = {
      ...investmentEdge,
      id: 'rel_review',
      confidence: 0.91,
      status: 'under_review'
    }

    const model = buildRiskWorkbenchModel(makeProfile(undefined, [reviewEdge]))

    expect(model.risk.level).toBe('medium')
    expect(model.risk.factors).toEqual(expect.arrayContaining([
      expect.objectContaining({
        relationIds: ['rel_review']
      })
    ]))
    expect(model.paths[0].riskLevel).toBe('medium')
  })

  it('marks empty graphs as unknown with an explicit summary', () => {
    const model = buildRiskWorkbenchModel(makeProfile([companyNode], []))

    expect(model.risk.level).toBe('unknown')
    expect(model.risk.score).toBe(0)
    expect(model.risk.summary).toContain('暂无足够图谱关系')
    expect(model.risk.factors).toHaveLength(0)
    expect(model.evidence).toHaveLength(0)
    expect(model.paths).toHaveLength(0)
  })
})
