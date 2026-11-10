<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ score: number | null; streaming?: boolean }>()

const RADIUS = 26
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

const offset = computed(() => {
  const value = props.score ?? 0
  return CIRCUMFERENCE * (1 - Math.max(0, Math.min(100, value)) / 100)
})

const color = computed(() => {
  if (props.score === null) return '#C7CCD6'
  if (props.score >= 80) return '#30A46C'
  if (props.score >= 60) return '#F5A524'
  return '#E5484D'
})

const label = computed(() => (props.score === null ? '--' : String(props.score)))
</script>

<template>
  <div class="flex items-center gap-2.5">
    <div class="relative h-[64px] w-[64px]">
      <svg viewBox="0 0 64 64" class="h-full w-full -rotate-90">
        <circle cx="32" cy="32" :r="RADIUS" fill="none" stroke="#EDF0F5" stroke-width="6" />
        <circle
          cx="32"
          cy="32"
          :r="RADIUS"
          fill="none"
          :stroke="color"
          stroke-width="6"
          stroke-linecap="round"
          :stroke-dasharray="CIRCUMFERENCE"
          :stroke-dashoffset="offset"
          class="transition-all duration-700 ease-out"
        />
      </svg>
      <div class="absolute inset-0 flex flex-col items-center justify-center">
        <span class="text-[17px] font-semibold leading-none" :style="{ color }">{{ label }}</span>
        <span class="mt-0.5 text-[9px] text-ink-faint">安全分</span>
      </div>
    </div>
    <div class="leading-tight">
      <p class="text-xs text-ink-soft">满分 100</p>
      <p class="mt-0.5 text-[11px] text-ink-faint">
        {{ streaming ? '计算中…' : score === null ? '未开始' : score >= 60 ? '存在需谈判的点' : '风险较集中' }}
      </p>
    </div>
  </div>
</template>
