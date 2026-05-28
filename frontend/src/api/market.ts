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
  type: string
  label: string
  source_node_id: string
  source_text: string
}

export interface KlineResponse {
  stock_code: string
  market: string
  display_code: string
  company_name: string
  period: string
  adjust: string
  cached: boolean
  data_source: string
  kline_data: KlinePoint[]
  events: MarketEvent[]
}

export function getKline(stockCode: string, market = 'A', period = 'daily') {
  return apiGet<KlineResponse>(`/market/kline/${stockCode}?market=${market}&period=${period}`)
}
