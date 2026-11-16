<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, ChevronDown } from 'lucide-vue-next'
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

const collapsed = ref(false)
const canCollapse = computed(() => !props.streaming && props.steps.length > 0)

// 流式结束后自动折起：过程信息不该长期占着结论的位置
watch(
  () => props.streaming,
  (now, prev) => {
    if (prev && !now) collapsed.value = true
  },
)
</script>

<template>
  <div class="border border-line bg-white px-4 py-3.5">
    <button
      v-if="canCollapse && collapsed"
      class="flex w-full items-center gap-2 text-left"
      @click="collapsed = false"
    >
      <Check :size="12" class="shrink-0 text-risk-low" />
      <span class="text-[11.5px] text-ink-soft">审查完成</span>
      <span class="num text-[11px] text-ink-faint">{{ seconds }}s · {{ progress.done }}/{{ progress.total }}</span>
      <span class="ml-auto text-[11px] text-ink-faint">展开</span>
    </button>

    <div v-else>
    <div class="flex items-baseline justify-between">
      <p class="label">审查过程</p>
      <p class="num text-[11px] text-ink-faint">
        {{ seconds }}s
        <span class="text-ink-faint/60">·</span>
        {{ progress.done }}/{{ progress.total || '—' }}
      </p>
    </div>

    <div class="mt-[9px] h-[2px] w-full bg-paper-sunk">
      <div
        class="h-full bg-accent transition-all duration-500 ease-calm"
        :style="{ width: `${percent}%` }"
      />
    </div>

    <ol class="mt-3.5 space-y-2.5">
      <li v-for="(step, index) in steps" :key="step.key" class="relative flex gap-2.5">
        <!-- 时间轴：小方点 + 竖线，避免圆点带来的廉价感 -->
        <span class="relative mt-[5px] flex w-2 justify-center">
          <span
            class="h-[5px] w-[5px] shrink-0"
            :class="[
              step.status === 'done'
                ? 'bg-accent'
                : step.status === 'error'
                  ? 'bg-risk-high'
                  : step.status === 'running'
                    ? 'bg-accent/60 animate-pulseRing'
                    : 'bg-line',
            ]"
          />
          <span
            v-if="index < steps.length - 1"
            class="absolute top-[9px] h-[14px] w-px bg-line"
          />
        </span>
        <div class="min-w-0 flex-1 pb-0.5">
          <p
            class="text-[11.5px] leading-tight"
            :class="step.status === 'pending' ? 'text-ink-faint' : 'text-ink-soft'"
          >{{ step.title }}</p>
          <p class="mt-0.5 truncate text-[11px] leading-tight text-ink-faint" :title="step.detail">
            {{ step.detail }}
          </p>
        </div>
      </li>
    </ol>

    <p v-if="!steps.length" class="mt-3 text-[11px] text-ink-faint">等待开始…</p>

      <button
        v-if="canCollapse"
        class="mt-3 flex w-full items-center justify-center gap-1 text-[11px] text-ink-faint transition-colors hover:text-ink"
        @click="collapsed = true"
      >
        收起
        <ChevronDown :size="11" class="rotate-180" />
      </button>
    </div>
  </div>
</template>
