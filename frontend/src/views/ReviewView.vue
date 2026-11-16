<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ArrowLeft, MessageCircle, Printer, RefreshCw, TriangleAlert } from 'lucide-vue-next'
import { RouterLink } from 'vue-router'
import AgentTrace from '@/components/AgentTrace.vue'
import ClauseViewer from '@/components/ClauseViewer.vue'
import FindingPanel from '@/components/FindingPanel.vue'
import ReportSheet from '@/components/ReportSheet.vue'
import SafetyScore from '@/components/SafetyScore.vue'
import { useReviewStore } from '@/stores/review'
import { useAppStore } from '@/stores/reviewStore'

const props = defineProps<{ docId: string }>()
const store = useReviewStore()
const app = useAppStore()

const TYPE_LABEL: Record<string, string> = {
  lease: '房屋租赁合同',
  labor: '实习 / 劳动合同',
  prepaid: '培训贷 / 预付卡',
  unknown: '未识别类型',
}

const title = computed(() => store.document?.filename ?? '加载中…')

const stats = computed(() => {
  const counter = { high: 0, medium: 0, low: 0, pending: 0 }
  for (const f of store.findings) {
    if (f.confidence < 0.6) counter.pending += 1
    else if (f.risk_level === 'high') counter.high += 1
    else if (f.risk_level === 'medium') counter.medium += 1
    else if (f.risk_level === 'low') counter.low += 1
  }
  return counter
})

const CN_DIGIT: Record<string, number> = {
  零: 0, 一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9,
}

/** "第三条" / "第十一条" / "第11条" → 3 / 11 / 11；解析不出来的一律排到最后 */
function clauseOrdinal(label: string): number {
  const m = label.match(/第\s*([0-9]+|[零一二三四五六七八九十百]+)\s*条/)
  if (!m) return Number.MAX_SAFE_INTEGER
  const raw = m[1]
  if (/^[0-9]+$/.test(raw)) return Number(raw)

  // 中文数字按 百 / 十 / 个 逐段累加，够用到"第一百二十条"
  let total = 0
  let section = 0
  for (const ch of raw) {
    if (ch === '百') {
      total += (section || 1) * 100
      section = 0
    } else if (ch === '十') {
      total += (section || 1) * 10
      section = 0
    } else {
      section = CN_DIGIT[ch] ?? 0
    }
  }
  return total + section
}

// 手机上 chips 最多先给 4 个，其余折叠
const MOBILE_CHIP_LIMIT = 4
const chipsExpanded = ref(false)

const LEVEL_WEIGHT: Record<string, number> = { high: 3, medium: 2, low: 1, none: 0 }

/**
 * 一条条款可能命中多个审查项（第八条同时中了违约金和解除权），
 * chips 按条款去重、留最严重那条，否则同一句话会出现两次，点了还跳同一处。
 */
const riskyClauses = computed(() => {
  const byClause = new Map<string, {
    id: string
    no: string
    level: string
    title: string
    confidence: number
    basis: string
    count: number
  }>()

  for (const f of store.findings) {
    if (!f.clause_id) continue
    const prev = byClause.get(f.clause_id)
    if (prev) {
      prev.count += 1
      if ((LEVEL_WEIGHT[f.risk_level] ?? 0) > (LEVEL_WEIGHT[prev.level] ?? 0)) {
        prev.level = f.risk_level
        prev.title = f.title
        prev.confidence = f.confidence
        prev.basis = f.legal_basis[0]?.article ?? ''
      }
      continue
    }
    byClause.set(f.clause_id, {
      id: f.clause_id,
      no: f.clause_no ?? '未编号',
      level: f.risk_level,
      title: f.title,
      confidence: f.confidence,
      basis: f.legal_basis[0]?.article ?? '',
      count: 1,
    })
  }

  // 按条款序排，不按模型返回顺序：用户是照合同找条号的
  return [...byClause.values()].sort((a, b) => clauseOrdinal(a.no) - clauseOrdinal(b.no))
})

const LEVEL_TEXT: Record<string, string> = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
  none: '待复核',
}

const LEVEL_DOT: Record<string, string> = {
  high: 'bg-risk-high',
  medium: 'bg-risk-medium',
  low: 'bg-risk-low',
  none: 'bg-line-strong',
}
const typeLabel = computed(() => TYPE_LABEL[store.document?.contract_type ?? 'unknown'])

