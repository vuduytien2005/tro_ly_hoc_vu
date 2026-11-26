import { useEffect, useRef } from 'react'

/**
 * Bấm Esc -> gọi `onEscape` (đóng hộp thoại / ngăn trượt), trừ khi đang gõ trong ô nhiều dòng.
 * Luôn gọi bản `onEscape` mới nhất.
 */
export function useEscape(onEscape: () => void): void {
  const ref = useRef(onEscape)
  useEffect(() => {
    ref.current = onEscape
  })
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      // Đang soạn nội dung dài (vd câu trả lời của cán bộ) -> không đóng kẻo mất chữ đã gõ
      if (e.target instanceof HTMLTextAreaElement) return
      ref.current()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
}
