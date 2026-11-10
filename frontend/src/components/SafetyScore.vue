<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ score: number | null; streaming?: boolean }>()

const tone = computed(() => {
  if (props.score === null) return 'text-ink-faint'
  if (props.score >= 80) return 'text-risk-low'
  if (props.score >= 60) return 'text-risk-medium'
  return 'text-risk-high'
})

const barColor = computed(() => {
  if (props.score === null) return 'bg-line-strong'
  if (props.score >= 80) return 'bg-risk-low'
  if (props.score >= 60) return 'bg-risk-medium'
  return 'bg-risk-high'
})

const width = computed(() => `${Math.max(0, Math.min(100, props.score ?? 0))}%`)

const caption = computed(() => {
  if (props.streaming) return '判定中'
  if (props.score === null) return '待审查'
  if (props.score >= 80) return '条款较规范'
  if (props.score >= 60) return '有需谈判之处'
  return '风险较集中'
})
</script>

<template>
  <div class="flex items-end gap-4">
    <div>
      <p class="label">安全分</p>
      <div class="mt-1 flex items-baseline gap-1">
        <span class="num font-serif text-[34px] leading-none transition-colors duration-500" :class="tone">
          {{ score === null ? '—' : score }}
        </span>
        <span class="num text-[11px] text-ink-faint">/100</span>
      </div>
    </div>
    <div class="w-[92px] pb-1">
      <div class="h-[2px] w-full bg-line">
        <div
          class="h-full transition-all duration-700 ease-calm"
          :class="barColor"
          :style="{ width }"
        />
      </div>
      <p class="mt-1.5 text-[10px] text-ink-faint">{{ caption }}</p>
    </div>
  </div>
</template>
