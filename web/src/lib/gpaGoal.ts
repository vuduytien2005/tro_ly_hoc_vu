// "Học tập của em": điểm trung bình cần đạt học kỳ tới để lên / giữ một mức xếp loại.
// Ngưỡng theo kho hỏi đáp của Phòng Đào tạo ("Xếp loại học lực theo điểm trung bình", thang 4).
// Ước tính đơn giản: điểm tích lũy mới = (GPA × tín chỉ đã tích lũy + điểm kỳ tới × tín chỉ kỳ
// tới) / tổng tín chỉ — chưa tính học lại / cải thiện (điểm cũ bị thay thế).

export const GPA_CLASSES = [
  { label: 'Xuất sắc', min: 3.6 },
  { label: 'Giỏi', min: 3.2 },
  { label: 'Khá', min: 2.5 },
  { label: 'Trung bình', min: 2.0 },
] as const

export function classify(gpa: number): string {
  return GPA_CLASSES.find((c) => gpa >= c.min)?.label ?? 'Yếu'
}

/** Sai số dấu phẩy động (3.2 × 60 = 192.00000000000003) không được làm tròn lên thêm một bậc. */
const EPS = 1e-6

export type GpaGoal =
  /** Kỳ tới cần đạt ít nhất `needed` (≤ 4) */
  | { kind: 'can_dat'; needed: number }
  /** Đã đạt; kỳ tới chỉ cần ≥ `needed` để không tụt (0 = điểm nào cũng giữ được) */
  | { kind: 'giu'; needed: number }
  /** Một kỳ không đủ: cần `semesters` kỳ liên tiếp đạt 4.0 (null = không bao giờ, mục tiêu 4.0) */
  | { kind: 'qua_suc'; semesters: number | null }

export function gpaGoal(
  gpa: number,
  credits: number,
  target: number,
  nextCredits: number,
): GpaGoal | null {
  if (!Number.isFinite(nextCredits) || nextCredits <= 0) return null
  const raw = (target * (credits + nextCredits) - gpa * credits) / nextCredits
  const needed = Math.max(0, Math.ceil(raw * 100 - EPS) / 100)
  if (gpa >= target) return { kind: 'giu', needed }
  if (needed <= 4) return { kind: 'can_dat', needed }
  if (target >= 4) return { kind: 'qua_suc', semesters: null }
  const semesters = Math.ceil(((target - gpa) * credits) / ((4 - target) * nextCredits) - EPS)
  return { kind: 'qua_suc', semesters }
}
