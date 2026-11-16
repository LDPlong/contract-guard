<script setup lang="ts">
import { ref, watch } from 'vue'
import { ChevronDown, MessageCircle } from 'lucide-vue-next'
import type { Finding, Priority, RiskLevel } from '@/types'

const props = defineProps<{
  findings: Finding[]
  activeId: string | null
  streaming: boolean
}>()
const emit = defineEmits<{ (e: 'select', clauseId: string | null): void }>()

const expandedId = ref<string | null>(null)

// 同时只展开一条：多卡同开会让列表变成信息瀑布，用户失去"还剩几条"的空间感
watch(
  () => props.findings.length,
  (n) => {
    const latest = props.findings[n - 1]
    if (latest && expandedId.value === null && latest.confidence >= 0.6) {
      expandedId.value = latest.id
    }
  },
  { immediate: true },
)

// 静态类名，避免 Tailwind 扫描不到动态拼接
const LEVEL: Record<RiskLevel, { text: string; edge: string; dot: string; label: string }> = {
  high: { text: 'text-risk-high', edge: 'border-l-risk-high', dot: 'bg-risk-high', label: '高' },
  medium: { text: 'text-risk-medium', edge: 'border-l-risk-medium', dot: 'bg-risk-medium', label: '中' },
  low: { text: 'text-risk-low', edge: 'border-l-risk-low', dot: 'bg-risk-low', label: '低' },
  none: { text: 'text-ink-faint', edge: 'border-l-line-strong', dot: 'bg-line-strong', label: '待核' },
}

// 谈判优先级：只告诉用户谈的先后，不产出可签署的条文（文档 1.2）
const PRIORITY: Record<Priority, { label: string; cls: string }> = {
  must: { label: '必守', cls: 'text-risk-high border-risk-high/40' },
  negotiable: { label: '可谈', cls: 'text-accent border-accent/40' },
  yieldable: { label: '可让步', cls: 'text-ink-faint border-line' },
}

function toggle(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

function focus(finding: Finding) {
  if (finding.clause_id) emit('select', finding.clause_id)
}

function ordinal(index: number) {
  return String(index + 1).padStart(2, '0')
}
</script>

<template>
  <div class="space-y-2.5">
    <div v-if="!findings.length && streaming" class="border border-line bg-white p-5">
      <div class="space-y-2.5">
        <div class="h-2.5 w-16 animate-pulse bg-paper-sunk" />
        <div class="h-2.5 w-full animate-pulse bg-paper-sunk" />
        <div class="h-2.5 w-3/4 animate-pulse bg-paper-sunk" />
      </div>
    </div>

    <div v-else-if="!findings.length" class="border border-line bg-white px-6 py-10 text-center">
      <p class="font-serif text-[15px] text-ink">暂未发现明显风险条款</p>
      <p class="mx-auto mt-2 max-w-[260px] text-[11px] leading-relaxed text-ink-faint">
        这不代表合同没有其他问题。签署前建议自行核对，重大事项咨询专业律师。
      </p>
    </div>

    <article
      v-for="(f, i) in findings"
      :key="f.id"
      class="animate-rise cursor-pointer border border-l-2 border-line bg-white transition-colors duration-200 hover:border-line-strong"
      :class="[LEVEL[f.risk_level].edge, activeId === f.clause_id ? 'border-line-strong bg-paper/50' : '']"
      @click="focus(f)"
    >
      <div class="p-3.5">
        <div class="flex items-start justify-between gap-3">
          <div class="flex min-w-0 items-baseline gap-2">
            <span class="num font-serif text-[12px] text-ink-faint">{{ ordinal(i) }}</span>
            <span class="text-[10px] font-medium tracking-wide" :class="LEVEL[f.risk_level].text">
              {{ f.risk_level === 'none' ? '待复核' : `${LEVEL[f.risk_level].label}风险` }}
            </span>
            <span class="text-[10px] text-ink-faint">{{ f.category }}</span>
            <span
              v-if="f.needs_review"
              class="border border-line px-1 py-0.5 text-[10px] text-ink-faint"
            >待复核</span>
            <span
              v-else-if="f.priority"
              class="border px-1 py-0.5 text-[10px]"
              :class="PRIORITY[f.priority ?? 'yieldable'].cls"
            >{{ PRIORITY[f.priority ?? 'yieldable'].label }}</span>
            <span v-if="f.clause_no" class="text-[10px] text-ink-faint">· {{ f.clause_no }}</span>
          </div>
          <div class="flex shrink-0 items-center gap-1.5">
            <span
              v-if="f.confidence < 0.6"
              class="num border border-line px-1.5 py-0.5 text-[10px] text-ink-faint"
              title="置信度低于 0.6，建议人工复核"
            >
              {{ Math.round(f.confidence * 100) }}%
            </span>
            <button
              class="btn-quiet !px-1 !py-0.5"
              :aria-label="expandedId === f.id ? '收起' : '展开'"
              @click.stop="toggle(f.id)"
            >
              <ChevronDown
                :size="13"
                class="transition-transform duration-200"
                :class="expandedId === f.id ? 'rotate-180' : ''"
              />
            </button>
          </div>
        </div>

        <h3 class="mt-2 font-serif text-[15px] leading-snug text-ink">{{ f.title }}</h3>
        <p class="mt-1.5 text-[13.5px] leading-[1.8] text-ink-soft">{{ f.reason }}</p>

        <!-- 依据常驻折叠态：这是产品最有说服力的一点，不该埋在二级展开里 -->
        <p class="mt-2 flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5 text-[11.5px] leading-relaxed">
          <span class="text-ink-faint">依据</span>
          <template v-if="f.legal_basis.length">
            <span class="font-serif text-accent">{{ f.legal_basis[0].source }} {{ f.legal_basis[0].article }}</span>
            <span v-if="f.legal_basis.length > 1" class="num text-ink-faint">
              +{{ f.legal_basis.length - 1 }}
            </span>
          </template>
          <span v-else class="text-ink-faint">未检索到直接对应的法条</span>
        </p>

        <div v-if="expandedId === f.id" class="mt-3 space-y-3 border-t border-line pt-3">
          <div>
            <p class="label">法条原文</p>
            <template v-if="f.legal_basis.length">
              <div
                v-for="(b, k) in f.legal_basis"
                :key="k"
                class="mt-1.5 border-l border-line-strong pl-2.5"
              >
                <p class="text-[12px] text-ink-soft">{{ b.source }} {{ b.article }}</p>
                <p class="mt-0.5 text-[11.5px] leading-[1.75] text-ink-faint">{{ b.quote }}</p>
              </div>
            </template>
            <p v-else class="mt-1 text-[11px] leading-relaxed text-ink-faint">
              未检索到直接对应的法条，结论仅供参考。
            </p>
          </div>

          <div v-if="f.impact">
            <p class="label">可能影响</p>
            <p class="mt-1 text-[12.5px] leading-[1.75] text-ink-soft">{{ f.impact }}</p>
          </div>

          <div>
            <p class="label">建议方向</p>
            <p class="mt-1 text-[12.5px] leading-[1.75] text-ink-soft">{{ f.suggestion }}</p>
          </div>

          <div v-if="f.negotiation_tip" class="bg-accent-wash px-2.5 py-2">
            <p class="flex items-center gap-1 text-[10px] tracking-wide text-accent">
              <MessageCircle :size="10" /> 沟通建议
            </p>
            <p class="mt-1 text-[11.5px] leading-[1.7] text-ink-soft">{{ f.negotiation_tip }}</p>
          </div>
        </div>
      </div>
    </article>
  </div>
</template>
