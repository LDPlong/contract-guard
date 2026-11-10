<script setup lang="ts">
import { computed } from 'vue'
import { Check, Loader2 } from 'lucide-vue-next'
import type { TraceStep } from '@/stores/review'

const props = defineProps<{
  steps: TraceStep[]
  progress: { done: number; total: number }
  elapsedMs: number
  streaming: boolean
}>()

const seconds = computed(() => (props.elapsedMs / 1000).toFixed(1))
const percent = computed(() => {
  if (!props.progress.total) return 0
  return Math.round((props.progress.done / props.progress.total) * 100)
})
</script>

<template>
  <div class="card px-4 py-3">
    <div class="flex items-center justify-between">
      <p class="text-xs font-medium text-ink">审查过程</p>
      <span class="text-[11px] text-ink-faint">
        {{ streaming ? `进行中 ${seconds}s` : `耗时 ${seconds}s` }}
      </span>
    </div>

    <div class="mt-2 h-1 overflow-hidden rounded-full bg-[#EDF0F5]">
      <div
        class="h-full rounded-full bg-brand transition-all duration-500"
        :style="{ width: `${percent}%` }"
      />
    </div>
    <p class="mt-1 text-[11px] text-ink-faint">
      {{ progress.done }} / {{ progress.total || '—' }} 项判定完成
    </p>

    <ol class="mt-3 space-y-1.5">
      <li v-for="step in steps" :key="step.key" class="flex items-start gap-2">
        <span
          class="mt-[3px] flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full"
          :class="
            step.status === 'done'
              ? 'bg-risk-low/15 text-risk-low'
              : step.status === 'error'
                ? 'bg-risk-high/15 text-risk-high'
                : 'bg-brand-light text-brand'
          "
        >
          <Check v-if="step.status === 'done'" :size="9" :stroke-width="3" />
          <Loader2 v-else :size="9" class="animate-spin" />
        </span>
        <div class="min-w-0 flex-1">
          <p class="text-[11px] leading-tight text-ink-soft">{{ step.title }}</p>
          <p class="mt-0.5 truncate text-[11px] leading-tight text-ink-faint" :title="step.detail">
            {{ step.detail }}
          </p>
        </div>
      </li>
    </ol>

    <p v-if="!steps.length" class="mt-3 text-[11px] text-ink-faint">等待开始…</p>
  </div>
</template>
