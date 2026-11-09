import { defineStore } from 'pinia'
import { fetchHealth } from '@/api/review'
import type { HealthStatus } from '@/types'

type HealthState = 'unknown' | 'checking' | 'online' | 'offline'

export const useAppStore = defineStore('app', {
  state: () => ({
    health: null as HealthStatus | null,
    healthState: 'unknown' as HealthState,
    lastError: '' as string,
  }),

  getters: {
    isDemoMode: (state) => state.health?.demo_mode === true,
    backendOnline: (state) => state.healthState === 'online',
  },

  actions: {
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
