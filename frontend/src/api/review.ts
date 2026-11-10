import http, { ApiError, getSessionId, request } from '@/api/http'
import type { DocumentDetail, HealthStatus, ReviewDetail, StreamEvent, UploadResult } from '@/types'

/** 8.10 健康检查：返回裸 JSON，没有 {code,message,data} 信封，不能走 request() */
export async function fetchHealth(): Promise<HealthStatus> {
  const resp = await http.get('/health', { timeout: 8000 })
  return resp.data as HealthStatus
}

/** 8.1 上传合同 */
export async function uploadDocument(
  file: File,
  contractType?: string,
): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  if (contractType) form.append('contract_type', contractType)
  return request<UploadResult>({
    url: '/documents',
    method: 'POST',
    data: form,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30_000,
  })
}

/** 8.2 文档详情（含条款与 bbox） */
export async function fetchDocument(documentId: string): Promise<DocumentDetail> {
  return request<DocumentDetail>({ url: `/documents/${documentId}`, method: 'GET' })
}

/** 8.5 审查结果 */
export async function fetchReview(reviewId: string): Promise<ReviewDetail> {
  return request<ReviewDetail>({ url: `/reviews/${reviewId}`, method: 'GET' })
}

/**
 * 8.3 原始 PDF，交给 pdf.js 渲染。
 * 注意：该接口返回二进制流，**不套 {code,message,data} 信封**，
 * 不能走 request() 统一解包，否则会把 ArrayBuffer 当成响应体去读 .code 而误抛错。
 */
export async function fetchDocumentFile(documentId: string): Promise<ArrayBuffer> {
  const resp = await http.get(`/documents/${documentId}/file`, {
    responseType: 'arraybuffer',
    timeout: 60_000,
  })
  return resp.data as ArrayBuffer
}

export const SSE_ENDPOINT = (documentId: string) => `/api/v1/documents/${documentId}/review`

function parseFrame(block: string): StreamEvent | null {
  let event = ''
  const dataLines: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!event || dataLines.length === 0) return null
  try {
    return { event: event as StreamEvent['event'], data: JSON.parse(dataLines.join('')) }
  } catch {
    return null
  }
}

/**
 * 8.3 审查流。
 * 契约是 POST，原生 EventSource 只支持 GET，所以必须 fetch + ReadableStream
 * 手动解析 SSE 帧（文档 3.1 明令禁止 EventSource）。
 */
export async function* streamReview(
  documentId: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  const resp = await fetch(SSE_ENDPOINT(documentId), {
    method: 'POST',
    headers: {
      'X-Session-Id': getSessionId(),
      Accept: 'text/event-stream',
    },
    signal,
  })

  if (!resp.ok || !resp.body) {
    let message = `审查请求失败（${resp.status}）`
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
