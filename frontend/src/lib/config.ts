/**
 * 全站公共配置。
 *
 * 反馈邮箱全站唯一出处：反馈页、页脚入口都从这里取。
 * 换邮箱只改 FEEDBACK_EMAIL 这一行。
 */
export const FEEDBACK_EMAIL = 'ldplong@outlook.com'

/** 拼一个带预填主题与正文的 mailto 链接 */
export function makeMailto(subject: string, body: string): string {
  return (
    `mailto:${FEEDBACK_EMAIL}` +
    `?subject=${encodeURIComponent(subject)}` +
    `&body=${encodeURIComponent(body)}`
  )
}
