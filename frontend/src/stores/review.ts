import { defineStore } from 'pinia'
import { fetchDocument, streamReview } from '@/api/review'
import type { DocumentDetail, Finding, RiskLevel, StreamStep } from '@/types'

export type ReviewPhase = 'loading' | 'ready' | 'reviewing' | 'done' | 'error'

export interface TraceStep {
  key: StreamStep
  title: string
  detail: string
  status: 'running' | 'done' | 'error'
}

const STEP_TITLES: Record<string, string> = {
  plan: '读取审查清单',
  gate: '条款预筛',
  retrieve: '检索法条',
  judge: '风险判定',
  aggregate: '汇总评分',
  persist: '写入结果',
}

const RISK_ORDER: Record<RiskLevel, number> = { high: 3, medium: 2, low: 1, none: 0 }

export const useReviewStore = defineStore('review', {
  state: () => ({
    documentId: '',
    document: null as DocumentDetail | null,
    phase: 'loading' as ReviewPhase,
    steps: [] as TraceStep[],
    findings: [] as Finding[],
    score: null as number | null,
    summary: '',
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
    async load(documentId: string) {
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

    async start() {
      if (this.phase === 'reviewing') return
      this.phase = 'reviewing'
      this.steps = []
      this.findings = []
      this.score = null
      this.summary = ''
      this.error = ''
      this.progress = { done: 0, total: 0 }

      const startedAt = performance.now()
      const timer = window.setInterval(() => {
        this.elapsedMs = performance.now() - startedAt
      }, 200)

      try {
        for await (const frame of streamReview(this.documentId)) {
          const data = frame.data as Record<string, unknown>
          switch (frame.event) {
            case 'step': {
              const key = String(data.step ?? '') as StreamStep
              this._upsertStep(key, String(data.message ?? ''), key === 'gate' ? 'done' : 'running')
              if (key === 'plan') this.reviewId = (data.review_id as string) ?? this.reviewId
              break
            }
            case 'finding': {
              const finding = data as unknown as Finding
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
              break
            }
            case 'done': {
              this.score = (data.safety_score as number) ?? null
              this.summary = String(data.summary ?? '')
              this.reviewId = (data.review_id as string) ?? this.reviewId
              const finalFindings = data.findings as Finding[] | undefined
              if (Array.isArray(finalFindings)) this.findings = finalFindings
              this.steps = this.steps.map((s) => ({ ...s, status: 'done' }))
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
