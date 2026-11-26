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

/** Huy hiệu số việc chờ trên menu quản trị: rỗng = ẩn. */
export function countBadge(n: number | undefined): string {
  if (!n || n <= 0) return ''
  return n > 99 ? '99+' : String(n)
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
export function changedFields<T extends Record<string, string>>(
  initial: T,
  current: T,
): Partial<T> {
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

// ----- Đơn từ: thời gian chờ + mẫu trả lời (bổ sung 26/11/2026) -----

const VN_DATE = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' })
const CLOSED_STATUSES = new Set(['hoan_tat', 'tu_choi'])
/** Quá số ngày này mà đơn chưa xong -> tô cảnh báo trong danh sách. */
export const OVERDUE_DAYS = 3

/** Số ngày (theo lịch Việt Nam) đơn đã chờ; null khi đơn đã kết thúc. */
export function waitingAge(
  createdAt: string,
  status: string,
  now: Date = new Date(),
): { days: number; label: string; overdue: boolean } | null {
  if (CLOSED_STATUSES.has(status)) return null
  const day = (d: Date) => Date.parse(`${VN_DATE.format(d)}T00:00:00Z`)
  const days = Math.max(0, Math.round((day(now) - day(new Date(createdAt))) / 86_400_000))
  return {
    days,
    label: days === 0 ? 'Gửi hôm nay' : `Chờ ${days} ngày`,
    overdue: days > OVERDUE_DAYS,
  }
}

export interface ReplyTemplate {
  /** Bước xử lý mà mẫu này dùng kèm */
  buoc: string
  nhan: string
  noi_dung: string
}

/** Câu trả lời mẫu cho cán bộ, theo loại đơn. Cán bộ sửa lại cho đúng trường hợp trước khi gửi. */
const REPLY_TEMPLATES: Record<string, ReplyTemplate[]> = {
  giay_xac_nhan_sv: [
    {
      buoc: 'da_duyet',
      nhan: 'Đang làm giấy',
      noi_dung: 'Đơn đã được duyệt, giấy xác nhận đang được in và đóng dấu.',
    },
    {
      buoc: 'hoan_tat',
      nhan: 'Mời nhận giấy',
      noi_dung:
        'Giấy xác nhận đã sẵn sàng. Em mang thẻ sinh viên đến phòng Công tác sinh viên nhận trong giờ hành chính.',
    },
    {
      buoc: 'tu_choi',
      nhan: 'Thông tin chưa khớp',
      noi_dung:
        'Thông tin trên đơn chưa khớp với hồ sơ sinh viên. Em kiểm tra lại rồi gửi đơn mới nhé.',
    },
  ],
  bao_luu: [
    {
      buoc: 'da_duyet',
      nhan: 'Đã duyệt',
      noi_dung: 'Đơn bảo lưu đã được duyệt, quyết định bảo lưu sẽ được gửi tới em khi ban hành.',
    },
    {
      buoc: 'hoan_tat',
      nhan: 'Đã có quyết định',
      noi_dung:
        'Đã có quyết định bảo lưu. Trước khi quay lại học, em làm đơn nhập học lại theo hướng dẫn của phòng Đào tạo.',
    },
    {
      buoc: 'tu_choi',
      nhan: 'Thiếu minh chứng',
      noi_dung:
        'Đơn chưa có đủ giấy tờ minh chứng lý do bảo lưu theo quy chế. Em bổ sung rồi gửi lại đơn nhé.',
    },
  ],
  phuc_khao: [
    {
      buoc: 'da_duyet',
      nhan: 'Đã tiếp nhận',
      noi_dung: 'Đơn phúc khảo đã được tiếp nhận và chuyển cho giảng viên chấm lại.',
    },
    {
      buoc: 'hoan_tat',
      nhan: 'Đã chấm lại',
      noi_dung:
        'Bài thi đã được chấm phúc khảo. Nếu điểm thay đổi, điểm mới đã được cập nhật trên bảng điểm của em.',
    },
    {
      buoc: 'tu_choi',
      nhan: 'Quá hạn phúc khảo',
      noi_dung: 'Đơn được gửi sau thời hạn phúc khảo của học phần này nên không thể tiếp nhận.',
    },
  ],
  hoi_dap: [
    {
      buoc: 'tu_choi',
      nhan: 'Sai phòng ban',
      noi_dung:
        'Câu hỏi này không thuộc phạm vi phòng mình. Em gửi lại và chọn đúng phòng ban phụ trách nhé.',
    },
  ],
}

/** Mẫu của loại đơn, chỉ giữ những mẫu cho bước còn làm được ở trạng thái hiện tại. */
export function replyTemplates(loai: string, steps: string[]): ReplyTemplate[] {
  return (REPLY_TEMPLATES[loai] ?? []).filter((t) => steps.includes(t.buoc))
}

/** Chèn mẫu: ô trống -> thay bằng mẫu; đã có chữ -> nối xuống dòng mới (không xóa chữ cán bộ gõ). */
export function insertTemplate(current: string, template: string): string {
  return current.trim() ? `${current.replace(/\s+$/, '')}\n${template}` : template
}
