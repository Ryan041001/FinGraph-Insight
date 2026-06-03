import { apiPost, apiPostSse } from './client'

export interface StockAnalysisRequest {
  stockCode: string
  companyName: string
  refreshNews?: boolean
  useLlm?: boolean
}

export function analyzeStock({ stockCode, companyName, refreshNews = false, useLlm = false }: StockAnalysisRequest) {
  return apiPost<Record<string, unknown>>('/analysis/stock', stockAnalysisBody({ stockCode, companyName, refreshNews, useLlm }))
}

export interface StockAnalysisStreamHandlers {
  onMetadata?: (metadata: Record<string, unknown>) => void
  onStatus?: (status: Record<string, unknown>) => void
  onNewsEvent?: (event: Record<string, unknown>) => void
  onSubgraph?: (subgraph: Record<string, unknown>) => void
  onAnalysis?: (analysis: Record<string, unknown>) => void
  onDone?: (result: Record<string, unknown>) => void
  onError?: (message: string) => void
  onPing?: () => void
}

export function streamStockAnalysis(
  request: StockAnalysisRequest,
  handlers: StockAnalysisStreamHandlers
) {
  return apiPostSse('/analysis/stock/stream', stockAnalysisBody(request), (event, data) => {
    const payload = isRecord(data) ? data : {}
    if (event === 'metadata') {
      handlers.onMetadata?.(payload)
    } else if (event === 'status') {
      handlers.onStatus?.(payload)
    } else if (event === 'news_event') {
      const newsEvent = isRecord(payload.event) ? payload.event : payload
      handlers.onNewsEvent?.(newsEvent)
    } else if (event === 'subgraph') {
      handlers.onSubgraph?.(isRecord(payload.subgraph) ? payload.subgraph : payload)
    } else if (event === 'analysis') {
      handlers.onAnalysis?.(isRecord(payload.analysis) ? payload.analysis : payload)
    } else if (event === 'done') {
      handlers.onDone?.(payload)
    } else if (event === 'error') {
      handlers.onError?.(stringField(payload.message, '证据线索研判暂不可用，请稍后重试。'))
    } else if (event === 'ping') {
      handlers.onPing?.()
    }
  })
}

function stockAnalysisBody({ stockCode, companyName, refreshNews = false, useLlm = false }: StockAnalysisRequest) {
  return {
    stock_code: stockCode,
    company_name: companyName,
    depth: 2,
    news_window_days: 30,
    refresh_news: refreshNews,
    use_llm: useLlm,
    enrich_fundamentals: true,
    market: 'A'
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function stringField(value: unknown, fallback = '') {
  return typeof value === 'string' ? value : fallback
}
