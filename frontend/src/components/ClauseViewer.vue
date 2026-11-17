<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { FileText, Minus, Plus } from 'lucide-vue-next'
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

const PDF_FIRST_PAGE_TIMEOUT = 5000
const VIEW_MAX_WIDTH = 720
const MIN_ZOOM = 0.7
const MAX_ZOOM = 2

const scroller = ref<HTMLDivElement | null>(null)
const canvasHost = ref<HTMLDivElement | null>(null)
const metas = ref<PageMeta[]>([])
// text 是默认视图：先保证一定能看，再后台尝试升级成原版页面
const mode = ref<'text' | 'pdf'>('text')
const pdfState = ref<'idle' | 'loading' | 'ready' | 'failed'>('idle')
const zoom = ref(1)

let pdfDoc: any = null

const clauses = computed<Clause[]>(() => props.document?.clauses ?? [])

const COLOR: Record<RiskLevel, string> = {
  high: 'rgba(179,38,30,.10)',
  medium: 'rgba(169,106,0,.10)',
  low: 'rgba(47,107,79,.09)',
  none: 'transparent',
}
const EDGE: Record<RiskLevel, string> = {
  high: '#B3261E',
  medium: '#A96A00',
  low: '#2F6B4F',
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
    outline: props.activeClauseId === clause.id ? `1.5px solid ${EDGE[level ?? 'high']}` : 'none',
    cursor: level ? 'pointer' : 'default',
  }
}

/** 渲染任务引用：连续缩放时先取消上一轮，避免同一 canvas 并发 render 抛错 */
let renderTask: { cancel: () => void; promise: Promise<void> } | null = null
/** 加载序号：teardown/换文档后递增，在途 await 完成时发现序号不符即丢弃结果 */
let loadSeq = 0

async function paintPages() {
  if (!pdfDoc || !canvasHost.value) return
  renderTask?.cancel()
  renderTask = null
  const canvases = canvasHost.value.querySelectorAll<HTMLCanvasElement>('canvas[data-page]')
  const available = Math.min(VIEW_MAX_WIDTH, scroller.value?.clientWidth ?? VIEW_MAX_WIDTH) - 32
  // 下限只防“缩到看不清”。原来写死 460，在 390 宽屏上比容器还宽，页面直接横向溢出
  const baseScale = Math.max(available, 260) / (metas.value[0]?.widthPt || 595)

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
    const params: Record<string, unknown> = { canvasContext: ctx, viewport }
    if (dpr !== 1) params.transform = [dpr, 0, 0, dpr, 0, 0]
    const task = page.render(params)
    renderTask = task
    try {
      await task.promise
    } catch (err) {
      // 用户连续缩放时的主动取消不算异常；其余渲染错误上报但不中断其余页
      if (!(err instanceof Error && err.name === 'RenderingCancelledException')) {
        console.error('[pdf 渲染]', err)
      }
    } finally {
      if (renderTask === task) renderTask = null
    }

    const meta = metas.value.find((m) => m.no === pageNo)
    if (meta) meta.cssScale = viewport.width / meta.widthPt
  }
}

/** 首屏先渲染一页，成功才切到 PDF 视图；超时或失败就保持条款视图 */
async function upgradeToPdf() {
  if (pdfState.value !== 'idle' || !props.documentId) return
  pdfState.value = 'loading'
  const seq = loadSeq

  try {
    const bytes = await fetchDocumentFile(props.documentId)
    if (seq !== loadSeq) return
    const pdfjs: any = await import('pdfjs-dist')
    const worker: { default: string } = await import('pdfjs-dist/build/pdf.worker.min.mjs?url')
    pdfjs.GlobalWorkerOptions.workerSrc = worker.default

    const doc = await pdfjs.getDocument({ data: new Uint8Array(bytes) }).promise
    // teardown/换文档发生在加载期间：销毁刚拿到的文档，防止泄漏
    if (seq !== loadSeq) {
      void doc.destroy()
      return
    }
    pdfDoc = doc

    const pages: PageMeta[] = []
    for (let i = 1; i <= pdfDoc.numPages; i += 1) {
      const page = await pdfDoc.getPage(i)
      const vp = page.getViewport({ scale: 1 })
      pages.push({ no: i, widthPt: vp.width, heightPt: vp.height, cssScale: 1 })
    }
    metas.value = pages

    // 小屏留在条款视图：原版 PDF 在 390 宽下缩放后字太小，没有阅读价值
    if (window.innerWidth >= 640) mode.value = 'pdf'
    await nextTick()

    const firstPage = paintPages()
    let timeoutId: number | undefined
    const timeout = new Promise((_, reject) => {
      timeoutId = window.setTimeout(() => reject(new Error('render timeout')), PDF_FIRST_PAGE_TIMEOUT)
    })
    await Promise.race([firstPage, timeout])
    window.clearTimeout(timeoutId)

    pdfState.value = 'ready'

    // 首屏直接落在第一条命中条款上：PDF 第一页永远是封面，停在封面等于什么都没给
    await scrollToFirstHit()
  } catch {
    // 升级失败不影响使用，静默回落到条款视图
    mode.value = 'text'
    pdfState.value = 'failed'
  }
}

