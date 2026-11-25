import {
  BookOpen,
  ExternalLink,
  LoaderCircle,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
  UserRound,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../../lib/api'
import { articleNumber, openDocument } from '../../lib/documents'
import { citationLocation, citationNumber, linkCitations } from '../../lib/format'
import type { Citation, Verification } from '../../lib/types'
import { markUnverified, unverifiedIndex, verificationSummary } from '../../lib/verification'
import { isKnowledgeCitation } from '../../lib/knowledge'

/**
 * Câu trả lời dạng markdown; "[n]" thành nút mở popover nguồn; ý giám khảo đánh giá "không có
 * căn cứ" được gạch chân chấm (rê chuột xem lý do).
 */
export function AnswerText({
  text,
  citations,
  verification,
}: {
  text: string
  citations: Citation[] | null
  verification?: Verification | null
}) {
  const byNumber = new Map((citations ?? []).map((c) => [c.so, c]))
  return (
    <div className="prose-chat">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            const u = unverifiedIndex(href)
            if (u != null) {
              const claim = verification?.y[u]
              return (
                <span
                  title={claim?.ly_do ? `Chưa có căn cứ trong văn bản: ${claim.ly_do}` : 'Chưa có căn cứ trong văn bản'}
                  className="underline decoration-warn decoration-dotted decoration-2 underline-offset-4"
                >
                  {children}
                </span>
              )
            }
            const n = citationNumber(href)
            const citation = n != null ? byNumber.get(n) : undefined
            if (citation) return <CitationButton citation={citation} />
            return (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            )
          },
        }}
      >
        {linkCitations(markUnverified(text, verification), citations)}
      </Markdown>
    </div>
  )
}

function CitationButton({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false)
    }
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', esc)
    }
  }, [open])

  return (
    <span ref={ref} className="relative inline-block align-baseline">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={`Nguồn ${citation.so}`}
        className="cite mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-md bg-primary/10 px-1 text-xs font-semibold text-primary hover:bg-primary/20"
      >
        {citation.so}
      </button>
      {open && (
        <span
          role="dialog"
          className="absolute bottom-full left-1/2 z-20 mb-2 block w-72 -translate-x-1/2 rounded-xl border border-line bg-white p-3 text-left text-sm shadow-lg sm:w-80"
        >
          <span className="mb-1 flex items-start gap-2">
            <BookOpen size={16} className="mt-0.5 shrink-0 text-primary" />
            <span className="flex-1 font-semibold text-navy">
              {citation.van_ban}
              {isKnowledgeCitation(citation) && <StaffBadge />}
              {citation.phien_ban && !isKnowledgeCitation(citation) && (
                <span className="font-normal text-slate-500"> ({citation.phien_ban})</span>
              )}
            </span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Đóng"
              className="text-slate-400 hover:text-slate-700"
            >
              <X size={16} />
            </button>
          </span>
          <span className="mb-2 block text-xs text-slate-500">{citationLocation(citation)}</span>
          {citation.trich_doan && (
            <span className="block rounded-lg bg-page p-2 text-[13px] leading-relaxed text-slate-700">
              “{citation.trich_doan}”
            </span>
          )}
        </span>
      )}
    </span>
  )
}

