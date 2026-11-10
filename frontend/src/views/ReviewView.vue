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
