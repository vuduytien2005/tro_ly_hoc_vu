import { CircleCheck, ClipboardList, Clock, LoaderCircle, ShieldAlert, XCircle } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import {
  formErrors,
  formFields,
  formPayload,
  type FormField,
  type FormValues,
} from '../../lib/elicitation'
import { formatRemaining } from '../../lib/format'
import type { PendingAction } from '../../lib/types'

export type CardState = 'cho' | 'dang_xu_ly' | 'da_xac_nhan' | 'da_huy' | 'het_han' | 'loi'

function useRemaining(expiresAt: string): number {
  const deadline = new Date(expiresAt).getTime()
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  return deadline - now
}

/** Thẻ "Đề xuất thực hiện" (quy tắc 2): chỉ khi sinh viên bấm Xác nhận thì backend mới thực thi. */
export function PendingActionCard({
  action,
  state,
  error,
  onConfirm,
  onCancel,
  onSubmitInput,
}: {
  action: PendingAction
  state: CardState
  error?: string | null
  onConfirm: () => void
  onCancel: () => void
  onSubmitInput: (data: Record<string, string | number | boolean>) => void
}) {
  const remaining = useRemaining(action.het_han_luc)
  const expired = state === 'cho' && remaining <= 0
  const shown: CardState = expired ? 'het_han' : state
  const open = shown === 'cho'

  return (
    <div className="my-3 rounded-2xl border border-primary/30 bg-primary/5 p-4">
      <div className="mb-2 flex items-center gap-2">
        <ShieldAlert size={18} className="text-primary" />
        <span className="flex-1 font-semibold text-navy">Đề xuất thực hiện</span>
        {open && (
          <span
            className={`inline-flex items-center gap-1 text-xs ${remaining < 60_000 ? 'text-warn' : 'text-slate-500'}`}
          >
            <Clock size={14} /> Hết hạn sau {formatRemaining(remaining)}
          </span>
        )}
      </div>
      <p className="mb-3 whitespace-pre-line text-sm leading-relaxed text-slate-700">{action.mo_ta}</p>

      {error && <p className="mb-3 rounded-lg bg-err-bg px-3 py-2 text-sm text-err">{error}</p>}

      {open && action.bo_sung && (
        <ElicitationForm form={action.bo_sung} onCancel={onCancel} onSubmit={onSubmitInput} />
      )}
      {open && !action.bo_sung && (
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="h-11 rounded-[10px] border border-line bg-white px-5 text-sm font-medium hover:bg-page"
          >
            Hủy
          </button>
          <button
            onClick={onConfirm}
            className="h-11 rounded-[10px] bg-primary px-5 text-sm font-medium text-white hover:bg-primary-dark"
          >
            Xác nhận
          </button>
        </div>
      )}
      {shown === 'dang_xu_ly' && (
        <p className="flex items-center gap-2 text-sm text-slate-600">
          <LoaderCircle size={16} className="animate-spin" /> Đang thực hiện…
        </p>
      )}
      {shown === 'da_xac_nhan' && (
        <p className="flex items-center gap-2 text-sm font-medium text-ok">
          <CircleCheck size={16} /> Đã xác nhận
        </p>
      )}
      {shown === 'da_huy' && (
        <p className="flex items-center gap-2 text-sm text-slate-500">
          <XCircle size={16} /> Đã hủy
        </p>
      )}
      {shown === 'het_han' && (
        <p className="flex items-center gap-2 text-sm text-warn">
          <Clock size={16} /> Đã hết hạn — em hãy yêu cầu lại trợ lý nếu vẫn muốn thực hiện.
        </p>
      )}
    </div>
  )
}

/**
 * Biểu mẫu MCP elicitation: MCP server hỏi thêm sau khi sinh viên bấm Xác nhận (vd số điện thoại
 * liên hệ khi bảo lưu). Dữ liệu gửi thẳng tới hệ thống của trường, KHÔNG qua trợ lý AI.
 */
function ElicitationForm({
  form,
  onCancel,
  onSubmit,
}: {
  form: NonNullable<PendingAction['bo_sung']>
  onCancel: () => void
  onSubmit: (data: Record<string, string | number | boolean>) => void
}) {
  const fields = useMemo(() => formFields(form.schema), [form.schema])
  const [values, setValues] = useState<FormValues>({})
  const [touched, setTouched] = useState(false)
  const errors = formErrors(fields, values)
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setTouched(true)
    if (Object.keys(errors).length === 0) onSubmit(formPayload(fields, values))
  }
  return (
    <form onSubmit={submit} noValidate className="space-y-3 rounded-xl border border-line bg-white p-3">
      <p className="flex items-start gap-2 text-sm text-slate-700">
        <ClipboardList size={16} className="mt-0.5 shrink-0 text-primary" />
        <span>{form.thong_diep}</span>
      </p>
      {fields.map((f) => (
        <FieldInput
          key={f.name}
          field={f}
          value={values[f.name]}
          error={touched ? errors[f.name] : undefined}
          onChange={(v) => setValues((old) => ({ ...old, [f.name]: v }))}
        />
      ))}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="h-11 rounded-[10px] border border-line bg-white px-5 text-sm font-medium hover:bg-page"
        >
          Hủy
        </button>
        <button
          type="submit"
          className="h-11 rounded-[10px] bg-primary px-5 text-sm font-medium text-white hover:bg-primary-dark"
        >
          Gửi thông tin
        </button>
      </div>
    </form>
  )
}

function FieldInput({
  field,
  value,
  error,
  onChange,
}: {
  field: FormField
  value: string | boolean | undefined
  error?: string
  onChange: (v: string | boolean) => void
}) {
  const id = `bs-${field.name}`
  const base = `h-10 w-full rounded-lg border px-3 text-sm ${error ? 'border-err' : 'border-line'}`
  if (field.kind === 'checkbox') {
    return (
      <label htmlFor={id} className="flex items-center gap-2 text-sm">
        <input
          id={id}
          type="checkbox"
          checked={value === true}
          onChange={(e) => onChange(e.target.checked)}
        />
        {field.label}
      </label>
    )
  }
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">
        {field.label}
        {field.required && <span className="text-err"> *</span>}
      </label>
      {field.kind === 'select' ? (
        <select
          id={id}
          className={base}
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">— Chọn —</option>
          {field.schema.enum?.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          className={base}
          inputMode={field.kind === 'number' ? 'decimal' : undefined}
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={field.hint ? `${id}-hint` : undefined}
        />
      )}
      {field.hint && (
        <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">
          {field.hint}
        </p>
      )}
      {error && <p className="mt-1 text-xs text-err">{error}</p>}
    </div>
  )
}
