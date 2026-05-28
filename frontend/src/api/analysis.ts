import { apiPost } from './client'

export function analyzeStock(stockCode: string, companyName: string) {
  return apiPost<Record<string, unknown>>('/analysis/stock', {
    stock_code: stockCode,
    company_name: companyName,
    depth: 2,
    news_window_days: 30,
    refresh_news: false
  })
}
