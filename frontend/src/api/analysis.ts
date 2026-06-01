import { apiPost } from './client'

export interface StockAnalysisRequest {
  stockCode: string
  companyName: string
  refreshNews?: boolean
  useLlm?: boolean
}

export function analyzeStock({ stockCode, companyName, refreshNews = false, useLlm = false }: StockAnalysisRequest) {
  return apiPost<Record<string, unknown>>('/analysis/stock', {
    stock_code: stockCode,
    company_name: companyName,
    depth: 2,
    news_window_days: 30,
    refresh_news: refreshNews,
    use_llm: useLlm,
    enrich_fundamentals: true,
    market: 'A'
  })
}
