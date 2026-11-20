// Hàm thuần cho trang quản trị (có test).

/** "khóa 22..null" -> "Từ K22"; null..21 -> "Đến K21"; null..null -> "Mọi khóa". */
export function cohortRange(from: number | null, to: number | null): string {
  const k = (n: number) => `K${String(n).padStart(2, '0')}`
  if (from == null && to == null) return 'Mọi khóa'
  if (from != null && to != null) return from === to ? k(from) : `${k(from)} – ${k(to)}`
  return from != null ? `Từ ${k(from)}` : `Đến ${k(to!)}`
}

/** Tập khóa tham số có giá trị khác nhau giữa bản LLM gửi và bản thực thi (sau tiêm ngữ cảnh). */
export function injectedKeys(
  llm: Record<string, unknown> | null,
  actual: Record<string, unknown>,
): Set<string> {
  const keys = new Set<string>()
  if (!llm) return keys
  for (const key of new Set([...Object.keys(llm), ...Object.keys(actual)])) {
    if (JSON.stringify(llm[key]) !== JSON.stringify(actual[key])) keys.add(key)
  }
  return keys
}

/** Query string bỏ tham số rỗng. */
export function toQuery(params: Record<string, string | number | null | undefined>): string {
  const q = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') q.set(key, String(value))
  }
  const s = q.toString()
  return s ? `?${s}` : ''
}

export function formatPercent(ratio: number | null): string {
  return ratio == null ? '—' : `${Math.round(ratio * 1000) / 10}%`
}

export function formatMs(ms: number | null): string {
  if (ms == null) return '—'
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} giây`
}

/** Cùng quy tắc với backend (MAT_KHAU_YEU): 8–72 byte UTF-8, có chữ cái và chữ số. null = hợp lệ. */
export function passwordProblem(password: string): string | null {
  if (password.length < 8) return 'Mật khẩu cần ít nhất 8 ký tự.'
  if (new TextEncoder().encode(password).length > 72) return 'Mật khẩu quá dài (tối đa 72 byte).'
  if (!/\p{L}/u.test(password)) return 'Mật khẩu cần ít nhất một chữ cái.'
  if (!/\d/.test(password)) return 'Mật khẩu cần ít nhất một chữ số.'
  return null
}

/** Chỉ giữ các trường đã đổi so với ban đầu (so sau khi bỏ khoảng trắng hai đầu). */
export function changedFields<T extends Record<string, string>>(initial: T, current: T): Partial<T> {
  const out: Partial<T> = {}
  for (const key of Object.keys(current) as (keyof T)[]) {
    const value = current[key].trim()
    if (value !== initial[key].trim()) out[key] = value as T[keyof T]
  }
  return out
}
