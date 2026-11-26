import { useQuery } from '@tanstack/react-query'
import { Download, LoaderCircle, Syringe } from 'lucide-react'
import { useState } from 'react'
import {
  Badge,
  Card,
  Drawer,
  JsonBlock,
  PageHeader,
  Switch,
  inputClass,
  secondaryButton,
} from '../../components/admin/ui'
import { useFreshIds } from '../../lib/presentation'
import { formatMs, injectedKeys, toQuery } from '../../lib/admin'
import {
  CALL_STATUS,
  type AuditLogDetail,
  type AuditLogPage,
  type McpServerItem,
} from '../../lib/adminTypes'
import { ApiError, api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { EXPORT_LIMIT, auditFileName, auditToCsv, fetchAllAuditLogs } from '../../lib/auditCsv'
import { downloadCsv } from '../../lib/statsCsv'

const PAGE_SIZE = 20
const AUTO_REFRESH_MS = 3000

function InjectedBadge() {
  return (
    <Badge className="bg-accent/20 text-amber-800">
      <Syringe size={12} className="mr-1" /> Đã tiêm ngữ cảnh
    </Badge>
  )
}

export default function AuditPage() {
  const [filters, setFilters] = useState({
    tu: '',
    den: '',
    nguoi_dung_id: '',
    ten_cong_cu: '',
    trang_thai: '',
  })
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<number | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportNote, setExportNote] = useState<string | null>(null)
  const exportCsv = async () => {
    setExporting(true)
    setExportNote(null)
    try {
      const { rows, truncated, total } = await fetchAllAuditLogs(filters)
      downloadCsv(auditToCsv(rows), auditFileName(filters))
      setExportNote(
        truncated
          ? `Đã xuất ${EXPORT_LIMIT} lượt mới nhất trên ${total}. Thu hẹp khoảng ngày để xuất phần còn lại.`
          : `Đã xuất ${rows.length} lượt.`,
      )
    } catch (err) {
      setExportNote(err instanceof ApiError ? err.message : 'Chưa xuất được nhật ký, thử lại sau.')
    } finally {
      setExporting(false)
    }
  }
  const set = (key: keyof typeof filters) => (value: string) => {
    setFilters((f) => ({ ...f, [key]: value }))
    setPage(1)
  }

  const logs = useQuery({
    queryKey: ['admin', 'audit', filters, page],
    queryFn: () =>
      api<AuditLogPage>(
        `/api/admin/audit-logs${toQuery({ ...filters, page, page_size: PAGE_SIZE })}`,
      ),
    placeholderData: (prev) => prev,
    // Demo: dòng mới hiện ngay, không phải F5
    refetchInterval: autoRefresh ? AUTO_REFRESH_MS : false,
  })
  // Dòng mới (so với lần tải trước, cùng bộ lọc + trang) nổi bật ~1 giây
  const fresh = useFreshIds(
    logs.data?.luot_goi.map((l) => l.id),
    JSON.stringify([filters, page]),
  )
  // Danh sách tên công cụ cho ô lọc
  const servers = useQuery({
    queryKey: ['admin', 'mcp-servers'],
    queryFn: () => api<McpServerItem[]>('/api/admin/mcp-servers'),
  })
  const toolNames = (servers.data ?? []).flatMap((s) => s.cong_cu.map((t) => t.ten)).sort()
  const totalPages = logs.data ? Math.max(1, Math.ceil(logs.data.tong / PAGE_SIZE)) : 1

  return (
    <>
      <PageHeader title="Nhật ký gọi công cụ">
        <label className="inline-flex items-center gap-2 text-sm text-slate-600">
          <Switch checked={autoRefresh} onChange={setAutoRefresh} label="Tự cập nhật" />
          Tự cập nhật
        </label>
        <button
          className={secondaryButton}
          disabled={exporting}
          onClick={exportCsv}
          title="Xuất các lượt gọi theo bộ lọc đang chọn ra tệp CSV (mở bằng Excel)"
        >
          {exporting ? <LoaderCircle size={15} className="animate-spin" /> : <Download size={15} />}
          Xuất CSV
        </button>
      </PageHeader>
      {exportNote && (
        <p role="status" className="-mt-3 mb-4 text-sm text-slate-500">
          {exportNote}
        </p>
      )}
      <Card className="mb-4 flex flex-wrap items-end gap-3 p-4">
        <Filter label="Từ ngày">
          <input
            type="date"
            value={filters.tu}
            onChange={(e) => set('tu')(e.target.value)}
            className={inputClass}
          />
        </Filter>
        <Filter label="Đến ngày">
          <input
            type="date"
            value={filters.den}
            onChange={(e) => set('den')(e.target.value)}
            className={inputClass}
          />
        </Filter>
        <Filter label="Mã người dùng">
          <input
            inputMode="numeric"
            value={filters.nguoi_dung_id}
            onChange={(e) => set('nguoi_dung_id')(e.target.value.replace(/\D/g, ''))}
            className={`${inputClass} w-28`}
            placeholder="vd 1"
          />
        </Filter>
        <Filter label="Công cụ">
          <select
            value={filters.ten_cong_cu}
            onChange={(e) => set('ten_cong_cu')(e.target.value)}
            className={inputClass}
          >
            <option value="">Tất cả</option>
            {toolNames.map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </Filter>
        <Filter label="Trạng thái">
          <select
            value={filters.trang_thai}
            onChange={(e) => set('trang_thai')(e.target.value)}
            className={inputClass}
          >
            <option value="">Tất cả</option>
            {Object.entries(CALL_STATUS).map(([v, s]) => (
              <option key={v} value={v}>
                {s.label}
              </option>
            ))}
          </select>
        </Filter>
      </Card>

      {logs.isError && (
        <p className="mb-3 text-sm text-err">
          {logs.error instanceof ApiError ? logs.error.message : 'Không tải được nhật ký.'}
        </p>
      )}

      <Card className="overflow-x-auto">
        <table className="w-full min-w-[860px] text-sm">
          <thead className="border-b border-line bg-page text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Thời gian</th>
              <th className="px-4 py-3 font-medium">Người dùng</th>
              <th className="px-4 py-3 font-medium">Server / công cụ</th>
              <th className="px-4 py-3 font-medium">Trạng thái</th>
              <th className="px-4 py-3 text-right font-medium">Xử lý</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {logs.data?.luot_goi.map((l) => (
              <tr
                key={l.id}
                onClick={() => setSelected(l.id)}
                className={`cursor-pointer hover:bg-page ${fresh.has(l.id) ? 'trace-fresh' : ''}`}
              >
                <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                  {formatDateTime(l.created_at)}
                </td>
                <td className="px-4 py-3">
                  <p className="font-medium">{l.nguoi_dung.ho_ten}</p>
                  <p className="text-xs text-slate-500">
                    #{l.nguoi_dung.id} · {l.nguoi_dung.email}
                  </p>
                </td>
                <td className="px-4 py-3">
                  <p className="font-mono text-[13px] text-navy">{l.ten_cong_cu}</p>
                  <p className="text-xs text-slate-500">{l.mcp_server}</p>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    <Badge className={CALL_STATUS[l.trang_thai]?.className ?? ''}>
                      {CALL_STATUS[l.trang_thai]?.label ?? l.trang_thai}
                    </Badge>
                    {l.da_tiem_ngu_canh && <InjectedBadge />}
                  </div>
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-right tabular-nums text-slate-500">
                  {formatMs(l.thoi_gian_ms)}
                </td>
              </tr>
            ))}
            {logs.data?.luot_goi.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-slate-500">
                  Không có lượt gọi nào khớp bộ lọc.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>

      <div className="mt-4 flex items-center justify-between text-sm">
        <span className="text-slate-500">
          {logs.data ? `${logs.data.tong} lượt gọi · trang ${page}/${totalPages}` : 'Đang tải…'}
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

      {selected != null && <LogDrawer id={selected} onClose={() => setSelected(null)} />}
    </>
  )
}

function Filter({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="text-sm">
      <span className="mb-1 block text-xs font-medium text-slate-500">{label}</span>
      {children}
    </label>
  )
}

function LogDrawer({ id, onClose }: { id: number; onClose: () => void }) {
  const detail = useQuery({
    queryKey: ['admin', 'audit-log', id],
    queryFn: () => api<AuditLogDetail>(`/api/admin/audit-logs/${id}`),
  })
  const d = detail.data
  const injected = d ? injectedKeys(d.tham_so_llm, d.tham_so) : new Set<string>()

  return (
    <Drawer title={d ? `#${d.id} · ${d.ten_cong_cu}` : `Lượt gọi #${id}`} onClose={onClose}>
      {detail.isPending && <p className="text-sm text-slate-500">Đang tải…</p>}
      {detail.isError && <p className="text-sm text-err">Không tải được chi tiết.</p>}
      {d && (
        <div className="space-y-5 text-sm">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
            <dt className="text-slate-500">Thời gian</dt>
            <dd>{formatDateTime(d.created_at)}</dd>
            <dt className="text-slate-500">Người dùng</dt>
            <dd>
              {d.nguoi_dung.ho_ten} ({d.nguoi_dung.email})
            </dd>
            <dt className="text-slate-500">Hội thoại</dt>
            <dd>{d.hoi_thoai_id ?? '— (gọi trực tiếp từ trang Thủ tục)'}</dd>
            <dt className="text-slate-500">Trạng thái</dt>
            <dd className="flex flex-wrap gap-1">
              <Badge className={CALL_STATUS[d.trang_thai]?.className ?? ''}>
                {CALL_STATUS[d.trang_thai]?.label ?? d.trang_thai}
              </Badge>
              {d.da_tiem_ngu_canh && <InjectedBadge />}
            </dd>
            {d.ly_do && (
              <>
                <dt className="text-slate-500">Lý do</dt>
                <dd>{d.ly_do}</dd>
              </>
            )}
            <dt className="text-slate-500">Thời gian xử lý</dt>
            <dd>{formatMs(d.thoi_gian_ms)}</dd>
          </dl>

          {d.da_tiem_ngu_canh && (
            <p className="rounded-xl bg-accent/15 px-3 py-2 text-amber-900">
              Tham số mô hình AI gửi khác tham số thực thi: hệ thống đã điền/ghi đè{' '}
              <b>{[...injected].join(', ')}</b> theo tài khoản đang đăng nhập (quy tắc tiêm ngữ
              cảnh). Các dòng tô vàng là phần bị thay.
            </p>
          )}
          <section>
            <h3 className="mb-2 font-medium text-navy">Tham số do mô hình AI sinh (tham_so_llm)</h3>
            <JsonBlock value={d.tham_so_llm} highlight={injected} />
          </section>
          <section>
            <h3 className="mb-2 font-medium text-navy">Tham số thực thi (tham_so)</h3>
            <JsonBlock value={d.tham_so} highlight={injected} />
          </section>
          <section>
            <h3 className="mb-2 font-medium text-navy">Kết quả</h3>
            <JsonBlock value={d.ket_qua} />
          </section>
        </div>
      )}
    </Drawer>
  )
}
