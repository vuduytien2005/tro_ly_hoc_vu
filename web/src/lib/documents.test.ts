import { describe, expect, it } from 'vitest'
import { articleNumber, pageFragment } from './documents'

describe('pageFragment', () => {
  it('PDF có số trang -> #page=N', () => {
    expect(pageFragment('application/pdf', 8)).toBe('#page=8')
  })
  it('không phải PDF hoặc không có trang -> rỗng', () => {
    expect(pageFragment('text/plain; charset=utf-8', 8)).toBe('')
    expect(pageFragment('application/pdf', null)).toBe('')
    expect(pageFragment('application/pdf', 0)).toBe('')
    expect(pageFragment(null, 3)).toBe('')
  })
})

describe('articleNumber', () => {
  it('lấy số Điều từ nhãn', () => {
    expect(articleNumber('Điều 12. Đăng ký học phần')).toBe(12)
    expect(articleNumber('Điều 3')).toBe(3)
  })
  it('không có số Điều -> null', () => {
    expect(articleNumber(null)).toBeNull()
    expect(articleNumber('Chương II')).toBeNull()
  })
})
