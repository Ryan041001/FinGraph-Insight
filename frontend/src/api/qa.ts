import { apiPost } from './client'
import type { GraphRagResponse, Text2CypherResponse } from './types'

export function askGraphRag(question: string) {
  return apiPost<GraphRagResponse>('/qa/graph-rag', { question })
}

export function askText2Cypher(question: string) {
  return apiPost<Text2CypherResponse>('/qa/text2cypher', { question })
}
