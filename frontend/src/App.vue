<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useAppStore } from '@/stores/reviewStore'

const app = useAppStore()

const healthLabel = computed(() => {
  switch (app.healthState) {
    case 'online':
      return app.health?.db ? '服务正常' : '服务降级'
    case 'checking':
      return '检测中'
    case 'offline':
      return '后端未连接'
    default:
      return '未检测'
  }
})

const healthTone = computed(() => {
  if (app.healthState === 'online') return app.health?.db ? 'bg-risk-low' : 'bg-risk-medium'
  if (app.healthState === 'checking') return 'bg-ink-faint'
  return 'bg-risk-high'
})

onMounted(() => {
  void app.checkHealth()
})
</script>

<template>
  <div class="flex min-h-full flex-col">
    <header class="sticky top-0 z-20 border-b border-line bg-paper/90 backdrop-blur-sm">
      <div class="mx-auto flex h-14 w-full max-w-[1240px] items-center justify-between px-4 sm:px-6">
        <RouterLink to="/" class="group flex items-center gap-2.5 no-underline">
          <!-- 印章式标识：不用图标库，用一个字更有辨识度 -->
          <span
            class="flex h-7 w-7 items-center justify-center bg-accent font-serif text-[15px] leading-none text-white transition-colors group-hover:bg-accent-deep"
          >契</span>
          <span class="flex items-baseline gap-2">
            <span class="text-[13px] font-medium tracking-[0.04em] text-ink">ContractGuard</span>
            <span class="hidden font-serif text-[12px] text-ink-faint sm:inline">合同风险审查</span>
          </span>
        </RouterLink>

        <nav class="hidden items-center gap-5 text-[12px] sm:flex">
          <RouterLink
            to="/"
            class="text-ink-soft transition-colors hover:text-ink"
            active-class="!text-ink"
          >审查</RouterLink>
          <RouterLink
            to="/laws"
            class="text-ink-soft transition-colors hover:text-ink"
            active-class="!text-ink"
          >法规库</RouterLink>
          <RouterLink
            to="/guide"
            class="text-ink-soft transition-colors hover:text-ink"
            active-class="!text-ink"
          >使用说明</RouterLink>
        </nav>

        <div class="flex items-center gap-3">
          <span
            v-if="app.isDemoMode"
            class="rounded-card border border-risk-medium/40 px-2 py-0.5 text-[10px] tracking-wide text-risk-medium"
            title="DEMO_MODE=true：当前结果来自本地兜底数据"
          >
            演示模式
          </span>
          <span class="flex items-center gap-1.5 text-[11px] text-ink-faint" :title="app.lastError">
            <span class="h-1 w-1 rounded-full" :class="healthTone" />
            {{ healthLabel }}
          </span>
        </div>
      </div>
    </header>

    <main class="flex-1">
      <RouterView />
    </main>

    <footer class="mt-auto border-t border-line">
      <div
        class="mx-auto flex w-full max-w-[1240px] items-center justify-center px-4 py-5 text-[11px] leading-relaxed text-ink-faint sm:px-6"
      >
        <p>本工具仅提供风险提示与修改方向，不构成法律意见，不替代执业律师。</p>
      </div>
    </footer>
  </div>
</template>
