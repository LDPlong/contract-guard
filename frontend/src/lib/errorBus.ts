/** 全局错误上报：组件边界之外的异常也走这里，界面上给一条可关闭的提示。 */

type Handler = (message: string) => void

const handlers = new Set<Handler>()

export function onGlobalError(handler: Handler): () => void {
  handlers.add(handler)
  return () => {
    handlers.delete(handler)
  }
}

export function reportError(scope: string, error: unknown): string {
  const message = error instanceof Error ? error.message : String(error)
  // 控制台保留完整堆栈，界面只给一句人话
  console.error(`[${scope}]`, error)
  const text = message ? `${scope}：${message}` : scope
  for (const handler of handlers) handler(text)
  return text
}
