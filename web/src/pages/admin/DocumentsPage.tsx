import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileUp, Layers, LoaderCircle, RefreshCw, Trash2, Upload } from 'lucide-react'
import { useRef, useState, type DragEvent, type FormEvent } from 'react'
import {
  Badge,
  Card,
  Drawer,
  PageHeader,
  inputClass,
  primaryButton,
  secondaryButton,
} from '../../components/admin/ui'
import { cohortRange } from '../../lib/admin'
import {
  CHUNK_STRATEGIES,
  DOC_TYPES,
  type ChunkPage,
  type DocumentItem,
} from '../../lib/adminTypes'
import { ApiError, api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'

const STATUS: Record<string, { label: string; className: string }> = {
  dang_xu_ly: { label: 'Đang xử lý', className: 'bg-warn-bg text-warn' },
  da_lap_chi_muc: { label: 'Đã lập chỉ mục', className: 'bg-ok-bg text-ok' },
  loi: { label: 'Lỗi', className: 'bg-err-bg text-err' },
}

const ACCEPT = '.pdf,.docx,.txt'

function errorText(err: unknown): string {
  return err instanceof ApiError ? err.message : 'Có lỗi xảy ra, vui lòng thử lại.'
}

export default function DocumentsPage() {
  const queryClient = useQueryClient()
  const [viewing, setViewing] = useState<DocumentItem | null>(null)
  const docs = useQuery({
    queryKey: ['admin', 'documents'],
    queryFn: () => api<DocumentItem[]>('/api/admin/documents'),
    // Còn văn bản đang lập chỉ mục -> hỏi lại mỗi 2 giây để thấy trạng thái đổi
    refetchInterval: (q) =>
      q.state.data?.some((d) => d.trang_thai === 'dang_xu_ly') ? 2000 : false,
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['admin', 'documents'] })

  const reindex = useMutation({
    mutationFn: (id: number) => api(`/api/admin/documents/${id}/reindex`, { method: 'POST' }),
    onSettled: refresh,
  })
  const remove = useMutation({
    mutationFn: (id: number) => api(`/api/admin/documents/${id}`, { method: 'DELETE' }),
    onSettled: refresh,
  })
  const actionError = reindex.error ?? remove.error

  return (
    <>
      <PageHeader title="Tài liệu" />
      <UploadForm onUploaded={refresh} />

      {actionError && (
        <p role="alert" className="mb-3 rounded-xl bg-err-bg px-4 py-2 text-sm text-err">
          {errorText(actionError)}
        </p>
      )}

      <Card className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="border-b border-line bg-page text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3 font-medium">Văn bản</th>
              <th className="px-4 py-3 font-medium">Áp dụng</th>
              <th className="px-4 py-3 font-medium">Trạng thái</th>
              <th className="px-4 py-3 text-right font-medium">Số đoạn</th>
              <th className="px-4 py-3 font-medium">Cập nhật</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {docs.isPending && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-slate-500">
                  Đang tải…
                </td>
              </tr>
            )}
            {docs.isError && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-err">
                  {errorText(docs.error)}
                </td>
              </tr>
            )}
            {docs.data?.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-slate-500">
                  Chưa có văn bản nào. Tải tệp quy chế lên ở khung phía trên.
                </td>
              </tr>
            )}
            {docs.data?.map((d) => (
              <tr key={d.id} className="align-top">
                <td className="px-4 py-3">
                  <p className="font-medium text-navy">{d.ten}</p>
                  <p className="text-xs text-slate-500">
                    {DOC_TYPES[d.loai] ?? d.loai} · phiên bản {d.phien_ban} · {d.ten_tep}
                  </p>
                  {d.loi && <p className="mt-1 text-xs text-err">{d.loi}</p>}
                </td>
                <td className="whitespace-nowrap px-4 py-3">
                  {cohortRange(d.ap_dung_tu_khoa, d.ap_dung_den_khoa)}
                </td>
                <td className="px-4 py-3">
                  <Badge className={STATUS[d.trang_thai]?.className ?? ''}>
                    {d.trang_thai === 'dang_xu_ly' && (
                      <LoaderCircle size={12} className="mr-1 animate-spin" />
                    )}
                    {STATUS[d.trang_thai]?.label ?? d.trang_thai}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{d.so_doan}</td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                  {formatDateTime(d.updated_at)}
                </td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-1">
                    <IconButton
                      label="Xem các đoạn"
                      disabled={d.so_doan === 0}
                      onClick={() => setViewing(d)}
                    >
                      <Layers size={16} />
                    </IconButton>
                    <IconButton
                      label="Lập chỉ mục lại"
                      disabled={d.trang_thai === 'dang_xu_ly' || reindex.isPending}
                      onClick={() => reindex.mutate(d.id)}
                    >
                      <RefreshCw size={16} />
                    </IconButton>
                    <IconButton
                      label="Xóa"
                      disabled={d.trang_thai === 'dang_xu_ly' || remove.isPending}
                      onClick={() => {
                        if (window.confirm(`Xóa "${d.ten}" (${d.phien_ban}) và toàn bộ vector?`))
                          remove.mutate(d.id)
                      }}
                    >
                      <Trash2 size={16} />
                    </IconButton>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {viewing && <ChunksDrawer doc={viewing} onClose={() => setViewing(null)} />}
    </>
  )
}

function IconButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string
  onClick: () => void
  disabled?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-600 hover:bg-page disabled:opacity-30"
    >
      {children}
    </button>
  )
}

