<script setup lang="ts">
/**
 * 问题反馈页：表单填完调起邮件客户端，正文自动拼好。
 * 不走后端，零依赖；邮箱在 lib/config.ts 统一维护。
 */
import { computed, ref } from 'vue'
import { Mail } from 'lucide-vue-next'
import { FEEDBACK_EMAIL, makeMailto } from '@/lib/config'

const page = ref('')
const contact = ref('')
const detail = ref('')

const mailtoHref = computed(() => {
  const body = [
    `所在页面：${page.value.trim() || '（未填）'}`,
    `联系方式：${contact.value.trim() || '（未填）'}`,
    '',
    '问题描述：',
    detail.value.trim(),
    '',
    '（方便的话请附截图）',
  ].join('\n')
  return makeMailto('ContractGuard 问题反馈', body)
})

function submit() {
  if (!detail.value.trim()) return
  window.location.href = mailtoHref.value
}
</script>

<template>
  <div class="mx-auto w-full max-w-[640px] px-4 py-10 sm:px-6">
    <h1 class="font-serif text-[24px] leading-tight text-ink">问题反馈</h1>
    <p class="mt-2 text-[12px] leading-relaxed text-ink-faint">
      审查结论不准确、页面出错、或有功能建议，都可以告诉我们。一般 1–2 个工作日回复。
    </p>

    <form
      class="mt-8 space-y-5 border border-line bg-white px-5 py-5"
      @submit.prevent="submit"
    >
      <div>
        <label for="fb-page" class="label">所在页面</label>
        <input
          id="fb-page"
          v-model="page"
          type="text"
          placeholder="如：审查页 / 法规库 / 隐私说明"
          class="mt-1.5 w-full border border-line bg-paper px-3 py-2 text-[12.5px] text-ink placeholder:text-ink-faint focus:border-accent/50 focus:outline-none"
        />
      </div>

      <div>
        <label for="fb-contact" class="label">联系方式（选填）</label>
        <input
          id="fb-contact"
          v-model="contact"
          type="text"
          placeholder="邮箱或微信，方便我们回复你"
          class="mt-1.5 w-full border border-line bg-paper px-3 py-2 text-[12.5px] text-ink placeholder:text-ink-faint focus:border-accent/50 focus:outline-none"
        />
      </div>

      <div>
        <label for="fb-detail" class="label">问题描述</label>
        <textarea
          id="fb-detail"
          v-model="detail"
          rows="5"
          required
          placeholder="发生了什么、当时在做哪一步、期望的结果。方便的话请附截图。"
          class="mt-1.5 w-full resize-y border border-line bg-paper px-3 py-2 text-[12.5px] leading-[1.8] text-ink placeholder:text-ink-faint focus:border-accent/50 focus:outline-none"
        />
      </div>

      <div class="flex flex-wrap items-center justify-between gap-3">
        <p class="text-[11px] text-ink-faint">
          提交会调起你的邮件客户端，内容已按模板填好。
        </p>
        <button
          type="submit"
          class="btn-primary min-w-[148px]"
          :disabled="!detail.trim()"
        >
          <Mail :size="14" />
          <span>生成反馈邮件</span>
        </button>
      </div>
    </form>

    <p class="mt-4 text-[11.5px] leading-relaxed text-ink-faint">
      邮件客户端没反应？直接写信到
      <a
        :href="`mailto:${FEEDBACK_EMAIL}`"
        class="text-accent transition-colors hover:text-ink"
      >{{ FEEDBACK_EMAIL }}</a>
      也可以。
    </p>
  </div>
</template>
