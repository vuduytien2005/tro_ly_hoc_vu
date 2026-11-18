import { CircleAlert, CircleCheck, LoaderCircle } from 'lucide-react'

export interface ToolChip {
  ten: string
  nhan: string
  trang_thai: 'dang_chay' | 'thanh_cong' | 'loi'
}

// Nhãn dự phòng nếu backend không gửi "nhan" (docs/08: map tên tool -> câu tiếng Việt)
const LABELS: Record<string, string> = {
  search_regulations: 'Đang tra cứu quy chế',
  get_transcript: 'Đang xem bảng điểm của em',
  get_graduation_progress: 'Đang đối chiếu tiến độ tốt nghiệp',
  search_course_sections: 'Đang tìm lớp học phần',
  register_course: 'Đang đăng ký học phần',
}

export function toolLabel(ten: string, nhan?: string): string {
  return nhan || LABELS[ten] || `Đang dùng công cụ ${ten}`
}

export function ToolChips({ chips }: { chips: ToolChip[] }) {
  if (!chips.length) return null
  return (
    <div className="mb-2 flex flex-wrap gap-2" aria-live="polite">
      {chips.map((chip, i) => {
        const done = chip.trang_thai !== 'dang_chay'
        const failed = chip.trang_thai === 'loi'
        return (
          <span
            key={`${chip.ten}-${i}`}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs ${
              failed
                ? 'border-warn/30 bg-warn-bg text-warn'
                : done
                  ? 'border-ok/20 bg-ok-bg text-ok'
                  : 'border-line bg-white text-slate-600'
            }`}
          >
            {failed ? (
              <CircleAlert size={14} />
            ) : done ? (
              <CircleCheck size={14} />
            ) : (
              <LoaderCircle size={14} className="animate-spin" />
            )}
            {done ? chip.nhan.replace(/^Đang /, 'Đã ') : `${chip.nhan}…`}
          </span>
        )
      })}
    </div>
  )
}
