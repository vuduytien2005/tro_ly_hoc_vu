import { useMutation } from '@tanstack/react-query'
import { Check, Copy, ThumbsDown, ThumbsUp } from 'lucide-react'
import { useState } from 'react'
import { api } from '../../lib/api'

/** 👍 / 👎 (icon) dưới câu trả lời; 👎 mở ô góp ý. Gửi lại thì backend ghi đè. */
export function Feedback({
  messageId,
  initial,
  copyText,
}: {
  messageId: number
  initial: 1 | -1 | null
  /** Nội dung nút "Sao chép" (đã bỏ Markdown, kèm nguồn) */
  copyText?: string
}) {
  const [copied, setCopied] = useState(false)
  const [score, setScore] = useState<1 | -1 | null>(initial)
  const [asking, setAsking] = useState(false)
  const [note, setNote] = useState('')
  const [thanks, setThanks] = useState(false)

  const send = useMutation({
    mutationFn: (body: { diem: 1 | -1; gop_y?: string }) =>
      api(`/api/messages/${messageId}/feedback`, { method: 'POST', json: body }),
    onSuccess: (_data, body) => {
      setScore(body.diem)
      setThanks(true)
    },
  })

  const button = (value: 1 | -1) =>
    `flex h-9 w-9 items-center justify-center rounded-lg hover:bg-page ${
      score === value ? (value === 1 ? 'text-ok' : 'text-err') : 'text-slate-400'
    }`

  return (
    <div className="mt-2">
      <div className="flex items-center gap-1">
        {copyText && (
          <button
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 hover:bg-page"
            aria-label={copied ? 'Đã sao chép' : 'Sao chép câu trả lời'}
            title={copied ? 'Đã sao chép' : 'Sao chép câu trả lời (kèm nguồn)'}
            onClick={() => {
              const failed = () =>
                window.alert('Trình duyệt không cho sao chép, em bôi đen rồi sao chép nhé.')
              // Không phải localhost / https -> trình duyệt không cấp clipboard
              if (!navigator.clipboard) return failed()
              navigator.clipboard.writeText(copyText).then(() => {
                setCopied(true)
                window.setTimeout(() => setCopied(false), 2000)
              }, failed)
            }}
          >
            {copied ? <Check size={16} className="text-ok" /> : <Copy size={16} />}
          </button>
        )}
        <button
          className={button(1)}
          aria-label="Hữu ích"
          title="Hữu ích"
          aria-pressed={score === 1}
          onClick={() => {
            setAsking(false)
            send.mutate({ diem: 1 })
          }}
        >
          <ThumbsUp size={16} />
        </button>
        <button
          className={button(-1)}
          aria-label="Chưa đúng"
          title="Chưa đúng"
          aria-pressed={score === -1}
          onClick={() => {
            setThanks(false)
            setAsking(true)
          }}
        >
          <ThumbsDown size={16} />
        </button>
        {thanks && !asking && <span className="text-xs text-slate-400">Cảm ơn em đã góp ý!</span>}
        {send.isError && <span className="text-xs text-err">Chưa gửi được, thử lại nhé.</span>}
      </div>
      {asking && (
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <input
            autoFocus
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Câu trả lời chưa đúng ở đâu? (không bắt buộc)"
            className="h-10 flex-1 rounded-[10px] border border-line px-3 text-sm outline-none focus:border-primary"
            maxLength={2000}
          />
          <button
            onClick={() => {
              send.mutate({ diem: -1, gop_y: note.trim() || undefined })
              setAsking(false)
            }}
            className="h-10 rounded-[10px] bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark"
          >
            Gửi góp ý
          </button>
        </div>
      )}
    </div>
  )
}
