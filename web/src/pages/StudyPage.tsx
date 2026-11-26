import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  BookOpen,
  CalendarClock,
  CalendarDays,
  CheckCircle2,
  CircleAlert,
  GraduationCap,
  LoaderCircle,
  MessageCircle,
  Wallet,
  XCircle,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { ApiError } from '../lib/api'
import { formatDate } from '../lib/format'
import {
  CERTIFICATE_LABELS,
  OVERVIEW_QUERY,
  STUDENT_STATUS,
  TUITION_STATUS,
  buildAlerts,
  creditPercent,
  formatVnd,
  groupBySemester,
  semesterLabel,
  type Alert,
  type Overview,
  type Schedule,
  type TranscriptRow,
  weekGrid,
} from '../lib/overview'
import type { ChatPrefillState } from '../lib/reminders'

function useAsk(): (question: string) => void {
  const navigate = useNavigate()
  return (question) =>
    navigate('/chat', {
      state: { prefill: question } satisfies ChatPrefillState,
    })
}

function AskButton({ question, label = 'Hỏi trợ lý' }: { question: string; label?: string }) {
  const ask = useAsk()
  return (
    <button
      onClick={() => ask(question)}
      className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full border border-line bg-white px-3 text-xs font-medium text-primary hover:border-primary"
    >
      <MessageCircle size={14} /> {label}
    </button>
  )
}

function Card({
  icon,
  title,
  action,
  children,
}: {
  icon: ReactNode
  title: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="rounded-2xl border border-line bg-white p-4 sm:p-5">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-primary">{icon}</span>
        <h2 className="flex-1 font-semibold text-navy">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  )
}

function Unavailable({ paused }: { paused: boolean }) {
  return (
    <p className="text-sm text-slate-500">
      {paused
        ? 'Chức năng này đang tạm dừng.'
        : 'Chưa tải được phần này, em thử tải lại trang sau ít phút.'}
    </p>
  )
}

const ALERT_STYLE: Record<Alert['muc_do'], { box: string; icon: ReactNode }> = {
  khan: {
    box: 'border-err/30 bg-err-bg text-err',
    icon: <AlertTriangle size={20} />,
  },
  chu_y: {
    box: 'border-warn/30 bg-warn-bg text-warn',
    icon: <CircleAlert size={20} />,
  },
  tot: {
    box: 'border-ok/30 bg-ok-bg text-ok',
    icon: <CheckCircle2 size={20} />,
  },
}

function AlertBox({ alert }: { alert: Alert }) {
  const style = ALERT_STYLE[alert.muc_do]
  return (
    <div className={`flex flex-wrap items-start gap-3 rounded-2xl border p-4 ${style.box}`}>
      <span className="mt-0.5">{style.icon}</span>
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{alert.tieu_de}</p>
        <p className="text-sm opacity-90">{alert.chi_tiet}</p>
      </div>
      <AskButton question={alert.cau_hoi} />
    </div>
  )
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-line bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-navy">{value}</p>
      {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
    </div>
  )
}

function gradeClass(diemChu: string | null): string {
  if (diemChu === 'F') return 'bg-err-bg text-err'
  if (diemChu?.startsWith('A')) return 'bg-ok-bg text-ok'
  return 'bg-slate-100 text-slate-700'
}

/** "Học tập của em": đọc trực tiếp qua backend (không qua LLM) — xem /api/my/overview. */
export default function StudyPage() {
  const query = useQuery(OVERVIEW_QUERY)

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-4 px-3 py-6 sm:px-6">
        <div className="flex items-center gap-3">
          <GraduationCap className="text-primary" />
          <h1 className="text-xl font-semibold text-navy">Học tập của em</h1>
        </div>
        {query.isPending && (
          <p className="flex items-center gap-2 text-sm text-slate-500">
            <LoaderCircle size={16} className="animate-spin" /> Đang tải…
          </p>
        )}
        {query.isError && (
          <p className="text-sm text-err">
            {query.error instanceof ApiError
              ? query.error.message
              : 'Không tải được dữ liệu, vui lòng thử lại.'}
          </p>
        )}
        {query.data && <OverviewBody data={query.data} />}
      </div>
    </div>
  )
}

