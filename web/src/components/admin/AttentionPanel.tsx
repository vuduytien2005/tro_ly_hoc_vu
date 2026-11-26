// Khung "Cần chú ý" trên trang Sinh viên: ai đang bị cảnh báo học vụ, nợ học phí, đủ tín chỉ nhưng
// chưa đủ điều kiện tốt nghiệp (QLSV tính theo đúng quy tắc của trường). Bấm tên -> lọc bảng.
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ChevronDown, ChevronUp, LoaderCircle } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { api } from '../../lib/api'
import {
  ATTENTION_LABELS,
  countByType,
  filterByType,
  type AttentionList,
  type AttentionType,
} from '../../lib/attention'
import { Card } from './ui'

const REASON_STYLE = {
  khan: 'bg-err-bg text-err',
  chu_y: 'bg-warn-bg text-warn',
}

export default function AttentionPanel({ onPick }: { onPick: (maSv: string) => void }) {
  const [open, setOpen] = useState(true)
  const [type, setType] = useState<AttentionType | ''>('')
  const query = useQuery({
    queryKey: ['admin', 'students', 'attention'],
    queryFn: () => api<AttentionList>('/api/admin/students/attention'),
  })
  const list = query.data?.sinh_vien ?? []
  const counts = countByType(list)
  const shown = filterByType(list, type)

  return (
    <Card className="mb-4 p-4">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 text-left"
        aria-expanded={open}
      >
        <AlertTriangle size={18} className="text-warn" />
        <span className="flex-1 font-semibold text-navy">
          Cần chú ý{query.data ? ` (${query.data.tong})` : ''}
        </span>
        {query.isPending && <LoaderCircle size={16} className="animate-spin text-slate-400" />}
        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>

      {open && (
        <div className="mt-3">
          {query.isError && (
            <p className="text-sm text-err">
              Không tải được danh sách (hệ thống QLSV không phản hồi).
            </p>
          )}
          {query.data && list.length === 0 && (
            <p className="text-sm text-slate-500">Không có sinh viên đang học nào cần chú ý.</p>
          )}
          {list.length > 0 && (
            <>
              <div className="mb-3 flex flex-wrap gap-2">
                <Chip active={type === ''} onClick={() => setType('')}>
                  Tất cả · {list.length}
                </Chip>
                {(Object.keys(ATTENTION_LABELS) as AttentionType[]).map((t) => (
                  <Chip
                    key={t}
                    active={type === t}
                    onClick={() => setType(t)}
                    disabled={!counts[t]}
                  >
                    {ATTENTION_LABELS[t]} · {counts[t]}
                  </Chip>
                ))}
              </div>
              <ul className="max-h-72 divide-y divide-line overflow-y-auto">
                {shown.map((s) => (
                  <li
                    key={s.ma_sv}
                    className="flex flex-wrap items-start gap-x-4 gap-y-1 py-2 text-sm"
                  >
                    <button
                      type="button"
                      onClick={() => onPick(s.ma_sv)}
                      className="w-52 shrink-0 text-left hover:text-primary"
                      title="Lọc bảng theo sinh viên này"
                    >
                      <span className="block font-medium">{s.ho_ten}</span>
                      <span className="text-xs text-slate-500">
                        {s.ma_sv} · {s.lop} · {s.khoa}
                      </span>
                    </button>
                    <ul className="min-w-0 flex-1 space-y-1">
                      {s.ly_do.map((r) => (
                        <li key={r.loai} className="flex flex-wrap items-baseline gap-2">
                          <span
                            className={`rounded-full px-2 py-0.5 text-xs font-medium ${REASON_STYLE[r.muc_do]}`}
                          >
                            {ATTENTION_LABELS[r.loai]}
                          </span>
                          <span className="text-slate-600">{r.chi_tiet}</span>
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </Card>
  )
}

function Chip({
  active,
  disabled,
  onClick,
  children,
}: {
  active: boolean
  disabled?: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`h-8 rounded-full border px-3 text-xs disabled:opacity-40 ${
        active
          ? 'border-primary bg-primary text-white'
          : 'border-line bg-white hover:border-primary'
      }`}
    >
      {children}
    </button>
  )
}
