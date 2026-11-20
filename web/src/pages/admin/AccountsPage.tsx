// Quản lý tài khoản (AD-09): cấp tài khoản sinh viên từ mã SV, khóa/mở khóa, đặt lại mật khẩu.
// Họ tên, email, khóa do backend lấy từ hệ thống QLSV — quản trị viên chỉ nhập mã sinh viên.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, LoaderCircle, UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import {
  Badge,
  Card,
  Drawer,
  Field,
  PageHeader,
  PasswordInput,
  Switch,
  inputClass,
  primaryButton,
  secondaryButton,
} from '../../components/admin/ui'
import { passwordProblem, toQuery } from '../../lib/admin'
import { ROLE_LABELS, type Account, type AccountPage } from '../../lib/adminTypes'
import { ApiError, api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { formatDateTime } from '../../lib/format'

const PAGE_SIZE = 20
const KEY = ['admin', 'users']

const errorText = (err: unknown, fallback: string) =>
  err instanceof ApiError ? err.message : fallback

export default function AccountsPage() {
  const { user: me } = useAuth()
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState({ tu_khoa: '', vai_tro: '' })
  const [page, setPage] = useState(1)
  const [creating, setCreating] = useState(false)
  const [resetting, setResetting] = useState<Account | null>(null)
  const [error, setError] = useState<string | null>(null)
  const set = (key: keyof typeof filters) => (value: string) => {
    setFilters((f) => ({ ...f, [key]: value }))
    setPage(1)
  }

  const accounts = useQuery({
    queryKey: [...KEY, filters, page],
    queryFn: () =>
      api<AccountPage>(`/api/admin/users${toQuery({ ...filters, page, page_size: PAGE_SIZE })}`),
    placeholderData: (prev) => prev,
  })
  const totalPages = accounts.data ? Math.max(1, Math.ceil(accounts.data.tong / PAGE_SIZE)) : 1

  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      api<Account>(`/api/admin/users/${id}`, { method: 'PATCH', json: { dang_hoat_dong: active } }),
    onMutate: () => setError(null),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
    onError: (err) => setError(errorText(err, 'Không lưu được thay đổi.')),
  })

  return (
    <>
      <PageHeader title="Tài khoản">
        <button className={primaryButton} onClick={() => setCreating(true)}>
          <UserPlus size={16} /> Cấp tài khoản sinh viên
        </button>
      </PageHeader>

      <Card className="mb-4 flex flex-wrap items-end gap-3 p-4">
        <Field label="Tìm kiếm">
          <input
            value={filters.tu_khoa}
            onChange={(e) => set('tu_khoa')(e.target.value)}
            className={`${inputClass} w-72`}
            placeholder="Email, họ tên hoặc mã sinh viên"
          />
        </Field>
        <Field label="Vai trò">
          <select
            value={filters.vai_tro}
            onChange={(e) => set('vai_tro')(e.target.value)}
            className={inputClass}
          >
            <option value="">Tất cả</option>
            {Object.entries(ROLE_LABELS).map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </Field>
      </Card>

      {(error || accounts.isError) && (
        <p role="alert" className="mb-3 rounded-[10px] bg-err-bg px-3 py-2 text-sm text-err">
          {error ?? errorText(accounts.error, 'Không tải được danh sách tài khoản.')}
        </p>
      )}

      <Card className="overflow-x-auto">
        <table className="w-full min-w-[820px] text-sm">
          <thead className="border-b border-line bg-page text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Người dùng</th>
              <th className="px-4 py-3 font-medium">Mã SV / khóa</th>
              <th className="px-4 py-3 font-medium">Vai trò</th>
              <th className="px-4 py-3 font-medium">Ngày tạo</th>
              <th className="px-4 py-3 font-medium">Hoạt động</th>
              <th className="px-4 py-3 text-right font-medium" />
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {accounts.data?.nguoi_dung.map((a) => {
              const isMe = a.id === me?.id
              return (
                <tr key={a.id} className={a.dang_hoat_dong ? '' : 'bg-slate-50 text-slate-500'}>
                  <td className="px-4 py-3">
                    <p className="font-medium">
                      {a.ho_ten} {isMe && <span className="text-xs text-slate-500">(bạn)</span>}
                    </p>
                    <p className="text-xs text-slate-500">
                      #{a.id} · {a.email}
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    {a.ma_sv ? (
                      <>
                        <p className="font-mono text-[13px] text-navy">{a.ma_sv}</p>
                        <p className="text-xs text-slate-500">{a.ma_khoa}</p>
                      </>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      className={
                        a.vai_tro === 'admin' ? 'bg-navy/10 text-navy' : 'bg-primary/10 text-primary'
                      }
                    >
                      {ROLE_LABELS[a.vai_tro] ?? a.vai_tro}
                    </Badge>
                    {!a.dang_hoat_dong && (
                      <Badge className="ml-1 bg-err-bg text-err">Đã khóa</Badge>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                    {formatDateTime(a.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <Switch
                      checked={a.dang_hoat_dong}
                      disabled={isMe || toggle.isPending}
                      label={
                        isMe
                          ? 'Không thể tự khóa tài khoản đang đăng nhập'
                          : a.dang_hoat_dong
                            ? 'Khóa tài khoản'
                            : 'Mở khóa tài khoản'
                      }
                      onChange={(active) => toggle.mutate({ id: a.id, active })}
                    />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button className={secondaryButton} onClick={() => setResetting(a)}>
                      <KeyRound size={15} /> Đặt lại mật khẩu
                    </button>
                  </td>
                </tr>
              )
            })}
            {accounts.data?.nguoi_dung.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-slate-500">
                  Không có tài khoản nào khớp bộ lọc.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>

      <div className="mt-4 flex items-center justify-between text-sm">
        <span className="text-slate-500">
          {accounts.data
            ? `${accounts.data.tong} tài khoản · trang ${page}/${totalPages}`
            : 'Đang tải…'}
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

      {creating && <CreateDrawer onClose={() => setCreating(false)} />}
      {resetting && <ResetDrawer account={resetting} onClose={() => setResetting(null)} />}
    </>
  )
}

function CreateDrawer({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [maSv, setMaSv] = useState('')
  const [password, setPassword] = useState('')
  const create = useMutation({
    mutationFn: () =>
      api<Account>('/api/admin/users', {
        method: 'POST',
        json: { ma_sv: maSv.trim(), mat_khau: password },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })
  const created = create.data

  function submit(e: FormEvent) {
    e.preventDefault()
    if (maSv.trim() && !passwordProblem(password)) create.mutate()
  }

  return (
    <Drawer title="Cấp tài khoản sinh viên" onClose={onClose}>
      {created ? (
        <div className="space-y-4 text-sm">
          <p className="rounded-xl bg-ok-bg px-3 py-2 text-ok">Đã cấp tài khoản.</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
            <dt className="text-slate-500">Họ tên</dt>
            <dd>{created.ho_ten}</dd>
            <dt className="text-slate-500">Mã SV / khóa</dt>
            <dd>
              {created.ma_sv} · {created.ma_khoa}
            </dd>
            <dt className="text-slate-500">Email đăng nhập</dt>
            <dd className="font-mono">{created.email}</dd>
            <dt className="text-slate-500">Mật khẩu tạm</dt>
            <dd className="font-mono">{password}</dd>
          </dl>
          <p className="text-slate-500">
            Giao email và mật khẩu tạm cho sinh viên. Mật khẩu chỉ hiện lúc này — hệ thống chỉ lưu
            bản băm.
          </p>
          <button className={primaryButton} onClick={onClose}>
            Xong
          </button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4 text-sm">
          <p className="text-slate-500">
            Chỉ cần mã sinh viên. Họ tên, email và khóa học được lấy từ hệ thống quản lý sinh viên,
            nên tài khoản luôn gắn với một sinh viên có thật.
          </p>
          <Field label="Mã sinh viên">
            <input
              value={maSv}
              onChange={(e) => setMaSv(e.target.value.toUpperCase())}
              className={`${inputClass} w-full font-mono`}
              placeholder="vd SV22004"
              required
              autoFocus
            />
          </Field>
          <PasswordInput value={password} onChange={setPassword} />
          {create.isError && (
            <p role="alert" className="rounded-[10px] bg-err-bg px-3 py-2 text-err">
              {errorText(create.error, 'Không cấp được tài khoản.')}
            </p>
          )}
          <button
            type="submit"
            className={primaryButton}
            disabled={create.isPending || !maSv.trim() || !!passwordProblem(password)}
          >
            {create.isPending && <LoaderCircle size={16} className="animate-spin" />}
            Cấp tài khoản
          </button>
        </form>
      )}
    </Drawer>
  )
}

function ResetDrawer({ account, onClose }: { account: Account; onClose: () => void }) {
  const [password, setPassword] = useState('')
  const reset = useMutation({
    mutationFn: () =>
      api<void>(`/api/admin/users/${account.id}/reset-password`, {
        method: 'POST',
        json: { mat_khau: password },
      }),
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!passwordProblem(password)) reset.mutate()
  }

  return (
    <Drawer title={`Đặt lại mật khẩu · ${account.ho_ten}`} onClose={onClose}>
      {reset.isSuccess ? (
        <div className="space-y-4 text-sm">
          <p className="rounded-xl bg-ok-bg px-3 py-2 text-ok">
            Đã đặt lại mật khẩu cho <b>{account.email}</b>. Mật khẩu mới:{' '}
            <span className="font-mono">{password}</span>
          </p>
          <button className={primaryButton} onClick={onClose}>
            Xong
          </button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4 text-sm">
          <p className="text-slate-500">
            Mật khẩu cũ của <b>{account.email}</b> sẽ không dùng được nữa.
          </p>
          <PasswordInput value={password} onChange={setPassword} />
          {reset.isError && (
            <p role="alert" className="rounded-[10px] bg-err-bg px-3 py-2 text-err">
              {errorText(reset.error, 'Không đặt lại được mật khẩu.')}
            </p>
          )}
          <button
            type="submit"
            className={primaryButton}
            disabled={reset.isPending || !!passwordProblem(password)}
          >
            {reset.isPending && <LoaderCircle size={16} className="animate-spin" />}
            Đặt lại mật khẩu
          </button>
        </form>
      )}
    </Drawer>
  )
}
