<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Clock } from 'lucide-vue-next'
import { listDocuments } from '@/api/review'
import type { DocumentListItem } from '@/types'

/**
 * 顶栏「我的审查」：本会话审查过的合同，点击直达回看。
 * 回看逻辑在审查页里（resume：有结果直接展示，不重跑）。
 */
const router = useRouter()
const open = ref(false)
const loading = ref(false)
const items = ref<DocumentListItem[]>([])
const root = ref<HTMLElement | null>(null)

const TYPE_LABEL: Record<string, string> = {
  lease: '租赁',
  labor: '劳动',
  prepaid: '预付卡',
  unknown: '通用',
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  return `${Math.floor(hours / 24)} 天前`
}

function scoreTone(score: number | null): string {
  if (score === null || score === undefined) return 'text-ink-faint'
  if (score >= 80) return 'text-risk-low'
  if (score >= 40) return 'text-risk-medium'
  return 'text-risk-high'
}

async function toggle() {
  open.value = !open.value
  if (!open.value) return
  loading.value = true
  try {
    items.value = await listDocuments()
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function go(item: DocumentListItem) {
  open.value = false
  void router.push(`/review/${item.document_id}`)
}

function onOutside(e: MouseEvent) {
  if (root.value && !root.value.contains(e.target as Node)) open.value = false
}

function onEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') open.value = false
}

onMounted(() => {
  document.addEventListener('click', onOutside)
  document.addEventListener('keydown', onEsc)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onOutside)
  document.removeEventListener('keydown', onEsc)
})
</script>

<template>
  <div ref="root" class="relative hidden sm:block">
    <button
      type="button"
      class="flex items-center gap-1 text-[12px] text-ink-soft transition-colors hover:text-ink"
      :aria-expanded="open"
      aria-haspopup="true"
      @click="toggle"
    >
      <Clock :size="13" />
      审查记录
    </button>

    <div
      v-if="open"
      class="absolute right-0 top-8 z-40 w-[280px] border border-line bg-white shadow-lift"
      role="menu"
      aria-label="审查记录"
    >
      <p v-if="loading" class="px-4 py-4 text-[12px] text-ink-faint">加载中…</p>
      <p v-else-if="!items.length" class="px-4 py-4 text-[12px] leading-relaxed text-ink-faint">
        本会话还没有审查记录。上传一份合同后会出现在这里。
      </p>
      <ul v-else class="max-h-[360px] overflow-y-auto">
        <li v-for="item in items" :key="item.document_id">
          <button
            type="button"
            class="block w-full border-b border-line-soft px-4 py-2.5 text-left transition-colors last:border-b-0 hover:bg-paper"
            @click="go(item)"
          >
            <span class="flex items-center justify-between gap-2">
              <span class="truncate text-[12.5px] text-ink">{{ item.filename }}</span>
              <span
                class="num shrink-0 text-[11px] font-medium"
                :class="scoreTone(item.safety_score)"
              >{{ item.safety_score === null ? '—' : item.safety_score }}</span>
            </span>
            <span class="mt-0.5 flex items-center gap-2 text-[10px] text-ink-faint">
              <span>{{ TYPE_LABEL[item.contract_type] ?? item.contract_type }}</span>
              <span>·</span>
              <span>{{ timeAgo(item.created_at) }}</span>
            </span>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>
