import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, LoaderCircle, Plus, RefreshCw } from 'lucide-react'
import { Fragment, useState } from 'react'
import {
  Badge,
  Card,
  Drawer,
  Field,
  JsonBlock,
  PageHeader,
  Switch,
  inputClass,
  primaryButton,
  secondaryButton,
} from '../../components/admin/ui'
import { reviewBadge } from '../../lib/admin'
import {
  RISK_LABELS,
  type McpCheckResult,
  type McpServerItem,
  type Tool,
} from '../../lib/adminTypes'
import { ApiError, api } from '../../lib/api'

const KEY = ['admin', 'mcp-servers']

function errorText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback
}

const TONE_CLASS = { new: 'bg-sky-100 text-sky-800', changed: 'bg-warn-bg text-warn' }

function serverHint(hint: boolean | null): string | null {
  if (hint === true) return 'Server tự khai báo: chỉ đọc'
  if (hint === false) return 'Server tự khai báo: có thay đổi dữ liệu'
  return null
}

export default function McpPage() {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const [adding, setAdding] = useState(false)
  const [open, setOpen] = useState<number | null>(null)
  const servers = useQuery({
    queryKey: KEY,
    queryFn: () => api<McpServerItem[]>('/api/admin/mcp-servers'),
  })

  const refresh = useMutation({
    mutationFn: () => api<McpServerItem[]>('/api/admin/mcp-servers/refresh', { method: 'POST' }),
    onSuccess: (data) => queryClient.setQueryData(KEY, data),
  })

  const patch = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<Tool> }) =>
      api<Tool>(`/api/admin/tools/${id}`, { method: 'PATCH', json: body }),
    onMutate: () => setError(null),
    onSuccess: (tool) =>
      queryClient.setQueryData<McpServerItem[]>(KEY, (old) =>
        old?.map((s) => ({ ...s, cong_cu: s.cong_cu.map((t) => (t.id === tool.id ? tool : t)) })),
      ),
    onError: (err) => setError(errorText(err, 'Không lưu được thay đổi.')),
  })

  const update = (tool: Tool, body: Partial<Tool>) => patch.mutate({ id: tool.id, body })

  return (
    <>
      <PageHeader title="MCP & quyền">
        <button className={primaryButton} onClick={() => setAdding(true)}>
          <Plus size={16} />
          Thêm MCP server
        </button>
        <button
          className={secondaryButton}
          disabled={refresh.isPending}
          onClick={() => refresh.mutate()}
        >
          {refresh.isPending ? (
            <LoaderCircle size={16} className="animate-spin" />
          ) : (
            <RefreshCw size={16} />
          )}
          Đồng bộ lại
        </button>
      </PageHeader>

      <p className="mb-4 text-sm text-slate-500">
        Thay đổi có hiệu lực ngay ở câu hỏi tiếp theo của sinh viên. Công cụ tắt không được gửi
        cho mô hình AI; công cụ mức "Ghi"/"Nhạy cảm" luôn phải chờ sinh viên xác nhận. Bật một
        công cụ nghĩa là đã đọc và duyệt mô tả của nó: nếu server đổi mô tả sau đó, công cụ tự
        tắt và chờ duyệt lại.
      </p>
      {error && (
        <p role="alert" className="mb-3 rounded-xl bg-err-bg px-4 py-2 text-sm text-err">
          {error}
        </p>
      )}
      {servers.isPending && <p className="text-sm text-slate-500">Đang tải…</p>}
      {servers.isError && <p className="text-sm text-err">Không tải được danh sách server.</p>}

      <div className="space-y-5">
        {servers.data?.map((s) => {
          const ok = s.trang_thai === 'ok'
          return (
            <Card key={s.id} className="overflow-hidden">
              <div className="flex flex-wrap items-center gap-3 border-b border-line bg-page px-4 py-3">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${ok ? 'bg-emerald-500' : 'bg-red-500'}`}
                  aria-hidden
                />
                <span className="font-semibold text-navy">{s.ten}</span>
                <span className="text-sm text-slate-500">{s.mo_ta}</span>
                <span className="ml-auto text-xs text-slate-500">
                  {ok ? s.dia_chi : <span className="text-err">{s.trang_thai}</span>}
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-sm">
                  <thead className="text-left text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-4 py-2 font-medium">Công cụ</th>
                      <th className="px-4 py-2 font-medium">Mức rủi ro</th>
                      <th className="px-4 py-2 text-center font-medium">Cần xác nhận</th>
                      <th className="px-4 py-2 text-center font-medium">Bật</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {s.cong_cu.map((t) => {
                      const badge = reviewBadge(t.duyet)
                      const expanded = open === t.id
                      const hint = serverHint(t.chi_doc_theo_server)
                      return (
                        <Fragment key={t.id}>
                          <tr className={t.bat ? '' : 'bg-slate-50 text-slate-500'}>
                            <td className="px-4 py-3">
                              <div className="flex flex-wrap items-center gap-2">
                                <button
                                  onClick={() => setOpen(expanded ? null : t.id)}
                                  aria-expanded={expanded}
                                  aria-label={`Xem mô tả đầy đủ của ${t.ten}`}
                                  className="flex h-6 w-6 items-center justify-center rounded hover:bg-page"
                                >
                                  {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                                </button>
                                <span className="font-mono text-[13px] font-medium text-navy">
                                  {t.ten}
                                </span>
                                {t.title && <span className="text-xs text-slate-600">{t.title}</span>}
                                {badge && (
                                  <Badge className={TONE_CLASS[badge.tone]}>{badge.text}</Badge>
                                )}
                                {!t.co_tren_server && (
                                  <Badge className="bg-warn-bg text-warn">
                                    Server không còn cung cấp
                                  </Badge>
                                )}
                              </div>
                              <p className="ml-8 text-xs text-slate-500">{t.mo_ta}</p>
                            </td>
                            <td className="px-4 py-3">
                              <select
                                value={t.muc_rui_ro}
                                onChange={(e) =>
                                  update(t, {
                                    muc_rui_ro: e.target.value as Tool['muc_rui_ro'],
                                    // Nâng lên ghi/nhạy cảm thì bật luôn xác nhận (backend bắt buộc)
                                    ...(e.target.value !== 'doc' ? { can_xac_nhan: true } : {}),
                                  })
                                }
                                aria-label={`Mức rủi ro của ${t.ten}`}
                                className="h-9 rounded-lg border border-line bg-white px-2 text-sm"
                              >
                                {Object.entries(RISK_LABELS).map(([v, l]) => (
                                  <option key={v} value={v}>
                                    {l}
                                  </option>
                                ))}
                              </select>
                            </td>
                            <td className="px-4 py-3 text-center">
                              <Switch
                                checked={t.can_xac_nhan}
                                label={`Cần xác nhận: ${t.ten}`}
                                disabled={patch.isPending}
                                onChange={(v) => update(t, { can_xac_nhan: v })}
                              />
                            </td>
                            <td className="px-4 py-3 text-center">
                              <Switch
                                checked={t.bat}
                                label={`Bật ${t.ten}`}
                                disabled={patch.isPending}
                                onChange={(v) => update(t, { bat: v })}
                              />
                            </td>
                          </tr>
                          {expanded && (
                            <tr className="bg-page">
                              <td colSpan={4} className="space-y-2 px-4 py-3">
                                <p className="text-xs font-medium text-slate-500">
                                  Mô tả server gửi cho mô hình AI
                                  {hint && <span className="ml-2 font-normal">({hint})</span>}
                                </p>
                                <p className="whitespace-pre-wrap text-sm text-slate-700">
                                  {t.mo_ta_day_du ?? 'Server hiện không cung cấp công cụ này.'}
                                </p>
                                {t.tham_so && (
                                  <>
                                    <p className="text-xs font-medium text-slate-500">
                                      Tham số mô hình AI thấy (ma_sv / ma_khoa đã ẩn)
                                    </p>
                                    <JsonBlock value={t.tham_so} />
                                  </>
                                )}
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      )
                    })}
                    {s.cong_cu.length === 0 && (
                      <tr>
                        <td colSpan={4} className="px-4 py-3 text-slate-500">
                          Chưa có công cụ (server chưa đồng bộ được).
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              {s.cong_cu_bi_bo_qua.length > 0 && (
                <ul className="space-y-1 border-t border-line bg-warn-bg px-4 py-2 text-xs text-warn">
                  {s.cong_cu_bi_bo_qua.map((k) => (
                    <li key={k.ten}>
                      <span className="font-mono">{k.ten}</span>: trùng tên với công cụ của server{' '}
                      <span className="font-mono">{k.trung_voi}</span> — bị bỏ qua
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )
        })}
      </div>

      {adding && <AddServerDrawer onClose={() => setAdding(false)} />}
    </>
  )
}

function AddServerDrawer({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [ten, setTen] = useState('')
  const [moTa, setMoTa] = useState('')
  const [diaChi, setDiaChi] = useState('http://127.0.0.1:9105/mcp')
  const [checkedAddress, setCheckedAddress] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const check = useMutation({
    mutationFn: () =>
      api<McpCheckResult>('/api/admin/mcp-servers/check', {
        method: 'POST',
        json: { dia_chi: diaChi },
      }),
    onMutate: () => {
      setError(null)
      setCheckedAddress(null)
    },
    onSuccess: () => setCheckedAddress(diaChi),
    onError: (err) => setError(errorText(err, 'Không kiểm tra được kết nối.')),
  })

  const save = useMutation({
    mutationFn: () =>
      api<McpServerItem>('/api/admin/mcp-servers', {
        method: 'POST',
        json: { ten: ten.trim(), mo_ta: moTa.trim(), dia_chi: diaChi },
      }),
    onMutate: () => setError(null),
    onSuccess: (server) => {
      queryClient.setQueryData<McpServerItem[]>(KEY, (old) => [...(old ?? []), server])
      onClose()
    },
    onError: (err) => setError(errorText(err, 'Không lưu được server.')),
  })

  // Đổi địa chỉ sau khi kiểm tra -> phải kiểm tra lại mới được lưu
  const checked = checkedAddress !== null && checkedAddress === diaChi
  const preview = checked ? check.data?.cong_cu ?? [] : []

  return (
    <Drawer title="Thêm MCP server" onClose={onClose} wide>
      <div className="space-y-4">
        <Field label="Tên (chữ thường không dấu, số, gạch dưới — vd thu_vien)">
          <input
            className={`${inputClass} w-full font-mono`}
            value={ten}
            onChange={(e) => setTen(e.target.value)}
            maxLength={50}
          />
        </Field>
        <Field label="Mô tả">
          <input
            className={`${inputClass} w-full`}
            value={moTa}
            onChange={(e) => setMoTa(e.target.value)}
            maxLength={255}
          />
        </Field>
        <Field label="Địa chỉ (chỉ http://127.0.0.1:<cổng>/mcp hoặc http://localhost:<cổng>/mcp)">
          <input
            className={`${inputClass} w-full font-mono`}
            value={diaChi}
            onChange={(e) => setDiaChi(e.target.value)}
            maxLength={255}
          />
        </Field>

        {error && (
          <p role="alert" className="rounded-xl bg-err-bg px-4 py-2 text-sm text-err">
            {error}
          </p>
        )}

        <div className="flex gap-2">
          <button
            className={secondaryButton}
            disabled={check.isPending || !diaChi.trim()}
            onClick={() => check.mutate()}
          >
            {check.isPending && <LoaderCircle size={16} className="animate-spin" />}
            Kiểm tra kết nối
          </button>
          <button
            className={primaryButton}
            disabled={!checked || !ten.trim() || save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending && <LoaderCircle size={16} className="animate-spin" />}
            Lưu
          </button>
        </div>

        {checked && (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">
              Kết nối được, server cung cấp {preview.length} công cụ. Sau khi lưu, các công cụ ở
              trạng thái <b>tắt</b> và cần xác nhận; hãy đọc mô tả rồi mới bật.
            </p>
            {preview.map((t) => {
              const hint = serverHint(t.chi_doc_theo_server)
              return (
                <Card key={t.ten} className="space-y-1 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[13px] font-medium text-navy">{t.ten}</span>
                    {t.title && <span className="text-xs text-slate-600">{t.title}</span>}
                    {hint && <Badge className="bg-slate-100 text-slate-600">{hint}</Badge>}
                    {t.trung_ten_voi && (
                      <Badge className="bg-warn-bg text-warn">
                        Trùng tên với công cụ của server {t.trung_ten_voi} — sẽ bị bỏ qua
                      </Badge>
                    )}
                  </div>
                  <p className="whitespace-pre-wrap text-sm text-slate-700">{t.mo_ta}</p>
                  <JsonBlock value={t.tham_so} />
                </Card>
              )
            })}
          </div>
        )}
      </div>
    </Drawer>
  )
}
