<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { AlertCircle, ArrowRight, Check, FileText, Loader2 } from 'lucide-vue-next'
import { uploadDocument } from '@/api/review'
import SectionCollapse from '@/components/SectionCollapse.vue'

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

/** 三步流程：参考工具类落地页的惯例，把"会发生什么"先讲清楚 */
const steps = [
  {
    title: '上传合同',
    desc: '拖入 PDF 或合同照片，自动识别租赁 / 劳动 / 培训贷类型，条款自动切分定位。',
  },
  {
    title: '逐条核对',
    desc: '按对应类型的审查清单，逐条比对本地法规库，标出风险等级与低置信度项。',
  },
  {
    title: '拿到建议',
    desc: '每条给修改方向与谈判次序，汇总成报告，可一键打印导出 PDF。',
  },
]

/** 特性网格：只写产品真的做到的事，不写口号 */
const features = [
  {
    title: '依据到条号',
    desc: '每条结论附法条编号与原文引用，可直接跳到法规库核对原文，不凭感觉说话。',
  },
  {
    title: '分级不糊弄',
    desc: '高 / 中 / 低风险之外，置信度不足的结论会明确标出「待复核」，而不是硬给一个答案。',
  },
  {
    title: '谈判有次序',
    desc: '结论标注「必守 / 可谈 / 可让步」，先谈什么、后让什么，进场前心里有数。',
  },
  {
    title: '会话内隔离',
    desc: '文件仅存于本次匿名会话，可随时删除；不注册、不收集姓名手机号等身份信息。',
  },
]

const faqs = [
  {
    q: '它能代替律师吗？',
    a: '不能。它只做风险提示与沟通方向参考，结论由算法和模型生成，可能出错。金额较大、情况复杂的合同，请咨询执业律师。',
  },
  {
    q: '我的合同会被保存或泄露吗？',
    a: '上传的文件只与你的匿名会话绑定，可随时删除；不注册、不收集身份信息。审查过程会把条款文本发送给大模型服务完成判定，如含身份证号、银行卡号等敏感信息，建议上传前遮盖。',
  },
  {
    q: '支持哪些合同类型？',
    a: '目前覆盖房屋租赁、实习 / 劳动、培训贷 / 预付卡三类。其他类型也能审查，但按通用条款处理，结论仅供参考。',
  },
  {
    q: '结论的依据是什么？',
    a: '本地法规库收录民法典、劳动合同法、民事诉讼法、消费者权益保护法、社会保险法五部法律全文；每条结论都标注具体条号与原文，可在「法规库」页面直接核对。',
  },
  {
    q: '一次审查要多久？',
    a: '通常十几秒到一分钟，取决于合同页数与条款数量。审查过程有实时进度，可以看到核到了哪一条。',
  },
]

const GRID = {
  backgroundImage: 'radial-gradient(circle, #D8D3C6 1px, transparent 1px)',
  backgroundSize: '18px 18px',
}

function openPicker() {
  fileInput.value?.click()
}

/**
 * 微信内置浏览器（X5 内核）的文件选择器不支持选 PDF，
 * 点"选择合同 PDF"只会弹出拍摄/相册。前端绕不过，只能引导换浏览器打开。
 */
const inWeChat = /MicroMessenger/i.test(navigator.userAgent)

/** 示例合同：不用自己找文件，点一下就能看到完整审查流程 */
const demoLoading = ref(false)

async function loadDemo() {
  if (demoLoading.value) return
  demoLoading.value = true
  errorMsg.value = ''
  try {
    const resp = await fetch('/samples/demo-lease.pdf')
    if (!resp.ok) throw new Error(`示例文件加载失败（${resp.status}）`)
    const blob = await resp.blob()
    selected.value = new File([blob], '示例合同_长租机构版.pdf', { type: 'application/pdf' })
    await submit()
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '示例合同加载失败，请直接上传文件。'
    demoLoading.value = false
  }
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
  const name = file.name.toLowerCase()
  const isPdf = file.type === 'application/pdf' || name.endsWith('.pdf')
  const isImage = file.type.startsWith('image/') || /\.(jpg|jpeg|png)$/.test(name)
  if (!isPdf && !isImage) {
    errorMsg.value = '请上传 PDF，或合同的照片 / 扫描件（JPG、PNG）。'
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
  dragDepth = 0
  dragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) acceptFile(file)
}

