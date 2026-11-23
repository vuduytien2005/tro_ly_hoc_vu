import { useQuery } from '@tanstack/react-query'
import { Lock, Workflow } from 'lucide-react'
import { CALL_STATUS } from '../../lib/adminTypes'
import { api } from '../../lib/api'
import { traceKey, traceLines, useFreshIds } from '../../lib/presentation'
import type { TraceResponse, TraceStep } from '../../lib/types'

/**
 * Bảng "Bên trong Agent" (chế độ trình bày): các lượt gọi công cụ của hội thoại, đọc từ nhật ký
 * luot_goi_cong_cu. ChatPage gọi invalidate(traceKey) khi luồng báo tool_end / pending_action / done
 * và sau khi xác nhận / hủy thẻ — không poll.
 */
export function TracePanel({ conversationId }: { conversationId: number | null }) {
  const trace = useQuery({
    queryKey: traceKey(conversationId),
    queryFn: () => api<TraceResponse>(`/api/conversations/${conversationId}/trace`),
    enabled: conversationId != null,
    retry: false,
  })
  const steps = trace.data?.luot_goi ?? []
  const fresh = useFreshIds(trace.data?.luot_goi.map((s) => s.id), conversationId)

  return (
    <aside className="flex min-h-0 flex-col border-line bg-slate-50 lg:w-[360px] lg:shrink-0 lg:border-l max-lg:max-h-[40vh] max-lg:border-t">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3 font-semibold text-navy">
        <Workflow size={18} /> Bên trong Agent
      </div>
      <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
        {trace.isError && <p className="text-xs text-err">Không tải được nhật ký.</p>}
        {!trace.isError && steps.length === 0 && (
          <p className="text-sm text-slate-400">Chưa có bước nào. Agent gọi công cụ sẽ hiện ở đây.</p>
        )}
        {steps.map((s, i) => (
          <StepCard key={s.id} index={i + 1} step={s} fresh={fresh.has(s.id)} />
        ))}
      </div>
      <p className="border-t border-line px-4 py-2 text-xs text-slate-500">
        Bảng này đọc trực tiếp từ nhật ký hệ thống (luot_goi_cong_cu).
      </p>
    </aside>
  )
}

function StepCard({ index, step, fresh }: { index: number; step: TraceStep; fresh: boolean }) {
  const status = CALL_STATUS[step.trang_thai] ?? { label: step.trang_thai, className: 'bg-slate-100' }
  const { llm, system } = traceLines(step)
  return (
    <div className={`rounded-xl border border-line bg-white p-3 text-sm ${fresh ? 'trace-fresh' : ''}`}>
      <div className="flex items-start gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-navy text-xs font-semibold text-white">
          {index}
        </span>
        <div className="min-w-0 flex-1">
          <div className="font-medium text-slate-800">{step.nhan}</div>
          <div className="font-mono text-xs text-slate-400">{step.ten_cong_cu}</div>
        </div>
        <span className={`whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${status.className}`}>
          {status.label}
        </span>
      </div>
      <div className="mt-2 space-y-1 pl-8 text-xs">
        {llm == null ? (
          <div className="text-slate-500">Hệ thống tự gọi (kiểm tra trước khi tạo thẻ)</div>
        ) : (
          <div className="break-words text-slate-600">
            <span className="text-slate-400">LLM gửi:</span> <span className="font-mono">{llm}</span>
          </div>
        )}
        {system.map((line) => (
          <div key={line.key} className="flex items-start gap-1 rounded-md bg-accent/20 px-2 py-1 text-amber-900">
            <Lock size={12} className="mt-0.5 shrink-0" />
            <span className="break-words">
              {line.overridden != null ? (
                <>
                  LLM gửi <b className="font-mono">{line.overridden}</b> → hệ thống ghi đè{' '}
                  <b className="font-mono">{line.key}={line.value}</b>
                </>
              ) : (
                <>
                  Hệ thống điền: <b className="font-mono">{line.key}={line.value}</b>
                </>
              )}
            </span>
          </div>
        ))}
        {step.ly_do && step.trang_thai !== 'thanh_cong' && (
          <div className={step.trang_thai === 'bi_tu_choi' || step.trang_thai === 'loi' ? 'text-err' : 'text-slate-500'}>
            {step.ly_do}
          </div>
        )}
      </div>
    </div>
  )
}
