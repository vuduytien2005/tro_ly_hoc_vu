import { describe, expect, it } from 'vitest'
import { nextStatuses, reviewNoteProblem } from './admin'

describe('nextStatuses', () => {
  it('theo đúng máy trạng thái của qlsv_api', () => {
    expect(nextStatuses('moi_tao')).toEqual(['dang_xu_ly', 'da_duyet', 'tu_choi'])
    expect(nextStatuses('dang_xu_ly')).toEqual(['da_duyet', 'tu_choi'])
    expect(nextStatuses('da_duyet')).toEqual(['hoan_tat'])
  })
  it('trạng thái cuối không còn bước nào', () => {
    expect(nextStatuses('tu_choi')).toEqual([])
    expect(nextStatuses('hoan_tat')).toEqual([])
    expect(nextStatuses('la')).toEqual([])
  })
})

describe('reviewNoteProblem', () => {
  it('chỉ bắt buộc ghi chú khi từ chối', () => {
    expect(reviewNoteProblem('tu_choi', '  ')).not.toBeNull()
    expect(reviewNoteProblem('tu_choi', 'Thiếu minh chứng')).toBeNull()
    expect(reviewNoteProblem('da_duyet', '')).toBeNull()
  })
})
