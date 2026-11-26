import { citationLocation, formatDateTime } from './format'
import type { Conversation, Message } from './types'

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
    for (const c of m.trich_dan ?? []) {
      const source = [c.van_ban, c.phien_ban ? `(${c.phien_ban})` : null].filter(Boolean).join(' ')
      const where = citationLocation(c)
      lines.push(`    [${c.so}] ${source || 'Tài liệu'}${where ? ` — ${where}` : ''}`)
    }
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
