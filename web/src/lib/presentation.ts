// Chế độ trình bày (demo trước hội đồng): bật/tắt, cỡ chữ, định dạng một bước trong bảng
// "Bên trong Agent". Chỉ hiện khi backend bật CHE_DO_TRINH_BAY (/health.che_do_trinh_bay).
import { useEffect, useRef, useState } from 'react'
import type { TraceStep } from './types'

const MODE_KEY = 'tlhv_trinh_bay'
const FONT_KEY = 'tlhv_co_chu'

export type FontScale = 100 | 115 | 130
export const FONT_SCALES: FontScale[] = [100, 115, 130]

function readFont(): FontScale {
  const v = Number(localStorage.getItem(FONT_KEY))
  return (FONT_SCALES as number[]).includes(v) ? (v as FontScale) : 100
}

export function usePresentationMode(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(() => localStorage.getItem(MODE_KEY) === '1')
  const set = (value: boolean) => {
    localStorage.setItem(MODE_KEY, value ? '1' : '0')
    setOn(value)
  }
  return [on, set]
}

/** Cỡ chữ gốc của trang (html font-size) — mọi kích thước rem phóng theo. */
export function useFontScale(): [FontScale, (s: FontScale) => void] {
  const [scale, setScale] = useState<FontScale>(readFont)
  useEffect(() => {
    document.documentElement.style.fontSize = `${scale}%`
  }, [scale])
  const set = (s: FontScale) => {
    localStorage.setItem(FONT_KEY, String(s))
    setScale(s)
  }
  return [scale, set]
}

/** Id mới xuất hiện so với lần tải trước (cùng `scope`) — để tô nổi bật ~1,2 giây.
 *  Lần tải đầu của một scope (đổi hội thoại / bộ lọc) không tính là "mới". */
export function useFreshIds(ids: number[] | undefined, scope: unknown): Set<number> {
  const prev = useRef<{ scope: unknown; ids: Set<number> | null }>({ scope: undefined, ids: null })
  const [fresh, setFresh] = useState<Set<number>>(() => new Set())
  const key = ids?.join(',')
  useEffect(() => {
    if (key == null) return
    const ids = key === '' ? [] : key.split(',').map(Number)
    const known = prev.current.scope === scope ? prev.current.ids : null
    prev.current = { scope, ids: new Set(ids) }
    const added = known ? ids.filter((id) => !known.has(id)) : []
    if (added.length === 0) return
    setFresh(new Set(added))
    const timer = setTimeout(() => setFresh(new Set()), 1200)
    return () => clearTimeout(timer)
  }, [key, scope])
  return fresh
}

export const traceKey = (conversationId: number | null) => ['trace', conversationId] as const

function show(value: unknown): string {
  if (Array.isArray(value)) return value.map(show).join(', ')
  if (value !== null && typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export interface TraceLines {
  /** "ma_lop=IT004.02, thu=2"; null = hệ thống tự gọi (không qua LLM). */
  llm: string | null
  /** Tham số hệ thống điền; `overridden` = giá trị LLM gửi nhưng bị ghi đè. */
  system: { key: string; value: string; overridden?: string }[]
}

export function traceLines(step: TraceStep): TraceLines {
  const sent = step.tham_so_llm
  const llm =
    sent == null
      ? null
      : Object.entries(sent)
          .map(([k, v]) => `${k}=${show(v)}`)
          .join(', ') || '(không có)'
  const system = Object.entries(step.tham_so_he_thong_dien).map(([key, v]) => {
    const line: { key: string; value: string; overridden?: string } = { key, value: show(v) }
    if (sent != null && key in sent) line.overridden = show(sent[key])
    return line
  })
  return { llm, system }
}
