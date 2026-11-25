// Kho hỏi đáp cán bộ + lỗ hổng tri thức (thiết kế 2026-11-25-kho-hoi-dap-va-lo-hong-tri-thuc).
// Kho trả cho MỌI sinh viên qua RAG -> cảnh báo thông tin cá nhân ngay trên form (backend chặn lần
// cuối bằng cùng các mẫu: knowledge.personal_info_problem).

import type { StaffRequest } from './adminTypes'

export type GapSource = 'khong_can_cu' | 'khong_tim_thay' | 'hoi_can_bo' | 'danh_gia_xau'

export interface Gap {
  nguon: GapSource
  thoi_gian: string
  cau_hoi: string | null
  noi_dung: string
  ly_do: string | null
  tra_loi_can_bo: string | null
  tin_nhan_id: number | null
  ma_don: string | null
  phong_ban: string | null
  trang_thai: string | null
  da_vao_kho: boolean
}

export interface GapList {
  tu: string
  den: string
  dem: Record<GapSource, number>
  muc: Gap[]
  nguon_loi: GapSource[]
}

export interface KnowledgeEntry {
  id: number
  cau_hoi: string
  tra_loi: string
  phong_ban: string
  ma_don: string | null
  tin_nhan_id: number | null
  created_at: string
  updated_at: string
}

export interface KnowledgeList {
  van_ban: {
    id: number
    trang_thai: string
    so_doan: number
    loi: string | null
    updated_at: string
  } | null
  muc: KnowledgeEntry[]
}

export interface KnowledgeDraft {
  cau_hoi: string
  tra_loi: string
  phong_ban: string
  ma_don?: string | null
  tin_nhan_id?: number | null
}

export const GAP_SOURCES: Record<GapSource, { label: string; hint: string; className: string }> = {
  khong_can_cu: {
    label: 'Thiếu căn cứ',
    hint: 'Ý trong câu trả lời mà giám khảo không tìm thấy trong văn bản',
    className: 'bg-warn-bg text-warn',
  },
  khong_tim_thay: {
    label: 'Không tìm thấy',
    hint: 'Trợ lý đã tra cứu nhưng văn bản không có thông tin để trả lời',
    className: 'bg-slate-100 text-slate-700',
  },
  hoi_can_bo: {
    label: 'Hỏi cán bộ',
    hint: 'Câu hỏi sinh viên gửi cán bộ (ask_staff)',
    className: 'bg-primary/10 text-primary',
  },
  danh_gia_xau: {
    label: 'Đánh giá 👎',
    hint: 'Câu trả lời sinh viên đánh giá chưa đúng',
    className: 'bg-err-bg text-err',
  },
}

const PERSONAL_PATTERNS: [RegExp, string][] = [
  [/\bSV\d{5}\b/i, 'mã sinh viên'],
  [/[\w.+-]+@[\w-]+(?:\.[\w-]+)+/, 'địa chỉ email'],
  [/(?<![\d.,])(?:\+84|0)(?:[\s.-]?\d){8,10}(?!\d)/, 'số điện thoại'],
]

/** Loại thông tin cá nhân đầu tiên tìm thấy (vd "mã sinh viên"), không có -> null. */
export function personalInfoProblem(text: string): string | null {
  for (const [pattern, label] of PERSONAL_PATTERNS) if (pattern.test(text)) return label
  return null
}

/** Lỗi đầu tiên của bản nháp (độ dài như backend: câu hỏi 10–1000, trả lời 5–4000). */
export function draftProblem(draft: KnowledgeDraft): string | null {
  const q = draft.cau_hoi.trim()
  const a = draft.tra_loi.trim()
  if (q.length < 10) return 'Câu hỏi cần ít nhất 10 ký tự.'
  if (q.length > 1000) return 'Câu hỏi tối đa 1000 ký tự.'
  if (a.length < 5) return 'Câu trả lời cần ít nhất 5 ký tự.'
  if (a.length > 4000) return 'Câu trả lời tối đa 4000 ký tự.'
  for (const [field, text] of [
    ['Câu hỏi', q],
    ['Câu trả lời', a],
  ]) {
    const p = personalInfoProblem(text)
    if (p) return `${field} có ${p} — hãy bỏ thông tin cá nhân (kho trả cho mọi sinh viên).`
  }
  return null
}

export function gapToDraft(gap: Gap): KnowledgeDraft {
  return {
    cau_hoi: gap.cau_hoi ?? gap.noi_dung,
    tra_loi: gap.tra_loi_can_bo ?? '',
    phong_ban: gap.phong_ban ?? 'khac',
    tin_nhan_id: gap.tin_nhan_id,
    ma_don: gap.ma_don,
  }
}

export function requestToDraft(req: StaffRequest): KnowledgeDraft {
  const content = req.noi_dung as { cau_hoi?: unknown; phong_ban?: unknown }
  return {
    cau_hoi: String(content.cau_hoi ?? ''),
    tra_loi: req.ghi_chu_xu_ly ?? '',
    phong_ban: String(content.phong_ban ?? 'khac'),
    ma_don: req.ma_don,
    tin_nhan_id: null,
  }
}

/** Trích dẫn từ kho hỏi đáp cán bộ (không có tệp gốc để mở). */
export function isKnowledgeCitation(citation: { loai?: string | null }): boolean {
  return citation.loai === 'hoi_dap'
}
