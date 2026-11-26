// Xuất "Nhật ký gọi công cụ" (đúng bộ lọc đang chọn) ra CSV — minh chứng an toàn cho Chương 4:
// tham số LLM gửi vs tham số thực thi (sau tiêm ngữ cảnh), lượt bị từ chối, chờ xác nhận...
import { injectedKeys, toQuery } from './admin'
import { CALL_STATUS, type AuditLog, type AuditLogPage } from './adminTypes'
import { api } from './api'
import { csvCell } from './statsCsv'

const VN_TIME = new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Asia/Ho_Chi_Minh',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

const HEADER = [
  'Thời gian',
  'Người dùng',
  'Email',
  'Hội thoại',
  'MCP server',
  'Công cụ',
  'Trạng thái',
  'Lý do',
  'Thời gian xử lý (ms)',
  'Tiêm ngữ cảnh',
  'Tham số bị ghi đè',
  'Tham số thực thi (JSON)',
  'Tham số LLM gửi (JSON)',
]

export function auditToCsv(rows: AuditLog[]): string {
  const lines = [
    HEADER,
    ...rows.map((r) => [
      VN_TIME.format(new Date(r.created_at)),
      r.nguoi_dung.ho_ten,
      r.nguoi_dung.email,
      r.hoi_thoai_id,
      r.mcp_server,
      r.ten_cong_cu,
      CALL_STATUS[r.trang_thai]?.label ?? r.trang_thai,
      r.ly_do,
      r.thoi_gian_ms,
      r.da_tiem_ngu_canh ? 'Có' : 'Không',
      [...injectedKeys(r.tham_so_llm, r.tham_so)].join(' '),
      JSON.stringify(r.tham_so),
      r.tham_so_llm == null ? null : JSON.stringify(r.tham_so_llm),
    ]),
  ]
  return '﻿' + lines.map((l) => l.map(csvCell).join(',')).join('\r\n') + '\r\n'
}

export function auditFileName(filters: { tu: string; den: string }): string {
  if (!filters.tu && !filters.den) return 'nhat-ky_tat-ca.csv'
  return `nhat-ky_${filters.tu || 'dau'}_${filters.den || 'nay'}.csv`
}

/** Số lượt tối đa một lần xuất (20 lần gọi API 100 lượt) — đủ cho dữ liệu thực nghiệm. */
export const EXPORT_LIMIT = 2000

/** Lấy mọi trang theo bộ lọc (100 lượt/trang) đến hết hoặc tới `limit`. */
export async function fetchAllAuditLogs(
  filters: Record<string, string>,
  get: (url: string) => Promise<AuditLogPage> = (url) => api<AuditLogPage>(url),
  limit: number = EXPORT_LIMIT,
): Promise<{ rows: AuditLog[]; truncated: boolean; total: number }> {
  const rows: AuditLog[] = []
  let total = 0
  for (let page = 1; ; page++) {
    const data = await get(`/api/admin/audit-logs${toQuery({ ...filters, page, page_size: 100 })}`)
    total = data.tong
    rows.push(...data.luot_goi)
    if (rows.length >= limit) return { rows: rows.slice(0, limit), truncated: total > limit, total }
    if (data.luot_goi.length < 100 || rows.length >= total) return { rows, truncated: false, total }
  }
}
