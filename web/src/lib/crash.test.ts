import { describe, expect, it } from 'vitest'
import { crashMessage } from './crash'

describe('crashMessage', () => {
  it('không tải được phần mã của trang (vừa build lại) -> khuyên tải lại trang', () => {
    const chunk = new TypeError(
      'Failed to fetch dynamically imported module: /assets/StatsPage-abc.js',
    )
    expect(crashMessage(chunk)).toMatch(/phiên bản mới/)
    expect(crashMessage(new Error('Importing a module script failed.'))).toMatch(/phiên bản mới/)
  })

  it('lỗi khác -> thông báo chung, không lộ chi tiết kỹ thuật', () => {
    const msg = crashMessage(new Error("Cannot read properties of undefined (reading 'map')"))
    expect(msg).toMatch(/gặp sự cố/)
    expect(msg).not.toMatch(/undefined/)
  })
})
