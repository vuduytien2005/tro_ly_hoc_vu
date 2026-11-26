import { CircleCheck, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { createPortal } from 'react-dom'
import { changePasswordProblem } from '../lib/account'
import { ApiError, api } from '../lib/api'
import { useEscape } from '../lib/useEscape'

const inputClass =
  'h-10 w-full rounded-[10px] border border-line bg-white px-3 text-sm text-slate-800 focus:border-primary focus:outline-none'

/** Hộp thoại đổi mật khẩu của chính mình (sinh viên và quản trị viên dùng chung). */
export default function ChangePasswordDialog({ onClose }: { onClose: () => void }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)
  useEscape(onClose)

  async function submit(e: FormEvent) {
    e.preventDefault()
    const problem = changePasswordProblem(current, next, confirm)
    if (problem) {
      setError(problem)
      return
    }
    setSaving(true)
    setError(null)
    try {
      await api('/api/auth/change-password', {
        method: 'POST',
        json: { mat_khau_cu: current, mat_khau_moi: next },
      })
      setDone(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Không đổi được mật khẩu, vui lòng thử lại.')
    } finally {
      setSaving(false)
    }
  }

  // Portal: menu bên trái trượt bằng transform -> `fixed` bên trong sẽ bị kẹp theo menu
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-labelledby="change-password-title"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-2xl bg-white p-5 text-slate-800 shadow-xl"
      >
        <div className="mb-4 flex items-center gap-2">
          <h2 id="change-password-title" className="flex-1 text-lg font-semibold text-navy">
            Đổi mật khẩu
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng"
            className="flex h-9 w-9 items-center justify-center rounded-[10px] hover:bg-page"
          >
            <X size={18} />
          </button>
        </div>
        {done ? (
          <div className="space-y-4">
            <p className="flex items-center gap-2 rounded-xl bg-ok-bg px-3 py-2 text-sm text-ok">
              <CircleCheck size={18} /> Đã đổi mật khẩu. Lần đăng nhập sau dùng mật khẩu mới.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="h-10 w-full rounded-[10px] bg-primary text-sm font-medium text-white hover:opacity-90"
            >
              Xong
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-slate-500">
                Mật khẩu hiện tại
              </span>
              <input
                type="password"
                autoComplete="current-password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                className={inputClass}
                autoFocus
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-slate-500">Mật khẩu mới</span>
              <input
                type="password"
                autoComplete="new-password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
                className={inputClass}
                placeholder="Ít nhất 8 ký tự, có chữ và số"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-medium text-slate-500">
                Nhập lại mật khẩu mới
              </span>
              <input
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className={inputClass}
              />
            </label>
            {error && (
              <p role="alert" className="text-sm text-err">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={saving}
              className="h-10 w-full rounded-[10px] bg-primary text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {saving ? 'Đang lưu…' : 'Đổi mật khẩu'}
            </button>
          </form>
        )}
      </div>
    </div>,
    document.body,
  )
}
