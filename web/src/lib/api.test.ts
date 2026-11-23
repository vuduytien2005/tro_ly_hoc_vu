import { describe, expect, it } from 'vitest'
import { readCookie } from './api'

describe('readCookie', () => {
  it('đọc đúng cookie theo tên, giải mã giá trị', () => {
    const jar = 'a=1; tlhv_csrf=abc%2Bdef=; theme=dark'
    expect(readCookie('tlhv_csrf', jar)).toBe('abc+def=')
    expect(readCookie('theme', jar)).toBe('dark')
  })
  it('không có cookie -> null (không nhầm tên có tiền tố trùng)', () => {
    expect(readCookie('tlhv_csrf', 'xtlhv_csrf=1')).toBeNull()
    expect(readCookie('tlhv_csrf', '')).toBeNull()
  })
})
