<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { AlertCircle, FileText, House, Lock, Scale, Upload, Wallet } from 'lucide-vue-next'
import { uploadDocument } from '@/api/review'

const router = useRouter()

const MAX_MB = 20
const fileInput = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const uploading = ref(false)
const errorMsg = ref('')
const selected = ref<File | null>(null)

const selectedSize = computed(() =>
  selected.value ? (selected.value.size / 1024 / 1024).toFixed(1) : '',
)

const contractTypes = [
  { icon: House, title: '房屋租赁合同', desc: '押金、涨租、维修、提前退租' },
  { icon: Wallet, title: '实习 / 劳动合同', desc: '试用期、竞业、社保、违约金' },
  { icon: Scale, title: '培训贷 / 预付卡', desc: '退费、捆绑销售、贷款披露' },
]

function openPicker() {
  fileInput.value?.click()
}

function acceptFile(file: File) {
  errorMsg.value = ''
  if (file.type !== 'application/pdf') {
    errorMsg.value = '当前仅支持文字版 PDF。图片合同的 OCR 解析尚未开启，请先转成 PDF。'
    return
  }
  if (file.size > MAX_MB * 1024 * 1024) {
    errorMsg.value = `文件大小 ${(file.size / 1024 / 1024).toFixed(1)}MB，超出 ${MAX_MB}MB 上限。`
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
  if (!selected.value || uploading.value) return
  uploading.value = true
  errorMsg.value = ''
  try {
    const result = await uploadDocument(selected.value)
    await router.push({ name: 'review', params: { docId: result.document_id } })
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '上传失败，请重试'
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <div class="mx-auto w-full max-w-6xl px-4 py-12 sm:px-6 sm:py-16">
    <!-- 价值主张 -->
    <section class="mx-auto max-w-2xl text-center">
      <h1 class="text-[30px] font-semibold leading-tight tracking-tight text-ink sm:text-[38px]">
        签之前，先看清哪里会吃亏
      </h1>
      <p class="mt-4 text-[15px] leading-relaxed text-ink-soft">
        上传一份合同，逐条标出高风险条款，给出法条依据和可谈的方向。
        <br class="hidden sm:block" />
        面向租房、实习、培训贷——最容易踩坑、又最没人帮你看的三类合同。
      </p>
    </section>

    <!-- 上传区 -->
    <section class="mx-auto mt-10 max-w-2xl">
      <div
        class="card cursor-pointer border-2 border-dashed p-8 text-center transition-colors sm:p-10"
        :class="dragging ? 'border-brand bg-brand-light/40' : 'border-[#DDE2EA] hover:border-brand/50'"
        role="button"
        tabindex="0"
        @click="openPicker"
        @keydown.enter="openPicker"
        @keydown.space.prevent="openPicker"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
      >
        <div class="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-brand-light text-brand">
          <Upload :size="22" :stroke-width="2" />
        </div>
        <p class="mt-4 text-sm font-medium text-ink">把合同 PDF 拖进来，或点击选择文件</p>
        <p class="mt-1.5 text-xs text-ink-faint">支持文字版 PDF，≤ {{ MAX_MB }}MB，≤ 80 页</p>

        <div v-if="selected" class="mt-4 inline-flex items-center gap-2 rounded-card bg-[#F4F6F9] px-3 py-1.5 text-xs text-ink-soft">
          <FileText :size="14" />
          <span class="max-w-[240px] truncate">{{ selected.name }}</span>
          <span class="text-ink-faint">{{ selectedSize }}MB</span>
        </div>

        <input ref="fileInput" type="file" accept="application/pdf" class="hidden" @change="onFileChange" />
      </div>

      <div class="mt-4 flex items-center justify-between gap-3">
        <p v-if="errorMsg" class="flex items-start gap-1.5 text-xs leading-relaxed text-risk-high">
          <AlertCircle :size="14" class="mt-0.5 shrink-0" />
          {{ errorMsg }}
        </p>
        <p v-else class="text-xs text-ink-faint">
          上传即表示同意：文件仅用于本次审查，可随时删除。
        </p>

        <button class="btn-primary shrink-0" :disabled="!selected || uploading" @click.stop="submit">
          {{ uploading ? '上传中…' : '开始审查' }}
        </button>
      </div>
    </section>

    <!-- 支持范围 -->
    <section class="mx-auto mt-14 max-w-2xl">
      <p class="text-xs font-medium uppercase tracking-wider text-ink-faint">覆盖范围</p>
      <div class="mt-3 grid gap-3 sm:grid-cols-3">
        <div v-for="t in contractTypes" :key="t.title" class="card p-4">
          <component :is="t.icon" :size="18" class="text-brand" :stroke-width="1.9" />
          <p class="mt-2.5 text-sm font-medium text-ink">{{ t.title }}</p>
          <p class="mt-1 text-xs leading-relaxed text-ink-faint">{{ t.desc }}</p>
        </div>
      </div>
      <p class="mt-3 text-xs text-ink-faint">
        其他类型合同会明确提示「暂不支持」，不会给出不可靠的结论。
      </p>
    </section>

    <!-- 隐私说明 -->
    <section class="mx-auto mt-10 max-w-2xl">
      <div class="flex items-start gap-3 rounded-card border border-[#E9EBF0] bg-white p-4">
        <Lock :size="16" class="mt-0.5 shrink-0 text-ink-soft" />
        <div class="text-xs leading-relaxed text-ink-soft">
          <p class="font-medium text-ink">原件不入公开库</p>
          <p class="mt-1 text-ink-faint">
            合同仅存于本次会话，按匿名 session 隔离；身份证号、手机号、银行卡号入库前自动打码，
            日志不记录合同正文。审查完成后可一键删除文件与结论。
          </p>
        </div>
      </div>
    </section>
  </div>
</template>
