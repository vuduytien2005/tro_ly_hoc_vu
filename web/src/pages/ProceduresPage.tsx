import { useQuery } from '@tanstack/react-query'
import { Bot, ChevronRight, ClipboardList, LoaderCircle, User, X } from 'lucide-react'
import { useState } from 'react'
import { ApiError, api } from '../lib/api'
import { formatDate, formatDateTime } from '../lib/format'
import type { RequestDetail, RequestListResponse } from '../lib/types'

const FILTERS: { value: string; label: string }[] = [
  { value: '', label: 'Tất cả' },
  { value: 'moi_tao', label: 'Mới tạo' },
  { value: 'dang_xu_ly', label: 'Đang xử lý' },
  { value: 'da_duyet', label: 'Đã duyệt' },
  { value: 'tu_choi', label: 'Từ chối' },
  { value: 'hoan_tat', label: 'Hoàn tất' },
]

const BADGE: Record<string, string> = {
  moi_tao: 'bg-slate-100 text-slate-700',
  dang_xu_ly: 'bg-warn-bg text-warn',
  da_duyet: 'bg-ok-bg text-ok',
  hoan_tat: 'bg-ok-bg text-ok',
  tu_choi: 'bg-err-bg text-err',
}

function StatusBadge({ code, label }: { code: string; label: string }) {
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${BADGE[code] ?? BADGE.moi_tao}`}
    >
      {label}
    </span>
  )
}

function CreatorTag({ creator }: { creator: string }) {
  const ai = creator === 'Trợ lý AI'
  return (
    <span className="inline-flex items-center gap-1 text-xs text-slate-500">
      {ai ? <Bot size={14} /> : <User size={14} />} {creator}
    </span>
  )
}

function errorText(err: unknown): string {
  return err instanceof ApiError ? err.message : 'Không tải được dữ liệu, vui lòng thử lại.'
}

/** "Thủ tục của em": đọc trực tiếp qua backend (không qua LLM) — xem /api/my/requests. */
export default function ProceduresPage() {
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState<string | null>(null)

  const list = useQuery({
    queryKey: ['my-requests', filter],
    queryFn: () =>
      api<RequestListResponse>(
        `/api/my/requests${filter ? `?trang_thai=${encodeURIComponent(filter)}` : ''}`,
      ),
  })

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-4xl px-3 py-6 sm:px-6">
        <div className="mb-4 flex items-center gap-3">
          <ClipboardList className="text-primary" />
          <h1 className="text-xl font-semibold text-navy">Thủ tục của em</h1>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`h-9 rounded-full border px-4 text-sm ${
                filter === f.value
                  ? 'border-primary bg-primary text-white'
                  : 'border-line bg-white hover:border-primary'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="overflow-hidden rounded-2xl border border-line bg-white">
          {list.isPending && (
            <p className="flex items-center gap-2 p-6 text-sm text-slate-500">
              <LoaderCircle size={16} className="animate-spin" /> Đang tải…
            </p>
          )}
          {list.isError && <p className="p-6 text-sm text-err">{errorText(list.error)}</p>}
          {list.data && list.data.don.length === 0 && (
            <p className="p-6 text-sm text-slate-500">
              Em chưa có yêu cầu nào{filter ? ' ở trạng thái này' : ''}. Có thể nhờ trợ lý tạo
              giấy xác nhận, đơn bảo lưu hoặc đơn phúc khảo ngay trong khung chat.
            </p>
          )}
          {list.data && list.data.don.length > 0 && (
            <ul className="divide-y divide-line">
              {list.data.don.map((d) => (
                <li key={d.ma_don}>
                  <button
                    onClick={() => setSelected(d.ma_don)}
                    className="flex min-h-14 w-full items-center gap-3 px-4 py-3 text-left hover:bg-page"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-navy">{d.loai_don}</p>
                      <p className="flex flex-wrap items-center gap-x-3 text-xs text-slate-500">
                        <span>{d.ma_don}</span>
                        <span>{formatDate(d.ngay_tao)}</span>
                        <CreatorTag creator={d.tao_boi} />
                      </p>
                    </div>
                    <StatusBadge code={d.ma_trang_thai} label={d.trang_thai} />
                    <ChevronRight size={18} className="text-slate-400" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        {list.data?.thong_bao && (
          <p className="mt-3 text-xs text-slate-400">{list.data.thong_bao}</p>
        )}
      </div>

      {selected && <RequestDetailPanel maDon={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

/** Khóa trong noi_dung là tiếng Việt không dấu (snake_case) -> hiển thị dễ đọc. */
const FIELD_LABELS: Record<string, string> = {
  muc_dich: 'Mục đích',
  so_ban: 'Số bản',
  ly_do: 'Lý do',
  hoc_ky_bat_dau: 'Học kỳ bắt đầu',
  so_hoc_ky: 'Số học kỳ',
  ma_hp: 'Mã học phần',
  ma_hoc_phan: 'Mã học phần',
  ma_hoc_ky: 'Học kỳ',
  hoc_ky: 'Học kỳ',
  diem_hien_tai: 'Điểm hiện tại',
}

function fieldLabel(key: string): string {
  return FIELD_LABELS[key] ?? key.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())
}

function RequestDetailPanel({ maDon, onClose }: { maDon: string; onClose: () => void }) {
  const detail = useQuery({
    queryKey: ['my-request', maDon],
    queryFn: () => api<RequestDetail>(`/api/my/requests/${encodeURIComponent(maDon)}`),
  })
  const d = detail.data

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <aside
        role="dialog"
        aria-label={`Chi tiết ${maDon}`}
        onClick={(e) => e.stopPropagation()}
        className="h-full w-full max-w-md overflow-y-auto bg-white p-6"
      >
        <div className="mb-4 flex items-center gap-2">
          <h2 className="flex-1 text-lg font-semibold text-navy">{maDon}</h2>
          <button
            onClick={onClose}
            aria-label="Đóng"
            className="flex h-11 w-11 items-center justify-center rounded-[10px] hover:bg-page"
          >
            <X size={20} />
          </button>
        </div>

        {detail.isPending && <p className="text-sm text-slate-500">Đang tải…</p>}
        {detail.isError && <p className="text-sm text-err">{errorText(detail.error)}</p>}
        {d && (
          <div className="space-y-5 text-sm">
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-medium text-navy">{d.loai_don}</span>
              <StatusBadge code={d.ma_trang_thai} label={d.trang_thai} />
            </div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
              <dt className="text-slate-500">Ngày tạo</dt>
              <dd>{formatDate(d.ngay_tao)}</dd>
              <dt className="text-slate-500">Cập nhật</dt>
              <dd>{formatDateTime(d.cap_nhat_luc)}</dd>
              <dt className="text-slate-500">Người tạo</dt>
              <dd>
                <CreatorTag creator={d.tao_boi} />
              </dd>
            </dl>

            <section>
              <h3 className="mb-2 font-medium text-navy">Nội dung</h3>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-xl bg-page p-3">
                {Object.entries(d.noi_dung).map(([k, v]) => (
                  <div key={k} className="contents">
                    <dt className="text-slate-500">{fieldLabel(k)}</dt>
                    <dd className="break-words">
                      {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>

            {d.ghi_chu_xu_ly && (
              <section>
                <h3 className="mb-2 font-medium text-navy">Ghi chú của phòng ban</h3>
                <p className="rounded-xl bg-page p-3">{d.ghi_chu_xu_ly}</p>
              </section>
            )}
            {d.thong_bao && <p className="text-xs text-slate-400">{d.thong_bao}</p>}
          </div>
        )}
      </aside>
    </div>
  )
}
