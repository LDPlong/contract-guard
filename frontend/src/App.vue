<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { ShieldCheck } from 'lucide-vue-next'
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

const healthColor = computed(() => {
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
    <header class="border-b border-[#E9EBF0] bg-white">
      <div class="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
        <RouterLink to="/" class="flex items-center gap-2 text-ink no-underline">
          <span class="flex h-7 w-7 items-center justify-center rounded-md bg-brand text-white">
            <ShieldCheck :size="17" :stroke-width="2.2" />
          </span>
          <span class="text-[15px] font-semibold tracking-tight">ContractGuard</span>
          <span class="hidden text-xs text-ink-faint sm:inline">合同风险审查官</span>
        </RouterLink>

        <div class="flex items-center gap-3">
          <span
            v-if="app.isDemoMode"
            class="rounded-full bg-risk-medium/10 px-2.5 py-0.5 text-xs font-medium text-[#8A5A00]"
            title="DEMO_MODE=true：当前结果来自本地兜底数据，不代表真实模型输出"
          >
            演示模式（模拟数据）
          </span>
          <span class="flex items-center gap-1.5 text-xs text-ink-faint" :title="app.lastError">
            <span class="h-1.5 w-1.5 rounded-full" :class="healthColor" />
            {{ healthLabel }}
          </span>
        </div>
      </div>
    </header>

    <main class="flex-1">
      <RouterView />
    </main>

    <footer class="border-t border-[#E9EBF0] bg-white">
      <div class="mx-auto w-full max-w-6xl px-4 py-5 text-xs leading-relaxed text-ink-faint sm:px-6">
        本工具仅提供风险提示与修改方向，<strong class="font-medium text-ink-soft">不构成法律意见</strong>，
        不替代执业律师。合同签署前请自行核实，重大事项请咨询专业律师。
      </div>
    </footer>
  </div>
</template>
