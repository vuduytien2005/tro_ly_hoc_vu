import { useQuery } from '@tanstack/react-query'
import { Bell, BookOpen, CalendarClock, MessageSquare, Wallet } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { api } from '../lib/api'
import { badgeText, hasUrgent, type ChatPrefillState } from '../lib/reminders'
import type { Reminder, RemindersResponse } from '../lib/types'

const ICONS = {
  hoc_phi: Wallet,
  lich_thi: CalendarClock,
  sach: BookOpen,
} as const

/**
 * Chuông nhắc việc (học phí, lịch thi, sách sắp đến hạn) — xem /api/my/reminders.
 * Mỗi lần tải là 2–3 lượt gọi tool có ghi nhật ký -> giữ kết quả 5 phút, không tải lại khi đổi tab.
 */
export function RemindersBell({ onNavigate }: { onNavigate: () => void }) {
  const [open, setOpen] = useState(false)
  const boxRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const reminders = useQuery({
    queryKey: ['reminders'],
    queryFn: () => api<RemindersResponse>('/api/my/reminders'),
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    retry: false,
  })
  const items = reminders.data?.nhac_viec
  const badge = badgeText(items)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (
        e instanceof KeyboardEvent
          ? e.key === 'Escape'
          : !boxRef.current?.contains(e.target as Node)
      )
        setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  const ask = (r: Reminder) => {
    setOpen(false)
    onNavigate()
    navigate('/chat', {
      state: { prefill: r.cau_hoi } satisfies ChatPrefillState,
    })
  }

  return (
    <div ref={boxRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={badge ? `Nhắc việc (${badge} việc cần chú ý)` : 'Nhắc việc'}
        aria-expanded={open}
        title="Nhắc việc"
        className="relative flex h-11 w-11 items-center justify-center rounded-[10px] hover:bg-white/10"
      >
        <Bell size={20} />
        {badge && (
          <span
            className={`absolute right-1 top-1 flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-[11px] font-semibold text-white ${
              hasUrgent(items) ? 'bg-red-600' : 'bg-accent'
            }`}
          >
            {badge}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Nhắc việc"
          className="absolute left-0 top-12 z-50 w-80 max-w-[calc(100vw-1.5rem)] rounded-xl border border-line bg-white p-3 text-slate-800 shadow-xl"
        >
          <p className="mb-2 font-semibold text-navy">Việc cần chú ý</p>
          {reminders.isPending && <p className="text-sm text-slate-500">Đang kiểm tra…</p>}
          {reminders.isError && (
            <p className="text-sm text-warn">Chưa kiểm tra được nhắc việc, em thử lại sau nhé.</p>
          )}
          {items?.length === 0 && (
            <p className="text-sm text-slate-500">Hiện không có hạn nào sắp tới. 🎉</p>
          )}
          <ul className="max-h-96 space-y-2 overflow-y-auto">
            {items?.map((r, i) => {
              const Icon = ICONS[r.loai]
              const urgent = r.muc_do === 'khan'
              return (
                <li
                  key={`${r.loai}-${r.han}-${i}`}
                  className={`rounded-lg border p-2.5 ${urgent ? 'border-red-200 bg-red-50' : 'border-line bg-slate-50'}`}
                >
                  <div className="flex items-start gap-2">
                    <Icon
                      size={16}
                      className={`mt-0.5 shrink-0 ${urgent ? 'text-red-600' : 'text-primary'}`}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium">{r.tieu_de}</p>
                      <p className="text-xs text-slate-600">{r.chi_tiet}</p>
                      <button
                        onClick={() => ask(r)}
                        className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                      >
                        <MessageSquare size={12} /> Hỏi trợ lý
                      </button>
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
          {reminders.data && reminders.data.nguon_loi.length > 0 && (
            <p className="mt-2 text-xs text-slate-500">
              Một số nguồn tạm thời không kiểm tra được, danh sách có thể chưa đủ.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
