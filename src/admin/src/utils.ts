export function formatDateTime(value: unknown): string {
  if (value == null) return '—'
  const date = new Date(String(value))
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (n: number): string => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

export function toNumber(value: unknown, fallback = 0): number {
  const n = Number(value)
  return Number.isFinite(n) ? n : fallback
}

export function percent(count: unknown, total: unknown): string {
  const c = toNumber(count)
  const t = toNumber(total)
  if (t <= 0) return '—'
  return `${((c / t) * 100).toFixed(1)}%`
}

export function normalizeStringArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item))
  if (typeof value === 'string' && value.length > 0) return [value]
  return []
}

export function signedNumber(value: unknown): string {
  const n = toNumber(value)
  if (n > 0) return `+${n}`
  return String(n)
}

export function prettyJson(value: unknown): string {
  if (value == null) return ''
  try {
    return JSON.stringify(value, null, 2) ?? ''
  } catch {
    return String(value)
  }
}

export function auditActionTagType(action: unknown): 'success' | 'info' | 'error' | 'warning' | 'default' {
  const a = String(action ?? '')
  if (a === 'create' || a === 'unban') return 'success'
  if (a === 'update') return 'info'
  if (a === 'delete' || a === 'ban') return 'error'
  if (a === 'adjust_coins') return 'warning'
  return 'default'
}
