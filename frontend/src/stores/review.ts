import { defineStore } from 'pinia'
import { fetchDocument, fetchReview, listDocumentReviews, streamReview } from '@/api/review'
import type { DocumentDetail, Finding, RiskLevel, StreamStep } from '@/types'

export type ReviewPhase = 'loading' | 'ready' | 'reviewing' | 'done' | 'error'

export interface TraceStep {
  key: StreamStep
  title: string
  detail: string
  status: 'pending' | 'running' | 'done' | 'error'
}

/** 审查固定四段：开始就全部列出，避免步骤条一段段往下长 */
export const STEP_ORDER: StreamStep[] = ['plan', 'gate', 'judge', 'aggregate']

const STEP_TITLES: Record<string, string> = {
  plan: '读取合同',
  gate: '匹配审查项',
  retrieve: '查询法条',
  judge: '逐条核对',
  aggregate: '汇总结果',
  persist: '保存结果',
}

const RISK_ORDER: Record<RiskLevel, number> = { high: 3, medium: 2, low: 1, none: 0 }

/** 进行中审查流的 AbortController：模块级，供 abortStream 使用 */
let streamAbort: AbortController | null = null

export const useReviewStore = defineStore('review', {
  state: () => ({
    documentId: '',
    document: null as DocumentDetail | null,
    phase: 'loading' as ReviewPhase,
    steps: [] as TraceStep[],
    findings: [] as Finding[],
    score: null as number | null,
    summary: '',
    stance: '',
    openQuestion: '',
    reviewId: null as string | null,
    error: '',
    progress: { done: 0, total: 0 },
    activeClauseId: null as string | null,
    elapsedMs: 0,
  }),

  getters: {
    isStreaming: (state) => state.phase === 'reviewing',
    highCount: (state) => state.findings.filter((f) => f.risk_level === 'high').length,
    pendingReview: (state) => state.findings.filter((f) => f.confidence < 0.6).length,
    highlightedClauses(state): Record<string, RiskLevel> {
      const map: Record<string, RiskLevel> = {}
      for (const f of state.findings) {
        if (!f.clause_id) continue
        const prev = map[f.clause_id]
        if (!prev || RISK_ORDER[f.risk_level] > RISK_ORDER[prev]) {
          map[f.clause_id] = f.risk_level
        }
      }
      return map
    },
  },

  actions: {
    /** 中断进行中的 SSE 流：切文档/离开页面时防止晚到的帧写进新状态 */
    abortStream() {
      if (streamAbort) {
        streamAbort.abort()
        streamAbort = null
      }
    },

    async load(documentId: string) {
      this.abortStream()
      this.documentId = documentId
      this.phase = 'loading'
      this.error = ''
      try {
        this.document = await fetchDocument(documentId)
        this.phase = 'ready'
      } catch (err) {
        this.phase = 'error'
        this.error = err instanceof Error ? err.message : '文档加载失败'
      }
    },

    _upsertStep(key: StreamStep, detail: string, status: TraceStep['status']) {
      const existing = this.steps.find((s) => s.key === key)
      if (existing) {
        existing.detail = detail
        existing.status = status
        return
      }
      this.steps.push({ key, title: STEP_TITLES[key] ?? key, detail, status })
    },

    _resetSteps() {
      this.steps = STEP_ORDER.map((key) => ({
        key,
        title: STEP_TITLES[key] ?? key,
        detail: '',
        status: 'pending' as const,
      }))
    },

    /**
     * 进入审查页：有已完成的记录就直接回看，没有才跑一次新的。
     * 之前每次刷新都重跑，一次十秒加几万 token，回看历史完全没必要。
     */
    async resume(documentId: string) {
      await this.load(documentId)
      if (this.phase !== 'ready') return
      try {
        const history = await listDocumentReviews(documentId)
        const last = history.find((h) => h.status === 'done' || h.status === 'partial')
        if (!last) {
          void this.start()
          return
        }
        const detail = await fetchReview(last.review_id)
        this.reviewId = detail.id
        this.score = detail.safety_score
        this.summary = detail.summary ?? ''
        this.findings = (detail.findings ?? []).map((f, i) => ({
          ...f,
          id: f.id ?? (f as { item_id?: string }).item_id ?? `f-${i}`,
        }))
        this.steps = STEP_ORDER.map((key) => ({
          key,
          title: STEP_TITLES[key],
          detail: key === 'aggregate' ? this.summary || '已完成' : '历史结果',
          status: 'done' as const,
        }))
        this.phase = 'done'
      } catch {
        // 历史拉不到就退回重跑，不要让页面卡在空白
        void this.start()
      }
    },

    async start() {
      if (this.phase === 'reviewing') return
      this.abortStream()
      streamAbort = new AbortController()
      const startedFor = this.documentId
      this.phase = 'reviewing'
      this._resetSteps()
      this.findings = []
      this.score = null
      this.summary = ''
      this.stance = ''
      this.openQuestion = ''
      this.error = ''
      this.progress = { done: 0, total: 0 }

      const startedAt = performance.now()
      const timer = window.setInterval(() => {
        this.elapsedMs = performance.now() - startedAt
      }, 200)

      try {
        for await (const frame of streamReview(this.documentId, streamAbort?.signal)) {
          // 跨文档保护：用户已切到另一份合同时，晚到的帧直接丢弃
          if (this.documentId !== startedFor) return
          const data = frame.data as Record<string, unknown>
          switch (frame.event) {
            case 'step': {
              const key = String(data.step ?? '') as StreamStep
              this._upsertStep(key, String(data.message ?? ''), key === 'gate' ? 'done' : 'running')
              if (key === 'plan') this.reviewId = (data.review_id as string) ?? this.reviewId
              break
            }
            case 'finding': {
              const raw = data as unknown as Finding & { item_id?: string }
              // SSE 帧里只有 item_id、没有 id：补一个稳定 key，
              // 否则 v-for 的 key 全是 undefined，展开态会互相串
              const finding: Finding = {
                ...raw,
                id: raw.id ?? raw.item_id ?? `f-${this.findings.length}`,
              }
              this.findings.push(finding)
              this.findings.sort(
                (a, b) => RISK_ORDER[b.risk_level] - RISK_ORDER[a.risk_level],
              )
              break
            }
            case 'progress': {
              this.progress = {
                done: Number(data.done ?? 0),
                total: Number(data.total ?? 0),
              }
              // 有进度回来就说明已经在逐条判定
              this._upsertStep(
                'judge',
                `已判定 ${this.progress.done}/${this.progress.total} 项`,
                'running',
              )
              break
            }
            case 'done': {
              this.score = (data.safety_score as number) ?? null
              this.summary = String(data.summary ?? '')
              this.stance = String(data.stance ?? '')
              this.openQuestion = String(data.open_question ?? '')
              this.reviewId = (data.review_id as string) ?? this.reviewId
              const finalFindings = data.findings as Finding[] | undefined
              if (Array.isArray(finalFindings)) {
                // 同上：回查结果同样可能缺 id，统一补齐，保证 key 与展开态稳定
                this.findings = finalFindings.map((f, i) => ({
                  ...f,
                  id: f.id ?? (f as { item_id?: string }).item_id ?? `f-${i}`,
                }))
              }
              this.steps = this.steps.map((s) => ({
                ...s,
                detail: s.key === 'aggregate' ? this.summary || '已完成' : s.detail,
                status: 'done',
              }))
              this.phase = 'done'
              break
            }
            case 'error': {
              this.error = String(data.message ?? '审查中断')
              this.phase = 'error'
              break
            }
          }
        }
        if (this.phase === 'reviewing') {
          this.phase = this.findings.length ? 'done' : 'error'
          if (!this.error) this.error = '连接中断，已保留已获取的结论'
        }
      } catch (err) {
        if (this.phase !== 'done') {
          this.phase = 'error'
          this.error = err instanceof Error ? err.message : '审查请求失败'
        }
      } finally {
        window.clearInterval(timer)
        this.elapsedMs = performance.now() - startedAt
      }
    },

    select(clauseId: string | null) {
      this.activeClauseId = clauseId
    },

    reset() {
      this.$reset()
    },
  },
})