/**
 * dragleave 会在穿过子元素时反复触发，直接开关 dragging 会闪烁；
 * 用 dragenter/leave 的深度计数，进出子元素相抵消，只有真正离开才熄灭。
 */
let dragDepth = 0

function onDragEnter() {
  dragDepth += 1
  dragging.value = true
}

function onDragLeave() {
  dragDepth = Math.max(0, dragDepth - 1)
  if (dragDepth === 0) dragging.value = false
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
        v-if="inWeChat"
        class="mb-4 flex items-start gap-2.5 border border-risk-medium/40 bg-risk-medium/5 px-3.5 py-3"
        role="alert"
      >
        <AlertCircle :size="15" class="mt-0.5 shrink-0 text-risk-medium" />
        <p class="text-[12px] leading-relaxed text-ink-soft">
          当前在微信内打开，可能无法选择 PDF 文件（只能拍照 / 相册）。
          点右上角「···」选择<b class="text-ink">「在浏览器打开」</b>即可正常上传。
          相册里的合同照片也可以直接审查。
        </p>
      </div>
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
        @dragover.prevent
        @dragenter.prevent="onDragEnter"
        @dragleave.prevent="onDragLeave"
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
          也可以点击下方按钮选择 · PDF / JPG / PNG · ≤ {{ MAX_MB }}MB
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
          accept="application/pdf,.pdf,image/jpeg,image/png"
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

        <button
          type="button"
          class="btn-ghost"
          :disabled="demoLoading"
          @click="loadDemo"
        >
          <Loader2 v-if="demoLoading" :size="14" class="animate-spin" />
          <span>{{ demoLoading ? '正在加载示例…' : '没有合同？用示例试一试' }}</span>
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

    <!-- 三步流程：先讲清楚"会发生什么"，降低上传的心理门槛 -->
    <section class="mt-14">
      <p class="label">如何使用</p>
      <h2 class="mt-2 font-serif text-[20px] text-ink">三步拿到审查结论</h2>
      <ol class="mt-5 grid gap-px border border-line bg-line sm:grid-cols-3">
        <li v-for="(s, i) in steps" :key="s.title" class="bg-white px-4 py-4">
          <p class="num font-serif text-[13px] text-accent">0{{ i + 1 }}</p>
          <h3 class="mt-2 font-serif text-[14px] text-ink">{{ s.title }}</h3>
          <p class="mt-1.5 text-[11.5px] leading-[1.8] text-ink-soft">{{ s.desc }}</p>
        </li>
      </ol>
    </section>

    <!-- 特性：只写做得到的事，建立信任 -->
    <section class="mt-14">
      <p class="label">为什么可信</p>
      <h2 class="mt-2 font-serif text-[20px] text-ink">结论给依据，不糊弄</h2>
      <div class="mt-5 grid gap-3 sm:grid-cols-2">
        <div v-for="f in features" :key="f.title" class="border border-line bg-white px-4 py-4">
          <h3 class="font-serif text-[14px] text-ink">{{ f.title }}</h3>
          <p class="mt-1.5 text-[11.5px] leading-[1.8] text-ink-soft">{{ f.desc }}</p>
        </div>
      </div>
    </section>

    <!-- 常见问题：复用折叠组件 -->
    <section class="mt-14">
      <p class="label">常见问题</p>
      <h2 class="mt-2 font-serif text-[20px] text-ink">问得最多的几件事</h2>
      <div class="mt-2 border-t border-line">
        <SectionCollapse v-for="item in faqs" :key="item.q" :title="item.q">
          <p class="text-[12px] leading-[1.9] text-ink-soft">{{ item.a }}</p>
        </SectionCollapse>
      </div>
    </section>

  </div>
</template>