/**
 * 内联入口带上的上下文：助手是"就这份合同"回答，不是凭空答。
 * 只放类型、条数和前几条结论，后端还有 400 字上限，别写成整份合同。
 */
const reviewContext = computed(() => {
  const total = store.document?.clauses.length ?? 0
  const top = store.findings.slice(0, 5).map((f) => {
    const level = LEVEL_TEXT[f.risk_level] ?? ''
    return `- ${f.clause_no || '未定位条款'}：${f.title}（${level}）`
  })
  return [
    `当前审查的合同：${typeLabel.value}，共 ${total} 条条款。`,
    top.length ? `已标出的风险：\n${top.join('\n')}` : '目前未标出明显风险。',
  ].join('\n')
})

onMounted(() => {
  void store.resume(props.docId)
})

onBeforeUnmount(() => {
  store.reset()
})

const canExport = computed(() => store.phase === 'done' && store.findings.length > 0)

/** 走浏览器打印为 PDF：临时改标题，存下来的文件名才是报告名而不是"合同风险审查" */
function exportReport() {
  if (!canExport.value) return
  const original = document.title
  const name = store.document?.filename?.replace(/\.[^.]+$/, '') ?? '合同'
  document.title = `${name}-风险审查报告`
  window.print()
  document.title = original
}
</script>