function OverviewBody({ data }: { data: Overview }) {
  const paused = (tool: string) => data.tam_dung.includes(tool)
  const alerts = buildAlerts(data)
  const p = data.ho_so
  const t = data.bang_diem
  const g = data.tot_nghiep
  const fee = data.hoc_phi

  return (
    <>
      {p && (
        <div className="rounded-2xl bg-navy p-5 text-white">
          <p className="text-lg font-semibold">{p.ho_ten}</p>
          <p className="text-sm text-slate-300">
            Lớp {p.lop} · {p.nganh} · Khóa {p.khoa}
          </p>
          <span className="mt-2 inline-flex rounded-full bg-white/15 px-2.5 py-0.5 text-xs">
            {STUDENT_STATUS[p.trang_thai] ?? p.trang_thai}
          </span>
        </div>
      )}

      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((a) => (
            <AlertBox key={a.tieu_de} alert={a} />
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Stat
          label="GPA tích lũy"
          value={t ? t.gpa_tich_luy.toFixed(2) : '—'}
          sub={g ? `Tối thiểu để tốt nghiệp: ${g.gpa_toi_thieu.toFixed(2)}` : 'Thang điểm 4'}
        />
        <Stat
          label="Tín chỉ tích lũy"
          value={
            g
              ? `${g.tin_chi_tich_luy}/${g.tong_tin_chi_yeu_cau}`
              : t
                ? `${t.tin_chi_tich_luy}`
                : '—'
          }
          sub={
            g && (
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{
                    width: `${creditPercent(g.tin_chi_tich_luy, g.tong_tin_chi_yeu_cau)}%`,
                  }}
                />
              </div>
            )
          }
        />
        <Stat
          label="Học phí kỳ này"
          value={fee ? (fee.con_no > 0 ? formatVnd(fee.con_no) : 'Đã nộp đủ') : '—'}
          sub={
            fee &&
            (fee.con_no > 0
              ? `Còn nợ · ${TUITION_STATUS[fee.trang_thai] ?? fee.trang_thai}`
              : `${formatVnd(fee.phai_nop)} · ${semesterLabel(fee.hoc_ky)}`)
          }
        />
      </div>

      <div className="space-y-4">
        <Card
          icon={<CalendarDays size={18} />}
          title={`Thời khóa biểu${data.thoi_khoa_bieu ? ` · ${semesterLabel(data.thoi_khoa_bieu.hoc_ky)}` : ''}`}
        >
          {!data.thoi_khoa_bieu ? (
            <Unavailable paused={paused('get_current_schedule')} />
          ) : data.thoi_khoa_bieu.lop.length === 0 ? (
            <p className="text-sm text-slate-500">Em chưa đăng ký lớp nào trong học kỳ này.</p>
          ) : (
            <>
              <WeekTimetable classes={data.thoi_khoa_bieu.lop} />
              <ul className="divide-y divide-line sm:hidden">
                {data.thoi_khoa_bieu.lop.map((c) => (
                  <li key={c.ma_lop} className="py-2">
                    <p className="font-medium text-navy">{c.ten_hp}</p>
                    <p className="text-xs text-slate-500">
                      {c.thu}, tiết {c.tiet} · Phòng {c.phong} · {c.giang_vien} · {c.ma_lop}
                    </p>
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>

        <Card icon={<CalendarClock size={18} />} title="Lịch thi">
          {!data.lich_thi ? (
            <Unavailable paused={paused('get_exam_schedule')} />
          ) : data.lich_thi.lich_thi.length === 0 ? (
            <p className="text-sm text-slate-500">Chưa có lịch thi trong học kỳ này.</p>
          ) : (
            <ul className="divide-y divide-line">
              {data.lich_thi.lich_thi.map((e) => (
                <li key={e.ma_lop} className="flex items-center gap-3 py-2">
                  <div className="w-14 shrink-0 rounded-lg bg-page py-1 text-center">
                    <p className="text-sm font-semibold text-navy">
                      {formatDate(e.ngay_thi).slice(0, 5)}
                    </p>
                    <p className="text-[11px] text-slate-500">{e.gio}</p>
                  </div>
                  <div className="min-w-0">
                    <p className="font-medium text-navy">{e.ten_hp}</p>
                    <p className="text-xs text-slate-500">
                      Phòng {e.phong} · {e.hinh_thuc}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card
        icon={<GraduationCap size={18} />}
        title="Tiến độ tốt nghiệp"
        action={<AskButton question="Em còn thiếu gì để tốt nghiệp?" />}
      >
        {!g ? (
          <Unavailable paused={paused('get_graduation_progress')} />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div>
              <p className="mb-2 text-sm font-medium text-slate-600">Chứng chỉ</p>
              <ul className="space-y-1.5">
                {Object.entries(g.chung_chi).map(([k, ok]) => (
                  <li key={k} className="flex items-center gap-2 text-sm">
                    {ok ? (
                      <CheckCircle2 size={16} className="text-ok" />
                    ) : (
                      <XCircle size={16} className="text-err" />
                    )}
                    {CERTIFICATE_LABELS[k] ?? k}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="mb-2 text-sm font-medium text-slate-600">
                Học phần còn thiếu ({g.hoc_phan_con_thieu.length})
              </p>
              {g.hoc_phan_con_thieu.length === 0 ? (
                <p className="text-sm text-ok">Đã hoàn thành đủ học phần.</p>
              ) : (
                <ul className="max-h-48 space-y-1 overflow-y-auto pr-1 text-sm">
                  {g.hoc_phan_con_thieu.map((m) => (
                    <li key={m.ma_hp} className="flex gap-2">
                      <span className="w-14 shrink-0 text-slate-500">{m.ma_hp}</span>
                      <span className="flex-1">{m.ten_hp}</span>
                      <span className="text-xs text-slate-500">
                        {m.tin_chi} TC{m.bat_buoc ? '' : ' · tự chọn'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </Card>

      <Card
        icon={<BookOpen size={18} />}
        title="Bảng điểm"
        action={<AskButton question="Điểm của em thế nào, môn nào cần cải thiện?" />}
      >
        {!t ? (
          <Unavailable paused={paused('get_transcript')} />
        ) : t.ket_qua.length === 0 ? (
          <p className="text-sm text-slate-500">Em chưa có kết quả học tập nào.</p>
        ) : (
          <Transcript data={t.ket_qua} />
        )}
      </Card>

      {fee && fee.con_no > 0 && (
        <Card
          icon={<Wallet size={18} />}
          title={`Học phí · ${semesterLabel(fee.hoc_ky)}`}
          action={<AskButton question="Em nộp học phí bằng cách nào?" />}
        >
          <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-slate-500">Phải nộp</dt>
              <dd className="font-medium">{formatVnd(fee.phai_nop)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Đã nộp</dt>
              <dd className="font-medium">{formatVnd(fee.da_nop)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Còn nợ</dt>
              <dd className="font-medium text-err">{formatVnd(fee.con_no)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Hạn nộp</dt>
              <dd className="font-medium">{fee.han_nop ? formatDate(fee.han_nop) : '—'}</dd>
            </div>
          </dl>
        </Card>
      )}

      {data.nguon_loi.length > 0 && (
        <p className="text-xs text-slate-400">
          Một số phần chưa tải được do hệ thống quản lý sinh viên không phản hồi.
        </p>
      )}
    </>
  )
}

function Transcript({ data }: { data: TranscriptRow[] }) {
  const groups = groupBySemester(data)
  const [open, setOpen] = useState<string | null>(groups[0]?.hoc_ky ?? null)
  return (
    <div className="divide-y divide-line">
      {groups.map((grp) => (
        <div key={grp.hoc_ky}>
          <button
            onClick={() => setOpen(open === grp.hoc_ky ? null : grp.hoc_ky)}
            className="flex w-full items-center py-2 text-left text-sm"
          >
            <span className="flex-1 font-medium text-navy">{semesterLabel(grp.hoc_ky)}</span>
            <span className="text-xs text-slate-500">
              {grp.rows.length} học phần · {grp.tin_chi} TC {open === grp.hoc_ky ? '▲' : '▼'}
            </span>
          </button>
          {open === grp.hoc_ky && (
            <table className="mb-2 w-full text-sm">
              <tbody>
                {grp.rows.map((r) => (
                  <tr key={`${r.ma_hp}-${r.lan_hoc}`} className="border-t border-line/60">
                    <td className="w-16 py-1.5 text-slate-500">{r.ma_hp}</td>
                    <td className="py-1.5">
                      {r.ten_hp}
                      {r.lan_hoc > 1 && (
                        <span className="ml-1 text-xs text-slate-400">(học lại)</span>
                      )}
                    </td>
                    <td className="w-10 text-center text-slate-500">{r.tin_chi}</td>
                    <td className="w-12 text-right">{r.diem_tong_ket?.toFixed(1) ?? '—'}</td>
                    <td className="w-14 text-right">
                      <span
                        className={`inline-flex min-w-8 justify-center rounded-full px-2 py-0.5 text-xs font-semibold ${gradeClass(r.diem_chu)}`}
                      >
                        {r.diem_chu ?? '—'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}
    </div>
  )
}

const CLASS_COLORS = [
  'bg-blue-50 border-blue-300 text-blue-900',
  'bg-emerald-50 border-emerald-300 text-emerald-900',
  'bg-amber-50 border-amber-300 text-amber-900',
  'bg-violet-50 border-violet-300 text-violet-900',
  'bg-rose-50 border-rose-300 text-rose-900',
  'bg-cyan-50 border-cyan-300 text-cyan-900',
]

/** Lưới tuần (màn hình từ sm trở lên); điện thoại dùng danh sách bên dưới. */
function WeekTimetable({ classes }: { classes: Schedule['lop'] }) {
  const grid = weekGrid(classes)
  const colorOf = new Map(classes.map((c, i) => [c.ma_lop, CLASS_COLORS[i % CLASS_COLORS.length]]))
  return (
    <div
      className="hidden gap-px overflow-hidden rounded-xl border border-line bg-line text-xs sm:grid"
      style={{
        gridTemplateColumns: `2.75rem repeat(${grid.days.length}, minmax(0, 1fr))`,
        gridTemplateRows: `auto repeat(${grid.periods}, 1.75rem)`,
      }}
    >
      <div className="bg-page" />
      {grid.days.map((d) => (
        <div key={d} className="bg-page py-1.5 text-center font-medium text-slate-600">
          {d}
        </div>
      ))}
      {Array.from({ length: grid.periods }, (_, i) => (
        <div
          key={`p${i}`}
          className="flex items-center justify-center bg-page text-slate-400"
          style={{ gridColumn: 1, gridRow: i + 2 }}
        >
          {i + 1}
        </div>
      ))}
      {Array.from({ length: grid.periods * grid.days.length }, (_, i) => (
        <div
          key={`e${i}`}
          className="bg-white"
          style={{
            gridColumn: (i % grid.days.length) + 2,
            gridRow: Math.floor(i / grid.days.length) + 2,
          }}
        />
      ))}
      {grid.cells.map((c) => (
        <div
          key={c.ma_lop}
          className={`z-10 m-0.5 overflow-hidden rounded-md border-l-4 px-1.5 py-1 ${colorOf.get(c.ma_lop)}`}
          style={{ gridColumn: c.col + 2, gridRow: `${c.from + 1} / ${c.to + 2}` }}
          title={`${c.ten_hp} · tiết ${c.from}-${c.to} · phòng ${c.phong}`}
        >
          <p className="font-semibold leading-tight">{c.ten_hp}</p>
          <p className="opacity-80">
            {c.ma_lop} · {c.phong}
          </p>
        </div>
      ))}
    </div>
  )
}
