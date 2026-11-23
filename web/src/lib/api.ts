// Gọi assistant_api qua proxy Vite ("/api/..."); lỗi {detail, code} -> ApiError.
// Đăng nhập bằng cookie HttpOnly (bổ sung 23/11/2026): JavaScript KHÔNG giữ token (XSS không lấy
// được), trình duyệt tự gửi cookie cùng nguồn. Yêu cầu thay đổi dữ liệu kèm header X-CSRF-Token
// đọc từ cookie tlhv_csrf (trang web khác không đọc được cookie này -> chống CSRF).

const CSRF_COOKIE = 'tlhv_csrf'
const CSRF_HEADER = 'X-CSRF-Token'
const LEGACY_TOKEN_KEY = 'tlhv_token' // bản cũ lưu JWT ở localStorage -> xóa đi

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

/** Đọc một cookie (không HttpOnly) theo tên. */
export function readCookie(name: string, cookies: string = document.cookie): string | null {
  for (const part of cookies.split(';')) {
    const [k, ...v] = part.trim().split('=')
    if (k === name) return decodeURIComponent(v.join('='))
  }
  return null
}

/** Có dấu hiệu đang đăng nhập (cookie CSRF đi cùng cookie phiên) — chỉ để khỏi gọi /me thừa. */
export function hasSession(): boolean {
  localStorage.removeItem(LEGACY_TOKEN_KEY)
  return readCookie(CSRF_COOKIE) != null
}

/** Phiên hết hạn / bị khóa giữa chừng -> quay về trang đăng nhập. */
function handleUnauthorized(): void {
  if (window.location.pathname !== '/login') window.location.assign('/login')
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

/** Header chống CSRF (cookie phiên do trình duyệt tự gửi). */
export function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const csrf = readCookie(CSRF_COOKIE)
  return csrf ? { ...extra, [CSRF_HEADER]: csrf } : extra
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init
  const response = await fetch(path, {
    credentials: 'same-origin',
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
