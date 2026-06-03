import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { analyzeStock, streamStockAnalysis } from '../api/analysis'
import { getCompanyProfile, searchCompanies } from '../api/graph'
import { importFinancialDataset } from '../api/runtime'
import type { CompanyProfile, GraphEdge, GraphNode } from '../api/types'
import { loadReports, loadWatchlist } from '../product/storage'
import RiskWorkbench from './RiskWorkbench.vue'

const riskGraphCanvasStub = vi.hoisted(() => ({
  name: 'RiskGraphCanvas',
  props: ['nodes', 'edges', 'highlightedRelationIds'],
  emits: ['select-edge'],
  template: `
    <div data-testid="risk-graph-canvas">
      <span v-for="edge in edges" :key="edge.id">{{ edge.label }}</span>
    </div>
  `
}))

vi.mock('../api/graph', () => ({
  getCompanyProfile: vi.fn(),
  searchCompanies: vi.fn()
}))

vi.mock('../api/analysis', () => ({
  analyzeStock: vi.fn(),
  streamStockAnalysis: vi.fn()
}))

vi.mock('../api/runtime', () => ({
  importFinancialDataset: vi.fn()
}))

const DEFAULT_COMPANY_NAME = '邦盛科技'
const LAST_WORKBENCH_COMPANY_KEY = 'financial-risk-workbench-last-company'

const companyNode: GraphNode = {
  id: 'company_demo',
  label: DEFAULT_COMPANY_NAME,
  type: 'Company',
  risk_level: 'normal',
  properties: { industry: '金融科技', legal_representative: '张三' }
}

const investmentNode: GraphNode = {
  id: 'investment_event',
  label: 'B轮融资事件',
  type: 'Event',
  risk_level: 'normal',
  properties: {}
}

const riskNode: GraphNode = {
  id: 'risk_event',
  label: '异常担保事件',
  type: 'Event',
  risk_level: 'normal',
  properties: {}
}

const affiliateNode: GraphNode = {
  id: 'affiliate_company',
  label: '关联企业',
  type: 'Company',
  risk_level: 'normal',
  properties: {}
}

const investmentEdge: GraphEdge = {
  id: 'rel_invested_demo',
  source: 'company_demo',
  target: 'investment_event',
  type: 'INVESTED_IN',
  label: '投资',
  confidence: 0.91,
  status: 'confirmed',
  properties: { date: '2024-03-15' },
  provenance: {
    source_text: `${DEFAULT_COMPANY_NAME}完成B轮融资。`,
    source_doc_id: 'doc_demo'
  }
}

const riskEdge: GraphEdge = {
  id: 'rel_risk',
  source: 'company_demo',
  target: 'risk_event',
  type: 'RISK_EVENT',
  label: '涉及风险事件',
  confidence: 0.92,
  status: 'confirmed',
  properties: { date: '2024-05-01' },
  provenance: {
    source_text: `${DEFAULT_COMPANY_NAME}被报道涉及异常担保。`,
    source_doc_id: 'doc-risk'
  }
}

const secondHopEdge: GraphEdge = {
  id: 'rel_second_hop',
  source: 'investment_event',
  target: 'affiliate_company',
  type: 'INVESTED_IN',
  label: '投资',
  confidence: 0.88,
  status: 'confirmed',
  properties: { date: '2024-06-01' },
  provenance: {
    source_text: '融资事件关联到下游企业。',
    source_doc_id: 'doc-hop'
  }
}

const getCompanyProfileMock = vi.mocked(getCompanyProfile)
const searchCompaniesMock = vi.mocked(searchCompanies)
const analyzeStockMock = vi.mocked(analyzeStock)
const streamStockAnalysisMock = vi.mocked(streamStockAnalysis)
const importFinancialDatasetMock = vi.mocked(importFinancialDataset)

const docAbcEdge: GraphEdge = {
  ...investmentEdge,
  id: 'rel_doc_abc',
  label: '补充披露',
  provenance: {
    source_text: `${DEFAULT_COMPANY_NAME}披露补充融资信息。`,
    source_doc_id: 'doc_abc'
  }
}

