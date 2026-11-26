import { describe, expect, it } from 'vitest'
import { GPA_CLASSES, classify, gpaGoal } from './gpaGoal'

describe('classify', () => {
  it('xếp loại theo ngưỡng thang 4 của trường', () => {
    expect(classify(3.6)).toBe('Xuất sắc')
    expect(classify(3.59)).toBe('Giỏi')
    expect(classify(2.5)).toBe('Khá')
    expect(classify(2.0)).toBe('Trung bình')
    expect(classify(1.99)).toBe('Yếu')
    expect(GPA_CLASSES.map((c) => c.min)).toEqual([3.6, 3.2, 2.5, 2.0])
  })
})

describe('gpaGoal', () => {
  it('điểm cần đạt kỳ tới = (mục tiêu × tổng tín chỉ − điểm hiện có) / tín chỉ kỳ tới, làm tròn lên', () => {
    // 3.0 × 60 = 180; muốn 3.2 trên 75 tín chỉ = 240 -> kỳ tới cần 60/15 = 4.0
    expect(gpaGoal(3.0, 60, 3.2, 15)).toEqual({ kind: 'can_dat', needed: 4 })
    // 2.8 × 90 = 252; muốn 2.9 trên 110 = 319 -> 67/20 = 3.35
    expect(gpaGoal(2.8, 90, 2.9, 20)).toEqual({ kind: 'can_dat', needed: 3.35 })
    // làm tròn LÊN: 2.41 × 30 = 72.3; 2.5 × 45 = 112.5 -> 40.2/15 = 2.68
    expect(gpaGoal(2.41, 30, 2.5, 15)).toEqual({ kind: 'can_dat', needed: 2.68 })
  })

  it('đã đạt và chỉ cần giữ: điểm tối thiểu kỳ tới để không tụt dưới mục tiêu', () => {
    // 3.5 × 60 = 210; giữ 3.2 trên 75 = 240 -> kỳ tới >= 2.0
    expect(gpaGoal(3.5, 60, 3.2, 15)).toEqual({ kind: 'giu', needed: 2 })
    // cao hẳn -> kỳ tới 0 điểm vẫn giữ được
    expect(gpaGoal(3.9, 120, 2.0, 15)).toEqual({ kind: 'giu', needed: 0 })
  })

  it('cần trên 4.0 -> một kỳ không đủ; ước số kỳ liên tiếp đạt 4.0', () => {
    // 2.0 × 60 = 120; mỗi kỳ 4.0 × 15 tín chỉ: sau k kỳ (120 + 60k)/(60 + 15k) >= 3.2 -> k >= 6
    expect(gpaGoal(2.0, 60, 3.2, 15)).toEqual({ kind: 'qua_suc', semesters: 6 })
  })

  it('chưa có tín chỉ tích lũy hoặc tín chỉ kỳ tới không hợp lệ -> null', () => {
    expect(gpaGoal(0, 0, 3.2, 15)).toEqual({ kind: 'can_dat', needed: 3.2 })
    expect(gpaGoal(3, 60, 3.2, 0)).toBeNull()
    expect(gpaGoal(3, 60, 3.2, Number.NaN)).toBeNull()
  })
})