/** 原版视图首屏落到第一条命中条款，别停在封面上 */
let autoScrolled = false
async function scrollToFirstHit() {
  if (autoScrolled) return
  if (mode.value !== 'pdf' || pdfState.value !== 'ready') return
  const ids = Object.keys(props.highlights)
  if (!ids.length) return
  await nextTick()

  // 有 bbox 就精确滚到条款框；没有就退到它所在的那一页
  for (const id of ids) {
    const clause = clauses.value.find((c) => c.id === id)
    const box = scroller.value?.querySelector<HTMLElement>(`[data-clause-id="${id}"]`)
    const canvas = clause
      ? scroller.value?.querySelector<HTMLElement>(`canvas[data-page="${clause.page_no}"]`)
      : null
    const target = box ?? canvas?.parentElement
    if (!target) continue
    target.scrollIntoView({ block: 'center', inline: 'nearest' })
    autoScrolled = true
    return
  }
}

// PDF 通常比结论先就绪，所以命中进来后再补一次跳转
watch(
  () => Object.keys(props.highlights).length,
  (n) => {
    if (n > 0 && mode.value === 'pdf' && pdfState.value === 'ready') void scrollToFirstHit()
  },
)
/** 释放 pdf.js 文档与 worker：不销毁的话，换文档 / 卸载组件后内存会一直挂着 */
function teardownPdf() {
  loadSeq += 1
  renderTask?.cancel()
  renderTask = null
  if (pdfDoc) {
    pdfDoc.destroy()
    pdfDoc = null
  }
  metas.value = []
  pdfState.value = 'idle'
  mode.value = 'text'
  autoScrolled = false
}

onBeforeUnmount(teardownPdf)

watch(
  () => props.documentId,
  (id) => {
    if (!id) return
    // 路由参数变化会复用组件实例，必须先清掉上一份 PDF，否则 upgradeToPdf 的
    // idle 守卫会拦住重载，页面停留在旧文档上
    teardownPdf()
    void upgradeToPdf()
  },
  { immediate: true },
)

function zoomBy(delta: number) {
  const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Number((zoom.value + delta).toFixed(2))))
  if (next === zoom.value) return
  zoom.value = next
  void paintPages()
}

/**
 * PDF 抽出来的文本是"视觉行"，直接展示会把一句话拆成多行。
 * 这里按句末标点/编号起点做段落重排，恢复可读的分段。
 */
function reflow(text: string): string {
  const raw = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)

  // 竖排的单字（"填 / 写 / 说 / 明"）先并回一行
  const lines: string[] = []
  for (const line of raw) {
    const prev = lines[lines.length - 1]
    if (line.length === 1 && prev && prev.length === 1) lines[lines.length - 1] = prev + line
    else lines.push(line)
  }

  const result: string[] = []
  const startsNewBlock = /^([（(][一二三四五六七八九十\d]+[)）]|\d+[.、]|第[一二三四五六七八九十百零〇]+[条款])/

  for (const line of lines) {
    const prev = result[result.length - 1]
    const breakBefore = !prev || startsNewBlock.test(line) || /[。！？；：]$/.test(prev) || prev.length < 18
    if (breakBefore) result.push(line)
    else result[result.length - 1] = prev + line
  }
  return result.join('\n')
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
</script>

