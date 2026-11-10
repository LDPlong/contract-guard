<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { AlertCircle, ArrowRight, Check, FileText, Loader2 } from 'lucide-vue-next'
import { uploadDocument } from '@/api/review'
import SectionCollapse from '@/components/SectionCollapse.vue'

const router = useRouter()

const MAX_MB = 20
const fileInput = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const phase = ref<'idle' | 'uploading' | 'done'>('idle')
const uploading = computed(() => phase.value === 'uploading')
const errorMsg = ref('')
const selected = ref<File | null>(null)

const selectedSize = computed(() =>
  selected.value ? (selected.value.size / 1024 / 1024).toFixed(1) : '',
)

const facts = [
  ['支持范围', '3 类合同 · 24 项审查'],
  ['法条库', '民法典 1260 · 劳动合同法 98'],
  ['输入', '文字版 PDF · ≤ 20MB'],
  ['输出', '风险等级 · 依据原文 · 修改方向'],
]

const checklists = [
  {
    key: 'lease',
    title: '房屋租赁合同',
    count: 10,
    items: [
      ['押金退还条件与时限', '民法典 733'],
      ['违约金比例', '民法典 585'],
      ['单方解除权', '民法典 562、563'],
      ['转租条款', '民法典 716'],
      ['维修责任', '民法典 712、713'],
      ['涨租条款', '民法典 543'],
      ['提前退租责任', '民法典 584、585'],
      ['房屋权属与抵押', '民法典 725'],
      ['必备条款缺失', '民法典 704'],
      ['争议解决与管辖', '民事诉讼法 35'],
    ],
  },
  {
    key: 'labor',
    title: '实习 / 劳动合同',
    count: 8,
    items: [
      ['试用期期限', '劳动合同法 19'],
      ['试用期工资', '劳动合同法 20'],
      ['竞业限制', '劳动合同法 23、24'],
      ['违约金条款', '劳动合同法 25'],
      ['服务期与培训费', '劳动合同法 22'],
      ['社会保险约定', '劳动合同法 38'],
      ['加班与调休', '劳动合同法 31'],
      ['解除与经济补偿', '劳动合同法 39、46'],
    ],
  },
  {
    key: 'prepaid',
    title: '培训贷 / 预付卡',
    count: 6,
    items: [
      ['贷款性质与利率披露', '民法典 496'],
      ['退费条款', '民法典 497'],
      ['捆绑销售', '民法典 497'],
      ['解除与冷静期', '民法典 563'],
      ['退课违约金', '民法典 585'],
      ['主体资质与责任', '民法典 465'],
    ],
  },
]

const samples = [
  {
    level: '高',
    text: '乙方提前退租的，押金及剩余租金不予退还。',
    item: 'L07 提前退租责任',
    ref: '民法典 第五百八十五条',
    why: '押金与剩余租金全额不退，惩罚明显超过出租人实际损失，属于违约金过高的情形。',
  },
  {
    level: '高',
    text: '乙方在试用期内提出离职的，应向甲方支付违约金五千元。',
    item: 'W04 违约金条款',
    ref: '劳动合同法 第二十五条',
    why: '除服务期与竞业限制外，用人单位不得与劳动者约定由劳动者承担违约金。',
  },
  {
    level: '中',
    text: '租赁期内甲方有权根据市场情况调整租金，乙方应按调整后金额支付。',
    item: 'L06 涨租条款',
    ref: '民法典 第五百四十三条',
    why: '变更合同需双方协商一致，单方定价权使承租人无法预判成本。',
  },
]

const faq = [
  [
    '扫描件和拍照为什么暂不支持？',
    '需要 OCR 或多模态模型逐页识别，当前版本只处理带文字层的 PDF。扫描件请先转成可搜索 PDF 再上传。',
  ],
  [
    '「待复核」是什么意思？',
    '模型置信度低于 0.6，或没有检索到可引用的法条。这类结论不计入风险评分，建议对照原文人工确认。',
  ],
  [
    '法条库覆盖到哪些法规？',
    '民法典全文 1260 条、劳动合同法全文 98 条。民事诉讼法、消费者权益保护法尚未入库，相关审查项会显示未检索到直接依据。',
  ],
  [
    '上传的文件会保留多久？',
    '存于本次会话目录，按匿名 session 隔离，可在审查页直接删除；服务端日志只记录长度与哈希，不记录正文。',
  ],
]

