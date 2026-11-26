// Duyệt đơn — quản trị viên đóng vai cán bộ phòng CTSV / đào tạo (thiết kế 2026-11-23-duyet-don).
// Ghi qua qlsv_api (nguồn sự thật, kiểm tra máy trạng thái); sinh viên thấy kết quả và ghi chú ở
// "Thủ tục của em" hoặc hỏi trợ lý.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookPlus, Bot, Clock, Info, LoaderCircle, User } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import {
  Badge,
  Card,
  Drawer,
  Field,
  PageHeader,
  inputClass,
  primaryButton,
  secondaryButton,
} from '../../components/admin/ui'
import {
  OVERDUE_DAYS,
  insertTemplate,
  nextStatuses,
  replyTemplates,
  reviewNoteProblem,
  toQuery,
  waitingAge,
} from '../../lib/admin'
import {
  DEPARTMENTS,
  REQUEST_KIND,
  REQUEST_STATUS,
  type StaffRequest,
  type StaffRequestPage,
} from '../../lib/adminTypes'
import { ApiError, api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { requestToDraft } from '../../lib/knowledge'

const PAGE_SIZE = 20
const KEY = ['admin', 'requests']

const CONTENT_LABELS: Record<string, string> = {
  muc_dich: 'Mục đích',
  so_ban: 'Số bản',
  noi_nhan: 'Nơi nhận',
  ly_do: 'Lý do',
  tu_hoc_ky: 'Từ học kỳ',
  so_hoc_ky: 'Số học kỳ',
  ma_hp: 'Mã học phần',
  ten_hp: 'Tên học phần',
  ma_hoc_ky: 'Học kỳ',
  diem_thi: 'Điểm thi',
  lien_he: 'Liên hệ khi bảo lưu',
  so_dien_thoai: 'Số điện thoại',
  email_ca_nhan: 'Email cá nhân',
  cau_hoi: 'Câu hỏi',
  phong_ban: 'Phòng ban',
}

const ACTION_LABELS: Record<string, string> = {
  dang_xu_ly: 'Nhận xử lý',
  da_duyet: 'Duyệt',
  tu_choi: 'Từ chối',
  hoan_tat: 'Hoàn tất (đã trả kết quả)',
}

const errorText = (err: unknown, fallback: string) =>
  err instanceof ApiError ? err.message : fallback

function StatusBadge({ code }: { code: string }) {
  const s = REQUEST_STATUS[code]
  return <Badge className={s?.className ?? 'bg-slate-100'}>{s?.label ?? code}</Badge>
}

export default function RequestsPage() {
  const [filters, setFilters] = useState({
    trang_thai: 'moi_tao',
    loai_don: '',
  })
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState<StaffRequest | null>(null)
  const set = (key: keyof typeof filters) => (value: string) => {
    setFilters((f) => ({ ...f, [key]: value }))
    setPage(1)
  }

  const requests = useQuery({
    queryKey: [...KEY, filters, page],
    queryFn: () =>
      api<StaffRequestPage>(
        `/api/admin/requests${toQuery({ ...filters, page, page_size: PAGE_SIZE })}`,
      ),
    placeholderData: (prev) => prev,
  })
  const totalPages = requests.data ? Math.max(1, Math.ceil(requests.data.tong / PAGE_SIZE)) : 1

  return (
    <>
      <PageHeader title="Đơn từ" />

      <p className="mb-4 flex items-start gap-2 rounded-xl bg-primary/5 px-3 py-2 text-sm text-slate-600">
        <Info size={16} className="mt-0.5 shrink-0 text-primary" />
        Mô phỏng phần việc của phòng Công tác sinh viên: xử lý đơn sinh viên (hoặc trợ lý AI) đã
        nộp. Kết quả và ghi chú hiện ngay ở trang "Thủ tục của em" của sinh viên.
      </p>

      <Card className="mb-4 flex flex-wrap items-end gap-3 p-4">
        <Field label="Trạng thái">
          <select
            value={filters.trang_thai}
            onChange={(e) => set('trang_thai')(e.target.value)}
            className={inputClass}
          >
            <option value="">Tất cả</option>
            {Object.entries(REQUEST_STATUS).map(([v, s]) => (
              <option key={v} value={v}>
                {s.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Loại đơn">
          <select
            value={filters.loai_don}
            onChange={(e) => set('loai_don')(e.target.value)}
            className={inputClass}
          >
            <option value="">Tất cả</option>
            {Object.entries(REQUEST_KIND).map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </Field>
      </Card>

      {requests.isError && (
        <p role="alert" className="mb-3 rounded-[10px] bg-err-bg px-3 py-2 text-sm text-err">
          {errorText(requests.error, 'Không tải được danh sách đơn.')}
        </p>
      )}

      <Card className="overflow-x-auto">
        <table className="w-full min-w-[800px] text-sm">
          <thead className="border-b border-line bg-page text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Mã đơn</th>
              <th className="px-4 py-3 font-medium">Sinh viên</th>
              <th className="px-4 py-3 font-medium">Loại</th>
              <th className="px-4 py-3 font-medium">Nộp lúc</th>
              <th className="px-4 py-3 font-medium">Trạng thái</th>
              <th className="px-4 py-3 text-right font-medium" />
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {requests.data?.don.map((d) => (
              <tr key={d.ma_don}>
                <td className="px-4 py-3 font-mono text-navy">{d.ma_don}</td>
                <td className="px-4 py-3">
                  <p className="font-medium">{d.ho_ten}</p>
                  <p className="font-mono text-xs text-slate-500">{d.ma_sv}</p>
                </td>
                <td className="px-4 py-3">
                  <p>{REQUEST_KIND[d.loai_don] ?? d.loai_don}</p>
                  <p className="inline-flex items-center gap-1 text-xs text-slate-500">
                    {d.tao_boi === 'tro_ly_ai' ? <Bot size={13} /> : <User size={13} />}
                    {d.tao_boi === 'tro_ly_ai' ? 'Trợ lý AI' : 'Sinh viên'}
                  </p>
                </td>
                <td className="px-4 py-3">
                  <p>{formatDateTime(d.created_at)}</p>
                  <WaitingTag createdAt={d.created_at} status={d.trang_thai} />
                </td>
                <td className="px-4 py-3">
                  <StatusBadge code={d.trang_thai} />
                </td>
                <td className="px-4 py-3 text-right">
                  <button className={secondaryButton} onClick={() => setOpen(d)}>
                    {nextStatuses(d.trang_thai, d.loai_don).length ? 'Xử lý' : 'Xem'}
                  </button>
                </td>
              </tr>
            ))}
            {requests.data?.don.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-slate-500">
                  Không có đơn nào khớp bộ lọc.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>

      <div className="mt-4 flex items-center justify-between text-sm">
        <span className="text-slate-500">
          {requests.data ? `${requests.data.tong} đơn · trang ${page}/${totalPages}` : 'Đang tải…'}
        </span>
        <div className="flex gap-2">
          <button
            className={secondaryButton}
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Trước
          </button>
          <button
            className={secondaryButton}
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Sau
          </button>
        </div>
      </div>

      {open && <ReviewDrawer request={open} onClose={() => setOpen(null)} />}
    </>
  )
}

function ReviewDrawer({ request, onClose }: { request: StaffRequest; onClose: () => void }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [current, setCurrent] = useState(request)
  const [note, setNote] = useState('')
  const [problem, setProblem] = useState<string | null>(null)
  const isQuestion = current.loai_don === 'hoi_dap'
  const steps = nextStatuses(current.trang_thai, current.loai_don)
  const templates = replyTemplates(current.loai_don, steps)

  const review = useMutation({
    mutationFn: (trang_thai: string) =>
      api<StaffRequest>(`/api/admin/requests/${encodeURIComponent(current.ma_don)}`, {
        method: 'PATCH',
        json: { trang_thai, ghi_chu_xu_ly: note.trim() || null },
      }),
    onSuccess: (updated) => {
      setCurrent((c) => ({ ...c, ...updated }))
      setNote('')
      queryClient.invalidateQueries({ queryKey: KEY })
    },
  })

  const act = (target: string) => {
    const p = reviewNoteProblem(target, note, current.loai_don)
    setProblem(p)
    if (!p) review.mutate(target)
  }

  return (
    <Drawer title={`Đơn ${current.ma_don}`} onClose={onClose}>
      <dl className="mb-4 grid grid-cols-[9rem_1fr] gap-x-3 gap-y-2 text-sm">
        <dt className="text-slate-500">Sinh viên</dt>
        <dd>
          {current.ho_ten}{' '}
          <span className="font-mono text-xs text-slate-500">({current.ma_sv})</span>
        </dd>
        <dt className="text-slate-500">Loại đơn</dt>
        <dd>{REQUEST_KIND[current.loai_don] ?? current.loai_don}</dd>
        <dt className="text-slate-500">Trạng thái</dt>
        <dd>
          <StatusBadge code={current.trang_thai} />
        </dd>
        <dt className="text-slate-500">Nộp lúc</dt>
        <dd>{formatDateTime(current.created_at)}</dd>
        {Object.entries(current.noi_dung).map(([k, v]) =>
          v == null || v === '' ? null : (
            <Row
              key={k}
              label={CONTENT_LABELS[k] ?? k}
              value={k === 'phong_ban' ? (DEPARTMENTS[String(v)] ?? String(v)) : contentText(v)}
            />
          ),
        )}
        {current.ghi_chu_xu_ly && (
          <Row
            label={isQuestion ? 'Trả lời của cán bộ' : 'Ghi chú xử lý'}
            value={current.ghi_chu_xu_ly}
          />
        )}
      </dl>

      {steps.length > 0 ? (
        <div className="space-y-3 border-t border-line pt-4">
          {templates.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="text-slate-500">Câu mẫu:</span>
              {templates.map((t) => (
                <button
                  key={t.nhan}
                  type="button"
                  title={t.noi_dung}
                  onClick={() => setNote((n) => insertTemplate(n, t.noi_dung))}
                  className="rounded-full border border-line px-2.5 py-1 text-slate-600 hover:border-primary hover:text-primary"
                >
                  {t.nhan}
                </button>
              ))}
            </div>
          )}
          <Field
            label={
              isQuestion
                ? 'Nội dung trả lời (bắt buộc khi trả lời hoặc từ chối)'
                : 'Ghi chú gửi sinh viên (bắt buộc khi từ chối)'
            }
          >
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              maxLength={2000}
              className={`${inputClass} h-auto w-full py-2`}
              placeholder={
                isQuestion
                  ? 'Vd: Học bổng KKHT xét theo điểm học kỳ liền trước, tối thiểu 15 tín chỉ.'
                  : 'Vd: Nhận giấy tại phòng CTSV từ thứ Hai.'
              }
            />
          </Field>
          {(problem || review.isError) && (
            <p role="alert" className="rounded-[10px] bg-err-bg px-3 py-2 text-sm text-err">
              {problem ?? errorText(review.error, 'Không cập nhật được đơn, thử lại sau.')}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {steps.map((s) => (
              <button
                key={s}
                disabled={review.isPending}
                onClick={() => act(s)}
                className={
                  s === 'tu_choi'
                    ? `${secondaryButton} border-err text-err`
                    : s === 'dang_xu_ly'
                      ? secondaryButton
                      : primaryButton
                }
              >
                {review.isPending && review.variables === s && (
                  <LoaderCircle size={15} className="animate-spin" />
                )}
                {isQuestion && s === 'hoan_tat' ? 'Trả lời' : (ACTION_LABELS[s] ?? s)}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <p className="border-t border-line pt-4 text-sm text-slate-500">
          Đơn đã kết thúc, không còn bước xử lý nào.
        </p>
      )}
      {isQuestion && current.trang_thai === 'hoan_tat' && current.ghi_chu_xu_ly && (
        <div className="mt-4 rounded-xl bg-primary/5 p-3 text-sm">
          <p className="mb-2 text-slate-600">
            Câu hỏi này có thể giúp sinh viên khác? Đưa vào kho để trợ lý trả lời được lần sau (sẽ
            mở form để bỏ thông tin cá nhân trước khi lưu).
          </p>
          <button
            className={secondaryButton}
            onClick={() =>
              navigate('/admin/tri-thuc', { state: { draft: requestToDraft(current) } })
            }
          >
            <BookPlus size={15} /> Đưa vào kho hỏi đáp
          </button>
        </div>
      )}
    </Drawer>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="text-slate-500">{label}</dt>
      <dd className="whitespace-pre-wrap">{value}</dd>
    </>
  )
}

/** Giá trị trong noi_dung có thể lồng (vd lien_he: {so_dien_thoai, email_ca_nhan}). */
function contentText(v: unknown): string {
  if (v != null && typeof v === 'object') {
    return Object.entries(v as Record<string, unknown>)
      .filter(([, x]) => x != null && x !== '')
      .map(([k, x]) => `${CONTENT_LABELS[k] ?? k}: ${String(x)}`)
      .join(' · ')
  }
  return String(v)
}

/** "Chờ N ngày" dưới ngày gửi; quá hạn thì thêm biểu tượng đồng hồ + chữ đậm (không chỉ đổi màu). */
function WaitingTag({ createdAt, status }: { createdAt: string; status: string }) {
  const age = waitingAge(createdAt, status)
  if (!age) return null
  return (
    <p
      className={`inline-flex items-center gap-1 text-xs ${age.overdue ? 'font-medium text-warn' : 'text-slate-500'}`}
      title={age.overdue ? `Đã chờ quá ${OVERDUE_DAYS} ngày` : undefined}
    >
      {age.overdue && <Clock size={12} aria-hidden />}
      {age.label}
    </p>
  )
}
