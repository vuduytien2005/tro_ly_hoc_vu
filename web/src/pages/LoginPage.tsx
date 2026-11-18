import { GraduationCap, LoaderCircle } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { ApiError } from '../lib/api'
import { homeFor, useAuth } from '../lib/auth'

export default function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={homeFor(user.vai_tro)} replace />

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const me = await login(email.trim(), password)
      navigate(homeFor(me.vai_tro), { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Không kết nối được máy chủ.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center p-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-2xl border border-line bg-white p-8"
      >
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-navy text-accent">
            <GraduationCap size={30} />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-navy">Trợ lý học vụ</h1>
            <p className="text-sm text-slate-500">Đăng nhập bằng tài khoản sinh viên</p>
          </div>
        </div>

        <label className="mb-1 block text-sm font-medium" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mb-4 h-11 w-full rounded-[10px] border border-line px-3 outline-none focus:border-primary"
          placeholder="sv22001@truong.example"
        />
        <label className="mb-1 block text-sm font-medium" htmlFor="password">
          Mật khẩu
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-4 h-11 w-full rounded-[10px] border border-line px-3 outline-none focus:border-primary"
        />

        {error && (
          <p role="alert" className="mb-4 rounded-[10px] bg-err-bg px-3 py-2 text-sm text-err">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="flex h-11 w-full items-center justify-center gap-2 rounded-[10px] bg-primary font-medium text-white hover:bg-primary-dark disabled:opacity-60"
        >
          {busy && <LoaderCircle size={18} className="animate-spin" />}
          Đăng nhập
        </button>
      </form>
    </div>
  )
}
