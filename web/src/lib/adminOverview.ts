// Trang quản trị "Tổng quan": gom việc cần xử lý + tình trạng hệ thống từ các API sẵn có.
import { serverLabel } from './health'
import type { Gap } from './knowledge'

const VN_DAY = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' })

/** Khoảng `days` ngày gần nhất (tính cả hôm nay, theo ngày Việt Nam) cho /api/admin/stats. */
export function lastDaysRange(days: number, now: Date = new Date()): { tu: string; den: string } {
  const den = VN_DAY.format(now)
  const start = new Date(`${den}T00:00:00Z`)
  start.setUTCDate(start.getUTCDate() - (days - 1))
  return { tu: start.toISOString().slice(0, 10), den }
}

export type ServerState = 'ok' | 'tat' | 'loi'

export interface ServerRow {
  name: string
  label: string
  state: ServerState
  detail: string
}

const STATE_ORDER: Record<ServerState, number> = { loi: 0, ok: 1, tat: 2 }

/** Trạng thái MCP server từ /health: "ok" | "tắt" | thông báo lỗi. Gián đoạn lên đầu. */
export function serverRows(status: Record<string, string>): ServerRow[] {
  return Object.entries(status)
    .map(([name, value]): ServerRow => {
      const state: ServerState = value === 'ok' ? 'ok' : value === 'tắt' ? 'tat' : 'loi'
      const detail = state === 'ok' ? 'Hoạt động' : state === 'tat' ? 'Đang tắt' : value
      return { name, label: serverLabel(name), state, detail }
    })
    .sort((a, b) => STATE_ORDER[a.state] - STATE_ORDER[b.state] || a.name.localeCompare(b.name))
}

/** Lỗ hổng tri thức chưa được đưa vào kho hỏi đáp (việc cán bộ còn phải làm). */
export function pendingGapCount(gaps: Gap[]): number {
  return gaps.filter((g) => !g.da_vao_kho).length
}