const companySearchEmitterStub = {
  name: 'CompanySearch',
  props: ['modelValue', 'loading'],
  emits: ['update:modelValue', 'search'],
  template: '<div />'
}
function makeProfile(companyName = DEFAULT_COMPANY_NAME, edges: GraphEdge[] = []): CompanyProfile {
  return {
    company: {
      id: `company-${companyName}`,
      name: companyName,
      industry: '金融科技',
      legal_representative: '张三'
    },
    profile: {},
    graph: {
      nodes: [
        { ...companyNode, label: companyName },
        investmentNode,
        riskNode,
        affiliateNode
      ],
      edges
    }
  }
}

function analysisPayload(overrides: Record<string, unknown> = {}) {
  return {
    target: { stock_code: '', company_name: DEFAULT_COMPANY_NAME },
    fundamentals: { industry: '金融科技', data_time: 'local-cache' },
    news_events: [
      {
        event_type: 'graph_event',
        sentiment: 'unknown',
        title: '邦盛科技B轮融资事件',
        date: '2024-03-15',
        source_node_id: 'event_demo',
        evidence: '证据记录邦盛科技完成B轮融资。'
      }
    ],
    subgraph: { nodes: [], edges: [] },
    analysis: {
      summary: '基于证据线索生成研判摘要。',
      opportunity_factors: [],
      risk_factors: [],
      graph_insights: [],
      confidence: 0.74,
      missing_data: [],
      disclaimer: '本结果仅用于研究辅助，不构成投资建议。'
    },
    ...overrides
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve
    reject = promiseReject
  })

  return { promise, resolve, reject }
}

async function mountWorkbench() {
  const wrapper = mount(RiskWorkbench, {
    global: {
      stubs: {
        RiskGraphCanvas: riskGraphCanvasStub
      }
    }
  })
  await flushPromises()

  return wrapper
}

async function mountWorkbenchWithSearchEmitter() {
  const wrapper = mount(RiskWorkbench, {
    global: {
      stubs: {
        CompanySearch: companySearchEmitterStub,
        RiskGraphCanvas: riskGraphCanvasStub
      }
    }
  })
  await flushPromises()

  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  importFinancialDatasetMock.mockResolvedValue({
    import_run_id: 'test-import',
    nodes_created: 0,
    relationships_created: 0,
    nodes_skipped: 0,
    relationships_skipped: 0,
    status: 'success'
  })
  getCompanyProfileMock.mockResolvedValue(makeProfile())
  searchCompaniesMock.mockResolvedValue({ query: '', total: 0, companies: [] })
  analyzeStockMock.mockResolvedValue(analysisPayload())
  streamStockAnalysisMock.mockImplementation(async (_payload, handlers) => {
    handlers.onDone?.(analysisPayload())
  })
})

