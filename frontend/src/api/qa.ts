import { apiPost, apiPostSse } from './client'
import type { GraphRagResponse, Text2CypherResponse, UnifiedQaResponse } from './types'

export function askGraphRag(question: string) {
  return apiPost<GraphRagResponse>('/qa/graph-rag', { question })
}

export function askText2Cypher(question: string) {
  return apiPost<Text2CypherResponse>('/qa/text2cypher', { question })
}

export function askUnifiedQa(payload: { question: string; entity?: string; companyName?: string }) {
  return apiPost<UnifiedQaResponse>('/qa/unified', {
    question: payload.question,
    entity: payload.entity,
    company_name: payload.companyName
  })
}

export interface UnifiedQaStreamHandlers {
  onMetadata?: (metadata: Partial<UnifiedQaResponse>) => void
  onDelta?: (text: string) => void
  onDone?: (text: string) => void
  onError?: (message: string) => void
  onPing?: () => void
}

export function streamUnifiedQa(
  payload: { question: string; entity?: string; companyName?: string },
  handlers: UnifiedQaStreamHandlers
) {
  return apiPostSse(
    '/qa/unified/stream',
    {
      question: payload.question,
      entity: payload.entity,
      company_name: payload.companyName
    },
    (event, data) => {
      const payload = isRecord(data) ? data : {}
      if (event === 'metadata') {
        handlers.onMetadata?.(payload as Partial<UnifiedQaResponse>)
      } else if (event === 'delta') {
        handlers.onDelta?.(stringField(payload.text))
      } else if (event === 'done') {
        handlers.onDone?.(stringField(payload.text))
      } else if (event === 'error') {
        handlers.onError?.(stringField(payload.message, '问答生成失败，请稍后重试。'))
      } else if (event === 'ping') {
        handlers.onPing?.()
      }
    }
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function stringField(value: unknown, fallback = '') {
  return typeof value === 'string' ? value : fallback
}
