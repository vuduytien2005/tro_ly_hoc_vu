// Hồ sơ sinh viên trên hệ thống QLSV (AD-10) — MÔ PHỎNG phần mềm của phòng đào tạo để demo.
// Mọi thao tác ghi qua API của qlsv_api; sửa hồ sơ thì backend đồng bộ tài khoản trợ lý liên kết.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Info, KeyRound, LoaderCircle, Pencil, UserPlus } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import AttentionPanel from '../../components/admin/AttentionPanel'
import {
  Badge,
  Card,
  Drawer,
  Field,
  PageHeader,
  PasswordInput,
  inputClass,
  primaryButton,
  secondaryButton,
} from '../../components/admin/ui'
import { changedFields, passwordProblem, toQuery } from '../../lib/admin'
import {
  GENDER_LABELS,
  STUDENT_STATUS,
  type Account,
  type Program,
  type StudentCreateResult,
  type StudentFields,
  type StudentPage,
  type StudentRecord,
} from '../../lib/adminTypes'
import { ApiError, api } from '../../lib/api'
import { formatDate } from '../../lib/format'

const PAGE_SIZE = 20
const KEY = ['admin', 'students']

const errorText = (err: unknown, fallback: string) =>
  err instanceof ApiError ? err.message : fallback

type Editing = { mode: 'create' } | { mode: 'edit'; student: StudentRecord }