const legend = [
  ['高', '可能造成直接经济损失，或使一方丧失核心权利', 'text-risk-high'],
  ['中', '权利义务明显失衡，但可通过协商修正', 'text-risk-medium'],
  ['低', '表述不规范、缺少一般性约定，影响有限', 'text-risk-low'],
]

const boundaries = [
  '不输出可直接粘贴进合同的完整条文，只给修改方向',
  '不预测诉讼结果、不评价胜诉可能性',
  '企业批量审查、电子签章、手写体识别不在范围内',
]

const LEVEL_TONE: Record<string, string> = {
  高: 'bg-risk-high',
  中: 'bg-risk-medium',
  低: 'bg-risk-low',
}

function openPicker() {
  fileInput.value?.click()
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
    // 让"已完成"状态停留一瞬再跳转，用户能确认操作已生效
    await new Promise((resolve) => window.setTimeout(resolve, 420))
    await router.push({ name: 'review', params: { docId: result.document_id } })
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '上传失败，请重试'
    phase.value = 'idle'
  }
}

// 上传区内衬的网格底纹，只在悬停/拖入时浮现
const GRID = {
  backgroundImage: 'radial-gradient(circle, #D8D3C6 1px, transparent 1px)',
  backgroundSize: '18px 18px',
}
</script>

