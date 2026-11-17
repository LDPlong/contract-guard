<script setup lang="ts">
import { RouterLink } from 'vue-router'

/**
 * 使用条款：核心是把「不构成法律意见」的边界写清楚，其余从简。
 */
const clauses = [
  {
    title: '服务性质',
    body: '本工具仅对合同条款提供风险提示与修改方向参考，不构成法律意见，不替代执业律师的审查。签署任何文件前，请自行核对原文。',
  },
  {
    title: '结论的准确性',
    body: '审查结论由规则清单与人工智能模型共同生成，可能存在遗漏、误判或表述偏差；低置信度的结论会标注「待复核」，请结合人工判断使用。',
  },
  {
    title: '法规依据',
    body: '结论引用的法规文本来自公开的《民法典》《劳动合同法》《民事诉讼法》《消费者权益保护法》《社会保险法》。法律可能修订，引用以法规库收录版本为准，如与官方发布版本不一致，以后者为准。',
  },
  {
    title: '使用限制',
    body: '不得将本工具用于非法目的；不得上传你不拥有权利或未经授权处理的文件；不得试图干扰服务的正常运行。',
  },
  {
    title: '责任限制',
    body: '在法律允许的最大范围内，本工具不对因依赖审查结论而产生的任何直接或间接损失承担责任。重大金额、复杂情况的合同，请咨询执业律师。',
  },
  {
    title: '条款变更',
    body: '本条款如有实质变更，将在本页更新并保留在页脚入口处，继续使用即视为接受变更后的条款。',
  },
]
</script>

<template>
  <div class="mx-auto w-full max-w-[760px] px-4 py-10 sm:px-6">
    <h1 class="font-serif text-[24px] leading-tight text-ink">使用条款</h1>
    <p class="mt-2 text-[12px] leading-relaxed text-ink-faint">
      生效日期：2026 年 11 月 · 使用本工具即表示你已阅读并同意以下内容。
    </p>

    <div class="mt-8 space-y-8">
      <section v-for="(c, i) in clauses" :key="c.title">
        <h2 class="font-serif text-[16px] text-ink">
          <span class="num mr-2 text-[13px] text-ink-faint">{{ String(i + 1).padStart(2, '0') }}</span>{{ c.title }}
        </h2>
        <p class="mt-2 text-[12.5px] leading-[1.9] text-ink-soft">{{ c.body }}</p>
      </section>
    </div>

    <p class="mt-10 border-t border-line pt-4 text-[11px] leading-relaxed text-ink-faint">
      数据如何收集与处理，见
      <RouterLink to="/privacy" class="text-accent transition-colors hover:text-ink">隐私说明</RouterLink>；
      产品功能与边界见
      <RouterLink to="/guide" class="text-accent transition-colors hover:text-ink">使用说明</RouterLink>。
    </p>
  </div>
</template>
