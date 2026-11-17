import { getSessionId } from '@/api/http'
import { sseStream } from '@/lib/sse'
import type { AssistantEvent, LawRef } from '@/types'

const ASK_ENDPOINT = '/api/v1/assistant/ask'

/**
 * 答疑流：refs（检索到的法条）→ answer（回答）。
 * 帧解析共用 lib/sse.ts，契约是 POST，不能用 EventSource。
 */
export async function* askAssistant(
  question: string,
  context = '',
  signal?: AbortSignal,
): AsyncGenerator<AssistantEvent> {
  yield* sseStream<AssistantEvent>(
    ASK_ENDPOINT,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Id': getSessionId(),
      },
      body: JSON.stringify({ question, context }),
      signal,
    },
    '答疑请求失败',
  )
}

export type { LawRef }
