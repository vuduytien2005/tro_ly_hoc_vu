// Xuất số liệu trang Thống kê ra CSV (đưa vào phụ lục khóa luận / mở bằng Excel).
// BOM UTF-8 để Excel nhận đúng tiếng Việt; xuống dòng CRLF; ô bắt đầu bằng = + - @ được thêm ' để
// Excel không coi là công thức.
import type { Stats } from './adminTypes'
import { ACTION_SEGMENTS, CALL_SEGMENTS } from './safety'

type Cell = string | number | null | undefined

export function csvCell(value: Cell): string {
  if (value == null) return ''
  let text = String(value)
  if (typeof value === 'string' && /^[=+\-@]/.test(text)) text = `'${text}`
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

function percent(ratio: number | null): Cell {
  return ratio == null ? null : Math.round(ratio * 1000) / 10
}

export function statsToCsv(s: Stats): string {
  const rows: Cell[][] = [
    ['Thống kê trợ lý học vụ'],
    ['Từ ngày', s.tu],
    ['Đến ngày', s.den],
    [],
    ['Tổng quan', 'Giá trị'],
    ['Cuộc trò chuyện', s.so_hoi_thoai],
    ['Câu hỏi', s.so_cau_hoi],
    ['Lượt đánh giá', s.so_danh_gia],
    ['Đánh giá hữu ích', s.so_huu_ich],
    ['Tỉ lệ hữu ích (%)', percent(s.ti_le_huu_ich)],
    ['Phản hồi trung bình (ms)', s.thoi_gian_phan_hoi_tb_ms],
    ['Lượt gọi công cụ', s.so_luot_goi_cong_cu],
    [],
    ['An toàn & độ tin cậy', 'Giá trị'],
    ['Lần LLM tự điền mã SV (bị ghi đè)', s.an_toan.so_lan_chan_ma_sv],
    ['Câu trả lời được kiểm chứng', s.an_toan.so_cau_kiem_chung],
    ['Số ý được chấm', s.an_toan.so_menh_de],
    ['Số ý có căn cứ', s.an_toan.so_co_can_cu],
    ['Tỉ lệ ý có căn cứ (%)', percent(s.an_toan.ti_le_co_can_cu)],
    [],
    ['Lượt gọi theo kết quả', 'Số lượt'],
    ...CALL_SEGMENTS.map((d) => [d.label, s.an_toan.trang_thai_goi[d.key] ?? 0]),
    [],
    ['Hành động cần xác nhận', 'Số hành động'],
    ...ACTION_SEGMENTS.map((d) => [d.label, s.an_toan.hanh_dong[d.key] ?? 0]),
    [],
    ['Công cụ', 'Số lượt', 'Lỗi / từ chối'],
    ...s.top_cong_cu.map((t) => [t.ten_cong_cu, t.so_lan, t.so_loi]),
    [],
    ['Ngày', 'Số câu hỏi'],
    ...s.theo_ngay.map((d) => [d.ngay, d.so_cau_hoi]),
  ]
  return '﻿' + rows.map((r) => r.map(csvCell).join(',')).join('\r\n') + '\r\n'
}

export function statsFileName(s: Stats): string {
  return `thong-ke_${s.tu}_${s.den}.csv`
}

/** Tải tệp CSV về máy (chỉ chạy trên trình duyệt). */
export function downloadStatsCsv(s: Stats): void {
  const url = URL.createObjectURL(new Blob([statsToCsv(s)], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = statsFileName(s)
  a.click()
  URL.revokeObjectURL(url)
}
