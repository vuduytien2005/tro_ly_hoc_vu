import { useQuery } from '@tanstack/react-query'
import {
  ChevronRight,
  CircleAlert,
  CircleCheck,
  CircleMinus,
  Cpu,
  FileCheck,
  FileCheck2,
  GraduationCap,
  Lightbulb,
  MessageSquare,
  ThumbsUp,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { Card, PageHeader } from '../../components/admin/ui'
import { formatPercent } from '../../lib/admin'
import {
  lastDaysRange,
  pendingGapCount,
  serverRows,
  type ServerState,
} from '../../lib/adminOverview'
import type { Stats } from '../../lib/adminTypes'
import { api } from '../../lib/api'
import type { AttentionList } from '../../lib/attention'
import { fetchHealth } from '../../lib/health'
import type { GapList } from '../../lib/knowledge'
import { modelUsage } from '../../lib/safety'

const DAYS = 7

/** Trang đầu của quản trị viên: việc cần xử lý + tình trạng hệ thống + số liệu 7 ngày. */
export default function OverviewPage() {
  const range = lastDaysRange(DAYS)
  // Cùng khóa với huy hiệu menu / khung "Cần chú ý" / trang Tri thức -> dùng chung dữ liệu đã tải
  const requests = useQuery({
    queryKey: ['admin', 'requests', 'moi-tao'],
    queryFn: () => api<{ tong: number }>('/api/admin/requests?trang_thai=moi_tao&page_size=1'),
    refetchInterval: 30_000,
    retry: false,
  })
  const attention = useQuery({
    queryKey: ['admin', 'students', 'attention'],
    queryFn: () => api<AttentionList>('/api/admin/students/attention'),
    retry: false,
  })
  const gaps = useQuery({
    queryKey: ['admin', 'knowledge', 'gaps', DAYS],
    queryFn: () => api<GapList>(`/api/admin/knowledge/gaps?ngay=${DAYS}`),
    retry: false,
  })
  const stats = useQuery({
    queryKey: ['admin', 'stats', range],
    queryFn: () => api<Stats>(`/api/admin/stats?tu=${range.tu}&den=${range.den}`),
    retry: false,
  })
  const health = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
    retry: false,
  })

  const s = stats.data
  const usage = s
    ? modelUsage(s.an_toan.cau_tra_loi_theo_mo_hinh ?? {}, s.an_toan.mo_hinh_du_phong)
    : null

  return (
    <div>
      <PageHeader title="Tổng quan" />

      <h2 className="mb-2 text-sm font-medium text-slate-500">Việc cần xử lý</h2>
      <div className="mb-6 grid gap-3 md:grid-cols-3">
        <TaskTile
          to="/admin/don-tu"
          icon={<FileCheck size={20} />}
          label="Đơn mới chưa xử lý"
          value={requests.data?.tong}
          failed={requests.isError}
          hint="Đơn sinh viên vừa gửi, chưa có cán bộ nhận"
        />
        <TaskTile
          to="/admin/sinh-vien"
          icon={<GraduationCap size={20} />}
          label="Sinh viên cần chú ý"
          value={attention.data?.tong}
          failed={attention.isError}
          hint="Cảnh báo học vụ, nợ học phí, thiếu điều kiện tốt nghiệp"
        />
        <TaskTile
          to="/admin/tri-thuc"
          icon={<Lightbulb size={20} />}
          label={`Lỗ hổng tri thức (${DAYS} ngày)`}
          value={gaps.data ? pendingGapCount(gaps.data.muc) : undefined}
          failed={gaps.isError}
          hint="Câu trả lời thiếu căn cứ, bị chê… chưa đưa vào kho hỏi đáp"
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[2fr_3fr]">
        <Card className="p-4">
          <h2 className="mb-3 font-semibold text-navy">Tình trạng hệ thống</h2>
          {health.isPending && <p className="text-sm text-slate-500">Đang kiểm tra…</p>}
          {health.data === null && (
            <ul>
              <StatusLine state="loi" label="Máy chủ trợ lý" detail="Không gọi được /health" />
            </ul>
          )}
          {health.data && (
            <ul className="space-y-2">
              <StatusLine
                state={
                  health.data.llm_da_cau_hinh && health.data.llm_co_khoa !== false ? 'ok' : 'loi'
                }
                label="Mô hình ngôn ngữ"
                detail={
                  health.data.llm_da_cau_hinh
                    ? health.data.llm_co_khoa === false
                      ? 'Thiếu khóa API'
                      : 'Đã cấu hình'
                    : 'Chưa cấu hình LLM_MODEL'
                }
              />
              {serverRows(health.data.mcp_server).map((r) => (
                <StatusLine
                  key={r.name}
                  state={r.state}
                  label={r.label}
                  detail={`${r.name} · ${r.detail}`}
                />
              ))}
            </ul>
          )}
          <Link
            to="/admin/mcp"
            className="mt-3 inline-flex items-center gap-1 text-sm text-primary hover:underline"
          >
            Quản lý MCP &amp; quyền <ChevronRight size={14} />
          </Link>
        </Card>

        <Card className="p-4">
          <div className="mb-3 flex items-center gap-2">
            <h2 className="flex-1 font-semibold text-navy">{DAYS} ngày gần nhất</h2>
            <Link
              to="/admin/thong-ke"
              className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
            >
              Thống kê chi tiết <ChevronRight size={14} />
            </Link>
          </div>
          {stats.isPending && <p className="text-sm text-slate-500">Đang tải…</p>}
          {stats.isError && <p className="text-sm text-err">Chưa tải được số liệu thống kê.</p>}
          {s && usage && (
            <div className="grid gap-3 sm:grid-cols-2">
              <Figure
                icon={<MessageSquare size={18} />}
                label="Câu hỏi"
                value={String(s.so_cau_hoi)}
                hint={`${s.so_hoi_thoai} cuộc trò chuyện`}
              />
              <Figure
                icon={<ThumbsUp size={18} />}
                label="Đánh giá hữu ích"
                value={formatPercent(s.ti_le_huu_ich)}
                hint={`${s.so_huu_ich}/${s.so_danh_gia} lượt đánh giá`}
              />
              <Figure
                icon={<FileCheck2 size={18} />}
                label="Ý có căn cứ (kiểm chứng)"
                value={formatPercent(s.an_toan.ti_le_co_can_cu)}
                hint={`${s.an_toan.so_co_can_cu}/${s.an_toan.so_menh_de} ý được chấm`}
              />
              <Figure
                icon={<Cpu size={18} />}
                label="Dùng mô hình dự phòng"
                value={formatPercent(usage.fallbackRate)}
                hint={
                  usage.total
                    ? `${usage.total} câu trả lời có ghi mô hình`
                    : 'Chưa có câu trả lời ghi mô hình'
                }
              />
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

function TaskTile({
  to,
  icon,
  label,
  value,
  failed,
  hint,
}: {
  to: string
  icon: ReactNode
  label: string
  value: number | undefined
  failed: boolean
  hint: string
}) {
  const shown = failed ? '—' : value === undefined ? '…' : String(value)
  return (
    <Link
      to={to}
      className="group flex items-start gap-3 rounded-2xl border border-line bg-white p-4 hover:border-primary"
    >
      <span className="mt-0.5 text-primary">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm text-slate-500">{label}</span>
        <span className="block text-2xl font-semibold tabular-nums text-navy">{shown}</span>
        <span className="block text-xs text-slate-400">
          {failed ? 'Chưa tải được, thử tải lại trang' : hint}
        </span>
      </span>
      <ChevronRight size={18} className="mt-1 text-slate-300 group-hover:text-primary" />
    </Link>
  )
}

function Figure({
  icon,
  label,
  value,
  hint,
}: {
  icon: ReactNode
  label: string
  value: string
  hint: string
}) {
  return (
    <div className="rounded-xl border border-line p-3">
      <p className="flex items-center gap-2 text-sm text-slate-500">
        <span className="text-primary">{icon}</span>
        {label}
      </p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-navy">{value}</p>
      <p className="text-xs text-slate-400">{hint}</p>
    </div>
  )
}

const STATE_STYLE: Record<ServerState, { icon: ReactNode; text: string; className: string }> = {
  ok: { icon: <CircleCheck size={16} />, text: 'Hoạt động', className: 'text-ok' },
  tat: { icon: <CircleMinus size={16} />, text: 'Đang tắt', className: 'text-slate-400' },
  loi: { icon: <CircleAlert size={16} />, text: 'Gián đoạn', className: 'text-err' },
}

/** Một dòng trạng thái: biểu tượng + nhãn chữ (không dùng màu đơn thuần). */
function StatusLine({
  state,
  label,
  detail,
}: {
  state: ServerState
  label: string
  detail: string
}) {
  const style = STATE_STYLE[state]
  return (
    <li className="flex items-start gap-2 text-sm">
      <span className={`mt-0.5 ${style.className}`} aria-hidden>
        {style.icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-slate-800">{label}</span>
        <span className="block truncate text-xs text-slate-400" title={detail}>
          {detail}
        </span>
      </span>
      <span className={`shrink-0 text-xs font-medium ${style.className}`}>{style.text}</span>
    </li>
  )
}
