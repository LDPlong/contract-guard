<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { AlertCircle, FileText, Loader2, Minus, Plus } from 'lucide-vue-next'
import { fetchDocumentFile } from '@/api/review'
import type { Clause, DocumentDetail, RiskLevel } from '@/types'

const props = defineProps<{
  documentId: string
  document: DocumentDetail | null
  highlights: Record<string, RiskLevel>
  activeClauseId: string | null
}>()
const emit = defineEmits<{ (e: 'select', clauseId: string | null): void }>()

interface PageMeta {
  no: number
  widthPt: number
  heightPt: number
  cssScale: number
}

const VIEW_MAX_WIDTH = 720
const MIN_ZOOM = 0.7
const MAX_ZOOM = 2

const scroller = ref<HTMLDivElement | null>(null)
const canvasHost = ref<HTMLDivElement | null>(null)
const metas = ref<PageMeta[]>([])
const mode = ref<'loading' | 'pdf' | 'text'>('loading')
const failure = ref('')
const zoom = ref(1)

let pdfDoc: any = null
const rendered = new Set<number>()

const clauses = computed<Clause[]>(() => props.document?.clauses ?? [])

const COLOR: Record<RiskLevel, string> = {
  high: 'rgba(229,72,77,.30)',
  medium: 'rgba(245,165,36,.32)',
  low: 'rgba(48,164,108,.28)',
  none: 'rgba(0,0,0,0)',
}
const BORDER: Record<RiskLevel, string> = {
  high: 'rgba(229,72,77,.85)',
  medium: 'rgba(245,165,36,.85)',
  low: 'rgba(48,164,108,.8)',
  none: 'transparent',
}

function rectOf(clause: Clause) {
  if (!clause.bbox) return null
  const meta = metas.value.find((m) => m.no === clause.page_no)
  if (!meta) return null
  const [x0, y0, x1, y1] = clause.bbox
  return {
    left: `${x0 * meta.cssScale}px`,
    top: `${y0 * meta.cssScale}px`,
    width: `${Math.max(2, (x1 - x0) * meta.cssScale)}px`,
    height: `${Math.max(2, (y1 - y0) * meta.cssScale)}px`,
  }
}

function styleOf(clause: Clause) {
  const level = props.highlights[clause.id]
  const rect = rectOf(clause)
  if (!rect) return null
  return {
    ...rect,
    background: level ? COLOR[level] : 'transparent',
    outline: props.activeClauseId === clause.id ? `2px solid ${BORDER[level ?? 'high']}` : 'none',
    cursor: level ? 'pointer' : 'default',
  }
}

async function drawAll() {
  if (!pdfDoc || !canvasHost.value) return
  const host = canvasHost.value
  const canvases = host.querySelectorAll<HTMLCanvasElement>('canvas[data-page]')
  const available = Math.min(VIEW_MAX_WIDTH, scroller.value?.clientWidth ?? VIEW_MAX_WIDTH) - 24
  const baseScale = Math.max(available, 480) / (metas.value[0]?.widthPt || 595)

  for (const canvas of canvases) {
    const pageNo = Number(canvas.dataset.page)
    const page = await pdfDoc.getPage(pageNo)
    const viewport = page.getViewport({ scale: baseScale * zoom.value })
    const dpr = window.devicePixelRatio || 1

    canvas.width = Math.floor(viewport.width * dpr)
    canvas.height = Math.floor(viewport.height * dpr)
    canvas.style.width = `${Math.floor(viewport.width)}px`
    canvas.style.height = `${Math.floor(viewport.height)}px`

    const ctx = canvas.getContext('2d')
    if (!ctx) continue
    await page.render({
      canvasContext: ctx,
      viewport,
      transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : undefined,
    }).promise

    const meta = metas.value.find((m) => m.no === pageNo)
    if (meta) meta.cssScale = viewport.width / meta.widthPt
    rendered.add(pageNo)
  }
}

async function loadPdf() {
  mode.value = 'loading'
  failure.value = ''
  try {
    const bytes = await fetchDocumentFile(props.documentId)
    const pdfjs: any = await import('pdfjs-dist')
    const worker: { default: string } = await import('pdfjs-dist/build/pdf.worker.min.mjs?url')
    pdfjs.GlobalWorkerOptions.workerSrc = worker.default

    pdfDoc = await pdfjs.getDocument({ data: new Uint8Array(bytes) }).promise
    const pages: PageMeta[] = []
    for (let i = 1; i <= pdfDoc.numPages; i += 1) {
      const page = await pdfDoc.getPage(i)
      const vp = page.getViewport({ scale: 1 })
      pages.push({ no: i, widthPt: vp.width, heightPt: vp.height, cssScale: 1 })
    }
    metas.value = pages
    mode.value = 'pdf'
    await nextTick()
    await drawAll()
  } catch (err) {
    // 降级：pdf.js 不可用时退回文本渲染，保证高亮定位仍可用
    mode.value = 'text'
    failure.value = err instanceof Error ? err.message : 'PDF 渲染失败'
  }
}