function UploadForm({ onUploaded }: { onUploaded: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [form, setForm] = useState({
    ten: '',
    loai: 'quy_che',
    phien_ban: '',
    ap_dung_tu_khoa: '',
    ap_dung_den_khoa: '',
    ngay_hieu_luc: '',
    chien_luoc_chunk: 'theo_dieu',
  })
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }))

  const upload = useMutation({
    mutationFn: () => {
      const body = new FormData()
      body.append('tep', file!)
      for (const [key, value] of Object.entries(form)) body.append(key, value)
      return api<DocumentItem>('/api/admin/documents', { method: 'POST', body })
    },
    onSuccess: () => {
      setFile(null)
      setForm((f) => ({ ...f, ten: '', phien_ban: '', ngay_hieu_luc: '' }))
      if (inputRef.current) inputRef.current.value = ''
    },
    onSettled: onUploaded,
  })

  function pick(f: File | undefined) {
    if (!f) return
    setFile(f)
    // Gợi ý tên văn bản từ tên tệp nếu chưa nhập
    if (!form.ten) set('ten')(f.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' '))
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    pick(e.dataTransfer.files[0])
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    if (file) upload.mutate()
  }

  return (
    <Card className="mb-5 p-4">
      <form onSubmit={submit} className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className={`flex min-h-36 cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-4 text-center text-sm ${
            dragging ? 'border-primary bg-primary/5' : 'border-line hover:border-primary'
          }`}
        >
          <FileUp className="text-primary" />
          {file ? (
            <>
              <span className="break-all font-medium text-navy">{file.name}</span>
              <span className="text-xs text-slate-500">{(file.size / 1024).toFixed(0)} KB</span>
            </>
          ) : (
            <>
              <span className="font-medium">Kéo thả tệp vào đây hoặc bấm để chọn</span>
              <span className="text-xs text-slate-500">PDF, DOCX, TXT — tối đa 20 MB</span>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => pick(e.target.files?.[0])}
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <Field label="Tên văn bản" className="sm:col-span-2 xl:col-span-2">
            <input
              required
              value={form.ten}
              onChange={(e) => set('ten')(e.target.value)}
              className={`${inputClass} w-full`}
              placeholder="Quy chế đào tạo trình độ đại học"
            />
          </Field>
          <Field label="Loại">
            <select
              value={form.loai}
              onChange={(e) => set('loai')(e.target.value)}
              className={`${inputClass} w-full`}
            >
              {Object.entries(DOC_TYPES).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Phiên bản">
            <input
              required
              value={form.phien_ban}
              onChange={(e) => set('phien_ban')(e.target.value)}
              className={`${inputClass} w-full`}
              placeholder="2023"
            />
          </Field>
          <Field label="Áp dụng từ khóa">
            <input
              value={form.ap_dung_tu_khoa}
              onChange={(e) => set('ap_dung_tu_khoa')(e.target.value)}
              className={`${inputClass} w-full`}
              placeholder="K22 (trống = không giới hạn)"
            />
          </Field>
          <Field label="Áp dụng đến khóa">
            <input
              value={form.ap_dung_den_khoa}
              onChange={(e) => set('ap_dung_den_khoa')(e.target.value)}
              className={`${inputClass} w-full`}
              placeholder="trống = không giới hạn"
            />
          </Field>
          <Field label="Ngày hiệu lực">
            <input
              type="date"
              value={form.ngay_hieu_luc}
              onChange={(e) => set('ngay_hieu_luc')(e.target.value)}
              className={`${inputClass} w-full`}
            />
          </Field>
          <Field label="Cách chia đoạn">
            <select
              value={form.chien_luoc_chunk}
              onChange={(e) => set('chien_luoc_chunk')(e.target.value)}
              className={`${inputClass} w-full`}
            >
              {Object.entries(CHUNK_STRATEGIES).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </Field>
          <div className="flex items-end">
            <button type="submit" disabled={!file || upload.isPending} className={primaryButton}>
              {upload.isPending ? (
                <LoaderCircle size={16} className="animate-spin" />
              ) : (
                <Upload size={16} />
              )}
              Tải lên & lập chỉ mục
            </button>
          </div>
          {upload.isError && (
            <p role="alert" className="text-sm text-err sm:col-span-2 xl:col-span-3">
              {errorText(upload.error)}
            </p>
          )}
          {upload.isSuccess && (
            <p className="text-sm text-ok sm:col-span-2 xl:col-span-3">
              Đã tải lên. Trạng thái sẽ tự cập nhật khi lập chỉ mục xong.
            </p>
          )}
        </div>
      </form>
    </Card>
  )
}

function Field({
  label,
  className = '',
  children,
}: {
  label: string
  className?: string
  children: React.ReactNode
}) {
  return (
    <label className={`block text-sm ${className}`}>
      <span className="mb-1 block font-medium text-slate-700">{label}</span>
      {children}
    </label>
  )
}

function ChunksDrawer({ doc, onClose }: { doc: DocumentItem; onClose: () => void }) {
  const [page, setPage] = useState(1)
  const chunks = useQuery({
    queryKey: ['admin', 'chunks', doc.id, page],
    queryFn: () =>
      api<ChunkPage>(`/api/admin/documents/${doc.id}/chunks?page=${page}&page_size=10`),
    placeholderData: (prev) => prev,
  })
  const totalPages = chunks.data ? Math.max(1, Math.ceil(chunks.data.tong / 10)) : 1

  return (
    <Drawer title={`${doc.ten} (${doc.phien_ban})`} onClose={onClose} wide>
      {chunks.isError && <p className="text-sm text-err">{errorText(chunks.error)}</p>}
      <div className="space-y-3">
        {chunks.data?.doan.map((c) => (
          <div key={c.id} className="rounded-xl border border-line p-3">
            <p className="mb-1 flex flex-wrap gap-x-3 text-xs text-slate-500">
              <span className="font-medium text-navy">#{c.thu_tu}</span>
              {c.dieu && <span>{c.dieu}</span>}
              {c.khoan && <span>{c.khoan}</span>}
              {c.trang != null && <span>trang {c.trang}</span>}
              {c.so_token != null && <span>{c.so_token} token</span>}
            </p>
            <p className="whitespace-pre-wrap text-sm leading-relaxed">{c.noi_dung}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 flex items-center justify-between text-sm">
        <span className="text-slate-500">
          {chunks.data ? `${chunks.data.tong} đoạn · trang ${page}/${totalPages}` : 'Đang tải…'}
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
    </Drawer>
  )
}
