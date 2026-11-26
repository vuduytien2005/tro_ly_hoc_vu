import { citationLocation, formatDateTime } from './format'
import type { Citation, Conversation, Message } from './types'

/** Chuẩn hóa để tìm kiếm: bỏ dấu tiếng Việt (đ -> d), chữ thường, gộp khoảng trắng. */
export function normalizeSearch(text: string): string {
  return text
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'd')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()
}

export interface ConversationGroup {
  label: string
  items: Conversation[]
}

// Ngày theo giờ Việt Nam (YYYY-MM-DD) -> so số ngày lịch, không lệch vì múi giờ trình duyệt
const VN_DAY = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' })

function vnDayNumber(date: Date): number {
  return Date.parse(`${VN_DAY.format(date)}T00:00:00Z`) / 86_400_000
}

const GROUPS: { label: string; maxDays: number }[] = [
  { label: 'Hôm nay', maxDays: 0 },
  { label: '7 ngày qua', maxDays: 6 },
  { label: '30 ngày qua', maxDays: 29 },
  { label: 'Cũ hơn', maxDays: Infinity },
]

/** Lọc theo tiêu đề (không phân biệt dấu) rồi nhóm theo lần cập nhật cuối, mới nhất trước. */
export function groupConversations(
  list: Conversation[],
  query: string,
  now: Date = new Date(),
): ConversationGroup[] {
  const q = normalizeSearch(query)
  const today = vnDayNumber(now)
  const sorted = list
    .filter((c) => !q || normalizeSearch(c.tieu_de).includes(q))
    .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))
  const groups: ConversationGroup[] = GROUPS.map((g) => ({ label: g.label, items: [] }))
  for (const c of sorted) {
    const age = today - vnDayNumber(new Date(c.updated_at))
    const index = GROUPS.findIndex((g) => age <= g.maxDays)
    groups[index].items.push(c)
  }
  return groups.filter((g) => g.items.length > 0)
}

/** Nội dung tệp .txt khi sinh viên tải cuộc trò chuyện về máy (kèm nguồn trích dẫn). */
export function conversationText(
  title: string,
  messages: Message[],
  now: Date = new Date(),
): string {
  const lines = [title, `Trợ lý học vụ — tải về lúc ${formatDateTime(now.toISOString())}`, '']
  for (const m of messages) {
    const text = m.noi_dung.trim()
    if (!text) continue
    const who = m.vai_tro === 'user' ? 'Em' : 'Trợ lý'
    lines.push(`[${formatDateTime(m.created_at)}] ${who}: ${text}`)
    for (const c of m.trich_dan ?? []) lines.push(`    ${citationLine(c)}`)
    lines.push('')
  }
  lines.push(
    'Lưu ý: câu trả lời do trợ lý AI tổng hợp, chỉ để tham khảo; thông tin chính thức theo văn bản gốc của nhà trường.',
  )
  return lines.join('\n')
}

/** Tên tệp an toàn từ tiêu đề: "tro-chuyen-<tieu-de-khong-dau>.txt". */
export function exportFileName(title: string): string {
  const slug = normalizeSearch(title)
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
  return `tro-chuyen-${slug || 'hoi-thoai'}.txt`
}

/** "[1] Quy chế đào tạo (2021) — Điều 8, Khoản 2, trang 3" */
export function citationLine(c: Citation): string {
  const source = [c.van_ban, c.phien_ban ? `(${c.phien_ban})` : null].filter(Boolean).join(' ')
  const where = citationLocation(c)
  return `[${c.so}] ${source || 'Tài liệu'}${where ? ` — ${where}` : ''}`
}

/** Bỏ ký hiệu Markdown thường gặp trong câu trả lời (đậm, nghiêng, tiêu đề, liên kết). */
function stripMarkdown(text: string): string {
  return text
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/(\*\*|__)(.+?)\1/g, '$2')
    .replace(/(^|[^*\w])\*(?!\s)([^*\n]+?)\*(?!\w)/g, '$1$2')
    .replace(/`([^`]+)`/g, '$1')
}

/** Nội dung nút "Sao chép": chữ thường (dán vào Zalo / email) + danh sách nguồn ở cuối. */
export function answerCopyText(text: string, citations: Citation[] | null | undefined): string {
  const body = stripMarkdown(text.trim())
  if (!citations?.length) return body
  return `${body}\n\nNguồn:\n${citations.map(citationLine).join('\n')}`
}

/** Bộ đếm ký tự ô nhập: chỉ hiện khi đã dùng từ 90% giới hạn. */
export function charCounter(length: number, max: number): string | null {
  return length >= max * 0.9 ? `${length}/${max}` : null
}

const WEEKDAYS = ['Chủ nhật', 'Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy']
const VN_TIME = new Intl.DateTimeFormat('vi-VN', {
  timeZone: 'Asia/Ho_Chi_Minh',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/** Dòng phân cách ngày trong chat: "Hôm nay", "Hôm qua", "Thứ Hai, 23/11/2026" (giờ Việt Nam). */
export function dayLabel(iso: string, now: Date = new Date()): string {
  const date = new Date(iso)
  const day = vnDayNumber(date)
  const diff = vnDayNumber(now) - day
  if (diff === 0) return 'Hôm nay'
  if (diff === 1) return 'Hôm qua'
  const [y, m, d] = VN_DAY.format(date).split('-')
  // 01/01/1970 là thứ Năm -> (số ngày + 4) % 7 = thứ trong tuần (0 = Chủ nhật)
  return `${WEEKDAYS[(((day + 4) % 7) + 7) % 7]}, ${d}/${m}/${y}`
}

/** "08:05" theo giờ Việt Nam. */
export function formatTime(iso: string): string {
  return VN_TIME.format(new Date(iso))
}

/** id các tin nhắn mở đầu một ngày mới (để chèn dòng phân cách ngày). */
export function dayBreaks(messages: { id: number; created_at: string }[]): Set<number> {
  const out = new Set<number>()
  let previous: number | null = null
  for (const m of messages) {
    const day = vnDayNumber(new Date(m.created_at))
    if (day !== previous) out.add(m.id)
    previous = day
  }
  return out
}
