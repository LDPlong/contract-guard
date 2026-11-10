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

/** 三类合同的实际审查项，直接从清单文件来，不写虚的 */
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

/** 真实的坑条款长什么样，直接给条文片段和它踩的那一项 */
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

const LEVEL_TONE: Record<string, string> = {
  高: 'bg-risk-high',
  中: 'bg-risk-medium',
  低: 'bg-risk-low',
}

/** 用户真会问的问题，直接给答案，不写宣传语 */
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

const boundaries = [
  '不输出可直接粘贴进合同的完整条文，只给修改方向',
  '不预测诉讼结果、不评价胜诉可能性',
  '企业批量审查、电子签章、手写体识别不在范围内',
]

const legend = [
  ['高', '可能造成直接经济损失，或使一方丧失核心权利', 'text-risk-high'],
  ['中', '权利义务明显失衡，但可通过协商修正', 'text-risk-medium'],
  ['低', '表述不规范、缺少一般性约定，影响有限', 'text-risk-low'],
]

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
    <!-- 顶部：功能陈述 + 支持范围，不放标语 -->
    <section class="grid gap-10 border-b border-line py-12 lg:grid-cols-[1.3fr_1fr] lg:gap-16">
      <div>
        <h1 class="max-w-[560px] font-serif text-[28px] leading-[1.45] tracking-tightest text-ink sm:text-[34px]">
          上传合同 PDF，逐条对照法条，输出风险等级、依据原文与修改方向。
        </h1>
        <p class="mt-5 max-w-xl text-[13px] leading-[1.9] text-ink-soft">
          每条结论绑定具体法条编号与原文引用，可点开核对；无法检索到依据的，一律标注为待复核，
          不给无依据的判断。
        </p>
      </div>

      <div class="lg:border-l lg:border-line lg:pl-10">
        <p class="label">当前范围</p>
        <dl class="mt-3 space-y-2.5 text-[12px]">
          <div class="flex items-baseline justify-between border-b border-line pb-2.5">
            <dt class="text-ink-faint">支持</dt>
            <dd class="num text-ink-soft">3 类合同 · 24 项审查</dd>
          </div>
          <div class="flex items-baseline justify-between border-b border-line pb-2.5">
            <dt class="text-ink-faint">法条库</dt>
            <dd class="num text-ink-soft">民法典 1260 · 劳动合同法 98</dd>
          </div>
          <div class="flex items-baseline justify-between border-b border-line pb-2.5">
            <dt class="text-ink-faint">输入格式</dt>
            <dd class="num text-ink-soft">文字版 PDF · ≤ 20MB</dd>
          </div>
          <div class="flex items-baseline justify-between">
            <dt class="text-ink-faint">暂不支持</dt>
            <dd class="text-ink-faint">扫描件 / 手写 / 其他合同</dd>
          </div>
        </dl>
      </div>
    </section>

    <!-- 上传 -->
    <section class="grid gap-8 border-b border-line py-10 lg:grid-cols-[220px_1fr] lg:gap-16">
      <div>
        <p class="label">上传</p>
        <p class="mt-2 text-[12px] leading-relaxed text-ink-faint">
          文件重命名后存于本次会话目录，按匿名 session 隔离，可随时删除。
        </p>
      </div>

      <div>
        <div
          class="group cursor-pointer border border-dashed p-7 transition-colors duration-200 sm:p-8"
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
          <div class="flex flex-wrap items-center justify-between gap-5">
            <div class="flex flex-1 items-center gap-4">
              <span
                class="flex h-11 w-11 shrink-0 items-center justify-center border border-line bg-paper text-ink-soft transition-colors group-hover:border-accent/40 group-hover:text-accent"
              >
                <FileText :size="19" :stroke-width="1.6" />
              </span>
              <div class="min-w-0">
                <p class="text-[13px] text-ink">拖入 PDF，或点击选择文件</p>
                <p class="mt-1 text-[11px] leading-relaxed text-ink-faint">
                  自动识别合同类型并加载对应清单；识别失败会提示手动指定，不强行审查。
                </p>
                <p
                  v-if="selected"
                  class="mt-2 flex items-center gap-1.5 text-[11.5px] text-ink-soft"
                >
                  <FileText :size="12" class="text-ink-faint" />
                  <span class="max-w-[260px] truncate">{{ selected.name }}</span>
                  <span class="num text-ink-faint">{{ selectedSize }} MB</span>
                </p>
              </div>
            </div>

            <button
              class="btn-primary shrink-0"
              :disabled="!selected || uploading"
              @click.stop="submit"
            >
              <Loader2 v-if="uploading" :size="14" class="animate-spin" />
              <span>{{ uploading ? '解析中' : '开始审查' }}</span>
              <ArrowRight v-if="!uploading" :size="14" />
            </button>
          </div>

          <input
            ref="fileInput"
            type="file"
            accept="application/pdf,.pdf"
            class="hidden"
            @change="onFileChange"
          />
        </div>

        <div class="mt-2.5 flex items-center justify-between gap-4">
          <p v-if="errorMsg" class="flex items-start gap-1.5 text-[11px] leading-relaxed text-risk-high">
            <AlertCircle :size="13" class="mt-0.5 shrink-0" />
            {{ errorMsg }}
          </p>
          <p v-else class="text-[11px] text-ink-faint">上传的文件仅用于本次审查，可随时删除。</p>
        </div>
      </div>
    </section>

    <!-- 审查清单：三类合同的具体条目 -->
    <section class="grid gap-8 border-b border-line py-10 lg:grid-cols-[220px_1fr] lg:gap-16">
      <div>
        <p class="label">审查清单</p>
        <p class="mt-2 text-[12px] leading-relaxed text-ink-faint">
          清单固定、可评测。每项都有对应的风险规则与法条依据，不做开放式自由审查。
        </p>
      </div>

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
    </section>

    <!-- 典型条款示例 -->
    <section class="grid gap-8 border-b border-line py-10 lg:grid-cols-[220px_1fr] lg:gap-16">
      <div>
        <p class="label">示例</p>
        <p class="mt-2 text-[12px] leading-relaxed text-ink-faint">
          下面是三类合同里常见的写法，以及它会被判成什么、依据是哪一条。
        </p>
      </div>

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
    </section>

    <!-- 常见问题 -->
    <section class="grid gap-8 border-b border-line py-10 lg:grid-cols-[220px_1fr] lg:gap-16">
      <div>
        <p class="label">常见问题</p>
      </div>

      <div class="grid gap-x-10 gap-y-6 sm:grid-cols-2">
        <div v-for="[q, a] in faq" :key="q">
          <p class="text-[12px] font-medium text-ink">{{ q }}</p>
          <p class="mt-1.5 text-[11.5px] leading-[1.85] text-ink-faint">{{ a }}</p>
        </div>
      </div>
    </section>

    <!-- 结论怎么读 -->
    <section class="grid gap-8 py-10 lg:grid-cols-[220px_1fr] lg:gap-16">
      <div>
        <p class="label">结论说明</p>
        <p class="mt-2 text-[12px] leading-relaxed text-ink-faint">
          每个结论都带风险等级、依据和置信度，置信度低于 0.6 的折叠为待复核。
        </p>
      </div>

      <div>
        <div class="grid gap-px bg-line sm:grid-cols-3">
          <div v-for="[level, desc, tone] in legend" :key="level" class="bg-white p-4">
            <p class="text-[12px] font-medium" :class="tone">{{ level }}风险</p>
            <p class="mt-1.5 text-[11px] leading-relaxed text-ink-faint">{{ desc }}</p>
          </div>
        </div>

        <div class="mt-4 border border-line bg-white px-4 py-3.5">
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
    </section>
  </div>
</template>
