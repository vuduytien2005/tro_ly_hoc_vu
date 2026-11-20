import { CircleCheck, Clock, LoaderCircle, ShieldAlert, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { formatRemaining } from '../../lib/format'
import type { PendingAction } from '../../lib/types'

export type CardState = 'cho' | 'dang_xu_ly' | 'da_xac_nhan' | 'da_huy' | 'het_han' | 'loi'

function useRemaining(expiresAt: string): number {
  const deadline = new Date(expiresAt).getTime()
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  return deadline - now
}

/** Thẻ "Đề xuất thực hiện" (quy tắc 2): chỉ khi sinh viên bấm Xác nhận thì backend mới thực thi. */
export function PendingActionCard({
  action,
  state,
  error,
  onConfirm,
  onCancel,
}: {
  action: PendingAction
  state: CardState
  error?: string | null
  onConfirm: () => void
  onCancel: () => void
}) {
  const remaining = useRemaining(action.het_han_luc)
  const expired = state === 'cho' && remaining <= 0
  const shown: CardState = expired ? 'het_han' : state
  const open = shown === 'cho'

  return (
    <div className="my-3 rounded-2xl border border-primary/30 bg-primary/5 p-4">
      <div className="mb-2 flex items-center gap-2">
        <ShieldAlert size={18} className="text-primary" />
        <span className="flex-1 font-semibold text-navy">Đề xuất thực hiện</span>
        {open && (
          <span
            className={`inline-flex items-center gap-1 text-xs ${remaining < 60_000 ? 'text-warn' : 'text-slate-500'}`}
          >
            <Clock size={14} /> Hết hạn sau {formatRemaining(remaining)}
          </span>
        )}
      </div>
      <p className="mb-3 whitespace-pre-line text-sm leading-relaxed text-slate-700">{action.mo_ta}</p>

      {error && <p className="mb-3 rounded-lg bg-err-bg px-3 py-2 text-sm text-err">{error}</p>}

      {open && (
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="h-11 rounded-[10px] border border-line bg-white px-5 text-sm font-medium hover:bg-page"
          >
            Hủy
          </button>
          <button
            onClick={onConfirm}
            className="h-11 rounded-[10px] bg-primary px-5 text-sm font-medium text-white hover:bg-primary-dark"
          >
            Xác nhận
          </button>
        </div>
      )}
      {shown === 'dang_xu_ly' && (
        <p className="flex items-center gap-2 text-sm text-slate-600">
          <LoaderCircle size={16} className="animate-spin" /> Đang thực hiện…
        </p>
      )}
      {shown === 'da_xac_nhan' && (
        <p className="flex items-center gap-2 text-sm font-medium text-ok">
          <CircleCheck size={16} /> Đã xác nhận
        </p>
      )}
      {shown === 'da_huy' && (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <XCircle size={16} /> Đã hủy
        </p>
      )}
      {shown === 'het_han' && (
        <p className="flex items-center gap-2 text-sm text-warn">
          <Clock size={16} /> Đã hết hạn — em hãy yêu cầu lại trợ lý nếu vẫn muốn thực hiện.
        </p>
      )}
    </div>
  )
}
