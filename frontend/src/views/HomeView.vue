<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { AlertCircle, ArrowRight, Check, FileText, Loader2 } from 'lucide-vue-next'
import { uploadDocument } from '@/api/review'

const router = useRouter()

const MAX_MB = 20
const fileInput = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const phase = ref<'idle' | 'uploading' | 'done'>('idle')
const errorMsg = ref('')
const selected = ref<File | null>(null)

const selectedSize = computed(() =>
  selected.value ? (selected.value.size / 1024 / 1024).toFixed(1) : '',
)
const primaryLabel = computed(() => {
  if (phase.value === 'uploading') return '解析中'
  if (phase.value === 'done') return '已受理'
  return selected.value ? '开始审查' : '选择合同 PDF'
})

const facts = [
  ['合同类型', '房屋租赁 / 劳动 / 培训贷'],
  ['文件处理', '仅存本次会话，可随时删除'],
  ['结论依据', '法条编号 + 原文引用'],
]

const GRID = {
  backgroundImage: 'radial-gradient(circle, #D8D3C6 1px, transparent 1px)',
  backgroundSize: '18px 18px',
}

function openPicker() {
  fileInput.value?.click()
}

function onPrimary() {
  if (!selected.value) {
    openPicker()
    return
  }
  void submit()
}

function acceptFile(file: File) {
  errorMsg.value = ''
  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
  if (!isPdf) {
    errorMsg.value = '当前仅支持文字版 PDF。图片合同的多模态解析尚未开启。'
    return
  }
  if (file.size > MAX_MB * 1024 * 1024) {
    errorMsg.value = `文件 ${(file.size / 1024 / 1024).toFixed(1)}MB，超出 ${MAX_MB}MB 上限。`
    return
  }
  selected.value = file
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) acceptFile(file)
  input.value = ''
}

function onDrop(e: DragEvent) {
  dragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) acceptFile(file)
}

async function submit() {
  if (!selected.value || phase.value === 'uploading') return
  phase.value = 'uploading'
  errorMsg.value = ''
  try {
    const result = await uploadDocument(selected.value)
    phase.value = 'done'
    await new Promise((resolve) => window.setTimeout(resolve, 420))
    await router.push({ name: 'review', params: { docId: result.document_id } })
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '上传失败，请重试'
    phase.value = 'idle'
  }
}
</script>

<template>
  <div class="mx-auto w-full max-w-[880px] px-4 sm:px-6">
    <!-- 主视觉：居中，只留一句话和两个动作 -->
    <section class="pt-16 text-center sm:pt-24">
      <h1 class="font-serif text-[30px] leading-tight tracking-tightest text-ink sm:text-[36px]">
        合同风险审查
      </h1>
      <p class="mx-auto mt-4 max-w-[480px] text-[12.5px] leading-[1.9] text-ink-soft">
        上传合同 PDF，自动识别类型，逐条核对并指出有风险的条款。
      </p>
    </section>

    <!-- 投放区 -->
    <section class="mt-9">
      <div
        class="group relative flex min-h-[240px] cursor-pointer flex-col items-center justify-center overflow-hidden border border-dashed px-6 py-10 text-center transition-colors duration-200 sm:min-h-[260px]"
        :class="
          dragging
            ? 'border-ink bg-paper-deep'
            : 'border-line-strong bg-white hover:border-ink/40'
        "
        role="button"
        tabindex="0"
        @click="openPicker"
        @keydown.enter="openPicker"
        @keydown.space.prevent="openPicker"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
      >
        <span
          class="pointer-events-none absolute inset-0 transition-opacity duration-300"
          :class="dragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-40'"
          :style="GRID"
        />

        <span
          class="relative flex h-12 w-12 items-center justify-center border border-line bg-paper text-ink-soft transition-all duration-300 ease-calm group-hover:border-ink/30 group-hover:text-ink"
          :class="dragging ? '-translate-y-1 scale-105' : ''"
        >
          <FileText :size="21" :stroke-width="1.5" />
        </span>

        <p class="relative mt-5 font-serif text-[16px] text-ink">把合同 PDF 拖到这里</p>
        <p class="relative mt-1.5 text-[11.5px] text-ink-faint">
          也可以点击下方按钮选择 · ≤ {{ MAX_MB }}MB、≤ 80 页
        </p>

        <p
          v-if="selected"
          class="animate-rise relative mt-4 flex items-center gap-2 border border-line bg-paper px-2.5 py-1.5 text-[12px] text-ink-soft"
        >
          <FileText :size="13" class="text-ink-faint" />
          <span class="max-w-[260px] truncate">{{ selected.name }}</span>
          <span class="num text-ink-faint">{{ selectedSize }} MB</span>
        </p>

        <input
          ref="fileInput"
          type="file"
          accept="application/pdf,.pdf"
          class="hidden"
          @change="onFileChange"
        />
      </div>

      <!-- 两个动作：实心主按钮 + 描边次按钮 -->
      <div class="mt-5 flex flex-wrap items-center justify-center gap-3">
        <button
          class="btn-primary min-w-[148px]"
          :class="phase === 'done' ? '!bg-risk-low' : ''"
          :disabled="phase === 'uploading'"
          @click="onPrimary"
        >
          <Loader2 v-if="phase === 'uploading'" :size="14" class="animate-spin" />
          <Check v-else-if="phase === 'done'" :size="14" />
          <FileText v-else-if="!selected" :size="14" />
          <span>{{ primaryLabel }}</span>
          <ArrowRight v-if="phase === 'idle' && selected" :size="14" />
        </button>

        <RouterLink to="/guide" class="btn-ghost">查看使用说明</RouterLink>
      </div>

      <p
        v-if="errorMsg"
        class="mt-3 flex items-center justify-center gap-1.5 text-[11px] text-risk-high"
      >
        <AlertCircle :size="13" />
        {{ errorMsg }}
      </p>
    </section>

    <!-- 一行事实，不堆信息 -->
    <dl class="mt-10 grid gap-px border-y border-line bg-line sm:grid-cols-3">
      <div v-for="[k, v] in facts" :key="k" class="bg-paper px-3 py-3 text-center">
        <dt class="label">{{ k }}</dt>
        <dd class="mt-1 text-[11.5px] text-ink-soft">{{ v }}</dd>
      </div>
    </dl>

  </div>
</template>
