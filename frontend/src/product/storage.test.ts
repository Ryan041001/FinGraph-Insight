import { describe, expect, it } from 'vitest'
import type { DueDiligenceReport, WatchlistItem } from './types'
import { loadReports, loadWatchlist, removeWatchlistItem, saveReport, saveWatchlistItem } from './storage'

const WATCHLIST_KEY = 'financial-risk-workbench-watchlist'
const REPORTS_KEY = 'financial-risk-workbench-reports'

const watchlistItem: WatchlistItem = {
  companyName: '示例科技',
  industry: '金融科技',
  riskLevel: 'low',
  summary: '当前样例数据暂未发现高风险路径',
  updatedAt: '2026-05-27T00:00:00.000Z'
}

const report: DueDiligenceReport = {
  id: 'report-demo',
  companyName: '示例科技',
  riskLevel: 'low',
  summary: '当前样例数据暂未发现高风险路径',
  factors: [],
  evidence: [],
  createdAt: '2026-05-27T00:00:00.000Z'
}

const invalidStoredShapes = [
  { label: 'null', value: null },
  { label: 'object', value: {} },
  { label: 'array with null', value: [null] },
  { label: 'array with empty objects', value: [{}, {}] }
]

describe('product storage', () => {
  it('saves one watchlist item per company name', () => {
    saveWatchlistItem(watchlistItem)
    saveWatchlistItem({ ...watchlistItem, industry: '软件服务' })

    expect(loadWatchlist()).toEqual([{ ...watchlistItem, industry: '软件服务' }])
  })

  it('removes a watchlist item by company name', () => {
    saveWatchlistItem(watchlistItem)
    removeWatchlistItem('示例科技')

    expect(loadWatchlist()).toEqual([])
  })

  it('stores reports newest first', () => {
    saveReport({ ...report, id: 'old', createdAt: '2026-05-26T00:00:00.000Z' })
    saveReport({ ...report, id: 'new', createdAt: '2026-05-27T00:00:00.000Z' })

    expect(loadReports().map((item) => item.id)).toEqual(['new', 'old'])
  })

  it('persists reports newest first when an older report is saved last', () => {
    saveReport({ ...report, id: 'new', createdAt: '2026-05-27T00:00:00.000Z' })
    saveReport({ ...report, id: 'old', createdAt: '2026-05-26T00:00:00.000Z' })

    const storedReports = JSON.parse(localStorage.getItem(REPORTS_KEY) ?? '[]') as DueDiligenceReport[]

    expect(loadReports().map((item) => item.id)).toEqual(['new', 'old'])
    expect(storedReports.map((item) => item.id)).toEqual(['new', 'old'])
  })

  it.each(['', '{malformed-json'])(
    'removes malformed watchlist storage and returns fallback for %j',
    (storedValue) => {
      localStorage.setItem(WATCHLIST_KEY, storedValue)

      expect(loadWatchlist()).toEqual([])
      expect(localStorage.getItem(WATCHLIST_KEY)).toBeNull()
    }
  )

  it.each(['', '{malformed-json'])(
    'removes malformed reports storage and returns fallback for %j',
    (storedValue) => {
      localStorage.setItem(REPORTS_KEY, storedValue)

      expect(loadReports()).toEqual([])
      expect(localStorage.getItem(REPORTS_KEY)).toBeNull()
    }
  )

  it.each(invalidStoredShapes)(
    'removes invalid watchlist storage shape: $label',
    ({ value }) => {
      localStorage.setItem(WATCHLIST_KEY, JSON.stringify(value))

      expect(loadWatchlist()).toEqual([])
      expect(localStorage.getItem(WATCHLIST_KEY)).toBeNull()
    }
  )

  it.each(invalidStoredShapes)(
    'removes invalid reports storage shape without crashing sort: $label',
    ({ value }) => {
      localStorage.setItem(REPORTS_KEY, JSON.stringify(value))

      expect(loadReports()).toEqual([])
      expect(localStorage.getItem(REPORTS_KEY)).toBeNull()
    }
  )

  it('removes persisted reports that still contain internal relation fields', () => {
    localStorage.setItem(REPORTS_KEY, JSON.stringify([{
      ...report,
      factors: [{
        id: 'factor-rel-risk',
        level: 'high',
        title: '存在风险事件',
        description: '建议复核。',
        relationIds: ['rel-risk']
      }],
      evidence: [{
        id: 'evidence-rel-risk',
        relationId: 'rel-risk',
        title: '风险事件',
        text: '公开证据。',
        source: '图谱来源',
        confidence: 0.92,
        date: '2024-05-01'
      }]
    }]))

    expect(loadReports()).toEqual([])
    expect(localStorage.getItem(REPORTS_KEY)).toBeNull()
  })
})
