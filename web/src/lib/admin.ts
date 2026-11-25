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

/** Nhãn duyệt mô tả công cụ MCP: mới thêm (chưa duyệt) hoặc server đã đổi mô tả sau khi duyệt. */
export function reviewBadge(
  duyet: 'da_duyet' | 'moi' | 'thay_doi',
): { text: string; tone: 'new' | 'changed' } | null {
  if (duyet === 'moi') return { text: 'Mới — cần duyệt', tone: 'new' }
  if (duyet === 'thay_doi') return { text: 'Mô tả đã thay đổi — cần duyệt lại', tone: 'changed' }
  return null
}

/**
 * Các bước kế tiếp hợp lệ của một đơn — bản sao máy trạng thái ở qlsv_api
 * (request_service.next_statuses) chỉ để hiện đúng nút; qlsv_api vẫn là nơi kiểm tra.
 */
const NEXT_STATUSES: Record<string, string[]> = {
  moi_tao: ['dang_xu_ly', 'da_duyet', 'tu_choi'],
  dang_xu_ly: ['da_duyet', 'tu_choi'],
  da_duyet: ['hoan_tat'],
}
/** Câu hỏi gửi cán bộ: không có bước duyệt; hoan_tat = đã trả lời. */
const QUESTION_NEXT_STATUSES: Record<string, string[]> = {
  moi_tao: ['dang_xu_ly', 'hoan_tat', 'tu_choi'],
  dang_xu_ly: ['hoan_tat', 'tu_choi'],
}

export function nextStatuses(current: string, loai?: string): string[] {
  const machine = loai === 'hoi_dap' ? QUESTION_NEXT_STATUSES : NEXT_STATUSES
  return machine[current] ?? []
}

/**
 * Từ chối phải có lý do (422 CAN_LY_DO_TU_CHOI); trả lời câu hỏi phải có nội dung
 * (422 CAN_NOI_DUNG_TRA_LOI).
 */
export function reviewNoteProblem(target: string, note: string, loai?: string): string | null {
  if (note.trim()) return null
  if (target === 'tu_choi') return 'Cần ghi lý do từ chối để sinh viên biết.'
  if (target === 'hoan_tat' && loai === 'hoi_dap') return 'Cần nhập nội dung trả lời cho sinh viên.'
  return null
}