<template>
  <div class="mx-auto w-full max-w-[1240px] px-4 py-5 sm:px-6 print:hidden">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex min-w-0 items-center gap-3">
        <RouterLink
          to="/"
          class="flex h-8 w-8 shrink-0 items-center justify-center border border-line bg-white text-ink-soft transition-colors hover:border-line-strong hover:text-accent"
          aria-label="返回上传"
        >
          <ArrowLeft :size="15" />
        </RouterLink>
        <div class="min-w-0">
          <p class="truncate font-serif text-[15px] text-ink">{{ title }}</p>
          <p class="mt-1 text-[11px] text-ink-faint">
            {{ typeLabel }}
            <span v-if="store.document"> · {{ store.document.clauses.length }} 条条款</span>
          </p>
        </div>
      </div>

      <div class="flex flex-wrap items-center justify-end gap-3">
        <SafetyScore :score="store.score" :streaming="store.isStreaming" />
        <button
          v-if="canExport"
          class="btn-ghost shrink-0 whitespace-nowrap !px-2.5 text-xs sm:!px-5"
          title="用浏览器另存为 PDF，内容与本页一致"
          aria-label="导出报告"
          @click="exportReport"
        >
          <Printer :size="13" />
          <span class="hidden sm:inline">导出报告</span>
        </button>
        <button
          class="btn-ghost shrink-0 whitespace-nowrap !px-2.5 text-xs sm:!px-5"
          :disabled="store.isStreaming || store.phase === 'loading'"
          aria-label="重新审查"
          @click="store.start()"
        >
          <RefreshCw :size="13" :class="store.isStreaming ? 'animate-spin' : ''" />
          <span class="hidden sm:inline">重新审查</span>
        </button>
      </div>
    </div>

    <div
      v-if="store.error"
      class="mt-4 flex items-start gap-2 border border-risk-high/30 bg-risk-high/[0.04] px-3 py-2.5"
    >
      <TriangleAlert :size="14" class="mt-0.5 shrink-0 text-risk-high" />
      <div class="flex-1">
        <p class="text-[12px] text-ink">{{ store.error }}</p>
        <p class="mt-1 text-[11px] text-ink-faint">
          已获取的结论仍然保留，可点击「重新审查」再试一次。
        </p>
      </div>
    </div>

    <!-- 统计与条款导航：给"这份合同哪里有问题"一个总览入口 -->
    <div
      v-if="store.findings.length"
      class="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-y border-line py-2.5"
    >
      <div class="flex items-center gap-4 text-[11px]">
        <span class="num text-ink-soft">高 {{ stats.high }}</span>
        <span class="num text-ink-soft">中 {{ stats.medium }}</span>
        <span class="num text-ink-soft">低 {{ stats.low }}</span>
        <span v-if="stats.pending" class="num text-ink-faint">待复核 {{ stats.pending }}</span>
      </div>

      <div class="flex flex-1 flex-wrap items-center gap-1.5">
        <span class="label mr-1">命中条款</span>
        <div
          v-for="(c, i) in riskyClauses"
          :key="c.id"
          class="group/chip relative"
          :class="i >= MOBILE_CHIP_LIMIT && !chipsExpanded ? 'hidden sm:block' : ''"
        >
          <button
            class="flex min-h-[32px] items-center gap-1.5 border px-2.5 py-1.5 text-[11px] transition-colors sm:min-h-0 sm:px-2 sm:py-0.5"
            :class="
              store.activeClauseId === c.id
                ? 'border-ink bg-ink text-white'
                : 'border-line text-ink-soft hover:border-line-strong'
            "
            @click="store.select(c.id)"
          >
            <span class="h-1 w-1 rounded-full" :class="LEVEL_DOT[c.level]" />
            {{ c.no }}
          </button>

          <!-- 悬停预览：不必点进去就能看到结论 -->
          <div
            class="pointer-events-none absolute bottom-full z-10 mb-2 hidden w-[220px] border border-line bg-white p-2.5 opacity-0 shadow-lift transition-all duration-150 ease-calm group-hover/chip:-translate-y-0.5 group-hover/chip:opacity-100 sm:block"
            :class="
              i === riskyClauses.length - 1 ? 'left-auto right-0' : 'left-1/2 -translate-x-1/2'
            "
          >
            <p class="flex items-center gap-1.5 text-[10px]">
              <span class="h-1 w-1 rounded-full" :class="LEVEL_DOT[c.level]" />
              <span class="text-ink-faint">{{ LEVEL_TEXT[c.level] ?? c.level }}</span>
              <span v-if="c.basis" class="num text-ink-faint">· {{ c.basis }}</span>
            </p>
            <p class="mt-1 text-[11.5px] leading-snug text-ink">{{ c.title }}</p>
            <p class="num mt-1 text-[10px] text-ink-faint">
              置信度 {{ Math.round(c.confidence * 100) }}%
            </p>
          </div>
        </div>

        <!-- 手机上默认只给 4 个，其余折起来，别让 chips 把结论顶到三屏之外 -->
        <button
          v-if="riskyClauses.length > MOBILE_CHIP_LIMIT"
          class="text-[11px] text-accent transition-colors hover:text-ink sm:hidden"
          @click="chipsExpanded = !chipsExpanded"
        >
          {{ chipsExpanded ? '收起' : `还有 ${riskyClauses.length - MOBILE_CHIP_LIMIT} 条` }}
        </button>
      </div>
    </div>

    <div class="mt-4 grid gap-3 lg:grid-cols-[minmax(0,3fr)_minmax(360px,2fr)]">
      <div class="order-2 h-[calc(100vh-214px)] min-h-[420px] lg:order-1">
        <ClauseViewer
          :document-id="store.documentId"
          :document="store.document"
          :highlights="store.highlightedClauses"
          :active-clause-id="store.activeClauseId"
          @select="store.select"
        />
      </div>

      <div class="order-1 flex h-[calc(100vh-214px)] min-h-[420px] flex-col gap-2.5 overflow-hidden lg:order-2">
        <AgentTrace
          :steps="store.steps"
          :progress="store.progress"
          :elapsed-ms="store.elapsedMs"
          :streaming="store.isStreaming"
        />

        <p
          v-if="store.summary"
          class="border border-line bg-white px-3.5 py-2.5 text-[12px] leading-[1.8] text-ink-soft"
        >
          {{ store.summary }}
        </p>

        <div class="min-h-0 flex-1 overflow-auto pr-0.5">
          <FindingPanel
            :findings="store.findings"
            :active-id="store.activeClauseId"
            :streaming="store.isStreaming"
            @select="store.select"
          />
        </div>

        <!-- 提问入口内联在右栏底部：既不遮结论，又带上「当前合同」这个上下文 -->
        <button
          class="flex w-full shrink-0 items-center justify-center gap-1.5 border border-line bg-white py-2.5 text-[12px] text-accent transition-colors hover:border-line-strong"
          @click="app.openAssistant(reviewContext)"
        >
          <MessageCircle :size="12" />
          就这份合同提问
        </button>
      </div>
    </div>
  </div>

  <!-- 打印时才出现：屏幕上的双栏布局带滚动容器，直接打印会被截断 -->
  <ReportSheet
    class="hidden px-[2mm] py-[2mm] print:block"
    :document="store.document"
    :findings="store.findings"
    :score="store.score"
    :summary="store.summary"
    :stance="store.stance"
    :open-question="store.openQuestion"
  />
</template>
