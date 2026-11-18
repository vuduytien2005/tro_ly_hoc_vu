// Hàm định dạng thuần (có test): trích dẫn, đồng hồ đếm ngược, ngày giờ.

import type { Citation } from './types'

const CITATION_RE = /\[(\d{1,3})\](?!\()/g

/**
 * Biến "[n]" trong câu trả lời thành liên kết markdown "#cite-n" (component Markdown hiển thị
 * thành nút trích dẫn). Chỉ đổi các số có trong danh sách nguồn; "[n](url)" giữ nguyên.
 */
export function linkCitations(text: string, citations: Citation[] | null | undefined): string {
  if (!citations?.length) return text
  const known = new Set(citations.map((c) => c.so))
  return text.replace(CITATION_RE, (match, n: string) =>
    known.has(Number(n)) ? `[\\[${n}\\]](#cite-${n})` : match,
  )
}

export function citationNumber(href: string | undefined): number | null {
  const m = href?.match(/^#cite-(\d+)$/)
  return m ? Number(m[1]) : null
}

export function citationLocation(c: Citation): string {
  return [c.dieu, c.khoan, c.trang != null ? `trang ${c.trang}` : null]
    .filter(Boolean)
    .join(', ')
}

/** Số mili-giây còn lại -> "mm:ss" (âm -> "00:00"). */
export function formatRemaining(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000))
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

const DATE_TIME = new Intl.DateTimeFormat('vi-VN', {
  timeZone: 'Asia/Ho_Chi_Minh',
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})
const DATE = new Intl.DateTimeFormat('vi-VN', {
  timeZone: 'Asia/Ho_Chi_Minh',
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})

export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : DATE_TIME.format(d)
}

export function formatDate(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00+07:00` : iso)
  return Number.isNaN(d.getTime()) ? iso : DATE.format(d)
}

/** Tin user do hệ thống lưu khi sinh viên bấm Xác nhận / Hủy trên thẻ (xem backend loop.py). */
export const CONFIRM_PREFIX = 'Xác nhận: '
export const CANCEL_PREFIX = 'Hủy: '
