<script setup lang="ts">
import { ArrowLeft } from 'lucide-vue-next'
import { RouterLink } from 'vue-router'

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
    '五部法全文共 1825 条：民法典、劳动合同法、民事诉讼法、消费者权益保护法、社会保险法。三类合同审查项引用的法条都能查到原文。',
  ],
  [
    '上传的文件会保留多久？',
    '存于本次会话目录，按匿名 session 隔离，可在审查页直接删除；服务端日志只记录长度与哈希，不记录正文。',
  ],
]

const LEVEL_TONE: Record<string, string> = {
  高: 'bg-risk-high',
  中: 'bg-risk-medium',
  低: 'bg-risk-low',
}
</script>

<template>
  <div class="mx-auto w-full max-w-[880px] px-4 py-8 sm:px-6">
    <RouterLink
      to="/"
      class="inline-flex items-center gap-1.5 text-[12px] text-ink-faint transition-colors hover:text-ink"
    >
      <ArrowLeft :size="13" />
      返回
    </RouterLink>

    <header class="mt-5 border-b border-line pb-6">
      <p class="label">Usage</p>
      <h1 class="mt-2 font-serif text-[26px] leading-tight text-ink">使用说明</h1>
      <p class="mt-2 max-w-[560px] text-[12px] leading-[1.9] text-ink-soft">
        审查范围、风险等级的含义，以及目前不支持的情况。
      </p>
    </header>

    <!-- 审查清单 -->
    <section class="border-b border-line py-8">
      <p class="label">01</p>
      <h2 class="mt-2 font-serif text-[19px] text-ink">审查清单</h2>
      <p class="mt-1.5 max-w-[600px] text-[12px] leading-[1.9] text-ink-soft">
        每类合同固定核对以下条目，逐项检查，不遗漏也不额外发挥。
      </p>

      <div class="mt-5 grid gap-px bg-line sm:grid-cols-3">
        <div v-for="group in checklists" :key="group.key" class="bg-white p-4">
          <div class="flex items-baseline justify-between border-b border-line pb-2">
            <h3 class="text-[13px] font-medium text-ink">{{ group.title }}</h3>
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

    <!-- 示例 -->
    <section class="border-b border-line py-8">
      <p class="label">02</p>
      <h2 class="mt-2 font-serif text-[19px] text-ink">常见问题条款</h2>
      <p class="mt-1.5 max-w-[600px] text-[12px] leading-[1.9] text-ink-soft">
        三类合同里最容易出问题的写法，以及它的依据。
      </p>

      <div class="mt-5 space-y-px bg-line">
        <div v-for="(s, i) in samples" :key="i" class="bg-white px-4 py-4">
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

    <!-- 结论说明 -->
    <section class="border-b border-line py-8">
      <p class="label">03</p>
      <h2 class="mt-2 font-serif text-[19px] text-ink">风险等级</h2>
      <p class="mt-1.5 max-w-[600px] text-[12px] leading-[1.9] text-ink-soft">
        结论分高、中、低三级。置信度低于 0.6 的会标为待复核，请对照原文确认。
      </p>

      <div class="mt-5 grid gap-px bg-line sm:grid-cols-3">
        <div v-for="[level, desc, tone] in legend" :key="level" class="bg-white p-4">
          <p class="text-[12px] font-medium" :class="tone">{{ level }}风险</p>
          <p class="mt-1.5 text-[11px] leading-relaxed text-ink-faint">{{ desc }}</p>
        </div>
      </div>

      <div class="mt-3 border border-line bg-white px-4 py-3.5">
        <p class="label">适用范围</p>
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
    </section>

    <!-- 常见问题 -->
    <section class="py-8">
      <p class="label">04</p>
      <h2 class="mt-2 font-serif text-[19px] text-ink">常见问题</h2>

      <div class="mt-5 grid gap-x-10 gap-y-6 sm:grid-cols-2">
        <div v-for="[q, a] in faq" :key="q">
          <p class="text-[12px] font-medium text-ink">{{ q }}</p>
          <p class="mt-1.5 text-[11.5px] leading-[1.85] text-ink-faint">{{ a }}</p>
        </div>
      </div>
    </section>
  </div>
</template>
