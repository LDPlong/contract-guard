import { ApiError, getSessionId } from '@/api/http'
import type { AssistantEvent, LawRef } from '@/types'

const ASK_ENDPOINT = '/api/v1/assistant/ask'

function parseFrame(block: string): AssistantEvent | null {
  let event = ''
  const dataLines: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!event || dataLines.length === 0) return null
  try {
    return { event: event as AssistantEvent['event'], data: JSON.parse(dataLines.join('')) }
  } catch {
    return null
  }
}

/**
 * 答疑流：refs（检索到的法条）→ answer（回答）。
 * 与审查流同一套 SSE 解析方式，契约是 POST，不能用 EventSource。
 */
export async function* askAssistant(
  question: string,
  context = '',
  signal?: AbortSignal,
): AsyncGenerator<AssistantEvent> {
  const resp = await fetch(ASK_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Session-Id': getSessionId(),
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({ question, context }),
    signal,
  })

  if (!resp.ok || !resp.body) {
    let message = `答疑请求失败（${resp.status}）`
    try {
      const body = await resp.json()
      if (body?.message) message = body.message
    } catch {
      /* 保持默认文案 */
    }
    throw new ApiError(resp.status, message)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const frame = parseFrame(block)
        if (frame) yield frame
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export type { LawRef }
