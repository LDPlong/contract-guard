import http, { getSessionId, request } from '@/api/http'
import { sseStream } from '@/lib/sse'
import type {
  DocumentDetail,
  DocumentListItem,
  HealthStatus,
  ReviewDetail,
  StreamEvent,
  UploadResult,
} from '@/types'

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

/** 8.1 文档列表：本会话审查过的合同，供顶栏「我的审查」下拉使用 */
export async function listDocuments(): Promise<DocumentListItem[]> {
  return request<DocumentListItem[]>({ url: '/documents', method: 'GET' })
}

/** 8.2 文档详情（含条款与 bbox） */
export async function fetchDocument(documentId: string): Promise<DocumentDetail> {
  return request<DocumentDetail>({ url: `/documents/${documentId}`, method: 'GET' })
}

/** 8.5 审查结果 */
export async function fetchReview(reviewId: string): Promise<ReviewDetail> {
  return request<ReviewDetail>({ url: `/reviews/${reviewId}`, method: 'GET' })
}

/** 文档的历史审查记录：进入页面时用它判断有没有现成结果可回看 */
export async function listDocumentReviews(
  documentId: string,
): Promise<{ review_id: string; status: string; safety_score: number | null; started_at: string | null }[]> {
  return request({
    url: `/documents/${documentId}/reviews`,
    method: 'GET',
  })
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

/**
 * 8.3 审查流。帧解析共用 lib/sse.ts（文档 3.1 明令禁止 EventSource）。
 */
export async function* streamReview(
  documentId: string,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent> {
  yield* sseStream<StreamEvent>(
    SSE_ENDPOINT(documentId),
    {
      method: 'POST',
      headers: {
        'X-Session-Id': getSessionId(),
      },
      signal,
    },
    '审查请求失败',
  )
}
