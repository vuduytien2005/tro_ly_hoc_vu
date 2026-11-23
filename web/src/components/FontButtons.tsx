import { AArrowDown, AArrowUp } from 'lucide-react'
import { FONT_SCALES, type FontScale } from '../lib/presentation'

/** Nút A− / A+ đổi cỡ chữ gốc của trang (chế độ trình bày, trang quản trị). */
export function FontButtons({
  scale,
  onScale,
}: {
  scale: FontScale
  onScale: (s: FontScale) => void
}) {
  const index = FONT_SCALES.indexOf(scale)
  return (
    <span className="inline-flex items-center gap-1">
      <button
        type="button"
        aria-label="Thu nhỏ chữ"
        disabled={index <= 0}
        onClick={() => onScale(FONT_SCALES[index - 1])}
        className="rounded-md border border-line p-1 hover:bg-slate-50 disabled:opacity-40"
      >
        <AArrowDown size={16} />
      </button>
      <span className="w-10 text-center text-xs text-slate-500">{scale}%</span>
      <button
        type="button"
        aria-label="Phóng to chữ"
        disabled={index >= FONT_SCALES.length - 1}
        onClick={() => onScale(FONT_SCALES[index + 1])}
        className="rounded-md border border-line p-1 hover:bg-slate-50 disabled:opacity-40"
      >
        <AArrowUp size={16} />
      </button>
    </span>
  )
}
