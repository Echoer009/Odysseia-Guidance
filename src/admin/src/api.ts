import { toastError } from './feedback'

export const API_BASE = `${import.meta.env.BASE_URL.replace(/\/$/, '')}/api`

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function notifyUnauthorized(): void {
  window.dispatchEvent(new CustomEvent('admin:unauthorized'))
}

async function readErrorMessage(res: Response): Promise<string> {
  let msg = `请求失败（HTTP ${res.status}）`
  try {
    const text = await res.text()
    if (text.length > 0) {
      const data: unknown = JSON.parse(text)
      if (typeof data === 'string' && data.length > 0) {
        msg = data
      } else if (data != null && typeof data === 'object') {
        const record = data as Record<string, unknown>
        const detail = record.detail ?? record.error ?? record.message
        if (typeof detail === 'string' && detail.length > 0) msg = detail
        else msg = text.slice(0, 300)
      }
    }
  } catch {}
  return msg
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (options.body != null) headers['Content-Type'] = 'application/json'
  const res = await fetch(`${API_BASE}/${path.replace(/^\/+/, '')}`, { ...options, headers })
  if (res.status === 401) {
    notifyUnauthorized()
    throw new ApiError(401, '登录状态已失效')
  }
  if (!res.ok) {
    const errorMessage = await readErrorMessage(res)
    toastError(errorMessage)
    throw new ApiError(res.status, errorMessage)
  }
  if (res.status === 204) return undefined as T
  const text = await res.text()
  if (text.length === 0) return undefined as T
  try {
    return JSON.parse(text) as T
  } catch {
    return undefined as T
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
