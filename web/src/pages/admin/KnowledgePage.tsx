// Tri thức — lỗ hổng tri thức + kho hỏi đáp cán bộ (thiết kế 2026-11-25-kho-hoi-dap-va-lo-hong-tri-thuc).
// Vòng khép kín: trợ lý thiếu căn cứ / sinh viên hỏi cán bộ / đánh giá 👎 -> cán bộ viết câu trả lời
// (đã bỏ thông tin cá nhân) -> kho được lập chỉ mục -> trợ lý trả lời được, có trích dẫn.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  BookPlus,
  CheckCircle2,
  Info,
  LoaderCircle,
  Pencil,
  ShieldAlert,
  Trash2,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'
import {
  Badge,
  Card,
  Drawer,
  Field,
  PageHeader,
  inputClass,
  primaryButton,
  secondaryButton,
} from '../../components/admin/ui'
import { toQuery } from '../../lib/admin'
import { DEPARTMENTS, REQUEST_STATUS } from '../../lib/adminTypes'
import { ApiError, api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import {
  GAP_SOURCES,
  type Gap,
  type GapList,
  type GapSource,
  type KnowledgeDraft,
  type KnowledgeEntry,
  type KnowledgeList,
  draftProblem,
  gapToDraft,
  personalInfoProblem,
} from '../../lib/knowledge'

const KB_KEY = ['admin', 'knowledge']
const GAPS_KEY = ['admin', 'knowledge', 'gaps']
type Tab = 'lo-hong' | 'kho'

const errorText = (err: unknown, fallback: string) =>
  err instanceof ApiError ? err.message : fallback

/** Bản nháp mở form: thêm mới (có thể điền sẵn) hoặc sửa một mục. */
type Editing = { draft: KnowledgeDraft; id?: number }

export default function KnowledgePage() {
  const location = useLocation()
  const navigate = useNavigate()
  const incoming = (location.state as { draft?: KnowledgeDraft } | null)?.draft
  const [tab, setTab] = useState<Tab>(incoming ? 'kho' : 'lo-hong')
  const [editing, setEditing] = useState<Editing | null>(incoming ? { draft: incoming } : null)

  // Đã nhận bản nháp từ trang Đơn từ -> xóa khỏi lịch sử (tải lại trang không mở lại form)
  useEffect(() => {
    if (incoming) navigate(location.pathname, { replace: true, state: null })
  }, [incoming, navigate, location.pathname])

  const startDraft = (draft: KnowledgeDraft) => setEditing({ draft })

  return (
    <>
      <PageHeader title="Tri thức">
        <button
          className={primaryButton}
          onClick={() => startDraft({ cau_hoi: '', tra_loi: '', phong_ban: 'khac' })}
        >
          <BookPlus size={16} /> Thêm hỏi–đáp
        </button>
      </PageHeader>

      <p className="mb-4 flex items-start gap-2 rounded-xl bg-primary/5 px-3 py-2 text-sm text-slate-600">
        <Info size={16} className="mt-0.5 shrink-0 text-primary" />
        Những câu trợ lý chưa trả lời được có căn cứ, câu hỏi sinh viên gửi cán bộ và câu trả lời bị
        đánh giá chưa đúng. Viết câu trả lời vào kho hỏi đáp để trợ lý trả lời được cho mọi sinh viên
        lần sau (có trích dẫn "Hỏi đáp cán bộ").
      </p>

      <div role="tablist" className="mb-4 flex gap-1 border-b border-line">
        {(
          [
            ['lo-hong', 'Lỗ hổng tri thức'],
            ['kho', 'Kho hỏi đáp'],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            role="tab"
            aria-selected={tab === value}
            onClick={() => setTab(value)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === value
                ? 'border-primary text-primary'
                : 'border-transparent text-slate-500 hover:text-navy'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'lo-hong' ? (
        <GapsTab onDraft={startDraft} />
      ) : (
        <KnowledgeTab onEdit={(e) => setEditing({ draft: e, id: e.id })} />
      )}

      {editing && (
        <EntryDrawer
          editing={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            setTab('kho')
          }}
        />
      )}
    </>
  )
}

// ----- Lỗ hổng tri thức -------------------------------------------------------------
function GapsTab({ onDraft }: { onDraft: (d: KnowledgeDraft) => void }) {
  const [days, setDays] = useState(30)
  const [source, setSource] = useState<GapSource | ''>('')
  const gaps = useQuery({
    queryKey: [...GAPS_KEY, days],
    queryFn: () => api<GapList>(`/api/admin/knowledge/gaps${toQuery({ ngay: days })}`),
  })
  const items = gaps.data?.muc.filter((m) => !source || m.nguon === source) ?? []

  return (
    <>
      <Card className="mb-4 flex flex-wrap items-end gap-3 p-4">
        <Field label="Khoảng thời gian">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className={inputClass}
          >
            {[7, 30, 90, 365].map((d) => (
              <option key={d} value={d}>
                {d} ngày gần đây
              </option>
            ))}
          </select>
        </Field>
        <div className="flex flex-wrap gap-2">
          {(Object.keys(GAP_SOURCES) as GapSource[]).map((key) => (
            <button
              key={key}
              title={GAP_SOURCES[key].hint}
              aria-pressed={source === key}
              onClick={() => setSource((s) => (s === key ? '' : key))}
              className={`${secondaryButton} ${source === key ? 'border-primary bg-primary/5' : ''}`}
            >
              {GAP_SOURCES[key].label}
              <Badge className={GAP_SOURCES[key].className}>{gaps.data?.dem[key] ?? '…'}</Badge>
            </button>
          ))}
        </div>
      </Card>

      {gaps.data?.nguon_loi.includes('hoi_can_bo') && (
        <p role="status" className="mb-3 rounded-[10px] bg-warn-bg px-3 py-2 text-sm text-warn">
          Không lấy được câu hỏi gửi cán bộ (hệ thống quản lý sinh viên chưa chạy); hai nguồn còn lại
          vẫn hiển thị.
        </p>
      )}
      {gaps.isError && (
        <p role="alert" className="mb-3 rounded-[10px] bg-err-bg px-3 py-2 text-sm text-err">
          {errorText(gaps.error, 'Không tải được lỗ hổng tri thức.')}
        </p>
      )}
      {gaps.isPending && <p className="text-sm text-slate-500">Đang tải…</p>}
      {gaps.data && items.length === 0 && (
        <Card className="p-6 text-sm text-slate-500">
          Không có lỗ hổng nào trong khoảng thời gian này. 🎉
        </Card>
      )}

      <div className="space-y-3">
        {items.map((g, i) => (
          <GapCard key={`${g.nguon}-${g.tin_nhan_id ?? g.ma_don}-${i}`} gap={g} onDraft={onDraft} />
        ))}
      </div>
    </>
  )
}

function GapCard({ gap, onDraft }: { gap: Gap; onDraft: (d: KnowledgeDraft) => void }) {
  const src = GAP_SOURCES[gap.nguon]
  return (
    <Card className="p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <Badge className={src.className}>{src.label}</Badge>
        <span>{formatDateTime(gap.thoi_gian)}</span>
        {gap.ma_don && <span className="font-mono">{gap.ma_don}</span>}
        {gap.trang_thai && (
          <Badge className={REQUEST_STATUS[gap.trang_thai]?.className ?? 'bg-slate-100'}>
            {REQUEST_STATUS[gap.trang_thai]?.label ?? gap.trang_thai}
          </Badge>
        )}
        {gap.phong_ban && <span>{DEPARTMENTS[gap.phong_ban] ?? gap.phong_ban}</span>}
        {gap.da_vao_kho && (
          <Badge className="bg-ok-bg text-ok">
            <CheckCircle2 size={12} className="mr-1" /> Đã có trong kho
          </Badge>
        )}
      </div>
      {gap.cau_hoi && (
        <p className="font-medium text-navy">
          <span className="text-slate-500">Sinh viên hỏi: </span>
          {gap.cau_hoi}
        </p>
      )}
      {gap.nguon !== 'hoi_can_bo' && (
        <p className="mt-1 text-sm">
          <span className="text-slate-500">
            {gap.nguon === 'khong_can_cu' ? 'Ý chưa có căn cứ: ' : 'Trợ lý đã trả lời: '}
          </span>
          <span
            className={gap.nguon === 'khong_can_cu' ? 'underline decoration-warn decoration-dotted' : ''}
          >
            {gap.noi_dung}
          </span>
        </p>
      )}
      {gap.ly_do && (
        <p className="mt-1 text-sm text-slate-600">
          <span className="text-slate-500">
            {gap.nguon === 'danh_gia_xau' ? 'Góp ý của sinh viên: ' : 'Giám khảo: '}
          </span>
          {gap.ly_do}
        </p>
      )}
      {gap.tra_loi_can_bo && (
        <p className="mt-1 text-sm">
          <span className="text-slate-500">Cán bộ đã trả lời: </span>
          {gap.tra_loi_can_bo}
        </p>
      )}
      <div className="mt-3">
        <button className={secondaryButton} onClick={() => onDraft(gapToDraft(gap))}>
          <BookPlus size={15} /> Viết câu trả lời vào kho
        </button>
      </div>
    </Card>
  )
}

// ----- Kho hỏi đáp -------------------------------------------------------------------
function KnowledgeTab({ onEdit }: { onEdit: (e: KnowledgeEntry) => void }) {
  const queryClient = useQueryClient()
  const kb = useQuery({
    queryKey: KB_KEY,
    queryFn: () => api<KnowledgeList>('/api/admin/knowledge'),
    // Đang lập chỉ mục -> hỏi lại mỗi 2 giây đến khi xong
    refetchInterval: (q) => (q.state.data?.van_ban?.trang_thai === 'dang_xu_ly' ? 2000 : false),
  })
  const remove = useMutation({
    mutationFn: (id: number) => api<void>(`/api/admin/knowledge/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KB_KEY }),
  })
  const doc = kb.data?.van_ban

  return (
    <>
      <Card className="mb-4 flex items-center gap-2 p-4 text-sm">
        {!doc ? (
          <span className="text-slate-500">
            Kho chưa có mục nào — trợ lý chưa dùng được kho hỏi đáp.
          </span>
        ) : doc.trang_thai === 'dang_xu_ly' ? (
          <>
            <LoaderCircle size={16} className="animate-spin text-primary" /> Đang lập chỉ mục kho…
          </>
        ) : doc.trang_thai === 'loi' ? (
          <span className="flex items-center gap-2 text-err">
            <AlertTriangle size={16} /> Lập chỉ mục lỗi: {doc.loi} — mở trang Tài liệu để lập chỉ mục
            lại.
          </span>
        ) : (
          <span className="flex items-center gap-2 text-ok">
            <CheckCircle2 size={16} /> Trợ lý đang dùng {doc.so_doan} mục (cập nhật{' '}
            {formatDateTime(doc.updated_at)}).
          </span>
        )}
      </Card>

      {(kb.isError || remove.isError) && (
        <p role="alert" className="mb-3 rounded-[10px] bg-err-bg px-3 py-2 text-sm text-err">
          {errorText(kb.error ?? remove.error, 'Không tải được kho hỏi đáp.')}
        </p>
      )}

      <div className="space-y-3">
        {kb.data?.muc.map((e) => (
          <Card key={e.id} className="p-4">
            <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span>{DEPARTMENTS[e.phong_ban] ?? e.phong_ban}</span>
              <span>· cập nhật {formatDateTime(e.updated_at)}</span>
              {e.ma_don && <span className="font-mono">· từ câu hỏi {e.ma_don}</span>}
              {e.tin_nhan_id != null && <span>· từ câu trả lời thiếu căn cứ</span>}
            </div>
            <p className="font-medium text-navy">{e.cau_hoi}</p>
            <p className="mt-1 whitespace-pre-wrap text-sm">{e.tra_loi}</p>
            <div className="mt-3 flex gap-2">
              <button className={secondaryButton} onClick={() => onEdit(e)}>
                <Pencil size={15} /> Sửa
              </button>
              <button
                className={`${secondaryButton} text-err`}
                disabled={remove.isPending}
                onClick={() => {
                  if (window.confirm('Gỡ mục này khỏi kho? Trợ lý sẽ không dùng nó nữa.'))
                    remove.mutate(e.id)
                }}
              >
                <Trash2 size={15} /> Gỡ
              </button>
            </div>
          </Card>
        ))}
      </div>
    </>
  )
}

// ----- Form thêm / sửa ---------------------------------------------------------------
function EntryDrawer({
  editing,
  onClose,
  onSaved,
}: {
  editing: Editing
  onClose: () => void
  onSaved: () => void
}) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<KnowledgeDraft>(editing.draft)
  const [problem, setProblem] = useState<string | null>(null)
  const set = (key: keyof KnowledgeDraft) => (value: string) =>
    setDraft((d) => ({ ...d, [key]: value }))

  const save = useMutation({
    mutationFn: () => {
      const body = {
        cau_hoi: draft.cau_hoi.trim(),
        tra_loi: draft.tra_loi.trim(),
        phong_ban: draft.phong_ban,
        ma_don: draft.ma_don ?? null,
        tin_nhan_id: draft.tin_nhan_id ?? null,
      }
      return editing.id == null
        ? api<KnowledgeEntry>('/api/admin/knowledge', { method: 'POST', json: body })
        : api<KnowledgeEntry>(`/api/admin/knowledge/${editing.id}`, { method: 'PUT', json: body })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: KB_KEY })
      onSaved()
    },
  })

  const submit = () => {
    const p = draftProblem(draft)
    setProblem(p)
    if (!p) save.mutate()
  }
  const liveWarnings = [
    ['Câu hỏi', personalInfoProblem(draft.cau_hoi)],
    ['Câu trả lời', personalInfoProblem(draft.tra_loi)],
  ].filter(([, p]) => p)

  return (
    <Drawer
      title={editing.id == null ? 'Thêm vào kho hỏi đáp' : 'Sửa mục trong kho'}
      onClose={onClose}
    >
      <p className="mb-4 flex items-start gap-2 rounded-xl bg-warn-bg px-3 py-2 text-sm text-warn">
        <ShieldAlert size={16} className="mt-0.5 shrink-0" />
        Kho trả cho MỌI sinh viên. Viết lại câu hỏi thành câu hỏi chung, bỏ tên, mã sinh viên, số điện
        thoại, email, hoàn cảnh riêng.
      </p>
      <div className="space-y-3">
        <Field label="Câu hỏi (viết chung cho mọi sinh viên)">
          <textarea
            value={draft.cau_hoi}
            onChange={(e) => set('cau_hoi')(e.target.value)}
            rows={3}
            maxLength={1000}
            className={`${inputClass} h-auto w-full py-2`}
            placeholder="Vd: Ký túc xá đóng cửa lúc mấy giờ?"
          />
        </Field>
        <Field label="Câu trả lời của cán bộ">
          <textarea
            value={draft.tra_loi}
            onChange={(e) => set('tra_loi')(e.target.value)}
            rows={6}
            maxLength={4000}
            className={`${inputClass} h-auto w-full py-2`}
            placeholder="Vd: Ký túc xá đóng cửa lúc 23 giờ, kể cả cuối tuần."
          />
        </Field>
        <Field label="Phòng ban trả lời">
          <select
            value={draft.phong_ban}
            onChange={(e) => set('phong_ban')(e.target.value)}
            className={inputClass}
          >
            {Object.entries(DEPARTMENTS).map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        {(draft.ma_don || draft.tin_nhan_id != null) && (
          <p className="text-xs text-slate-500">
            Nguồn:{' '}
            {draft.ma_don
              ? `câu hỏi ${draft.ma_don}`
              : 'câu trả lời thiếu căn cứ / bị đánh giá chưa đúng'}{' '}
            (trang Lỗ hổng sẽ đánh dấu "Đã có trong kho").
          </p>
        )}
        {liveWarnings.map(([field, p]) => (
          <p key={field} className="text-xs text-warn">
            ⚠ {field} có vẻ chứa {p}.
          </p>
        ))}
        {(problem || save.isError) && (
          <p role="alert" className="rounded-[10px] bg-err-bg px-3 py-2 text-sm text-err">
            {problem ?? errorText(save.error, 'Không lưu được, thử lại sau.')}
          </p>
        )}
        <div className="flex gap-2">
          <button className={primaryButton} disabled={save.isPending} onClick={submit}>
            {save.isPending && <LoaderCircle size={15} className="animate-spin" />}
            Lưu và cập nhật trợ lý
          </button>
          <button className={secondaryButton} onClick={onClose}>
            Hủy
          </button>
        </div>
      </div>
    </Drawer>
  )
}