function zoomBy(delta: number) {
  const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number((zoom.value + delta).toFixed(2))))
  if (next === zoom.value) return
  zoom.value = next
  void drawAll()
}

function pick(clause: Clause) {
  if (!props.highlights[clause.id]) return
  emit('select', clause.id)
}

watch(
  () => props.activeClauseId,
  async (id) => {
    if (!id) return
    await nextTick()
    const el = scroller.value?.querySelector<HTMLElement>(`[data-clause-id="${id}"]`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  },
)

watch(() => props.documentId, loadPdf, { immediate: true })
</script>

<template>
  <div ref="scroller" class="card flex h-full flex-col overflow-hidden">
    <div class="flex items-center justify-between border-b border-[#F0F2F6] px-3 py-2">
      <p class="flex items-center gap-1.5 text-xs font-medium text-ink">
        <FileText :size="13" class="text-ink-soft" />
        合同原文
        <span v-if="document" class="text-[11px] font-normal text-ink-faint">
          · {{ document.clauses.length }} 条 · {{ document.pages.length }} 页
        </span>
      </p>
      <div v-if="mode === 'pdf'" class="flex items-center gap-1">
        <button class="rounded p-1 text-ink-faint hover:bg-[#F4F6F9] hover:text-ink" @click="zoomBy(-0.15)">
          <Minus :size="13" />
        </button>
        <span class="w-9 text-center text-[11px] text-ink-faint">{{ Math.round(zoom * 100) }}%</span>
        <button class="rounded p-1 text-ink-faint hover:bg-[#F4F6F9] hover:text-ink" @click="zoomBy(0.15)">
          <Plus :size="13" />
        </button>
      </div>
    </div>

    <div class="min-h-0 flex-1 overflow-auto bg-[#F2F4F7] p-3">
      <div v-if="mode === 'loading'" class="flex h-full items-center justify-center">
        <Loader2 :size="20" class="animate-spin text-ink-faint" />
      </div>

      <!-- PDF 模式：canvas + bbox 叠层 -->
      <div v-else-if="mode === 'pdf'" ref="canvasHost" class="mx-auto flex flex-col items-center gap-3">
        <div
          v-for="meta in metas"
          :key="meta.no"
          class="relative bg-white shadow-[0_1px_4px_rgba(0,0,0,.12)]"
        >
          <canvas :data-page="meta.no" class="block" />
          <div class="absolute inset-0">
            <button
              v-for="clause in clauses.filter((c) => c.page_no === meta.no && c.bbox)"
              :key="clause.id"
              :data-clause-id="clause.id"
              class="absolute rounded-[3px] transition-[outline,background] duration-150"
              :style="styleOf(clause) ?? undefined"
              :aria-label="clause.clause_no ?? '条款'"
              @click="pick(clause)"
            />
          </div>
          <span class="absolute -left-6 top-1 text-[10px] text-ink-faint">{{ meta.no }}</span>
        </div>
      </div>

      <!-- 文本降级模式 -->
      <div v-else class="mx-auto max-w-[720px] space-y-2">
        <p class="mb-2 flex items-start gap-1.5 rounded bg-white px-2.5 py-2 text-[11px] text-ink-soft">
          <AlertCircle :size="12" class="mt-px shrink-0 text-risk-medium" />
          PDF 原件渲染不可用（{{ failure }}），已切换为文本模式，高亮定位仍然有效。
        </p>
        <div
          v-for="clause in clauses"
          :key="clause.id"
          :data-clause-id="clause.id"
          class="rounded bg-white p-3 text-[12px] leading-relaxed transition-shadow"
          :class="[
            highlights[clause.id] ? 'cursor-pointer' : '',
            activeClauseId === clause.id ? 'ring-2 ring-brand/50' : '',
          ]"
          :style="{
            boxShadow: highlights[clause.id]
              ? `inset 3px 0 0 ${BORDER[highlights[clause.id]]}`
              : 'none',
          }"
          @click="pick(clause)"
        >
          <p v-if="clause.clause_no" class="mb-1 text-[11px] font-medium text-ink-faint">
            {{ clause.clause_no }}
          </p>
          <p class="whitespace-pre-wrap text-ink-soft">{{ clause.text }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
