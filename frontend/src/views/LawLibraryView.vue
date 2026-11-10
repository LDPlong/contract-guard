<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Loader2, Search } from 'lucide-vue-next'
import {
  fetchArticles,
  fetchSources,
  searchKnowledge,
  type LawArticle,
  type LawSource,
  type SearchHit,
} from '@/api/knowledge'

const PAGE_SIZE = 30

const sources = ref<LawSource[]>([])
const activeSource = ref<string>('')
const articles = ref<LawArticle[]>([])
const total = ref(0)
const offset = ref(0)
const loading = ref(false)
const keyword = ref('')

const query = ref('')
const searching = ref(false)
const hits = ref<SearchHit[]>([])
const searchedFor = ref('')

const activeMeta = computed(() => sources.value.find((s) => s.source === activeSource.value))
const hasMore = computed(() => articles.value.length < total.value)

async function loadSources() {
  const data = await fetchSources()
  sources.value = data.items
  if (!activeSource.value && data.items.length) {
    activeSource.value = data.items[0].source
  }
}

async function loadArticles(reset = true) {
  if (loading.value) return
  loading.value = true
  try {
    if (reset) {
      offset.value = 0
      articles.value = []
    }
    const page = await fetchArticles({
      source: activeSource.value,
      q: keyword.value.trim() || undefined,
      offset: offset.value,
      limit: PAGE_SIZE,
    })
    total.value = page.total
    articles.value = [...articles.value, ...page.items]
    offset.value = articles.value.length
  } finally {
    loading.value = false
  }
}

async function pickSource(source: string) {
  if (activeSource.value === source) return
  activeSource.value = source
  query.value = ''
  hits.value = []
  await loadArticles(true)
}

async function runSearch() {
  const q = query.value.trim()
  if (!q) {
    hits.value = []
    return
  }
  searching.value = true
  try {
    const data = await searchKnowledge(q, 8)
    hits.value = data.items
    searchedFor.value = q
  } catch (err) {
    hits.value = []
    searchedFor.value = err instanceof Error ? err.message : q
  } finally {
    searching.value = false
  }
}

function clearSearch() {
  query.value = ''
  hits.value = []
}

onMounted(async () => {
  await loadSources()
  await loadArticles(true)
})
</script>

<template>
  <div class="mx-auto w-full max-w-[1080px] px-4 py-8 sm:px-6">
    <header class="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-4">
      <div>
        <h1 class="font-serif text-[24px] leading-tight text-ink">法规库</h1>
        <p class="mt-1.5 text-[11.5px] text-ink-faint">
          五部法律全文，按条浏览或检索；结论里引用的法条都能在这里查到原文。
        </p>
      </div>

      <div class="flex items-center gap-2">
        <div class="relative">
          <Search :size="13" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint" />
          <input
            v-model="query"
            type="search"
            placeholder="检索条文，如 押金 返还"
            class="w-[260px] border border-line bg-white py-1.5 pl-8 pr-2 text-[12px] text-ink placeholder:text-ink-faint focus:border-accent/50 focus:outline-none"
            @keyup.enter="runSearch"
          />
        </div>
        <button class="btn-ghost !py-1.5 text-[12px]" :disabled="searching" @click="runSearch">
          <Loader2 v-if="searching" :size="13" class="animate-spin" />
          <span>检索</span>
        </button>
      </div>
    </header>

    <!-- 检索结果 -->
    <section v-if="hits.length" class="mt-5">
      <div class="flex items-center justify-between border-b border-line pb-2">
        <p class="label">检索结果 · {{ hits.length }} 条</p>
        <button class="text-[11px] text-ink-faint hover:text-ink" @click="clearSearch">清除</button>
      </div>
      <article v-for="hit in hits" :key="hit.chunk_id" class="border-b border-line py-3.5">
        <div class="flex items-baseline gap-2">
          <span class="font-serif text-[12px] text-ink">{{ hit.article_no }}</span>
          <span class="text-[10px] text-ink-faint">{{ hit.source }}</span>
          <span v-if="hit.effective_date" class="num text-[10px] text-ink-faint">
            施行 {{ hit.effective_date }}
          </span>
        </div>
        <p class="mt-1.5 text-[12.5px] leading-[1.9] text-ink-soft">{{ hit.content }}</p>
      </article>
    </section>

    <!-- 检索无结果 -->
    <section v-else-if="searchedFor" class="mt-6 border border-line bg-white px-4 py-6 text-center">
      <p class="text-[12px] text-ink-soft">没有检索到「{{ searchedFor }}」相关条文</p>
      <p class="mt-1 text-[11px] text-ink-faint">换个说法试试，比如把口语换成法条用词。</p>
    </section>

    <!-- 浏览 -->
    <div v-else class="mt-5 grid gap-8 lg:grid-cols-[200px_1fr]">
      <aside class="lg:border-r lg:border-line lg:pr-6">
        <p class="label">法规</p>
        <ul class="mt-2 space-y-1">
          <li v-for="s in sources" :key="s.source">
            <button
              class="flex w-full items-baseline justify-between gap-2 border-l-2 py-1.5 pl-2.5 text-left transition-colors"
              :class="
                activeSource === s.source
                  ? 'border-accent text-ink'
                  : 'border-transparent text-ink-soft hover:text-ink'
              "
              @click="pickSource(s.source)"
            >
              <span class="text-[12px]">{{ s.source }}</span>
              <span class="num text-[10px] text-ink-faint">{{ s.count }}</span>
            </button>
          </li>
        </ul>

        <div v-if="activeMeta" class="mt-4 border-t border-line pt-3 text-[10.5px] leading-relaxed text-ink-faint">
          <p>{{ activeMeta.title }}</p>
          <p v-if="activeMeta.version" class="mt-1">{{ activeMeta.version }}</p>
          <p v-if="activeMeta.effective_date" class="num mt-0.5">
            施行 {{ activeMeta.effective_date }}
          </p>
        </div>
      </aside>

      <section>
        <div class="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-2">
          <p class="label">共 {{ total }} 条</p>
          <input
            v-model="keyword"
            type="search"
            placeholder="在本法规内筛选"
            class="w-[180px] border border-line bg-white px-2 py-1 text-[11px] text-ink placeholder:text-ink-faint focus:border-accent/50 focus:outline-none"
            @keyup.enter="loadArticles(true)"
          />
        </div>

        <article v-for="a in articles" :key="a.id" class="border-b border-line py-3.5">
          <div class="flex items-baseline gap-2">
            <span class="font-serif text-[12px] text-ink">{{ a.article_no }}</span>
            <span class="text-[10px] text-ink-faint">{{ a.source }}</span>
          </div>
          <p class="mt-1.5 text-[12.5px] leading-[1.9] text-ink-soft">{{ a.content }}</p>
        </article>

        <div class="mt-4 flex items-center justify-center">
          <button
            v-if="hasMore"
            class="btn-ghost text-[12px]"
            :disabled="loading"
            @click="loadArticles(false)"
          >
            <Loader2 v-if="loading" :size="13" class="animate-spin" />
            <span>{{ loading ? '加载中' : '加载更多' }}</span>
          </button>
          <p v-else-if="articles.length" class="text-[11px] text-ink-faint">已到末尾</p>
        </div>
      </section>
    </div>
  </div>
</template>
