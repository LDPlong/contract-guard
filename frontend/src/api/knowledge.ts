import { request } from '@/api/http'

export interface LawSource {
  source: string
  title: string
  version: string | null
  effective_date: string | null
  count: number
}

export interface LawArticle {
  id: string
  source: string
  title: string
  article_no: string
  article_index: number
  version: string | null
  effective_date: string | null
  content: string
}

export interface ArticlePage {
  total: number
  items: LawArticle[]
}

export interface SearchHit {
  chunk_id: string
  source: string
  article_no: string
  content: string
  score: number
  effective_date: string | null
}

export function fetchSources(): Promise<{ items: LawSource[] }> {
  return request({ url: '/knowledge/sources', method: 'GET' })
}

export function fetchArticles(params: {
  source?: string
  q?: string
  offset?: number
  limit?: number
}): Promise<ArticlePage> {
  return request({ url: '/knowledge/articles', method: 'GET', params })
}

export function searchKnowledge(q: string, topK = 8): Promise<{ items: SearchHit[] }> {
  return request({
    url: '/knowledge/search',
    method: 'GET',
    params: { q, top_k: topK },
    timeout: 30_000,
  })
}
