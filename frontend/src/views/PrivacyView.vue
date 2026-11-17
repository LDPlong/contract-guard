<script setup lang="ts">
import { RouterLink } from 'vue-router'

/**
 * 隐私说明：只写实际的做法，不写做不到的承诺。
 * 条款文本送大模型判定是审查流程的必要环节，必须如实披露。
 */
const sections = [
  {
    title: '我们收集什么',
    body: [
      '匿名会话标识：浏览器随机生成，仅保存在你的浏览器本地（localStorage），用于隔离历史记录，不关联任何身份信息。',
      '上传的合同文件：以及解析出的条款文本，仅用于本次审查。',
    ],
  },
  {
    title: '文件如何处理',
    body: [
      '上传的文件只与当前匿名会话绑定，用于解析与审查，审查完成后可在页面内删除。',
      '文件与条款内容不会用于训练模型，不会用于营销，也不会提供给与审查流程无关的第三方。',
    ],
  },
  {
    title: '审查过程调用大模型',
    body: [
      '逐条判定由大语言模型完成，条款文本会在审查时发送至大模型服务。这是产出结论的必要环节，无法跳过。',
      '如合同含身份证号、银行卡号、家庭住址等敏感个人信息，建议上传前先行遮盖，不影响风险判定。',
    ],
  },
  {
    title: '不收集身份信息',
    body: [
      '无需注册登录，不使用 Cookie 做行为追踪，不要求填写姓名、手机号、邮箱。',
    ],
  },
  {
    title: '你的控制权',
    body: [
      '你可以随时删除已上传的文件；清空浏览器 localStorage 即可移除本地保存的会话标识。',
    ],
  },
]
</script>

<template>
  <div class="mx-auto w-full max-w-[760px] px-4 py-10 sm:px-6">
    <h1 class="font-serif text-[24px] leading-tight text-ink">隐私说明</h1>
    <p class="mt-2 text-[12px] leading-relaxed text-ink-faint">
      生效日期：2026 年 11 月 · 如条款有实质变更，会在本页更新生效日期。
    </p>

    <div class="mt-8 space-y-8">
      <section v-for="s in sections" :key="s.title">
        <h2 class="font-serif text-[16px] text-ink">{{ s.title }}</h2>
        <div class="mt-2 space-y-1.5">
          <p
            v-for="(p, i) in s.body"
            :key="i"
            class="text-[12.5px] leading-[1.9] text-ink-soft"
          >{{ p }}</p>
        </div>
      </section>
    </div>

    <p class="mt-10 border-t border-line pt-4 text-[11px] leading-relaxed text-ink-faint">
      对本说明有疑问，可通过
      <RouterLink to="/guide" class="text-accent transition-colors hover:text-ink">使用说明</RouterLink>
      页了解产品的工作方式。本工具的免责边界见
      <RouterLink to="/terms" class="text-accent transition-colors hover:text-ink">使用条款</RouterLink>。
    </p>
  </div>
</template>