<template>
  <div class="mx-auto w-full max-w-[1080px] px-4 sm:px-6">
    <section class="pt-10 sm:pt-14">
      <h1
        class="max-w-[780px] font-serif text-[26px] leading-[1.45] tracking-tightest text-ink sm:text-[30px]"
      >
        上传合同 PDF，逐条对照法条，输出风险等级、依据原文与修改方向。
      </h1>
    </section>

    <!-- 上传区：首屏主体 -->
    <section class="mt-7">
      <div
        class="group relative flex min-h-[340px] cursor-pointer flex-col items-center justify-center overflow-hidden border border-dashed px-6 py-14 text-center transition-colors duration-200 sm:min-h-[400px]"
        :class="
          dragging
            ? 'border-accent bg-accent-wash/60'
            : 'border-line-strong bg-white hover:border-accent/50'
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
        <!-- 网格底纹：静态时不可见，悬停淡入，拖入时满显 -->
        <span
          class="pointer-events-none absolute inset-0 transition-opacity duration-300"
          :class="dragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-40'"
          :style="GRID"
        />

        <span
          class="relative flex h-14 w-14 items-center justify-center border border-line bg-paper text-ink-soft transition-all duration-300 ease-calm group-hover:border-accent/40 group-hover:text-accent"
          :class="dragging ? '-translate-y-1 scale-105 border-accent/60 text-accent' : ''"
        >
          <FileText :size="24" :stroke-width="1.5" />
        </span>

        <p class="mt-6 font-serif text-[17px] text-ink">把合同 PDF 拖到这里</p>
        <p class="mt-2 text-[12px] text-ink-faint">
          或点击选择文件 · 支持文字版 PDF，≤ {{ MAX_MB }}MB、≤ 80 页
        </p>

        <p
          v-if="selected"
          class="animate-rise mt-5 flex items-center gap-2 border border-line bg-paper px-2.5 py-1.5 text-[12px] text-ink-soft"
        >
          <FileText :size="13" class="text-ink-faint" />
          <span class="max-w-[280px] truncate">{{ selected.name }}</span>
          <span class="num text-ink-faint">{{ selectedSize }} MB</span>
        </p>

        <button
          class="btn-primary relative mt-6 min-w-[124px] overflow-hidden"
          :class="phase === 'done' ? '!bg-risk-low' : ''"
          :disabled="(!selected || uploading) && phase !== 'done'"
          @click.stop="submit"
        >
          <Loader2 v-if="phase === 'uploading'" :size="14" class="animate-spin" />
          <Check v-else-if="phase === 'done'" :size="14" />
          <span>{{ phase === 'uploading' ? '解析中' : phase === 'done' ? '已受理' : '开始审查' }}</span>
          <ArrowRight v-if="phase === 'idle'" :size="14" />
        </button>

        <p
          v-if="errorMsg"
          class="mt-4 flex items-start gap-1.5 text-[11px] leading-relaxed text-risk-high"
        >
          <AlertCircle :size="13" class="mt-0.5 shrink-0" />
          {{ errorMsg }}
        </p>
        <p v-else class="mt-4 text-[11px] text-ink-faint">
          文件按匿名会话隔离存储，可随时删除
        </p>

        <input
          ref="fileInput"
          type="file"
          accept="application/pdf,.pdf"
          class="hidden"
          @change="onFileChange"
        />
      </div>
    </section>

    <!-- 事实条 -->
    <dl class="mt-6 grid grid-cols-2 gap-px border-y border-line bg-line sm:grid-cols-4">
      <div v-for="[k, v] in facts" :key="k" class="bg-paper px-3 py-3">
        <dt class="label">{{ k }}</dt>
        <dd class="mt-1 text-[11.5px] text-ink-soft">{{ v }}</dd>
      </div>
    </dl>

    <!-- 说明区：全部折叠，置于页面底部 -->
    <div class="mt-10">
      <SectionCollapse title="审查清单" hint="3 类合同 · 24 项 · 每项对应具体法条">
        <div class="grid gap-px bg-line sm:grid-cols-3">
          <div v-for="group in checklists" :key="group.key" class="bg-white p-4">
            <div class="flex items-baseline justify-between border-b border-line pb-2">
              <h2 class="text-[13px] font-medium text-ink">{{ group.title }}</h2>
              <span class="num text-[11px] text-ink-faint">{{ group.count }} 项</span>
            </div>
            <ul class="mt-2 space-y-1.5">
              <li
                v-for="[name, ref] in group.items"
                :key="name"
                class="flex items-baseline justify-between gap-2 text-[11px]"
              >
                <span class="text-ink-soft">{{ name }}</span>
                <span class="num shrink-0 text-[10px] text-ink-faint">{{ ref }}</span>
              </li>
            </ul>
          </div>
        </div>
      </SectionCollapse>

      <SectionCollapse title="示例：常见坑条款" hint="条文片段 · 命中项 · 判定理由">
        <div class="space-y-px bg-line">
          <div v-for="(s, i) in samples" :key="i" class="bg-white px-4 py-3.5">
            <div class="flex items-center gap-2">
              <span class="h-1.5 w-1.5 rounded-full" :class="LEVEL_TONE[s.level]" />
              <span class="text-[10px] text-ink-faint">{{ s.level }}风险</span>
              <span class="text-[10px] text-ink-faint">· {{ s.item }}</span>
            </div>
            <p class="mt-1.5 font-serif text-[13px] leading-relaxed text-ink">「{{ s.text }}」</p>
            <p class="mt-1.5 text-[11.5px] leading-[1.8] text-ink-soft">{{ s.why }}</p>
            <p class="mt-1 text-[10px] text-ink-faint">依据 {{ s.ref }}</p>
          </div>
        </div>
      </SectionCollapse>

      <SectionCollapse title="常见问题" hint="支持范围 · 待复核 · 法条覆盖 · 文件保留">
        <div class="grid gap-x-10 gap-y-6 sm:grid-cols-2">
          <div v-for="[q, a] in faq" :key="q">
            <p class="text-[12px] font-medium text-ink">{{ q }}</p>
            <p class="mt-1.5 text-[11.5px] leading-[1.85] text-ink-faint">{{ a }}</p>
          </div>
        </div>
      </SectionCollapse>

      <SectionCollapse title="结论说明与适用边界" hint="风险分级 · 置信度 · 不做的事">
        <div class="space-y-4">
          <div class="grid gap-px bg-line sm:grid-cols-3">
            <div v-for="[level, desc, tone] in legend" :key="level" class="bg-white p-4">
              <p class="text-[12px] font-medium" :class="tone">{{ level }}风险</p>
              <p class="mt-1.5 text-[11px] leading-relaxed text-ink-faint">{{ desc }}</p>
            </div>
          </div>

          <div class="border border-line bg-white px-4 py-3.5">
            <p class="label">不做的事</p>
            <ul class="mt-2 space-y-1.5">
              <li
                v-for="line in boundaries"
                :key="line"
                class="flex gap-2 text-[11.5px] leading-relaxed text-ink-soft"
              >
                <span class="mt-[7px] h-px w-2.5 shrink-0 bg-line-strong" />
                {{ line }}
              </li>
            </ul>
          </div>
        </div>
      </SectionCollapse>
    </div>
  </div>
</template>
