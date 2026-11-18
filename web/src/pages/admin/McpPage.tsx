import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LoaderCircle, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Badge, Card, PageHeader, Switch, secondaryButton } from '../../components/admin/ui'
import { RISK_LABELS, type McpServerItem, type Tool } from '../../lib/adminTypes'
import { ApiError, api } from '../../lib/api'

const KEY = ['admin', 'mcp-servers']

export default function McpPage() {
  const queryClient = useQueryClient()
  const [error, setError] = useState<string | null>(null)
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
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : 'Không lưu được thay đổi.'),
  })

  const update = (tool: Tool, body: Partial<Tool>) => patch.mutate({ id: tool.id, body })

  return (
    <>
      <PageHeader title="MCP & quyền">
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
        cho mô hình AI; công cụ mức "Ghi"/"Nhạy cảm" luôn phải chờ sinh viên xác nhận.
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
                    {s.cong_cu.map((t) => (
                      <tr key={t.id} className={t.bat ? '' : 'bg-slate-50 text-slate-500'}>
                        <td className="px-4 py-3">
                          <p className="font-mono text-[13px] font-medium text-navy">
                            {t.ten}
                            {!t.co_tren_server && (
                              <Badge className="ml-2 bg-warn-bg font-sans text-warn">
                                Server không còn cung cấp
                              </Badge>
                            )}
                          </p>
                          <p className="text-xs text-slate-500">{t.mo_ta}</p>
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
                    ))}
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
            </Card>
          )
        })}
      </div>
    </>
  )
}
