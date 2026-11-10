<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { ArrowLeft, RefreshCw, TriangleAlert } from 'lucide-vue-next'
import { RouterLink } from 'vue-router'
import AgentTrace from '@/components/AgentTrace.vue'
import ClauseViewer from '@/components/ClauseViewer.vue'
import FindingPanel from '@/components/FindingPanel.vue'
import SafetyScore from '@/components/SafetyScore.vue'
import { useReviewStore } from '@/stores/review'

const props = defineProps<{ docId: string }>()
const store = useReviewStore()

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

const riskyClauses = computed(() =>
  store.findings
    .filter((f) => f.clause_id)
    .map((f) => ({ id: f.clause_id as string, no: f.clause_no ?? '未编号', level: f.risk_level })),
)

const LEVEL_DOT: Record<string, string> = {
  high: 'bg-risk-high',
  medium: 'bg-risk-medium',
  low: 'bg-risk-low',
  none: 'bg-line-strong',
}
const typeLabel = computed(() => TYPE_LABEL[store.document?.contract_type ?? 'unknown'])

onMounted(async () => {
  await store.load(props.docId)
  if (store.phase === 'ready') void store.start()
})

onBeforeUnmount(() => {
  store.reset()
})
</script>

<template>
  <div class="mx-auto w-full max-w-[1240px] px-4 py-5 sm:px-6">
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

      <div class="flex items-center gap-4">
        <SafetyScore :score="store.score" :streaming="store.isStreaming" />
        <button
          class="btn-ghost text-xs"
          :disabled="store.isStreaming || store.phase === 'loading'"
          @click="store.start()"
        >
          <RefreshCw :size="13" :class="store.isStreaming ? 'animate-spin' : ''" />
          重新审查
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
        <button
          v-for="c in riskyClauses"
          :key="c.id"
          class="flex items-center gap-1.5 border px-2 py-0.5 text-[11px] transition-colors"
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
      </div>
    </div>

    <div class="mt-4 grid gap-3 lg:grid-cols-[minmax(0,3fr)_minmax(360px,2fr)]">
      <div class="h-[calc(100vh-190px)] min-h-[420px]">
        <ClauseViewer
          :document-id="store.documentId"
          :document="store.document"
          :highlights="store.highlightedClauses"
          :active-clause-id="store.activeClauseId"
          @select="store.select"
        />
      </div>

      <div class="flex h-[calc(100vh-190px)] min-h-[420px] flex-col gap-2.5 overflow-hidden">
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
      </div>
    </div>
  </div>
</template>