export default function StudentsPage() {
  const [filters, setFilters] = useState({ q: '', trang_thai: '' })
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState<Editing | null>(null)
  const [granting, setGranting] = useState<StudentRecord | null>(null)
  const set = (key: keyof typeof filters) => (value: string) => {
    setFilters((f) => ({ ...f, [key]: value }))
    setPage(1)
  }

  const students = useQuery({
    queryKey: [...KEY, filters, page],
    queryFn: () =>
      api<StudentPage>(`/api/admin/students${toQuery({ ...filters, page, page_size: PAGE_SIZE })}`),
    placeholderData: (prev) => prev,
  })
  const totalPages = students.data ? Math.max(1, Math.ceil(students.data.tong / PAGE_SIZE)) : 1

  return (
    <>
      <PageHeader title="Sinh viên (hệ thống QLSV)">
        <button className={primaryButton} onClick={() => setEditing({ mode: 'create' })}>
          <UserPlus size={16} /> Thêm sinh viên
        </button>
      </PageHeader>

      <p className="mb-4 flex items-start gap-2 rounded-xl bg-primary/5 px-3 py-2 text-sm text-slate-600">
        <Info size={16} className="mt-0.5 shrink-0 text-primary" />
        Trang này mô phỏng phần mềm của phòng đào tạo: dữ liệu ghi vào hệ thống QLSV (nguồn dữ
        liệu gốc), không phải vào trợ lý. Sinh viên mới chưa có điểm và lịch học.
      </p>

      <AttentionPanel onPick={(maSv) => set('q')(maSv)} />

      <Card className="mb-4 flex flex-wrap items-end gap-3 p-4">
        <Field label="Tìm kiếm">
          <input
            value={filters.q}
            onChange={(e) => set('q')(e.target.value)}
            className={`${inputClass} w-72`}
            placeholder="Mã SV, họ tên, email hoặc lớp"
          />
        </Field>
        <Field label="Trạng thái">
          <select
            value={filters.trang_thai}
            onChange={(e) => set('trang_thai')(e.target.value)}
            className={inputClass}
          >
            <option value="">Tất cả</option>
            {Object.entries(STUDENT_STATUS).map(([v, s]) => (
              <option key={v} value={v}>
                {s.label}
              </option>
            ))}
          </select>
        </Field>
      </Card>

      {students.isError && (
        <p role="alert" className="mb-3 rounded-[10px] bg-err-bg px-3 py-2 text-sm text-err">
          {errorText(students.error, 'Không tải được danh sách sinh viên.')}
        </p>
      )}

      <Card className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-sm">
          <thead className="border-b border-line bg-page text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Sinh viên</th>
              <th className="px-4 py-3 font-medium">Lớp / ngành</th>
              <th className="px-4 py-3 font-medium">Khóa</th>
              <th className="px-4 py-3 font-medium">Trạng thái</th>
              <th className="px-4 py-3 font-medium">Tài khoản trợ lý</th>
              <th className="px-4 py-3 text-right font-medium" />
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {students.data?.sinh_vien.map((s) => (
              <tr key={s.ma_sv}>
                <td className="px-4 py-3">
                  <p className="font-medium">{s.ho_ten}</p>
                  <p className="text-xs text-slate-500">
                    <span className="font-mono text-navy">{s.ma_sv}</span> · {s.email}
                  </p>
                </td>
                <td className="px-4 py-3">
                  <p>{s.lop}</p>
                  <p className="text-xs text-slate-500">{s.nganh}</p>
                </td>
                <td className="px-4 py-3">{s.khoa}</td>
                <td className="px-4 py-3">
                  <Badge className={STUDENT_STATUS[s.trang_thai]?.className ?? ''}>
                    {STUDENT_STATUS[s.trang_thai]?.label ?? s.trang_thai}
                  </Badge>
                </td>
                <td className="px-4 py-3">
                  {s.tai_khoan ? (
                    <Badge
                      className={
                        s.tai_khoan.dang_hoat_dong ? 'bg-ok-bg text-ok' : 'bg-err-bg text-err'
                      }
                    >
                      {s.tai_khoan.dang_hoat_dong ? 'Đã có' : 'Đã khóa'}
                    </Badge>
                  ) : (
                    <button className={secondaryButton} onClick={() => setGranting(s)}>
                      <KeyRound size={15} /> Cấp tài khoản
                    </button>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    className={secondaryButton}
                    onClick={() => setEditing({ mode: 'edit', student: s })}
                  >
                    <Pencil size={15} /> Sửa
                  </button>
                </td>
              </tr>
            ))}
            {students.data?.sinh_vien.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-slate-500">
                  Không có sinh viên nào khớp bộ lọc.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>

      <div className="mt-4 flex items-center justify-between text-sm">
        <span className="text-slate-500">
          {students.data
            ? `${students.data.tong} sinh viên · trang ${page}/${totalPages}`
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

      {editing && <StudentDrawer editing={editing} onClose={() => setEditing(null)} />}
      {granting && <GrantDrawer student={granting} onClose={() => setGranting(null)} />}
    </>
  )
}

const EMPTY: StudentFields = {
  ho_ten: '',
  email: '',
  ngay_sinh: '',
  gioi_tinh: 'nam',
  ma_nganh: '',
  ma_khoa: '',
  lop: '',
  trang_thai: 'dang_hoc',
}

function fieldsOf(s: StudentRecord): StudentFields {
  return {
    ho_ten: s.ho_ten,
    email: s.email,
    ngay_sinh: s.ngay_sinh,
    gioi_tinh: s.gioi_tinh,
    ma_nganh: s.ma_nganh,
    ma_khoa: s.khoa,
    lop: s.lop,
    trang_thai: s.trang_thai,
  }
}

function StudentDrawer({ editing, onClose }: { editing: Editing; onClose: () => void }) {
  const queryClient = useQueryClient()
  const isEdit = editing.mode === 'edit'
  const initial = useMemo(
    () => (editing.mode === 'edit' ? fieldsOf(editing.student) : EMPTY),
    [editing],
  )
  const [form, setForm] = useState<StudentFields>(initial)
  const [maSv, setMaSv] = useState('')
  const [grant, setGrant] = useState(true)
  const [password, setPassword] = useState('')
  const set = (key: keyof StudentFields) => (value: string) => setForm((f) => ({ ...f, [key]: value }))

  const programs = useQuery({
    queryKey: ['admin', 'programs'],
    queryFn: () => api<Program[]>('/api/admin/students/programs'),
    staleTime: Infinity,
  })
  const majors = [...new Map((programs.data ?? []).map((p) => [p.ma_nganh, p.ten_nganh]))]
  const cohorts = (programs.data ?? [])
    .filter((p) => p.ma_nganh === form.ma_nganh)
    .map((p) => p.ma_khoa)

  const save = useMutation({
    mutationFn: async () => {
      if (editing.mode === 'edit') {
        return api<StudentRecord>(`/api/admin/students/${editing.student.ma_sv}`, {
          method: 'PATCH',
          json: changedFields(initial, form),
        })
      }
      return api<StudentCreateResult>('/api/admin/students', {
        method: 'POST',
        json: {
          ...form,
          ma_sv: maSv.trim(),
          ...(grant ? { cap_tai_khoan: true, mat_khau: password } : {}),
        },
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEY })
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })

  const changes = isEdit ? changedFields(initial, form) : null
  const incomplete =
    !isEdit &&
    (!maSv.trim() ||
      Object.values(form).some((v) => !v.trim()) ||
      (grant && !!passwordProblem(password)))
  const nothingChanged = isEdit && Object.keys(changes ?? {}).length === 0

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!incomplete && !nothingChanged) save.mutate()
  }

  if (save.isSuccess) {
    const created = !isEdit ? (save.data as StudentCreateResult) : null
    return (
      <Drawer title={isEdit ? 'Đã lưu hồ sơ' : 'Đã thêm sinh viên'} onClose={onClose}>
        <div className="space-y-4 text-sm">
          <p className="rounded-xl bg-ok-bg px-3 py-2 text-ok">
            {isEdit
              ? 'Đã cập nhật hồ sơ trên hệ thống QLSV. Tài khoản trợ lý (nếu có) đã được đồng bộ họ tên, email và khóa.'
              : `Đã thêm ${created?.sinh_vien.ho_ten} (${created?.sinh_vien.ma_sv}) vào hệ thống QLSV.`}
          </p>
          {created?.tai_khoan && (
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
              <dt className="text-slate-500">Email đăng nhập</dt>
              <dd className="font-mono">{created.tai_khoan.email}</dd>
              <dt className="text-slate-500">Mật khẩu tạm</dt>
              <dd className="font-mono">{password}</dd>
            </dl>
          )}
          {created?.canh_bao && (
            <p className="rounded-xl bg-warn-bg px-3 py-2 text-warn">{created.canh_bao}</p>
          )}
          <button className={primaryButton} onClick={onClose}>
            Xong
          </button>
        </div>
      </Drawer>
    )
  }

  return (
    <Drawer
      title={
        editing.mode === 'edit'
          ? `Sửa hồ sơ · ${editing.student.ma_sv}`
          : 'Thêm sinh viên vào hệ thống QLSV'
      }
      onClose={onClose}
    >
      <form onSubmit={submit} className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-2">
        {isEdit ? (
          <p className="text-slate-500 sm:col-span-2">
            Mã sinh viên không đổi được (tài khoản trợ lý và mọi dữ liệu gắn với mã này).
          </p>
        ) : (
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
        )}
        <Field label="Họ tên">
          <input
            value={form.ho_ten}
            onChange={(e) => set('ho_ten')(e.target.value)}
            className={`${inputClass} w-full`}
            required
          />
        </Field>
        <Field label="Email">
          <input
            type="email"
            value={form.email}
            onChange={(e) => set('email')(e.target.value)}
            className={`${inputClass} w-full`}
            placeholder="sv22004@truong.example"
            required
          />
        </Field>
        <Field label="Ngày sinh">
          <input
            type="date"
            value={form.ngay_sinh}
            onChange={(e) => set('ngay_sinh')(e.target.value)}
            className={`${inputClass} w-full`}
            required
          />
        </Field>
        <Field label="Giới tính">
          <select
            value={form.gioi_tinh}
            onChange={(e) => set('gioi_tinh')(e.target.value)}
            className={`${inputClass} w-full`}
          >
            {Object.entries(GENDER_LABELS).map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Lớp">
          <input
            value={form.lop}
            onChange={(e) => set('lop')(e.target.value)}
            className={`${inputClass} w-full`}
            placeholder="vd KTPM2022"
            required
          />
        </Field>
        <Field label="Ngành">
          <select
            value={form.ma_nganh}
            onChange={(e) => setForm((f) => ({ ...f, ma_nganh: e.target.value, ma_khoa: '' }))}
            className={`${inputClass} w-full`}
            required
          >
            <option value="">— Chọn ngành —</option>
            {majors.map(([ma, ten]) => (
              <option key={ma} value={ma}>
                {ten} ({ma})
              </option>
            ))}
          </select>
        </Field>
        <Field label="Khóa">
          <select
            value={form.ma_khoa}
            onChange={(e) => set('ma_khoa')(e.target.value)}
            className={`${inputClass} w-full`}
            required
            disabled={!form.ma_nganh}
          >
            <option value="">— Chọn khóa —</option>
            {cohorts.map((k) => (
              <option key={k}>{k}</option>
            ))}
          </select>
        </Field>
        <Field label="Trạng thái học tập">
          <select
            value={form.trang_thai}
            onChange={(e) => set('trang_thai')(e.target.value)}
            className={`${inputClass} w-full`}
          >
            {Object.entries(STUDENT_STATUS).map(([v, s]) => (
              <option key={v} value={v}>
                {s.label}
              </option>
            ))}
          </select>
        </Field>

        {isEdit && form.trang_thai !== 'dang_hoc' && initial.trang_thai === 'dang_hoc' && (
          <p className="rounded-xl bg-warn-bg px-3 py-2 text-warn sm:col-span-2">
            Sinh viên không ở trạng thái "Đang học" sẽ không đăng ký học phần và nộp đơn được. Tài
            khoản trợ lý vẫn đăng nhập được — muốn chặn hẳn thì khóa ở trang Tài khoản.
          </p>
        )}
        {isEdit && changes?.ma_khoa && (
          <p className="rounded-xl bg-warn-bg px-3 py-2 text-warn sm:col-span-2">
            Đổi khóa sẽ đổi phiên bản quy chế trợ lý dùng để trả lời sinh viên này.
          </p>
        )}

        {!isEdit && (
          <div className="space-y-3 rounded-xl border border-line p-3 sm:col-span-2">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={grant} onChange={(e) => setGrant(e.target.checked)} />
              Cấp tài khoản trợ lý luôn
            </label>
            {grant && <PasswordInput value={password} onChange={setPassword} />}
          </div>
        )}

        {save.isError && (
          <p role="alert" className="rounded-[10px] bg-err-bg px-3 py-2 text-err sm:col-span-2">
            {errorText(save.error, 'Không lưu được hồ sơ.')}
          </p>
        )}
        <div className="sm:col-span-2">
          <button
            type="submit"
            className={primaryButton}
            disabled={save.isPending || incomplete || nothingChanged}
          >
            {save.isPending && <LoaderCircle size={16} className="animate-spin" />}
            {isEdit ? 'Lưu thay đổi' : 'Thêm sinh viên'}
          </button>
        </div>
      </form>
    </Drawer>
  )
}

function GrantDrawer({ student, onClose }: { student: StudentRecord; onClose: () => void }) {
  const queryClient = useQueryClient()
  const [password, setPassword] = useState('')
  const grant = useMutation({
    mutationFn: () =>
      api<Account>('/api/admin/users', {
        method: 'POST',
        json: { ma_sv: student.ma_sv, mat_khau: password },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KEY })
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!passwordProblem(password)) grant.mutate()
  }

  return (
    <Drawer title={`Cấp tài khoản · ${student.ho_ten}`} onClose={onClose}>
      {grant.isSuccess ? (
        <div className="space-y-4 text-sm">
          <p className="rounded-xl bg-ok-bg px-3 py-2 text-ok">Đã cấp tài khoản.</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
            <dt className="text-slate-500">Email đăng nhập</dt>
            <dd className="font-mono">{grant.data.email}</dd>
            <dt className="text-slate-500">Mật khẩu tạm</dt>
            <dd className="font-mono">{password}</dd>
          </dl>
          <button className={primaryButton} onClick={onClose}>
            Xong
          </button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4 text-sm">
          <p className="text-slate-500">
            {student.ma_sv} · {student.email} · {student.khoa} · sinh ngày{' '}
            {formatDate(student.ngay_sinh)}
          </p>
          <PasswordInput value={password} onChange={setPassword} />
          {grant.isError && (
            <p role="alert" className="rounded-[10px] bg-err-bg px-3 py-2 text-err">
              {errorText(grant.error, 'Không cấp được tài khoản.')}
            </p>
          )}
          <button
            type="submit"
            className={primaryButton}
            disabled={grant.isPending || !!passwordProblem(password)}
          >
            {grant.isPending && <LoaderCircle size={16} className="animate-spin" />}
            Cấp tài khoản
          </button>
        </form>
      )}
    </Drawer>
  )
}
