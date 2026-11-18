// Gọi assistant_api qua proxy Vite ("/api/..."), tự gắn JWT; lỗi {detail, code} -> ApiError.

const TOKEN_KEY = 'tlhv_token'

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

/** Token hết hạn / bị khóa giữa chừng -> xóa token, quay về trang đăng nhập. */
function handleUnauthorized(): void {
  if (getToken()) {
    setToken(null)
    if (window.location.pathname !== '/login') window.location.assign('/login')
  }
}

export async function toApiError(response: Response): Promise<ApiError> {
  let detail = 'Có lỗi xảy ra, vui lòng thử lại.'
  let code = `HTTP_${response.status}`
  try {
    const body = (await response.json()) as { detail?: unknown; code?: unknown }
    if (typeof body.detail === 'string') detail = body.detail
    if (typeof body.code === 'string') code = body.code
  } catch {
    // phản hồi không phải JSON (vd backend chưa chạy -> proxy trả 502/504)
    if (response.status >= 500) detail = 'Không kết nối được máy chủ trợ lý. Kiểm tra backend đã chạy chưa.'
  }
  if (response.status === 401) handleUnauthorized()
  return new ApiError(response.status, code, detail)
}

export function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getToken()
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init
  const response = await fetch(path, {
    ...rest,
    headers: authHeaders({
      ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(headers as Record<string, string> | undefined),
    }),
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  })
  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
