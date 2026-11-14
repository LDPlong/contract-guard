<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { askAssistant } from '@/api/assistant'
import type { LawRef } from '@/types'

interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  text: string
  refs: LawRef[]
  /** 越界拒答：用更淡的样式，不加"依据" */
  refused?: boolean
  pending?: boolean
}

const props = defineProps<{ context?: string }>()

// ?ask=1 可直接唤起面板，方便从其他页面的“问一句”入口直达
const open = ref(new URLSearchParams(window.location.search).has('ask'))
const input = ref('')
const sending = ref(false)
const stage = ref('')
const messages = ref<ChatMessage[]>([])
const scrollBox = ref<HTMLElement | null>(null)
const inputBox = ref<HTMLTextAreaElement | null>(null)
let seq = 0
let controller: AbortController | null = null

const SUGGESTIONS = [
  '房东不退押金合法吗',
  '试用期最长能约定多久',
  '合同里写"概不退款"有效吗',
]

const canSend = computed(() => input.value.trim().length > 0 && !sending.value)
const hasConversation = computed(() => messages.value.length > 0)

function scrollToBottom() {
  void nextTick(() => {
    const box = scrollBox.value
    if (box) box.scrollTop = box.scrollHeight
  })
}

function toggle(next = !open.value) {
  open.value = next
  if (next) {
    scrollToBottom()
    void nextTick(() => inputBox.value?.focus())
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && open.value) toggle(false)
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  controller?.abort()
})

watch(open, (value) => {
  document.body.classList.toggle('overflow-hidden', value && window.innerWidth < 640)
})

async function send(text?: string) {
  const question = (text ?? input.value).trim()
  if (!question || sending.value) return

  input.value = ''
  messages.value.push({ id: ++seq, role: 'user', text: question, refs: [] })
  const reply: ChatMessage = {
    id: ++seq,
    role: 'assistant',
    text: '',
    refs: [],
    pending: true,
  }
  messages.value.push(reply)
  sending.value = true
  stage.value = '检索法规'
  scrollToBottom()

  controller = new AbortController()
  try {
    for await (const frame of askAssistant(question, props.context ?? '', controller.signal)) {
      if (frame.event === 'refs') {
        stage.value = '组织回答'
      } else {
        reply.text = frame.data.answer
        reply.refs = frame.data.refs ?? []
        reply.refused = !frame.data.scope_ok
        reply.pending = false
      }
      scrollToBottom()
    }
  } catch (error) {
    if ((error as Error)?.name === 'AbortError') return
    reply.pending = false
    reply.text = error instanceof Error ? error.message : '提问失败，请稍后再试。'
    reply.refused = true
  } finally {
    reply.pending = false
    sending.value = false
    stage.value = ''
    controller = null
    scrollToBottom()
  }
}

function onEnter(event: KeyboardEvent) {
  if (event.isComposing) return
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    void send()
  }
}
</script>

