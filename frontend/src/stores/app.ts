import { defineStore } from 'pinia'
import { fetchHealth } from '@/api/review'
import type { HealthStatus } from '@/types'

type HealthState = 'unknown' | 'checking' | 'online' | 'offline'

export const useAppStore = defineStore('app', {
  state: () => ({
    health: null as HealthStatus | null,
    healthState: 'unknown' as HealthState,
    lastError: '' as string,
    // 答疑面板的开合状态放在全局：审查台的内联入口也要能打开它
    assistantOpen: false as boolean,
    // 带上当前合同摘要，助手才知道"这份合同"指哪一份；从别的页面打开时为空
    assistantContext: '' as string,
  }),

  getters: {
    isDemoMode: (state) => state.health?.demo_mode === true,
    backendOnline: (state) => state.healthState === 'online',
  },

  actions: {
    openAssistant(context = '') {
      this.assistantContext = context
      this.assistantOpen = true
    },
    closeAssistant() {
      this.assistantOpen = false
    },
    async checkHealth() {
      this.healthState = 'checking'
      try {
        this.health = await fetchHealth()
        this.healthState = 'online'
        this.lastError = ''
      } catch (err) {
        this.healthState = 'offline'
        this.lastError = err instanceof Error ? err.message : '后端不可达'
      }
    },
  },
})
