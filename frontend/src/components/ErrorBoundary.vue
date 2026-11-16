<script setup lang="ts">
import { onErrorCaptured, ref } from 'vue'

/**
 * 页面级错误边界。
 *
 * 没有它的话，任何一处渲染抛错都会让整棵组件树被卸载 —— 用户看到的就是白屏，
 * 而且控制台之外没有任何提示。这里兜住子树异常，换成一张可重试的说明页。
 */
const message = ref('')
const info = ref('')
const nonce = ref(0)

onErrorCaptured((error, _instance, detail) => {
  message.value = error instanceof Error ? error.message : String(error)
  info.value = detail
  // 这里不再走全局提示条：页面本身已经是完整说明，两处同时弹只会更吵。
  // 顶部条只留给边界之外（事件处理、未捕获的 Promise、chunk 加载失败）。
  console.error('[页面渲染]', error)
  // 返回 false：不再往上冒泡，避免触发全局兜底又弹一次
  return false
})

function retry() {
  message.value = ''
  info.value = ''
  nonce.value += 1
}

function refresh() {
  window.location.reload()
}
</script>

<template>
  <div v-if="message" class="mx-auto w-full max-w-[560px] px-4 py-20">
    <p class="font-serif text-[17px] text-ink">这一页没能正常显示</p>
    <p class="mt-2 text-[13px] leading-relaxed text-ink-soft">
      页面渲染时出了点问题，不是你的操作有误。可以先重试一次；如果反复出现，刷新页面即可。
    </p>
    <p class="mt-4 text-[10px] tracking-wide text-ink-faint">技术信息（反馈时可附上）</p>
    <pre
      class="mt-4 max-h-[120px] overflow-auto border border-line bg-paper-deep px-3 py-2 text-[11px] leading-relaxed text-ink-faint"
    >{{ message }}<span v-if="info">（{{ info }}）</span></pre>
    <div class="mt-5 flex items-center gap-2">
      <button class="btn-ghost text-xs" @click="retry">重试</button>
      <button class="btn-ghost text-xs" @click="refresh">刷新页面</button>
    </div>
  </div>

  <div v-else :key="nonce" class="contents">
    <slot />
  </div>
</template>
