<script setup lang="ts">
import { ref, watch } from 'vue'
import { ChevronDown, Quote, Sparkles, Scale, MessageCircle } from 'lucide-vue-next'
import type { Finding, RiskLevel } from '@/types'

const props = defineProps<{
  findings: Finding[]
  activeId: string | null
  streaming: boolean
}>()
const emit = defineEmits<{ (e: 'select', clauseId: string | null): void }>()

const expanded = ref<Record<string, boolean>>({})

watch(
  () => props.findings.length,
  (n) => {
    // 新到的结论默认展开，用户手动折叠过的不覆盖
    const latest = props.findings[n - 1]
    if (latest && expanded.value[latest.id] === undefined) {
      expanded.value[latest.id] = latest.confidence >= 0.6
    }
  },
  { immediate: true },
)

const LEVEL_META: Record<RiskLevel, { label: string; color: string; bg: string; bar: string }> = {
  high: { label: '高风险', color: 'text-risk-high', bg: 'bg-risk-high/10', bar: 'bg-risk-high' },
  medium: { label: '中风险', color: 'text-[#8A5A00]', bg: 'bg-risk-medium/15', bar: 'bg-risk-medium' },
  low: { label: '低风险', color: 'text-risk-low', bg: 'bg-risk-low/10', bar: 'bg-risk-low' },
  none: { label: '待复核', color: 'text-ink-soft', bg: 'bg-[#EDF0F5]', bar: 'bg-ink-faint' },
}

function toggle(id: string) {
  expanded.value[id] = !expanded.value[id]
}

function focus(finding: Finding) {
  if (finding.clause_id) emit('select', finding.clause_id)
}
</script>

<template>
  <div class="space-y-2.5">
    <div v-if="!findings.length && streaming" class="card space-y-2 p-4">
      <div class="h-3 w-20 animate-pulse rounded bg-[#EDF0F5]" />
      <div class="h-3 w-full animate-pulse rounded bg-[#EDF0F5]" />
      <div class="h-3 w-2/3 animate-pulse rounded bg-[#EDF0F5]" />
    </div>

    <div v-else-if="!findings.length" class="card p-6 text-center">
      <Sparkles :size="18" class="mx-auto text-risk-low" />
      <p class="mt-2 text-sm text-ink">暂未发现明显风险条款</p>
      <p class="mt-1 text-[11px] leading-relaxed text-ink-faint">
        这不代表合同没有其他问题，签署前建议自行核对或咨询专业律师。
      </p>
    </div>

    <article
      v-for="f in findings"
      :key="f.id"
      class="card cursor-pointer overflow-hidden transition-shadow hover:shadow-[0_2px_10px_rgba(0,0,0,.08)]"
      :class="activeId === f.clause_id ? 'ring-2 ring-brand/50' : ''"
      @click="focus(f)"
    >
      <div class="flex">
        <div class="w-1 shrink-0" :class="LEVEL_META[f.risk_level].bar" />
        <div class="min-w-0 flex-1 p-3.5">
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-1.5">
                <span
                  class="rounded px-1.5 py-0.5 text-[10px] font-medium"
                  :class="[LEVEL_META[f.risk_level].color, LEVEL_META[f.risk_level].bg]"
                >
                  {{ LEVEL_META[f.risk_level].label }}
                </span>
                <span class="text-[10px] text-ink-faint">{{ f.category }}</span>
                <span v-if="f.clause_no" class="text-[10px] text-ink-faint">
                  · {{ f.clause_no }}
                </span>
                <span
                  v-if="f.confidence < 0.6"
                  class="rounded bg-[#EDF0F5] px-1.5 py-0.5 text-[10px] text-ink-soft"
                  title="模型置信度低于 0.6，建议人工复核"
                >
                  待复核 {{ Math.round(f.confidence * 100) }}%
                </span>
              </div>
              <h3 class="mt-1.5 text-[13px] font-medium leading-snug text-ink">{{ f.title }}</h3>
            </div>
            <button
              class="mt-0.5 shrink-0 rounded p-1 text-ink-faint hover:bg-[#F4F6F9] hover:text-ink-soft"
              :aria-label="expanded[f.id] ? '收起' : '展开'"
              @click.stop="toggle(f.id)"
            >
              <ChevronDown
                :size="14"
                class="transition-transform"
                :class="expanded[f.id] ? 'rotate-180' : ''"
              />
            </button>
          </div>

          <p class="mt-2 text-[12px] leading-relaxed text-ink-soft">{{ f.reason }}</p>

          <div v-if="expanded[f.id]" class="mt-2.5 space-y-2.5 border-t border-[#F0F2F6] pt-2.5">
            <div v-if="f.legal_basis.length">
              <p class="flex items-center gap-1 text-[10px] font-medium text-ink-faint">
                <Scale :size="11" /> 法律依据
              </p>
              <div
                v-for="(b, i) in f.legal_basis"
                :key="i"
                class="mt-1 rounded bg-[#F7F9FC] px-2 py-1.5"
              >
                <p class="text-[11px] font-medium text-ink-soft">{{ b.source }} {{ b.article }}</p>
                <p class="mt-0.5 flex gap-1 text-[11px] leading-relaxed text-ink-faint">
                  <Quote :size="9" class="mt-1 shrink-0" />
                  <span>{{ b.quote }}</span>
                </p>
              </div>
            </div>
            <div v-else>
              <p class="text-[10px] font-medium text-ink-faint">法律依据</p>
              <p class="mt-0.5 text-[11px] text-ink-faint">
                未检索到直接对应的法条，该结论仅供参考，建议人工核对。
              </p>
            </div>

            <div>
              <p class="text-[10px] font-medium text-ink-faint">建议方向</p>
              <p class="mt-0.5 text-[11px] leading-relaxed text-ink-soft">{{ f.suggestion }}</p>
            </div>

            <div v-if="f.negotiation_tip" class="rounded bg-brand-light/60 px-2 py-1.5">
              <p class="flex items-center gap-1 text-[10px] font-medium text-brand">
                <MessageCircle :size="10" /> 可以这样谈
              </p>
              <p class="mt-0.5 text-[11px] leading-relaxed text-ink-soft">{{ f.negotiation_tip }}</p>
            </div>
          </div>

          <p class="mt-2 text-[10px] leading-relaxed text-ink-faint">
            本结论仅提示风险，不构成法律意见。
          </p>
        </div>
      </div>
    </article>
  </div>
</template>
