import { request } from '@/api/http'
import type { DocumentDetail, HealthStatus, UploadResult } from '@/types'

/** 8.10 健康检查（不走 Envelope） */
export async function fetchHealth(): Promise<HealthStatus> {
  return request<HealthStatus>({ url: '/health', method: 'GET' })
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

/**
 * 8.4 SSE 审查流。
 * 契约是 POST，原生 EventSource 只支持 GET，因此必须用 fetch + ReadableStream
 * 手动解析 SSE 帧（文档 3.1 禁止事项）。实现放在 M4。
 */
export const SSE_ENDPOINT = (documentId: string) => `/api/v1/documents/${documentId}/review`
