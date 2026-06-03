import { apiGet } from './client'

export interface KlinePoint {
  date: string
  open: number
  close: number
  high: number
  low: number
  volume: number
  amount: number
}

export interface MarketEvent {
  date: string
  label: string
  event_type?: string
  round?: string
  amount?: string
  description?: string
  source?: string
}

export interface KlineResponse {
  stock_code: string
  market: string
  display_code: string
  company_name: string
  period: string
  adjust: string
  cached: boolean
  cache_status?: string
  cache_layer?: string
  data_source: string
  start_date?: string | null
  end_date?: string | null
  kline_data: KlinePoint[]
  events: MarketEvent[]
  source_errors?: string[]
}

export function getKline(stockCode: string, market = 'A', period = 'daily', companyName = '') {
  const params = new URLSearchParams({ market, period })
  if (companyName.trim()) {
    params.set('company_name', companyName.trim())
  }

  return apiGet<KlineResponse>(`/market/kline/${encodeURIComponent(stockCode)}?${params.toString()}`)
}