describe('RiskWorkbench', () => {
  it('loads a product-safe default company instead of sample wording', async () => {
    getCompanyProfileMock.mockImplementation(async (query) => makeProfile(String(query)))

    const wrapper = await mountWorkbench()

    expect(importFinancialDatasetMock).toHaveBeenCalledTimes(1)
    expect(importFinancialDatasetMock.mock.invocationCallOrder[0]).toBeLessThan(getCompanyProfileMock.mock.invocationCallOrder[0])
    expect(getCompanyProfileMock).toHaveBeenCalledWith(DEFAULT_COMPANY_NAME)
    expect(wrapper.text()).toContain(DEFAULT_COMPANY_NAME)
    expect(wrapper.text()).not.toContain('示例')
  })

  it('restores the last searched company instead of returning to the default workbench company', async () => {
    localStorage.setItem(LAST_WORKBENCH_COMPANY_KEY, '平安银行股份有限公司')
    getCompanyProfileMock.mockImplementation(async (query) => makeProfile(String(query)))

    const wrapper = await mountWorkbench()

    expect(getCompanyProfileMock).toHaveBeenCalledWith('平安银行股份有限公司')
    expect(getCompanyProfileMock).not.toHaveBeenCalledWith(DEFAULT_COMPANY_NAME)
    expect(wrapper.text()).toContain('平安银行股份有限公司')
  })

  it('remembers the latest submitted company for later workbench visits', async () => {
    const wrapper = await mountWorkbench()
    getCompanyProfileMock.mockClear()

    await wrapper.find('input[type="search"]').setValue('  科大智能  ')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(getCompanyProfileMock).toHaveBeenCalledWith('科大智能')
    expect(localStorage.getItem(LAST_WORKBENCH_COMPANY_KEY)).toBe('科大智能')
  })

  it('loads productized risk content without raw output or roadmap copy', async () => {
    const wrapper = await mountWorkbench()

    expect(wrapper.text()).toContain(DEFAULT_COMPANY_NAME)
    expect(wrapper.text()).toContain('风险等级')
    expect(wrapper.text()).toContain('暂无足够数据生成风险因子。')
    expect(wrapper.text()).toContain('暂无可展示关系路径。')
    expect(wrapper.find('pre').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('图谱视图将在下一步升级为可交互风险路径。')
    expect(wrapper.text()).not.toContain('关联图谱')
    expect(wrapper.text()).toContain('关系图谱')
  })

  it('automatically runs unified evidence and AI analysis after loading a company', async () => {
    const wrapper = await mountWorkbench()

    expect(streamStockAnalysisMock).toHaveBeenCalledWith(
      {
        stockCode: '',
        companyName: DEFAULT_COMPANY_NAME,
        refreshNews: true,
        useLlm: true
      },
      expect.any(Object)
    )
    expect(wrapper.find('[data-testid="evidence-hub-panel"]').text()).toContain('无需手动整理材料')
    expect(wrapper.find('[data-testid="evidence-status"]').text()).toContain('AI研判已完成')
    expect(wrapper.find('[data-testid="news-evidence-list"]').text()).toContain('邦盛科技B轮融资事件')
    expect(wrapper.find('[data-testid="news-evidence-list"]').text()).toContain('证据线索')
    expect(wrapper.find('[data-testid="evidence-hub-panel"]').text()).not.toContain('最新消息')
    expect(wrapper.find('[data-testid="evidence-hub-panel"]').text()).not.toContain('新闻')
  })

  it('renders streamed evidence before the final analysis is done', async () => {
    const finalAnalysis = deferred<Record<string, unknown>>()
    streamStockAnalysisMock.mockImplementationOnce(async (_payload, handlers) => {
      handlers.onNewsEvent?.({
        event_type: 'announcement',
        sentiment: 'neutral',
        title: '平安银行披露经营更新',
        date: '2026-06-01',
        source_url: 'https://example.com/pab',
        evidence: '平安银行公开披露经营更新。'
      })
      const donePayload = await finalAnalysis.promise
      handlers.onDone?.(donePayload)
    })
    getCompanyProfileMock.mockResolvedValue(makeProfile('平安银行股份有限公司'))

    const wrapper = await mountWorkbench()

    expect(wrapper.find('[data-testid="news-evidence-list"]').text()).toContain('平安银行披露经营更新')
    expect(wrapper.text()).not.toContain('最终 AI 研判摘要。')

    finalAnalysis.resolve(analysisPayload({
      target: { stock_code: '000001', company_name: '平安银行股份有限公司' },
      news_events: [
        {
          event_type: 'announcement',
          sentiment: 'neutral',
          title: '平安银行披露经营更新',
          date: '2026-06-01',
          source_url: 'https://example.com/pab',
          evidence: '平安银行公开披露经营更新。'
        }
      ],
      analysis: {
        summary: '最终 AI 研判摘要。',
        opportunity_factors: [],
        risk_factors: [],
        graph_insights: [],
        confidence: 0.78,
        missing_data: [],
        disclaimer: '本结果仅用于研究辅助，不构成投资建议。'
      }
    }))
    await flushPromises()

    expect(wrapper.text()).toContain('最终 AI 研判摘要。')
  })

  it('refreshes unified evidence and AI analysis from the workbench evidence hub', async () => {
    streamStockAnalysisMock
      .mockImplementationOnce(async (_payload, handlers) => {
        handlers.onDone?.(analysisPayload())
      })
      .mockImplementationOnce(async (_payload, handlers) => {
        handlers.onDone?.(analysisPayload({
        news_events: [
          {
            event_type: 'announcement',
            sentiment: 'neutral',
            title: '邦盛科技发布业务更新',
            date: '2026-06-01',
            source_url: 'https://example.com/news',
            evidence: '公开新闻摘要。'
          }
        ],
        analysis: {
          summary: '结合证据线索后的AI研判摘要。',
          opportunity_factors: [],
          risk_factors: [],
          graph_insights: [],
          confidence: 0.82,
          missing_data: [],
          disclaimer: '本结果仅用于研究辅助，不构成投资建议。'
        }
        }))
      })

    const wrapper = await mountWorkbench()

    await wrapper.findAll('button').find((button) => button.text().includes('重新分析'))!.trigger('click')
    await flushPromises()

    expect(streamStockAnalysisMock).toHaveBeenLastCalledWith(
      {
        stockCode: '',
        companyName: DEFAULT_COMPANY_NAME,
        refreshNews: true,
        useLlm: true
      },
      expect.any(Object)
    )
    expect(wrapper.find('[data-testid="evidence-status"]').text()).toContain('AI研判已完成')
    expect(wrapper.find('[data-testid="news-evidence-list"]').text()).toContain('邦盛科技发布业务更新')
    expect(wrapper.text()).toContain('结合证据线索后的AI研判摘要。')
  })

  it('shows the market module as a graph-side auxiliary entry when no stock code is known', async () => {
    const wrapper = await mountWorkbench()
    const marketModule = wrapper.find('.market-mini-module')

    expect(marketModule.text()).toContain('上市公司行情')
    expect(marketModule.text()).toContain('待识别股票代码')
    expect(marketModule.find('.market-module-link').attributes('href')).toBe('/market')
  })

  it('links known listed companies to the market candlestick module with query context', async () => {
    getCompanyProfileMock.mockResolvedValue(makeProfile('招商银行'))

    const wrapper = await mountWorkbench()
    const marketModule = wrapper.find('.market-mini-module')

    expect(marketModule.text()).toContain('K 线与事件')
    expect(marketModule.text()).toContain('打开行情模块')
    expect(marketModule.find('.market-module-link').attributes('href')).toBe(
      '/market?company=%E6%8B%9B%E5%95%86%E9%93%B6%E8%A1%8C&stock_code=600036'
    )
  })

  it('recognizes known listed companies when the graph returns their full legal names', async () => {
    getCompanyProfileMock.mockResolvedValue(makeProfile('平安银行股份有限公司'))

    const wrapper = await mountWorkbench()
    const marketModule = wrapper.find('.market-mini-module')

    expect(marketModule.text()).toContain('K 线与事件')
    expect(marketModule.find('.market-module-link').attributes('href')).toBe(
      '/market?company=%E5%B9%B3%E5%AE%89%E9%93%B6%E8%A1%8C%E8%82%A1%E4%BB%BD%E6%9C%89%E9%99%90%E5%85%AC%E5%8F%B8&stock_code=000001'
    )
    expect(streamStockAnalysisMock).toHaveBeenCalledWith(
      {
        stockCode: '000001',
        companyName: '平安银行股份有限公司',
        refreshNews: true,
        useLlm: true
      },
      expect.any(Object)
    )
  })

  it('does not render raw relation or document IDs in product UI text', async () => {
    getCompanyProfileMock.mockResolvedValue(makeProfile(DEFAULT_COMPANY_NAME, [riskEdge, investmentEdge, docAbcEdge]))

    const wrapper = await mountWorkbench()

    expect(wrapper.text()).not.toContain('rel_risk')
    expect(wrapper.text()).not.toContain('rel_invested_demo')
    expect(wrapper.text()).not.toContain('rel_doc_abc')
    expect(wrapper.text()).not.toContain('doc-risk')
    expect(wrapper.text()).not.toContain('doc_demo')
    expect(wrapper.text()).not.toContain('doc_abc')
  })

  it('does not render demo copy for loaded low-risk workbench content', async () => {
    getCompanyProfileMock.mockResolvedValue(makeProfile(DEFAULT_COMPANY_NAME, [investmentEdge]))

    const wrapper = await mountWorkbench()

    expect(wrapper.text()).toContain('低风险')
    expect(wrapper.text()).toContain('暂未发现高风险路径')
    expect(wrapper.text()).not.toContain('当前样例数据')
    expect(wrapper.text()).not.toContain('当前样例图谱')
  })

  it('shows a validation error and does not call the API for blank submitted queries', async () => {
    const wrapper = await mountWorkbench()
    getCompanyProfileMock.mockClear()

    await wrapper.find('input[type="search"]').setValue('   ')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('请输入企业名称或股票代码。')
    expect(getCompanyProfileMock).not.toHaveBeenCalled()
  })

  it('shows a product-safe API failure and retries with the edited keyword', async () => {
    getCompanyProfileMock
      .mockRejectedValueOnce(new Error('backend stack trace'))
      .mockImplementationOnce(async (query) => makeProfile(String(query)))

    const wrapper = await mountWorkbench()

    expect(wrapper.text()).toContain('服务暂不可用，请稍后重试。')
    expect(wrapper.text()).not.toContain('backend stack trace')

    await wrapper.find('input[type="search"]').setValue(' 当前企业 ')
    await wrapper.find('.state-panel button').trigger('click')
    await flushPromises()

    expect(getCompanyProfileMock).toHaveBeenLastCalledWith('当前企业')
    expect(wrapper.text()).toContain('当前企业')
  })

  it('submits the trimmed query to getCompanyProfile', async () => {
    const wrapper = await mountWorkbench()
    getCompanyProfileMock.mockClear()

    await wrapper.find('input[type="search"]').setValue('  招商银行  ')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(getCompanyProfileMock).toHaveBeenCalledTimes(1)
    expect(getCompanyProfileMock).toHaveBeenCalledWith('招商银行')
  })

  it('keeps an unavailable user search on its no-result state instead of falling back to default', async () => {
    getCompanyProfileMock.mockImplementation(async (query) => {
      if (query === DEFAULT_COMPANY_NAME) {
        return makeProfile(DEFAULT_COMPANY_NAME, [investmentEdge])
      }

      const missingProfile: CompanyProfile = {
        ...makeProfile(String(query)),
        found: false,
        graph: { nodes: [], edges: [] }
      }

      return missingProfile
    })

    const wrapper = await mountWorkbench()
    getCompanyProfileMock.mockClear()
    analyzeStockMock.mockClear()
    streamStockAnalysisMock.mockClear()

    await wrapper.find('input[type="search"]').setValue('宇树科技')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(getCompanyProfileMock).toHaveBeenCalledTimes(1)
    expect(getCompanyProfileMock).toHaveBeenCalledWith('宇树科技')
    expect(getCompanyProfileMock).not.toHaveBeenCalledWith(DEFAULT_COMPANY_NAME)
    expect(streamStockAnalysisMock).toHaveBeenCalledWith(
      {
        stockCode: '',
        companyName: '宇树科技',
        refreshNews: true,
        useLlm: true
      },
      expect.any(Object)
    )
    expect(wrapper.text()).toContain('宇树科技')
    expect(wrapper.text()).toContain('关系图谱')
    expect(wrapper.text()).not.toContain('未查询到“宇树科技”的图谱数据')
  })

  it('renders the merged runtime graph returned by refreshed news analysis', async () => {
    const liveCompanyNode: GraphNode = {
      id: 'company_unitree',
      label: '宇树科技',
      type: 'Company',
      risk_level: 'normal',
      properties: { source: 'merged_runtime_graph' }
    }
    const liveEventNode: GraphNode = {
      id: 'news_event_unitree',
      label: '宇树科技发布四足机器人新品',
      type: 'Event',
      risk_level: 'normal',
      properties: { source: 'realtime_news' }
    }
    const liveEdge: GraphEdge = {
      id: 'rel_unitree_news',
      source: 'company_unitree',
      target: 'news_event_unitree',
      type: 'MENTIONED_IN',
      label: '相关新闻',
      confidence: 0.82,
      status: 'confirmed',
      properties: {},
      provenance: { source_text: '宇树科技公开披露机器人产品进展。' }
    }

    getCompanyProfileMock.mockResolvedValue({
      ...makeProfile('宇树科技'),
      found: false,
      graph: { nodes: [], edges: [] }
    })
    streamStockAnalysisMock.mockImplementationOnce(async (_payload, handlers) => {
      handlers.onDone?.(analysisPayload({
        target: { stock_code: '', company_name: '宇树科技' },
        subgraph: {
          nodes: [liveCompanyNode, liveEventNode],
          edges: [liveEdge]
        }
      }))
    })

    const wrapper = await mountWorkbench()

    expect(wrapper.findComponent({ name: 'RiskGraphCanvas' }).props('nodes')).toEqual(
      expect.arrayContaining([expect.objectContaining({ label: '宇树科技发布四足机器人新品' })])
    )
    expect(wrapper.findComponent({ name: 'RiskGraphCanvas' }).props('edges')).toEqual(
      expect.arrayContaining([expect.objectContaining({ type: 'MENTIONED_IN' })])
    )
    expect(wrapper.find('[data-testid="path-list"]').text()).toContain('宇树科技发布四足机器人新品')
    expect(wrapper.find('[data-testid="evidence-list"]').text()).toContain('宇树科技公开披露机器人产品进展。')
  })

  it('disables duplicate same-query submit while a company analysis is loading', async () => {
    const pendingResponse = deferred<CompanyProfile>()
    getCompanyProfileMock.mockReturnValue(pendingResponse.promise)

    const wrapper = mount(RiskWorkbench)
    await flushPromises()

    const submitButton = wrapper.find('button[type="submit"]')
    expect(submitButton.attributes('disabled')).toBeDefined()
    expect(submitButton.text()).toContain('搜索中')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(getCompanyProfileMock).toHaveBeenCalledTimes(1)

    pendingResponse.resolve(makeProfile(DEFAULT_COMPANY_NAME))
    await flushPromises()
  })

  it('lets a different real search supersede a slow loading request and renders the newer company', async () => {
    const slowResponse = deferred<CompanyProfile>()
    getCompanyProfileMock.mockImplementation(async (query) => {
      if (query === DEFAULT_COMPANY_NAME) {
        return slowResponse.promise
      }

      return makeProfile(String(query), [investmentEdge])
    })

    const wrapper = mount(RiskWorkbench)
    await wrapper.vm.$nextTick()

    await wrapper.find('input[type="search"]').setValue('快速企业')
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeUndefined()

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(getCompanyProfileMock).toHaveBeenCalledTimes(2)
    expect(getCompanyProfileMock).toHaveBeenLastCalledWith('快速企业')
    expect(wrapper.text()).toContain('快速企业')

    slowResponse.resolve(makeProfile('慢速企业', [riskEdge]))
    await flushPromises()

    expect(wrapper.text()).toContain('快速企业')
    expect(wrapper.text()).not.toContain('慢速企业')
  })

  it('ignores duplicate same-query search emissions while loading', async () => {
    const pendingResponse = deferred<CompanyProfile>()
    getCompanyProfileMock.mockReturnValue(pendingResponse.promise)

    const wrapper = await mountWorkbenchWithSearchEmitter()

    wrapper.findComponent({ name: 'CompanySearch' }).vm.$emit('search', DEFAULT_COMPANY_NAME)
    await flushPromises()

    expect(getCompanyProfileMock).toHaveBeenCalledTimes(1)

    pendingResponse.resolve(makeProfile(DEFAULT_COMPANY_NAME))
    await flushPromises()
  })

  it('shows an evidence empty state when the model has no evidence', async () => {
    const wrapper = await mountWorkbench()

    expect(wrapper.text()).toContain('暂无可展示证据。')
    expect(wrapper.text()).not.toContain('当前样例数据')
  })

  it('shows source, date, and confidence metadata for evidence', async () => {
    getCompanyProfileMock.mockResolvedValue(makeProfile(DEFAULT_COMPANY_NAME, [riskEdge]))

    const wrapper = await mountWorkbench()
    const evidenceList = wrapper.find('[data-testid="evidence-list"]')

    expect(evidenceList.text()).toContain('涉及风险事件')
    expect(evidenceList.text()).toContain(`${DEFAULT_COMPANY_NAME}被报道涉及异常担保。`)
    expect(evidenceList.text()).toContain('来源：图谱来源')
    expect(evidenceList.text()).not.toContain('doc-risk')
    expect(evidenceList.text()).toContain('日期：2024-05-01')
    expect(evidenceList.text()).toContain('置信度：92%')
  })

  it('filters visible paths and evidence after factor selection and can clear the selection', async () => {
    getCompanyProfileMock.mockResolvedValue(makeProfile(DEFAULT_COMPANY_NAME, [riskEdge, investmentEdge]))

    const wrapper = await mountWorkbench()

    expect(wrapper.findAll('[data-testid="path-row"]')).toHaveLength(2)
    expect(wrapper.find('[data-testid="evidence-list"]').text()).toContain('投资')

    const riskFactor = wrapper.findAll('button.risk-factor').find((button) => button.text().includes('涉及风险事件'))
    expect(riskFactor).toBeTruthy()
    await riskFactor!.trigger('click')

    expect(wrapper.text()).toContain('已筛选 1 条相关关系')
    expect(wrapper.find('.risk-factor-selected').text()).toContain('涉及风险事件')
    expect(wrapper.findAll('[data-testid="path-row"]')).toHaveLength(1)
    expect(wrapper.find('[data-testid="path-list"]').text()).toContain(`${DEFAULT_COMPANY_NAME} -> 异常担保事件`)
    expect(wrapper.find('[data-testid="path-list"]').text()).not.toContain('B轮融资事件')
    expect(wrapper.find('[data-testid="evidence-list"]').text()).toContain('涉及风险事件')
    expect(wrapper.find('[data-testid="evidence-list"]').text()).not.toContain('投资')

    await wrapper.find('[data-testid="clear-relation-filter"]').trigger('click')

    expect(wrapper.text()).not.toContain('已筛选 1 条相关关系')
    expect(wrapper.findAll('[data-testid="path-row"]')).toHaveLength(2)
    expect(wrapper.find('[data-testid="evidence-list"]').text()).toContain('投资')
  })

  it('filters graph edges by relation type and shows selected edge evidence', async () => {
    getCompanyProfileMock.mockResolvedValue(makeProfile(DEFAULT_COMPANY_NAME, [riskEdge, investmentEdge]))

    const wrapper = await mountWorkbench()

    const graph = wrapper.findComponent({ name: 'RiskGraphCanvas' })
    expect(graph.props('edges')).toHaveLength(2)
    expect(wrapper.text()).toContain('关系图谱')
    expect(wrapper.text()).toContain('风险事件')
    expect(wrapper.text()).toContain('投资')

    await wrapper.findAll('.relation-filter-bar button').find((button) => button.text().includes('风险事件'))!.trigger('click')

    expect(wrapper.findComponent({ name: 'RiskGraphCanvas' }).props('edges')).toHaveLength(1)
    expect(wrapper.findComponent({ name: 'RiskGraphCanvas' }).text()).toContain('风险事件')
    expect(wrapper.findComponent({ name: 'RiskGraphCanvas' }).text()).not.toContain('投资')

    wrapper.findComponent({ name: 'RiskGraphCanvas' }).vm.$emit('select-edge', riskEdge)
    await flushPromises()

    expect(wrapper.text()).toContain('选中关系证据')
    expect(wrapper.find('[data-testid="evidence-list"]').text()).toContain('风险事件')
    expect(wrapper.find('[data-testid="evidence-list"]').text()).not.toContain('披露完成融资。')
  })

  it('applies depth filtering to graph paths and evidence', async () => {
    getCompanyProfileMock.mockResolvedValue(makeProfile(DEFAULT_COMPANY_NAME, [investmentEdge, secondHopEdge]))

    const wrapper = await mountWorkbench()

    expect(wrapper.findComponent({ name: 'RiskGraphCanvas' }).props('edges')).toHaveLength(2)
    expect(wrapper.find('[data-testid="path-list"]').text()).toContain('关联企业')
    expect(wrapper.find('[data-testid="evidence-list"]').text()).toContain('融资事件关联到下游企业。')

    await wrapper.find('.relation-filter-bar select').setValue('1')

    expect(wrapper.findComponent({ name: 'RiskGraphCanvas' }).props('edges')).toHaveLength(1)
    expect(wrapper.findComponent({ name: 'RiskGraphCanvas' }).props('nodes')).not.toEqual(expect.arrayContaining([
      expect.objectContaining({ id: 'affiliate_company' })
    ]))
    expect(wrapper.find('[data-testid="path-list"]').text()).not.toContain('关联企业')
    expect(wrapper.find('[data-testid="evidence-list"]').text()).not.toContain('融资事件关联到下游企业。')
  })

  it('folds long path lists and keeps them expandable', async () => {
    const extraEdges = Array.from({ length: 7 }, (_, index): GraphEdge => ({
      ...investmentEdge,
      id: `rel_extra_${index}`,
      target: index % 2 === 0 ? 'investment_event' : 'affiliate_company',
      label: `补充路径${index + 1}`
    }))
    getCompanyProfileMock.mockResolvedValue(makeProfile(DEFAULT_COMPANY_NAME, [investmentEdge, secondHopEdge, ...extraEdges]))

    const wrapper = await mountWorkbench()

    expect(wrapper.findAll('[data-testid="path-row"]')).toHaveLength(5)
    expect(wrapper.find('[data-testid="path-list-toggle"]').text()).toContain('展开全部')

    await wrapper.find('[data-testid="path-list-toggle"]').trigger('click')

    expect(wrapper.findAll('[data-testid="path-row"]').length).toBeGreaterThan(5)
    expect(wrapper.find('[data-testid="path-list-toggle"]').text()).toContain('收起路径列表')
  })

  it('saves the current company to the watchlist from the workbench', async () => {
    getCompanyProfileMock.mockResolvedValue(makeProfile(DEFAULT_COMPANY_NAME, [riskEdge]))

    const wrapper = await mountWorkbench()

    await wrapper.findAll('button').find((button) => button.text() === '加入关注')!.trigger('click')

    expect(loadWatchlist()).toEqual([
      expect.objectContaining({
        companyName: DEFAULT_COMPANY_NAME,
        industry: '金融科技',
        riskLevel: 'high'
      })
    ])
  })

  it('saves a due diligence report from quick actions', async () => {
    getCompanyProfileMock.mockResolvedValue(makeProfile(DEFAULT_COMPANY_NAME, [riskEdge]))

    const wrapper = await mountWorkbench()

    await wrapper.findAll('button').find((button) => button.text() === '保存报告')!.trigger('click')

    expect(loadReports()).toEqual([
      expect.objectContaining({
        companyName: DEFAULT_COMPANY_NAME,
        riskLevel: 'high',
        factors: expect.arrayContaining([
          expect.objectContaining({ title: expect.stringContaining('风险事件') })
        ]),
        evidence: expect.arrayContaining([
          expect.objectContaining({ title: expect.stringContaining('风险事件') })
        ])
      })
    ])
    const [report] = loadReports()
    expect(report.factors[0]).not.toHaveProperty('id')
    expect(report.factors[0]).not.toHaveProperty('relationIds')
    expect(report.evidence[0]).not.toHaveProperty('id')
    expect(report.evidence[0]).not.toHaveProperty('relationId')
  })

  it('creates distinct report IDs for rapid repeated saves', async () => {
    const dateNowSpy = vi.spyOn(Date, 'now').mockReturnValue(1779917219908)
    getCompanyProfileMock.mockResolvedValue(makeProfile(DEFAULT_COMPANY_NAME, [riskEdge]))

    const wrapper = await mountWorkbench()
    const saveButton = wrapper.findAll('button').find((button) => button.text() === '保存报告')!

    await saveButton.trigger('click')
    await saveButton.trigger('click')

    const reports = loadReports()
    expect(reports).toHaveLength(2)
    expect(new Set(reports.map((report) => report.id)).size).toBe(2)

    dateNowSpy.mockRestore()
  })

  it('does not let a slow older response overwrite a faster later search result', async () => {
    const slowResponse = deferred<CompanyProfile>()
    getCompanyProfileMock.mockImplementation(async (query) => {
      if (query === DEFAULT_COMPANY_NAME) {
        return slowResponse.promise
      }

      return makeProfile(String(query), [investmentEdge])
    })

    const wrapper = await mountWorkbenchWithSearchEmitter()

    const search = wrapper.findComponent({ name: 'CompanySearch' })
    search.vm.$emit('update:modelValue', '快速企业')
    search.vm.$emit('search', '快速企业')
    await flushPromises()

    expect(wrapper.text()).toContain('快速企业')

    slowResponse.resolve(makeProfile('慢速企业', [riskEdge]))
    await flushPromises()

    expect(wrapper.text()).toContain('快速企业')
    expect(wrapper.text()).not.toContain('慢速企业')
  })
})
