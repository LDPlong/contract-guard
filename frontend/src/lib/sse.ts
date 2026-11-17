import { ApiError } from '@/api/http'

/**
 * POST SSE 流的共用实现。
 *
 * 契约是 POST，原生 EventSource 只支持 GET，所以必须 fetch + ReadableStream
 * 手动解析 SSE 帧。审查流与答疑流共用这一份，避免两处拷贝漂移。
 *
 * 帧分隔兼容 LF（\n\n）与 CRLF（\r\n\r\n）两种行尾。
 */
function parseFrame<F extends { event: string }>(block: string): F | null {
  let event = ''
  const dataLines: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!event || dataLines.length === 0) return null
  try {
    return { event, data: JSON.parse(dataLines.join('')) } as unknown as F
  } catch {
    return null
  }
}

export async function* sseStream<F extends { event: string }>(
  url: string,
  init: RequestInit,
  failLabel: string,
): AsyncGenerator<F> {
  const resp = await fetch(url, {
    ...init,
    headers: {
      Accept: 'text/event-stream',
      ...(init.headers as Record<string, string> | undefined),
    },
  })

  if (!resp.ok || !resp.body) {
    let message = `${failLabel}（${resp.status}）`
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
      // CRLF 统一折成 LF，帧分隔就只需要找 \n\n
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')

      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        const frame = parseFrame<F>(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
        if (frame) yield frame
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    reader.releaseLock()
  }
}
