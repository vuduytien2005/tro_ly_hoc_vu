import { useQuery } from '@tanstack/react-query'
import { Clock, MessageSquare, MessagesSquare, ThumbsUp } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Card, PageHeader, inputClass } from '../../components/admin/ui'
import { formatMs, formatPercent, toQuery } from '../../lib/admin'
import type { Stats } from '../../lib/adminTypes'
import { ApiError, api } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'

const PRIMARY = '#1D4ED8'
const ERROR = '#B91C1C'

export default function StatsPage() {
  const [range, setRange] = useState({ tu: '', den: '' })
  const stats = useQuery({
    queryKey: ['admin', 'stats', range],
    queryFn: () => api<Stats>(`/api/admin/stats${toQuery(range)}`),
    placeholderData: (prev) => prev,
  })
  const s = stats.data

  return (
    <>
      <PageHeader title="Thống kê">
        <label className="flex items-center gap-2 text-sm">
          Từ
          <input
            type="date"
            value={range.tu || s?.tu || ''}
            onChange={(e) => setRange((r) => ({ ...r, tu: e.target.value }))}
            className={inputClass}
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          đến
          <input
            type="date"
            value={range.den || s?.den || ''}
            onChange={(e) => setRange((r) => ({ ...r, den: e.target.value }))}
            className={inputClass}
          />
        </label>
      </PageHeader>

      {stats.isError && (
        <p className="mb-3 text-sm text-err">
          {stats.error instanceof ApiError ? stats.error.message : 'Không tải được thống kê.'}
        </p>
      )}
      {!s && stats.isPending && <p className="text-sm text-slate-500">Đang tải…</p>}

      {s && (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Metric icon={<MessagesSquare size={20} />} label="Cuộc trò chuyện" value={s.so_hoi_thoai} />
            <Metric icon={<MessageSquare size={20} />} label="Câu hỏi" value={s.so_cau_hoi} />
            <Metric
              icon={<ThumbsUp size={20} />}
              label="Tỉ lệ hữu ích"
              value={formatPercent(s.ti_le_huu_ich)}
              hint={`${s.so_huu_ich}/${s.so_danh_gia} đánh giá`}
            />
            <Metric
              icon={<Clock size={20} />}
              label="Phản hồi trung bình"
              value={formatMs(s.thoi_gian_phan_hoi_tb_ms)}
              hint={`${s.so_luot_goi_cong_cu} lượt gọi công cụ`}
            />
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <Card className="p-4">
              <h2 className="mb-3 font-semibold text-navy">Câu hỏi theo ngày</h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={s.theo_ngay} margin={{ left: -20, right: 8 }}>
                    <CartesianGrid stroke="#E3E8F0" vertical={false} />
                    <XAxis
                      dataKey="ngay"
                      tickFormatter={(v: string) => v.slice(8, 10) + '/' + v.slice(5, 7)}
                      tick={{ fontSize: 12 }}
                      minTickGap={16}
                    />
                    <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                    <Tooltip
                      labelFormatter={(v) => formatDate(String(v))}
                      formatter={(v) => [v, 'Câu hỏi']}
                    />
                    <Line type="monotone" dataKey="so_cau_hoi" stroke={PRIMARY} strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card className="p-4">
              <h2 className="mb-3 font-semibold text-navy">Công cụ dùng nhiều</h2>
              {s.top_cong_cu.length === 0 ? (
                <p className="text-sm text-slate-500">Chưa có lượt gọi công cụ trong khoảng này.</p>
              ) : (
                <div style={{ height: Math.max(160, s.top_cong_cu.length * 34) }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={s.top_cong_cu} layout="vertical" margin={{ left: 10, right: 16 }}>
                      <CartesianGrid stroke="#E3E8F0" horizontal={false} />
                      <XAxis type="number" allowDecimals={false} tick={{ fontSize: 12 }} />
                      <YAxis
                        type="category"
                        dataKey="ten_cong_cu"
                        width={170}
                        tick={{ fontSize: 12 }}
                      />
                      <Tooltip
                        formatter={(v, name) => [v, name === 'so_loi' ? 'Lỗi/từ chối' : 'Số lượt']}
                      />
                      <Bar dataKey="so_lan" fill={PRIMARY} radius={[0, 4, 4, 0]} />
                      <Bar dataKey="so_loi" fill={ERROR} radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Card>
          </div>

          <Card className="p-4">
            <h2 className="mb-3 font-semibold text-navy">Câu trả lời bị đánh giá "chưa đúng"</h2>
            {s.cau_bi_che.length === 0 && (
              <p className="text-sm text-slate-500">Không có đánh giá tiêu cực trong khoảng này.</p>
            )}
            <ul className="divide-y divide-line">
              {s.cau_bi_che.map((d) => (
                <li key={d.tin_nhan_id} className="py-3 text-sm">
                  <p className="mb-1 text-xs text-slate-500">
                    {formatDateTime(d.created_at)} · {d.nguoi_dung} · hội thoại #{d.hoi_thoai_id}
                  </p>
                  <p className="font-medium text-navy">Hỏi: {d.cau_hoi ?? '—'}</p>
                  <p className="line-clamp-3 text-slate-600">Đáp: {d.cau_tra_loi}</p>
                  {d.gop_y && (
                    <p className="mt-1 rounded-lg bg-err-bg px-2 py-1 text-err">Góp ý: {d.gop_y}</p>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}
    </>
  )
}

function Metric({
  icon,
  label,
  value,
  hint,
}: {
  icon: ReactNode
  label: string
  value: string | number
  hint?: string
}) {
  return (
    <Card className="flex items-center gap-4 p-4">
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-sm text-slate-500">{label}</p>
        <p className="text-2xl font-semibold tabular-nums text-navy">{value}</p>
        {hint && <p className="text-xs text-slate-400">{hint}</p>}
      </div>
    </Card>
  )
}
