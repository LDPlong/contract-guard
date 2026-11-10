<script setup lang="ts">
import { ref } from 'vue'
import { Minus, Plus } from 'lucide-vue-next'

const props = defineProps<{
  title: string
  hint?: string
  defaultOpen?: boolean
}>()

const open = ref(props.defaultOpen ?? false)
</script>

<template>
  <section class="border-b border-line">
    <button
      class="flex w-full items-center justify-between gap-6 py-4 text-left transition-colors hover:text-accent"
      :aria-expanded="open"
      @click="open = !open"
    >
      <span class="flex min-w-0 items-baseline gap-3">
        <span class="text-[13px] text-ink">{{ title }}</span>
        <span v-if="hint" class="truncate text-[11px] text-ink-faint">{{ hint }}</span>
      </span>
      <span
        class="flex h-5 w-5 shrink-0 items-center justify-center border border-line text-ink-faint"
      >
        <Minus v-if="open" :size="11" />
        <Plus v-else :size="11" />
      </span>
    </button>

    <div v-show="open" class="pb-6 pt-1">
      <slot />
    </div>
  </section>
</template>
