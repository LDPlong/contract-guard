import axios, { type AxiosRequestConfig } from 'axios'
import type { Envelope } from '@/types'

const SESSION_KEY = 'cg_session_id'

/** 匿名 session：仅用于隔离历史记录，不做身份认证（文档 6.1 约定 3） */
export function getSessionId(): string {
  let sid = localStorage.getItem(SESSION_KEY)
  if (!sid) {
    sid =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `s_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
    localStorage.setItem(SESSION_KEY, sid)
  }
  return sid
}

export class ApiError extends Error {
  code: number

  constructor(code: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
  }
}

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 60_000,
})

http.interceptors.request.use((config) => {
  config.headers.set('X-Session-Id', getSessionId())
  return config
})

/** 统一解包 {code,message,data}：code !== 0 一律抛 ApiError，调用方只处理业务数据 */
export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  let body: Envelope<T>
  try {
    const res = await http.request<Envelope<T>>(config)
    body = res.data
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const payload = err.response?.data as Partial<Envelope<unknown>> | undefined
      if (payload && typeof payload.code === 'number') {
        throw new ApiError(payload.code, payload.message ?? '请求失败')
      }
      throw new ApiError(-1, err.message || '网络错误，请检查后端是否启动')
    }
    throw err
  }
  if (!body || body.code !== 0) {
    throw new ApiError(body?.code ?? -1, body?.message ?? '未知错误')
  }
  return body.data
}

export default http
