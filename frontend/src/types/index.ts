/**
 * 与后端 schema 一一对应的类型（文档 8 节接口契约）。
 * 改动此处必须同步改 backend/app/schemas/，禁止前端私自扩展字段。
 */

export interface Envelope<T> {
  code: number
  message: string
  data: T
}

export type ContractType = 'lease' | 'labor' | 'prepaid' | 'unknown'
export type RiskLevel = 'high' | 'medium' | 'low' | 'none'
export type DocumentStatus = 'uploaded' | 'parsing' | 'parsed' | 'failed'
export type ReviewStatus = 'pending' | 'running' | 'done' | 'partial' | 'failed'

/** 8.10 健康检查（不走 Envelope 包装） */
export interface HealthStatus {
  status: 'ok' | 'degraded'
  db: boolean
  vector: boolean
  index_built: boolean
  embedding_dim: number | null
  llm: boolean
  ocr_enabled: boolean
  demo_mode: boolean
  env: string
}

/** 8.1 上传响应 */
export interface UploadResult {
  document_id: string
  status: DocumentStatus
  contract_type: ContractType
  type_source: 'rule' | 'llm' | 'user' | 'unknown'
  page_count: number
  clause_count: number
}

export interface PageInfo {
  page_no: number
  width: number
  height: number
}

/**
 * bbox 约定（文档 9.2）：PDF point、左上原点、y 向下、绝对坐标 [x0,y0,x1,y1]。
 * 前端换算一律用 viewport.convertToViewportRectangle()，不要自己乘 scale。
 */
export interface Clause {
  id: string
  seq: number
  clause_no: string | null
  page_no: number
  bbox: [number, number, number, number] | null
  text: string
}

/** 8.2 文档详情 */
export interface DocumentDetail {
  id: string
  filename: string
  contract_type: ContractType
  status: DocumentStatus
  pages: PageInfo[]
  clauses: Clause[]
}

export interface LegalBasis {
  source: string
  article: string
  quote: string
  chunk_id: string
}

/** 8.5 结论 */
export interface Finding {
  id: string
  clause_id: string | null
  /** 条款编号，SSE 与回查接口都会带；缺失时为 null */
  clause_no?: string | null
  risk_level: RiskLevel
  category: string
  title: string
  reason: string
  legal_basis: LegalBasis[]
  /** 修改方向说明，非可直接签署的条文（文档 1.2） */
  suggestion: string
  negotiation_tip: string | null
  confidence: number
}

/** 8.5 审查结果 */
export interface ReviewDetail {
  id: string
  document_id: string
  status: ReviewStatus
  /** 0-100，越高越安全 */
  safety_score: number | null
  summary: string | null
  checklist_version: string
  findings: Finding[]
}

/** 8.6 历史列表项 */
export interface DocumentListItem {
  document_id: string
  filename: string
  contract_type: ContractType
  safety_score: number | null
  status: ReviewStatus
  created_at: string
}

/** SSE 事件（文档 8.4） */
export type StreamStep = 'plan' | 'gate' | 'retrieve' | 'judge' | 'aggregate' | 'persist'

export interface StreamEvent {
  event: 'step' | 'finding' | 'progress' | 'done' | 'error'
  data: Record<string, unknown>
}
