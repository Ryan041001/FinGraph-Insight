export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly payload: unknown
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`)
  if (!response.ok) {
    throw await buildApiError(response)
  }
  return parseJsonResponse<T>(response)
}

export async function apiPost<T>(path: string, body: unknown = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!response.ok) {
    throw await buildApiError(response)
  }
  return parseJsonResponse<T>(response)
}

export async function apiPostSse(
  path: string,
  body: unknown,
  onEvent: (event: string, data: unknown) => void
): Promise<void> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!response.ok) {
    throw await buildApiError(response)
  }
  if (!response.body) {
    throw new ApiError('服务未返回可读取的数据流', response.status, null)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split(/\r?\n\r?\n/)
    buffer = parts.pop() ?? ''
    for (const part of parts) {
      emitSsePart(part, onEvent)
    }
  }

  buffer += decoder.decode()
  if (buffer.trim()) {
    emitSsePart(buffer, onEvent)
  }
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const text = await response.text()
  return repairMojibake(JSON.parse(text)) as T
}

function repairMojibake(value: unknown): unknown {
  if (typeof value === 'string') {
    return repairString(value)
  }
  if (Array.isArray(value)) {
    return value.map((item) => repairMojibake(item))
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, repairMojibake(item)])
    )
  }
  return value
}

function emitSsePart(part: string, onEvent: (event: string, data: unknown) => void) {
  const lines = part.split(/\r?\n/)
  let event = 'message'
  const dataLines: string[] = []
  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart())
    }
  }

  if (dataLines.length === 0) {
    return
  }

  const dataText = dataLines.join('\n')
  try {
    onEvent(event, repairMojibake(JSON.parse(dataText)))
  } catch {
    onEvent(event, repairMojibake(dataText))
  }
}

function repairString(value: string): string {
  if (!/[ÃÂÐÑåæçèéäöï¼]/.test(value)) {
    return value
  }

  try {
    const bytes = Uint8Array.from(Array.from(value, (char) => char.charCodeAt(0) & 0xff))
    const repaired = new TextDecoder('utf-8', { fatal: false }).decode(bytes)
    return repaired.includes('\uFFFD') ? value : repaired
  } catch {
    return value
  }
}

async function buildApiError(response: Response): Promise<ApiError> {
  const text = await response.text()
  let payload: unknown = text

  try {
    payload = JSON.parse(text)
  } catch {
    payload = text
  }

  return new ApiError(pickErrorMessage(payload), response.status, payload)
}

function pickErrorMessage(payload: unknown): string {
  if (!payload || typeof payload !== 'object') {
    return typeof payload === 'string' && payload ? payload : '请求失败'
  }

  const record = payload as Record<string, unknown>
  const detail = record.detail
  if (detail && typeof detail === 'object') {
    const message = (detail as Record<string, unknown>).message
    if (typeof message === 'string' && message) {
      return message
    }
  }

  if (typeof record.message === 'string' && record.message) {
    return record.message
  }

  const fields = record.fields
  if (Array.isArray(fields) && fields.length > 0) {
    const firstMessage = (fields[0] as Record<string, unknown>).message
    if (typeof firstMessage === 'string' && firstMessage) {
      return firstMessage
    }
  }

  return '请求失败'
}
