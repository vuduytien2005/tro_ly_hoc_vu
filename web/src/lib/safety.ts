// Trang Thống kê — mục "An toàn & độ tin cậy": nhãn, màu và phép tính cho các thanh trạng thái.

export interface SegmentDef {
  key: string
  label: string
  /** Lớp màu Tailwind của đoạn thanh và chấm chú thích. */
  color: string
}

export interface Segment extends SegmentDef {
  count: number
  pct: number
}

/** Trạng thái lượt gọi công cụ (bảng luot_goi_cong_cu). */
export const CALL_SEGMENTS: SegmentDef[] = [
  { key: 'thanh_cong', label: 'Thành công', color: 'bg-emerald-500' },
  { key: 'cho_xac_nhan', label: 'Chờ sinh viên xác nhận', color: 'bg-primary' },
  { key: 'bi_tu_choi', label: 'Bị từ chối (tắt / không đủ quyền)', color: 'bg-amber-500' },
  { key: 'loi', label: 'Lỗi', color: 'bg-red-600' },
  { key: 'da_huy', label: 'Đã hủy', color: 'bg-slate-400' },
]

/** Kết cục của hành động cần xác nhận (bảng hanh_dong_cho_xac_nhan). */
export const ACTION_SEGMENTS: SegmentDef[] = [
  { key: 'da_xac_nhan', label: 'Sinh viên xác nhận', color: 'bg-emerald-500' },
  { key: 'da_huy', label: 'Sinh viên hủy', color: 'bg-slate-400' },
  { key: 'het_han', label: 'Hết hạn (quá 10 phút)', color: 'bg-amber-500' },
  { key: 'cho', label: 'Đang chờ', color: 'bg-primary' },
  { key: 'cho_bo_sung', label: 'Chờ bổ sung thông tin', color: 'bg-sky-400' },
]

export function toSegments(counts: Record<string, number>, defs: SegmentDef[]): Segment[] {
  const total = defs.reduce((sum, d) => sum + (counts[d.key] ?? 0), 0)
  if (total === 0) return []
  return defs
    .filter((d) => (counts[d.key] ?? 0) > 0)
    .map((d) => ({
      ...d,
      count: counts[d.key],
      pct: Math.round((counts[d.key] / total) * 1000) / 10,
    }))
}

/** Tỉ lệ sinh viên bấm Xác nhận trên các hành động đã kết thúc. */
export function confirmRate(actions: Record<string, number>): number | null {
  const done = (actions.da_xac_nhan ?? 0) + (actions.da_huy ?? 0) + (actions.het_han ?? 0)
  return done === 0 ? null : (actions.da_xac_nhan ?? 0) / done
}

export interface ModelUsageRow {
  model: string
  count: number
  share: number
  fallback: boolean
}

/** Câu trả lời theo mô hình đã viết: nhiều nhất trước, đánh dấu mô hình dự phòng. */
export function modelUsage(
  byModel: Record<string, number>,
  fallbackModel: string | null,
): { rows: ModelUsageRow[]; total: number; fallbackRate: number | null } {
  const total = Object.values(byModel).reduce((a, b) => a + b, 0)
  const rows = Object.entries(byModel)
    .map(([model, count]) => ({
      model,
      count,
      share: total ? count / total : 0,
      fallback: model === fallbackModel,
    }))
    .sort((a, b) => b.count - a.count || a.model.localeCompare(b.model))
  const used = rows.filter((r) => r.fallback).reduce((a, r) => a + r.count, 0)
  return { rows, total, fallbackRate: total ? used / total : null }
}