<template>
  <!-- 入口：右下角印章式按钮，不抢页面视觉 -->
  <button
    type="button"
    class="fixed bottom-6 right-5 z-40 flex h-11 w-11 items-center justify-center border border-accent-deep bg-accent font-serif text-[15px] leading-none text-white shadow-[0_6px_18px_rgba(18,41,77,0.22)] transition-all hover:-translate-y-0.5 hover:bg-accent-deep print:hidden"
    :aria-label="open ? '收起答疑助手' : '打开答疑助手'"
    @click="toggle()"
  >
    问
  </button>

  <!-- 遮罩：只在移动端铺满，桌面端允许边看边问 -->
  <div
    v-if="open"
    class="fixed inset-0 z-40 bg-ink/20 sm:hidden"
    @click="toggle(false)"
  />

  <aside
    class="fixed right-0 top-0 z-50 flex h-full w-full flex-col border-l border-line bg-paper shadow-[-12px_0_32px_rgba(21,23,28,0.10)] transition-transform duration-300 sm:w-[400px] print:hidden"
    :class="open ? 'translate-x-0' : 'translate-x-full'"
    role="dialog"
    aria-label="合同法律答疑助手"
    :aria-hidden="!open"
  >
    <header class="flex items-start justify-between border-b border-line px-5 py-4">
      <div>
        <h2 class="font-serif text-[15px] text-ink">合同答疑</h2>
        <p class="mt-1 text-[11px] leading-relaxed text-ink-faint">
          只解释法条与风险成因，每条回答附依据；不预测输赢、不代写条款。
        </p>
      </div>
      <button
        type="button"
        class="-mr-1 -mt-0.5 p-1 text-ink-faint transition-colors hover:text-ink"
        aria-label="关闭"
        @click="toggle(false)"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.3">
          <path d="M1 1l12 12M13 1L1 13" />
        </svg>
      </button>
    </header>

    <div ref="scrollBox" class="flex-1 space-y-4 overflow-y-auto px-5 py-4">
      <!-- 空白态：给三个常见问题，降低开口成本 -->
      <div v-if="!hasConversation" class="space-y-3">
        <p class="text-[12px] leading-relaxed text-ink-soft">
          关于押金、违约金、试用期、退费这些条款，可以直接问。回答会引到具体的法条上，
          查不到依据时我会直说。
        </p>
        <div class="space-y-1.5">
          <button
            v-for="item in SUGGESTIONS"
            :key="item"
            type="button"
            class="block w-full border border-line bg-paper-deep/60 px-3 py-2 text-left text-[12px] text-ink-soft transition-colors hover:border-accent-soft hover:text-ink"
            @click="send(item)"
          >
            {{ item }}
          </button>
        </div>
      </div>

      <template v-for="message in messages" :key="message.id">
        <div v-if="message.role === 'user'" class="flex justify-end">
          <p
            class="max-w-[85%] whitespace-pre-wrap bg-accent px-3 py-2 text-[12.5px] leading-relaxed text-white"
          >
            {{ message.text }}
          </p>
        </div>

        <div v-else class="flex flex-col gap-2">
          <p
            v-if="message.pending"
            class="text-[12px] text-ink-faint"
          >
            {{ stage || '思考中' }}<span class="animate-pulse">…</span>
          </p>
          <template v-else>
            <p
              class="whitespace-pre-wrap text-[12.5px] leading-[1.75]"
              :class="message.refused ? 'text-ink-faint' : 'text-ink'"
            >
              {{ message.text }}
            </p>
            <div v-if="message.refs.length" class="space-y-1 border-l-2 border-accent-wash pl-2.5">
              <p class="text-[10px] tracking-wide text-ink-faint">依据</p>
              <button
                v-for="ref in message.refs"
                :key="ref.chunk_id"
                type="button"
                class="block text-left text-[11px] leading-relaxed text-accent-soft transition-colors hover:text-accent-deep"
                :title="ref.content"
              >
                {{ ref.source }} {{ ref.article_no }}
              </button>
            </div>
          </template>
        </div>
      </template>
    </div>

    <div class="border-t border-line px-4 py-3">
      <div class="border border-line bg-white/60 focus-within:border-accent-soft">
        <textarea
          ref="inputBox"
          v-model="input"
          rows="2"
          maxlength="200"
          placeholder="问一句，比如：押金能扣多少"
          class="w-full resize-none bg-transparent px-3 py-2 text-[12.5px] leading-relaxed text-ink outline-none placeholder:text-ink-faint"
          @keydown="onEnter"
        />
        <div class="flex items-center justify-between px-3 pb-2">
          <span class="text-[10px] text-ink-faint">{{ input.length }}/200</span>
          <button
            type="button"
            class="px-2 py-1 text-[11px] transition-colors"
            :class="canSend ? 'bg-accent text-white hover:bg-accent-deep' : 'cursor-not-allowed text-ink-faint'"
            :disabled="!canSend"
            @click="send()"
          >
            {{ sending ? '回答中' : '发送' }}
          </button>
        </div>
      </div>
      <p class="mt-2 text-[10px] leading-relaxed text-ink-faint">
        回答依据来自本地法规库，仅作风险提示，不构成法律意见。
      </p>
    </div>
  </aside>
</template>
