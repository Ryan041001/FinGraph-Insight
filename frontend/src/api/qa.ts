import { apiPost } from './client'

export function askGraphRag(question: string) {
  return apiPost<Record<string, unknown>>('/qa/graph-rag', { question })
}

export function askText2Cypher(question: string) {
  return apiPost<Record<string, unknown>>('/qa/text2cypher', { question })
}