<template>
  <div ref="scroller" class="flex h-full flex-col overflow-hidden border border-line bg-white">
    <div class="flex items-center justify-between border-b border-line px-3.5 py-2.5">
      <div class="flex items-center gap-3">
        <p class="flex items-center gap-1.5 text-[12px] text-ink">
          <FileText :size="13" class="text-ink-faint" />
          合同原文
          <span v-if="document" class="num text-[11px] font-normal text-ink-faint">
            · {{ document.clauses.length }} 条 · {{ document.pages.length }} 页
          </span>
        </p>
        <div v-if="pdfState === 'ready'" class="flex overflow-hidden rounded-sm border border-line">
          <button
            class="min-h-[28px] px-2.5 py-1 text-[11px] transition-colors"
            :class="mode === 'text' ? 'bg-ink text-white' : 'text-ink-faint hover:text-ink'"
            @click="mode = 'text'"
          >条款</button>
          <button
            class="min-h-[28px] px-2.5 py-1 text-[11px] transition-colors"
            :class="mode === 'pdf' ? 'bg-ink text-white' : 'text-ink-faint hover:text-ink'"
            @click="mode = 'pdf'"
          >原版</button>
        </div>
      </div>

      <div v-if="mode === 'pdf'" class="flex items-center gap-1">
        <button class="p-1 text-ink-faint transition-colors hover:text-accent" @click="zoomBy(-0.15)">
          <Minus :size="13" />
        </button>
        <span class="num w-9 text-center text-[11px] text-ink-faint">{{ Math.round(zoom * 100) }}%</span>
        <button class="p-1 text-ink-faint transition-colors hover:text-accent" @click="zoomBy(0.15)">
          <Plus :size="13" />
        </button>
      </div>
    </div>

    <div class="min-h-0 flex-1 overflow-auto bg-paper-deep p-4">
      <!-- 原版页面：canvas + bbox 叠层 -->
      <div v-if="mode === 'pdf'" ref="canvasHost" class="mx-auto flex flex-col items-center gap-3">
        <div
          v-for="meta in metas"
          :key="meta.no"
          class="relative bg-white shadow-page"
        >
          <canvas :data-page="meta.no" class="block" />
          <div class="absolute inset-0">
            <button
              v-for="clause in clauses.filter((c) => c.page_no === meta.no && c.bbox)"
              :key="clause.id"
              :data-clause-id="clause.id"
              class="absolute rounded-[2px] transition-[outline] duration-150"
              :style="styleOf(clause) ?? undefined"
              :aria-label="clause.clause_no ?? '条款'"
              @click="pick(clause)"
            />
          </div>
          <span class="num absolute -left-5 top-1 text-[10px] text-ink-faint">{{ meta.no }}</span>
        </div>
      </div>

      <!-- 条款视图（默认）：段落式排版，命中风险时左侧压色 -->
      <div v-else class="mx-auto max-w-[680px] space-y-1.5">
        <div
          v-for="clause in clauses"
          :key="clause.id"
          :data-clause-id="clause.id"
          class="border-l-2 py-2 pl-3.5 pr-2 transition-colors duration-200"
          :class="[
            highlights[clause.id] ? 'cursor-pointer hover:bg-white/70' : '',
            activeClauseId === clause.id ? 'bg-white' : '',
          ]"
          :style="{
            borderLeftColor: EDGE[highlights[clause.id] ?? 'none'],
            background: activeClauseId === clause.id ? '#fff' : COLOR[highlights[clause.id] ?? 'none'],
          }"
          @click="pick(clause)"
        >
          <p v-if="clause.clause_no" class="mb-1 font-serif text-[11.5px] tracking-wide text-ink-faint">
            {{ clause.clause_no }}
          </p>
          <p class="whitespace-pre-wrap text-[15px] leading-[1.9] text-ink-soft">
            {{ reflow(clause.text) }}
          </p>
        </div>

        <p v-if="!clauses.length" class="py-16 text-center text-[12px] text-ink-faint">
          正在读取条款…
        </p>
      </div>
    </div>
  </div>
</template>
