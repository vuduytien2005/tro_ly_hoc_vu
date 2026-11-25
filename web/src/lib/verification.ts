// Hiển thị kết quả LLM giám khảo kiểm chứng câu trả lời (backend: agent/verifier.py).
import type { Verification } from './types'

const CITATION_MARK = /\s*\[\d{1,3}\]/g
const TRAILING_PUNCT = /[\s.,;:!?]+$/
const MARKDOWN_CHARS = /[[\]*_`#<>|\\]/

/**
 * Biến mỗi ý "khong_co_can_cu" thành liên kết markdown "#unverified-<i>" (Answer.tsx vẽ thành chữ
 * gạch chân). Chỉ bọc phần chữ, không gồm "[n]" -> liên kết trích dẫn vẫn nguyên; ý chứa ký tự
 * markdown hoặc không tìm thấy trong câu trả lời thì bỏ qua. Gọi TRƯỚC linkCitations.
 */
export function markUnverified(text: string, v: Verification | null | undefined): string {
  if (!v) return text
  let out = text
  v.y.forEach((claim, i) => {
    if (claim.ket_luan !== 'khong_co_can_cu') return
    const core = claim.cau.replace(CITATION_MARK, '').replace(TRAILING_PUNCT, '').trim()
    if (!core || MARKDOWN_CHARS.test(core)) return
    const at = out.indexOf(core)
    if (at < 0) return
    out = `${out.slice(0, at)}[${core}](#unverified-${i})${out.slice(at + core.length)}`
  })
  return out
}

export function unverifiedIndex(href: string | undefined): number | null {
  const m = href?.match(/^#unverified-(\d+)$/)
  return m ? Number(m[1]) : null
}

export function verificationSummary(v: Verification): { label: string; ok: boolean } | null {
  // 0 ý: câu trả lời không khẳng định gì về quy chế (vd "văn bản không đề cập") -> không có nhãn
  if (v.tong === 0) return null
  return {
    label: `Đã kiểm chứng ${v.co_can_cu}/${v.tong} ý với văn bản`,
    ok: v.co_can_cu === v.tong,
  }
}

/** Câu điền sẵn vào ô chat khi sinh viên bấm "Hỏi cán bộ". */
export const ASK_STAFF_PROMPT = 'Mình muốn gửi câu hỏi này cho cán bộ phòng ban phụ trách.'
