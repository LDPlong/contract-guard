<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { AlertCircle, ArrowRight, FileText, Loader2 } from 'lucide-vue-next'
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

const coverage = [
  {
    no: '01',
    title: '房屋租赁合同',
    desc: '押金退还、违约金、涨租、转租、维修责任、提前退租',
  },
  {
    no: '02',
    title: '实习 / 劳动合同',
    desc: '试用期、竞业限制、服务期违约金、社保、加班与补偿',
  },
  {
    no: '03',
    title: '培训贷 / 预付卡',
    desc: '贷款披露、退费条款、捆绑销售、退课违约金',
  },
]

const flow = [
  { no: 'Ⅰ', title: '读条款', desc: '按「第X条」切分，保留页码与坐标' },
  { no: 'Ⅱ', title: '对法条', desc: '检索民法典、劳动合同法原文，逐条比对' },
  { no: 'Ⅲ', title: '给方向', desc: '指出风险、标注依据、给出可谈的修改方向' },
]

function openPicker() {
  fileInput.value?.click()
}

function acceptFile(file: File) {
  errorMsg.value = ''
  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
  if (!isPdf) {
    errorMsg.value = '当前仅支持文字版 PDF。图片合同的多模态解析尚在接入中。'
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
  <div class="mx-auto w-full max-w-[1240px] px-4 sm:px-6">
    <!-- 主视觉：左标题右说明，中间一条竖线 -->
    <section class="grid gap-10 border-b border-line py-14 lg:grid-cols-[1.35fr_1fr] lg:gap-16 lg:py-20">
      <div>
        <p class="label">Contract Review · 面向个人</p>
        <h1 class="mt-5 font-serif text-[38px] leading-[1.18] tracking-tightest text-ink sm:text-[52px]">
          签之前，<br />
          先看清哪里<span class="border-b-2 border-risk-high/60 pb-[3px]">会吃亏</span>
        </h1>
        <p class="mt-6 max-w-lg text-[15px] leading-[1.85] text-ink-soft">
          上传一份合同，逐条标出高风险条款，每条结论都绑定法条原文。
          面向租房、实习、培训贷——最容易踩坑、又最没人帮你看的三类合同。
        </p>
      </div>

      <div class="flex flex-col justify-end lg:border-l lg:border-line lg:pl-10">
        <dl class="grid grid-cols-3 gap-4">
          <div>
            <dt class="label">覆盖类型</dt>
            <dd class="num mt-1.5 font-serif text-[26px] leading-none text-ink">3</dd>
            <p class="mt-1 text-[11px] text-ink-faint">类合同</p>
          </div>
          <div>
            <dt class="label">审查项</dt>
            <dd class="num mt-1.5 font-serif text-[26px] leading-none text-ink">24</dd>
            <p class="mt-1 text-[11px] text-ink-faint">条清单</p>
          </div>
          <div>
            <dt class="label">法条库</dt>
            <dd class="num mt-1.5 font-serif text-[26px] leading-none text-ink">1358</dd>
            <p class="mt-1 text-[11px] text-ink-faint">条现行有效</p>
          </div>
        </dl>
        <p class="mt-6 text-[11px] leading-relaxed text-ink-faint">
          只做风险提示与修改方向，不代拟文书、不预测结果。
        </p>
      </div>
    </section>

    <!-- 上传：左侧编号标签 + 右侧投递区 -->
    <section class="grid gap-8 border-b border-line py-12 lg:grid-cols-[220px_1fr] lg:gap-16">
      <div>
        <p class="label">Step 01</p>
        <h2 class="mt-2 font-serif text-[22px] leading-snug text-ink">上传合同</h2>
        <p class="mt-2 text-[12px] leading-relaxed text-ink-faint">
          文字版 PDF，≤ {{ MAX_MB }}MB，≤ 80 页。原件仅存于本次会话，可随时删除。
        </p>
      </div>

      <div>
        <div
          class="group cursor-pointer border border-dashed p-8 transition-colors duration-200 sm:p-10"
          :class="
            dragging
              ? 'border-accent bg-accent-wash/60'
              : 'border-line-strong bg-white hover:border-accent/60'
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
          <div class="flex flex-col items-center text-center sm:flex-row sm:items-center sm:gap-5 sm:text-left">
            <span
              class="flex h-11 w-11 shrink-0 items-center justify-center border border-line bg-paper text-ink-soft transition-colors group-hover:border-accent/40 group-hover:text-accent"
            >
              <FileText :size="19" :stroke-width="1.6" />
            </span>
            <div class="mt-3 sm:mt-0">
              <p class="text-[14px] font-medium text-ink">把合同 PDF 拖到这里，或点击选择</p>
              <p class="mt-1 text-[11px] text-ink-faint">
                识别为「房屋租赁 / 劳动 / 培训贷」后自动加载对应审查清单
              </p>
            </div>
          </div>

          <div
            v-if="selected"
            class="mt-5 flex items-center gap-2 border-t border-line pt-4 text-[12px] text-ink-soft"
          >
            <FileText :size="13" class="text-ink-faint" />
            <span class="max-w-[320px] truncate">{{ selected.name }}</span>
            <span class="num text-ink-faint">{{ selectedSize }} MB</span>
          </div>

          <input
            ref="fileInput"
            type="file"
            accept="application/pdf,.pdf"
            class="hidden"
            @change="onFileChange"
          />
        </div>

        <div class="mt-4 flex items-center justify-between gap-4">
          <p v-if="errorMsg" class="flex items-start gap-1.5 text-[11px] leading-relaxed text-risk-high">
            <AlertCircle :size="13" class="mt-0.5 shrink-0" />
            {{ errorMsg }}
          </p>
          <p v-else class="text-[11px] text-ink-faint">上传即表示同意：文件仅用于本次审查。</p>

          <button class="btn-primary shrink-0" :disabled="!selected || uploading" @click.stop="submit">
            <Loader2 v-if="uploading" :size="14" class="animate-spin" />
            <span>{{ uploading ? '上传中' : '开始审查' }}</span>
            <ArrowRight v-if="!uploading" :size="14" />
          </button>
        </div>
      </div>
    </section>

    <!-- 覆盖范围：编号列表，不用卡片网格 -->
    <section class="grid gap-8 border-b border-line py-12 lg:grid-cols-[220px_1fr] lg:gap-16">
      <div>
        <p class="label">Step 02</p>
        <h2 class="mt-2 font-serif text-[22px] leading-snug text-ink">覆盖范围</h2>
        <p class="mt-2 text-[12px] leading-relaxed text-ink-faint">
          其他类型会明确提示「暂不支持」，不给不可靠的结论。
        </p>
      </div>

      <div class="grid gap-px bg-line sm:grid-cols-3">
        <div v-for="item in coverage" :key="item.no" class="bg-white p-5">
          <p class="num font-serif text-[13px] text-accent">{{ item.no }}</p>
          <h3 class="mt-2 text-[14px] font-medium text-ink">{{ item.title }}</h3>
          <p class="mt-1.5 text-[11px] leading-relaxed text-ink-faint">{{ item.desc }}</p>
        </div>
      </div>
    </section>

    <!-- 流程 -->
    <section class="grid gap-8 py-12 lg:grid-cols-[220px_1fr] lg:gap-16">
      <div>
        <p class="label">How it works</p>
        <h2 class="mt-2 font-serif text-[22px] leading-snug text-ink">它做了什么</h2>
      </div>

      <ol class="grid gap-6 sm:grid-cols-3">
        <li v-for="step in flow" :key="step.no" class="border-t border-ink/15 pt-4">
          <p class="num font-serif text-[15px] text-ink">{{ step.no }}</p>
          <p class="mt-2 text-[13px] font-medium text-ink">{{ step.title }}</p>
          <p class="mt-1 text-[11px] leading-relaxed text-ink-faint">{{ step.desc }}</p>
        </li>
      </ol>
    </section>
  </div>
</template>
