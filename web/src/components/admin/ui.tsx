import { X } from 'lucide-react'
import type { ReactNode } from 'react'
import { passwordProblem } from '../../lib/admin'

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-center gap-3">
      <h1 className="flex-1 text-xl font-semibold text-navy">{title}</h1>
      {children}
    </div>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-line bg-white ${className}`}>{children}</div>
  )
}

export function Badge({ className, children }: { className: string; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}
    >
      {children}
    </span>
  )
}

export function Switch({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean
  onChange: (value: boolean) => void
  disabled?: boolean
  label: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${
        checked ? 'bg-primary' : 'bg-slate-300'
      }`}
    >
      <span
        className={`inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
          checked ? 'translate-x-5.5' : 'translate-x-0.5'
        }`}
      />
    </button>
  )
}

/** Ngăn trượt bên phải (chi tiết nhật ký, các đoạn của văn bản). */
export function Drawer({
  title,
  onClose,
  children,
  wide,
}: {
  title: ReactNode
  onClose: () => void
  children: ReactNode
  wide?: boolean
}) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <aside
        role="dialog"
        onClick={(e) => e.stopPropagation()}
        className={`flex h-full w-full flex-col bg-white ${wide ? 'max-w-3xl' : 'max-w-xl'}`}
      >
        <div className="flex items-center gap-2 border-b border-line px-5 py-3">
          <h2 className="min-w-0 flex-1 truncate text-lg font-semibold text-navy">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Đóng"
            className="flex h-11 w-11 items-center justify-center rounded-[10px] hover:bg-page"
          >
            <X size={20} />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
      </aside>
    </div>
  )
}

export function JsonBlock({ value, highlight }: { value: unknown; highlight?: Set<string> }) {
  if (value && typeof value === 'object' && !Array.isArray(value) && highlight?.size) {
    // Tô vàng các khóa do hệ thống tiêm (ma_sv, ma_khoa)
    const entries = Object.entries(value as Record<string, unknown>)
    return (
      <pre className="overflow-x-auto rounded-xl bg-slate-900 p-3 text-xs leading-relaxed text-slate-100">
        {'{\n'}
        {entries.map(([k, v], i) => (
          <span key={k} className={highlight.has(k) ? 'bg-accent/40 text-white' : undefined}>
            {`  ${JSON.stringify(k)}: ${JSON.stringify(v)}${i < entries.length - 1 ? ',' : ''}\n`}
          </span>
        ))}
        {'}'}
      </pre>
    )
  }
  return (
    <pre className="overflow-x-auto rounded-xl bg-slate-900 p-3 text-xs leading-relaxed text-slate-100">
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}

export const inputClass =
  'h-10 rounded-[10px] border border-line bg-white px-3 text-sm outline-none focus:border-primary'
export const primaryButton =
  'inline-flex h-10 items-center justify-center gap-2 rounded-[10px] bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50'
export const secondaryButton =
  'inline-flex h-10 items-center justify-center gap-2 rounded-[10px] border border-line bg-white px-4 text-sm font-medium hover:bg-page disabled:opacity-50'

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs font-medium text-slate-500">{label}</span>
      {children}
    </label>
  )
}

/** Ô mật khẩu tạm: hiện rõ chữ (quản trị viên cần đọc lại để giao cho sinh viên). */
export function PasswordInput({
  value,
  onChange,
}: {
  value: string
  onChange: (value: string) => void
}) {
  const problem = value ? passwordProblem(value) : null
  return (
    <Field label="Mật khẩu tạm">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="new-password"
        className={`${inputClass} w-full font-mono`}
        placeholder="Ít nhất 8 ký tự, có chữ và số"
      />
      {problem && <span className="mt-1 block text-xs text-err">{problem}</span>}
    </Field>
  )
}