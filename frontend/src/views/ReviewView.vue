<script setup lang="ts">
import { ArrowLeft, Loader2 } from 'lucide-vue-next'

defineProps<{ docId: string }>()
</script>

<template>
  <div class="mx-auto w-full max-w-6xl px-4 py-10 sm:px-6">
    <RouterLink to="/" class="inline-flex items-center gap-1.5 text-sm text-ink-soft hover:text-brand">
      <ArrowLeft :size="15" />
      返回上传
    </RouterLink>

    <div class="mt-6 grid gap-4 lg:grid-cols-[3fr_2fr]">
      <div class="card flex min-h-[420px] flex-col items-center justify-center p-8 text-center">
        <div class="flex h-11 w-11 items-center justify-center rounded-full bg-brand-light text-brand">
          <Loader2 :size="20" class="animate-spin" />
        </div>
        <p class="mt-4 text-sm font-medium text-ink">审查台建设中</p>
        <p class="mt-1.5 max-w-sm text-xs leading-relaxed text-ink-faint">
          双栏审查台（左 pdf.js 原页 + bbox 高亮，右结论卡片）在 M2 接入。
          <br />
          文档 ID：<code class="rounded bg-[#F4F6F9] px-1.5 py-0.5 text-[11px]">{{ docId }}</code>
        </p>
      </div>

      <div class="card min-h-[420px] p-5">
        <p class="text-xs font-medium uppercase tracking-wider text-ink-faint">审查进度</p>
        <ul class="mt-4 space-y-3 text-sm text-ink-faint">
          <li>解析条款 · 待接入</li>
          <li>法条检索 · 待接入</li>
          <li>风险判定 · 待接入</li>
          <li>生成报告 · 待接入</li>
        </ul>
      </div>
    </div>
  </div>
</template>
