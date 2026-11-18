import { useMutation } from '@tanstack/react-query'
import { LoaderCircle, Search } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Card, PageHeader, Switch, inputClass, primaryButton } from '../../components/admin/ui'
import type { RagSearchResult } from '../../lib/adminTypes'
import { ApiError, api } from '../../lib/api'

const COHORTS = ['K20', 'K21', 'K22', 'K23', 'K24', 'K25']

const TOGGLES = [
  { key: 'use_vector', label: 'Vector (ngữ nghĩa)' },
  { key: 'use_keyword', label: 'Từ khóa (BM25)' },
  { key: 'use_version_filter', label: 'Lọc phiên bản theo khóa' },
  { key: 'use_rerank', label: 'Rerank (cross-encoder)' },
] as const

type ToggleKey = (typeof TOGGLES)[number]['key']

/** Gọi đúng bộ truy xuất mà trợ lý dùng, bật/tắt từng thành phần để so sánh (minh họa Chương 4). */
export default function RetrievalPage() {
  const [question, setQuestion] = useState('')
  const [cohort, setCohort] = useState('K22')
  const [topK, setTopK] = useState(5)
  const [toggles, setToggles] = useState<Record<ToggleKey, boolean>>({
    use_vector: true,
    use_keyword: true,
    use_version_filter: true,
    use_rerank: false,
  })

  const search = useMutation({
    mutationFn: () =>
      api<RagSearchResult>('/api/admin/rag/search', {
        method: 'POST',
        json: { cau_hoi: question.trim(), ma_khoa: cohort, top_k: topK, ...toggles },
      }),
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    if (question.trim().length >= 2) search.mutate()
  }

  const result = search.data

  return (
    <>
      <PageHeader title="Thử truy xuất" />
      <Card className="mb-5 p-4">
        <form onSubmit={submit} className="space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ví dụ: học lại học phần bị điểm F như thế nào?"
              className={`${inputClass} flex-1`}
              aria-label="Câu hỏi"
            />
            <select
              value={cohort}
              onChange={(e) => setCohort(e.target.value)}
              className={inputClass}
              aria-label="Khóa"
            >
              {COHORTS.map((k) => (
                <option key={k}>{k}</option>
              ))}
            </select>
            <select
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              className={inputClass}
              aria-label="Số đoạn"
            >
              {[3, 5, 8, 10].map((n) => (
                <option key={n} value={n}>
                  {n} đoạn
                </option>
              ))}
            </select>
            <button
              type="submit"
              disabled={search.isPending || question.trim().length < 2}
              className={primaryButton}
            >
              {search.isPending ? (
                <LoaderCircle size={16} className="animate-spin" />
              ) : (
                <Search size={16} />
              )}
              Tìm
            </button>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-3">
            {TOGGLES.map((t) => (
              <label key={t.key} className="flex items-center gap-2 text-sm">
                <Switch
                  checked={toggles[t.key]}
                  label={t.label}
                  onChange={(v) => setToggles((s) => ({ ...s, [t.key]: v }))}
                />
                {t.label}
              </label>
            ))}
          </div>
        </form>
      </Card>

      {search.isError && (
        <p role="alert" className="mb-3 rounded-xl bg-err-bg px-4 py-2 text-sm text-err">
          {search.error instanceof ApiError ? search.error.message : 'Không truy xuất được.'}
        </p>
      )}

      {result && (
        <>
          <p className="mb-3 text-sm text-slate-500">
            {result.doan.length} đoạn · {result.thoi_gian_ms} ms
            {result.ghi_chu.map((n) => (
              <span key={n} className="ml-2 text-warn">
                · {n}
              </span>
            ))}
          </p>
          {result.doan.length === 0 && (
            <Card className="p-6 text-sm text-slate-500">
              Không tìm thấy đoạn nào phù hợp với cấu hình này.
            </Card>
          )}
          <div className="space-y-3">
            {result.doan.map((d) => (
              <Card key={d.doan_id} className="p-4">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
                  <span className="flex h-6 min-w-6 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
                    {d.so}
                  </span>
                  <span className="font-medium text-navy">
                    {d.van_ban} ({d.phien_ban})
                  </span>
                  <span className="text-slate-500">
                    {[d.dieu, d.khoan, d.trang != null ? `trang ${d.trang}` : null]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </div>
                <div className="mb-3 flex flex-wrap gap-2 text-xs">
                  <Score label={toggles.use_rerank && d.diem_rerank != null ? 'Điểm rerank' : 'Điểm RRF'} value={d.diem.toFixed(4)} strong />
                  <Score label="Hạng vector" value={d.hang_vector ?? '—'} />
                  <Score label="Hạng BM25" value={d.hang_tu_khoa ?? '—'} />
                </div>
                <p className="line-clamp-6 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                  {d.noi_dung}
                </p>
              </Card>
            ))}
          </div>
        </>
      )}
    </>
  )
}

function Score({ label, value, strong }: { label: string; value: string | number; strong?: boolean }) {
  return (
    <span
      className={`rounded-lg px-2 py-1 ${strong ? 'bg-primary/10 text-primary' : 'bg-page text-slate-600'}`}
    >
      {label}: <span className="font-semibold tabular-nums">{value}</span>
    </span>
  )
}
