<script setup lang="ts">
/**
 * 打印用的审查报告。
 *
 * 为什么不做后端生成 PDF：报告内容与屏幕完全一致，再走一套服务端模板等于维护两份样式，
 * 而且演示环境不该为了导出一个 PDF 就引入 WeasyPrint 这类重依赖。
 * 这里用浏览器自带的"打印为 PDF"，分页由 @page 与 break-inside 控制。
 */
import { computed } from 'vue'
import type { DocumentDetail, Finding } from '@/types'

const props = defineProps<{
  document: DocumentDetail | null
  findings: Finding[]
  score: number | null
  summary: string
}>()

const TYPE_LABEL: Record<string, string> = {
  lease: '房屋租赁合同',
  labor: '实习 / 劳动合同',
  prepaid: '培训贷 / 预付卡',
  unknown: '未识别类型',
}

const LEVEL_TEXT: Record<string, string> = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
  none: '待复核',
}

const RANK: Record<string, number> = { high: 3, medium: 2, low: 1, none: 0 }

/** 按风险从重到轻排，用户先看最要命的 */
const ordered = computed(() =>
  [...props.findings].sort((a, b) => (RANK[b.risk_level] ?? 0) - (RANK[a.risk_level] ?? 0)),
)

const counts = computed(() => {
  const c = { high: 0, medium: 0, low: 0, pending: 0 }
  for (const f of props.findings) {
    if (f.confidence < 0.6) c.pending += 1
    else if (f.risk_level === 'high') c.high += 1
    else if (f.risk_level === 'medium') c.medium += 1
    else if (f.risk_level === 'low') c.low += 1
  }
  return c
})

const today = new Date().toLocaleString('zh-CN', { hour12: false })
</script>

<template>
  <div class="report">
    <header class="report-head">
      <h1>合同风险审查报告</h1>
      <p class="meta">
        {{ document?.filename ?? '未命名文件' }} ·
        {{ TYPE_LABEL[document?.contract_type ?? 'unknown'] }} ·
        {{ document?.clauses.length ?? 0 }} 条条款 · {{ today }}
      </p>
    </header>

    <section class="score-row">
      <div class="score">
        <span class="num">{{ score ?? '—' }}</span>
        <span class="unit">/ 100 安全分</span>
      </div>
      <div class="tally">
        <span>高风险 {{ counts.high }}</span>
        <span>中风险 {{ counts.medium }}</span>
        <span>低风险 {{ counts.low }}</span>
        <span v-if="counts.pending">待复核 {{ counts.pending }}</span>
      </div>
    </section>

    <p v-if="summary" class="summary">{{ summary }}</p>

    <ol class="items">
      <li v-for="(f, i) in ordered" :key="f.id || i" class="item">
        <div class="item-head">
          <span class="badge" :class="`badge-${f.risk_level}`">
            {{ LEVEL_TEXT[f.risk_level] ?? f.risk_level }}
          </span>
          <span class="item-title">{{ f.title }}</span>
          <span class="item-ref">
            {{ f.clause_no || '未定位条款' }} ·
            置信度 {{ Math.round(f.confidence * 100) }}%
          </span>
        </div>

        <p class="line"><span class="k">问题</span>{{ f.reason }}</p>

        <p v-if="f.legal_basis.length" class="line">
          <span class="k">依据</span>
          <span v-for="(b, j) in f.legal_basis" :key="b.chunk_id || j" class="basis">
            《{{ b.source }}》{{ b.article }}：{{ b.quote }}
          </span>
        </p>
        <p v-else class="line"><span class="k">依据</span>未检索到可直接引用的法条，本项不计入评分。</p>

        <p v-if="f.suggestion" class="line"><span class="k">建议</span>{{ f.suggestion }}</p>
        <p v-if="f.negotiation_tip" class="line">
          <span class="k">话术</span>{{ f.negotiation_tip }}
        </p>
      </li>
    </ol>

    <footer class="report-foot">
      <p>
        本报告由 ContractGuard 自动生成，仅为合同条款的风险提示，<strong>不构成法律意见</strong>，
        不能替代执业律师的审查。评分由固定规则计算，结论依据均标注法条出处，可自行核对原文。
      </p>
    </footer>
  </div>
</template>

<style scoped>
.report {
  font-family: 'Songti SC', SimSun, 'Noto Serif SC', serif;
  color: #1a1a1a;
  font-size: 11pt;
  line-height: 1.75;
}

.report-head {
  border-bottom: 1.5pt solid #1a1a1a;
  padding-bottom: 4mm;
}

.report-head h1 {
  margin: 0;
  font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
  font-size: 18pt;
  letter-spacing: 0.02em;
}

.meta {
  margin: 2mm 0 0;
  font-size: 9pt;
  color: #555;
}

.score-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 6mm;
  margin: 5mm 0 3mm;
  padding-bottom: 3mm;
  border-bottom: 0.5pt solid #ccc;
}

.score .num {
  font-family: 'Microsoft YaHei', sans-serif;
  font-size: 26pt;
  font-weight: 600;
}

.score .unit {
  margin-left: 1.5mm;
  font-size: 9.5pt;
  color: #555;
}

.tally {
  display: flex;
  gap: 4mm;
  font-size: 9.5pt;
  color: #444;
}

.summary {
  margin: 0 0 5mm;
  padding: 3mm 3.5mm;
  background: #f6f5f1;
  font-size: 10pt;
}

.items {
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: item;
}

.item {
  counter-increment: item;
  margin-bottom: 5mm;
  padding-bottom: 4mm;
  border-bottom: 0.5pt dashed #d8d5cc;
  break-inside: avoid;
  page-break-inside: avoid;
}

.item-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 2.5mm;
  margin-bottom: 1.5mm;
}

.item-head::before {
  content: counter(item) '.';
  font-family: 'Microsoft YaHei', sans-serif;
  font-size: 10pt;
  color: #666;
}

.badge {
  font-family: 'Microsoft YaHei', sans-serif;
  font-size: 8pt;
  padding: 0.4mm 2mm;
  border: 0.5pt solid currentColor;
}

.badge-high {
  color: #b3261e;
}

.badge-medium {
  color: #a8641a;
}

.badge-low {
  color: #3a6b4f;
}

.badge-none {
  color: #666;
}

.item-title {
  font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
  font-size: 10.5pt;
  font-weight: 600;
}

.item-ref {
  font-size: 8.5pt;
  color: #666;
}

.line {
  margin: 1mm 0 0;
  text-align: justify;
}

.k {
  display: inline-block;
  min-width: 11mm;
  margin-right: 2mm;
  font-family: 'Microsoft YaHei', sans-serif;
  font-size: 9pt;
  color: #666;
}

.basis {
  display: block;
  font-size: 9.5pt;
  color: #333;
}

.report-foot {
  margin-top: 6mm;
  padding-top: 3mm;
  border-top: 0.5pt solid #ccc;
  font-size: 8.5pt;
  color: #555;
}
</style>
