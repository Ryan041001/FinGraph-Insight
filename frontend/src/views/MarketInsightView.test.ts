import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { analyzeStock } from '../api/analysis'
import { getKline } from '../api/market'
import MarketInsightView from './MarketInsightView.vue'

vi.mock('../api/analysis', () => ({
  analyzeStock: vi.fn()
}))

vi.mock('../api/market', () => ({
  getKline: vi.fn()
}))

const analyzeStockMock = vi.mocked(analyzeStock)
const getKlineMock = vi.mocked(getKline)

const baseKline = {
  stock_code: '600000',
  market: 'A',
  display_code: '600000.SH',
  company_name: '浦发银行',
  period: 'daily',
  adjust: 'qfq',
  cached: false,
  data_source: 'akshare',
  kline_data: [
    { date: '2026-05-28', open: 10, close: 10.5, high: 11, low: 9.8, volume: 1000, amount: 10000 },
    { date: '2026-05-29', open: 10.5, close: 10.8, high: 11.2, low: 10.2, volume: 1200, amount: 12000 }
  ],
  events: []
}

function analysisPayload(overrides: Record<string, unknown> = {}) {
  return {
    target: { stock_code: '600000', company_name: '浦发银行' },
    fundamentals: { industry: '银行', data_time: 'live' },
    news_events: [],
    subgraph: { nodes: [], edges: [] },
    analysis: {
      summary: '基于图谱和基本面生成摘要。',
      opportunity_factors: [],
      risk_factors: [],
      graph_insights: [],
      confidence: 0.72,
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

async function mountMarketView() {
  const wrapper = mount(MarketInsightView)
  await flushPromises()

  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  getKlineMock.mockResolvedValue(baseKline)
  analyzeStockMock.mockResolvedValue(analysisPayload())
})

describe('MarketInsightView', () => {
  it('renders kline data while the initial analysis request is still pending', async () => {
    const pendingAnalysis = deferred<Record<string, unknown>>()
    analyzeStockMock.mockReturnValue(pendingAnalysis.promise)

    const wrapper = mount(MarketInsightView)
    await flushPromises()

    expect(wrapper.text()).toContain('K 线数量')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('正在生成研判...')

    pendingAnalysis.resolve(analysisPayload())
    await flushPromises()

    expect(wrapper.text()).toContain('基于图谱和基本面生成摘要。')
  })

  it('loads the initial local graph analysis without refreshing realtime news', async () => {
    const wrapper = await mountMarketView()

    expect(getKlineMock).toHaveBeenCalledWith('600000', 'A', 'daily', '浦发银行')
    expect(analyzeStockMock).toHaveBeenCalledWith({
      stockCode: '600000',
      companyName: '浦发银行',
      refreshNews: false,
      useLlm: false
    })
    expect(wrapper.find('[data-testid="news-status"]').text()).toContain('本地图谱事件')
    expect(wrapper.find('[data-testid="news-status-detail"]').text()).toContain('尚未请求实时新闻')
  })

  it('renders OHLC candlesticks from valid kline points', async () => {
    const wrapper = await mountMarketView()

    expect(wrapper.find('[data-testid="candlestick-chart"]').exists()).toBe(true)
    expect(wrapper.findAll('.candle')).toHaveLength(2)
    expect(wrapper.text()).toContain('K 线蜡烛图')
  })

  it('filters invalid OHLC points before scaling the candlestick chart', async () => {
    getKlineMock.mockResolvedValue({
      ...baseKline,
      kline_data: [
        ...baseKline.kline_data,
        { date: '2026-06-01', open: 10.8, close: 0, high: 11, low: 10.6, volume: 1300, amount: 13000 },
        { date: '2026-06-02', open: 10.9, close: 11.1, high: 10.8, low: 10.7, volume: 1400, amount: 14000 }
      ]
    })

    const wrapper = await mountMarketView()

    expect(wrapper.findAll('.candle')).toHaveLength(2)
    expect(wrapper.find('[data-testid="kline-filter-note"]').text()).toContain('已过滤 2 条异常行情点')
    expect(wrapper.text()).toContain('2')
  })

  it('requests realtime news when running model-enhanced analysis and shows supplement status', async () => {
    analyzeStockMock
      .mockResolvedValueOnce(analysisPayload())
      .mockResolvedValueOnce(analysisPayload({
        news_events: [
          {
            event_type: 'announcement',
            sentiment: 'neutral',
            title: '浦发银行发布经营动态',
            date: '2026-05-29',
            source_url: 'https://example.com/news',
            evidence: '公开新闻摘要'
          }
        ],
        analysis: {
          summary: '结合实时新闻后的模型增强摘要。',
          opportunity_factors: [],
          risk_factors: [],
          graph_insights: [],
          confidence: 0.81,
          missing_data: [],
          disclaimer: '本结果仅用于研究辅助，不构成投资建议。'
        }
      }))

    const wrapper = await mountMarketView()

    await wrapper.findAll('button').find((button) => button.text().includes('模型增强 + 实时新闻'))!.trigger('click')
    await flushPromises()

    expect(analyzeStockMock).toHaveBeenLastCalledWith({
      stockCode: '600000',
      companyName: '浦发银行',
      refreshNews: true,
      useLlm: true
    })
    expect(wrapper.find('[data-testid="news-status"]').text()).toContain('实时新闻 1 条')
    expect(wrapper.find('[data-testid="news-status-detail"]').text()).toContain('已请求实时新闻补充')
    expect(wrapper.text()).toContain('结合实时新闻后的模型增强摘要。')
  })

  it('shows a clear fallback state when realtime news supplement is unavailable', async () => {
    analyzeStockMock
      .mockResolvedValueOnce(analysisPayload())
      .mockResolvedValueOnce(analysisPayload({
        analysis: {
          summary: '新闻失败后使用本地图谱摘要。',
          opportunity_factors: [],
          risk_factors: [],
          graph_insights: [],
          confidence: 0.62,
          missing_data: ['新闻补充暂不可用，已使用本地图谱事件：timeout'],
          disclaimer: '本结果仅用于研究辅助，不构成投资建议。'
        }
      }))

    const wrapper = await mountMarketView()

    await wrapper.findAll('button').find((button) => button.text().includes('模型增强 + 实时新闻'))!.trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="news-status"]').text()).toContain('实时新闻回退')
    expect(wrapper.find('[data-testid="news-status-detail"]').text()).toContain('新闻补充暂不可用')
  })
})
