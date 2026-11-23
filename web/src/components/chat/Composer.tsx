import { SendHorizontal } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'

const MAX_HEIGHT = 200

/** Câu điền sẵn từ ngoài (chế độ trình bày); `n` tăng mỗi lần bấm để điền lại cùng một câu. */
export interface Draft {
  text: string
  n: number
}

/** Ô nhập tự giãn: Enter gửi, Shift+Enter xuống dòng. `toolbar` hiện phía trên ô nhập. */
export function Composer({
  disabled,
  onSend,
  draft,
  toolbar,
}: {
  disabled: boolean
  onSend: (text: string) => void
  draft?: Draft | null
  toolbar?: ReactNode
}) {
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  // Điền câu soạn sẵn vào ô nhập (KHÔNG gửi): người trình bày nói xong mới bấm Gửi.
  // Cập nhật state ngay trong lúc render khi `draft` đổi (mẫu "điều chỉnh state theo prop").
  const [seenDraft, setSeenDraft] = useState<Draft | null | undefined>(draft)
  if (draft !== seenDraft) {
    setSeenDraft(draft)
    if (draft) setText(draft.text)
  }
  useEffect(() => {
    if (draft) ref.current?.focus()
  }, [draft])

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`
  }, [text])

  function submit() {
    const value = text.trim()
    if (!value || disabled) return
    onSend(value)
    setText('')
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // isComposing: đang gõ dấu bằng bộ gõ (Unikey/IME) -> Enter không phải lệnh gửi
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="border-t border-line bg-white px-3 pb-3 pt-3 sm:px-6">
      <div className="mx-auto max-w-3xl">
        {toolbar}
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-white p-2 focus-within:border-primary">
          <textarea
            ref={ref}
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            maxLength={2000}
            placeholder="Hỏi về quy chế, điểm, lịch thi, thủ tục…"
            aria-label="Nội dung tin nhắn"
            className="max-h-[200px] min-h-11 flex-1 resize-none bg-transparent px-2 py-2.5 outline-none"
          />
          <button
            onClick={submit}
            disabled={disabled || !text.trim()}
            aria-label="Gửi"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary text-white hover:bg-primary-dark disabled:opacity-40"
          >
            <SendHorizontal size={20} />
          </button>
        </div>
        <p className="mt-2 text-center text-xs text-slate-400">
          Câu trả lời do AI tạo, hãy đối chiếu văn bản gốc.
        </p>
      </div>
    </div>
  )
}