export function SourceList({ citations }: { citations: Citation[] | null }) {
  if (!citations?.length) return null
  return (
    <div className="mt-3 border-t border-line pt-3">
      <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        Nguồn tham khảo
      </p>
      <ul className="grid gap-2 sm:grid-cols-2">
        {citations.map((c) => (
          <li key={c.so} className="flex gap-2 rounded-[10px] border border-line p-2 text-sm">
            <span className="flex h-6 min-w-6 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
              {c.so}
            </span>
            <span className="min-w-0">
              <span className="block truncate font-medium text-navy" title={c.van_ban ?? ''}>
                {c.van_ban}
              </span>
              <span className="block text-xs text-slate-500">{citationLocation(c)}</span>
              {isKnowledgeCitation(c) ? (
                <StaffBadge />
              ) : (
                c.van_ban_id != null && <OpenDocumentButton citation={c} />
              )}
              {c.van_ban_id != null && articleNumber(c.dieu) != null && (
                <ReadArticleButton vanBanId={c.van_ban_id} dieu={articleNumber(c.dieu)!} />
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Trích dẫn từ kho hỏi đáp: câu trả lời của cán bộ đã được biên tập (không có tệp gốc). */
function StaffBadge() {
  return (
    <span className="ml-1 inline-block rounded-full bg-ok-bg px-2 py-0.5 align-middle text-[11px] font-medium text-ok">
      Cán bộ trả lời
    </span>
  )
}

function OpenDocumentButton({ citation }: { citation: Citation }) {
  const [error, setError] = useState<string | null>(null)
  const open = () => {
    setError(null)
    openDocument(citation.van_ban_id!, citation.trang).catch(() =>
      setError('Không mở được văn bản gốc.'),
    )
  }
  return (
    <>
      <button
        type="button"
        onClick={open}
        className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
      >
        <ExternalLink size={12} />
        {citation.trang != null ? `Mở văn bản (trang ${citation.trang})` : 'Mở văn bản'}
      </button>
      {error && <span className="block text-xs text-err">{error}</span>}
    </>
  )
}

interface ArticleOut {
  van_ban_id: number
  so_dieu: number
  noi_dung: string
}

/**
 * Nguyên văn cả Điều ngay dưới nguồn. Backend đọc MCP resource của quy_che (do ỨNG DỤNG đọc,
 * không qua LLM, không tốn lượt gọi công cụ) — xem GET /api/documents/{id}/articles/{so}.
 */
function ReadArticleButton({ vanBanId, dieu }: { vanBanId: number; dieu: number }) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const toggle = () => {
    setOpen((o) => !o)
    if (text != null || open) return
    setError(null)
    api<ArticleOut>(`/api/documents/${vanBanId}/articles/${dieu}`)
      .then((a) => setText(a.noi_dung))
      .catch(() => setError('Không đọc được nguyên văn Điều này.'))
  }
  return (
    <>
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="mt-1 ml-3 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
      >
        <ScrollText size={12} />
        {open ? 'Thu gọn' : `Đọc Điều ${dieu}`}
      </button>
      {open && (
        <span className="mt-1 block max-h-64 overflow-y-auto whitespace-pre-line rounded-lg bg-slate-50 p-2 text-xs leading-relaxed text-slate-700">
          {error ?? text ?? 'Đang tải…'}
        </span>
      )}
    </>
  )
}

/** Dòng kết quả kiểm chứng dưới câu trả lời + nút "Hỏi cán bộ" khi có ý chưa có căn cứ. */
export function VerificationBadge({
  verification,
  verifying,
  onAskStaff,
}: {
  verification: Verification | null | undefined
  verifying?: boolean
  onAskStaff?: () => void
}) {
  if (!verification) {
    return verifying ? (
      <p className="mt-2 flex items-center gap-1.5 text-xs text-slate-500">
        <LoaderCircle size={13} className="animate-spin" /> Đang kiểm chứng với văn bản…
      </p>
    ) : null
  }
  const summary = verificationSummary(verification)
  if (!summary) return null
  const { label, ok } = summary
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
      <span
        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ${
          ok ? 'bg-ok-bg text-ok' : 'bg-warn-bg text-warn'
        }`}
        title={`Mô hình kiểm chứng: ${verification.mo_hinh}`}
      >
        {ok ? <ShieldCheck size={13} /> : <ShieldAlert size={13} />}
        {label}
      </span>
      {!ok && onAskStaff && (
        <button
          type="button"
          onClick={onAskStaff}
          className="inline-flex items-center gap-1 rounded-full border border-line bg-white px-2 py-0.5 text-slate-600 hover:border-primary hover:text-primary"
        >
          <UserRound size={13} /> Hỏi cán bộ
        </button>
      )}
    </div>
  )
}
