import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getCompanyProfile } from '../api/graph'
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
  getCompanyProfile: vi.fn()
}))

const DEFAULT_COMPANY_NAME = '浙江数科控股有限公司'

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
  getCompanyProfileMock.mockResolvedValue(makeProfile())
})

describe('RiskWorkbench', () => {
  it('loads a product-safe default company instead of sample wording', async () => {
    getCompanyProfileMock.mockImplementation(async (query) => makeProfile(String(query)))

    const wrapper = await mountWorkbench()

    expect(getCompanyProfileMock).toHaveBeenCalledWith(DEFAULT_COMPANY_NAME)
    expect(wrapper.text()).toContain(DEFAULT_COMPANY_NAME)
    expect(wrapper.text()).not.toContain('示例')
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

  it('disables duplicate same-query submit while a company analysis is loading', async () => {
    const pendingResponse = deferred<CompanyProfile>()
    getCompanyProfileMock.mockReturnValue(pendingResponse.promise)

    const wrapper = mount(RiskWorkbench)
    await flushPromises()

    const submitButton = wrapper.find('button[type="submit"]')
    expect(submitButton.attributes('disabled')).toBeDefined()
    expect(submitButton.text()).toContain('分析中')

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
    await flushPromises()

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

  it('saves a due diligence report from the workbench preview', async () => {
    getCompanyProfileMock.mockResolvedValue(makeProfile(DEFAULT_COMPANY_NAME, [riskEdge]))

    const wrapper = await mountWorkbench()

    await wrapper.findAll('button').find((button) => button.text() === '保存研判报告')!.trigger('click')

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
    const saveButton = wrapper.findAll('button').find((button) => button.text() === '保存研判报告')!

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
