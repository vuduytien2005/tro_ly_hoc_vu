import { BookOpen, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { citationLocation, citationNumber, linkCitations } from '../../lib/format'
import type { Citation } from '../../lib/types'

/** Câu trả lời dạng markdown; "[n]" thành nút mở popover nguồn. */
export function AnswerText({ text, citations }: { text: string; citations: Citation[] | null }) {
  const byNumber = new Map((citations ?? []).map((c) => [c.so, c]))
  return (
    <div className="prose-chat">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
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
        {linkCitations(text, citations)}
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
              {citation.phien_ban && (
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
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
