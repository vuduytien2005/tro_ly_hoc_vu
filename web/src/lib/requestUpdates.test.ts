import { describe, expect, it } from 'vitest'
import { markSeen, snapshot, updatedRequests } from './requestUpdates'

const req = (ma_don: string, ma_trang_thai: string) => ({ ma_don, ma_trang_thai })

describe('updatedRequests', () => {
  it('lần đầu (chưa lưu gì) -> không báo gì, tránh cả loạt đơn cũ hiện "mới"', () => {
    expect(updatedRequests([req('A', 'hoan_tat')], null).size).toBe(0)
  })

  it('đơn đổi trạng thái so với lần xem trước -> báo', () => {
    const seen = { A: 'moi_tao', B: 'dang_xu_ly' }
    const now = [req('A', 'da_duyet'), req('B', 'dang_xu_ly')]
    expect([...updatedRequests(now, seen)]).toEqual(['A'])
  })

  it('đơn em vừa gửi (mới tạo, chưa từng thấy) không tính; đã được xử lý thì tính', () => {
    const seen = {}
    expect(updatedRequests([req('C', 'moi_tao')], seen).size).toBe(0)
    expect([...updatedRequests([req('C', 'tu_choi')], seen)]).toEqual(['C'])
  })
})

describe('snapshot / markSeen', () => {
  it('snapshot ghi trạng thái hiện tại của mọi đơn', () => {
    expect(snapshot([req('A', 'moi_tao'), req('B', 'hoan_tat')])).toEqual({
      A: 'moi_tao',
      B: 'hoan_tat',
    })
  })

  it('markSeen chỉ cập nhật các đơn được xem, giữ nguyên đơn khác', () => {
    const seen = { A: 'moi_tao', B: 'moi_tao' }
    expect(markSeen(seen, [req('A', 'hoan_tat')])).toEqual({ A: 'hoan_tat', B: 'moi_tao' })
    expect(markSeen(null, [req('A', 'hoan_tat')])).toEqual({ A: 'hoan_tat' })
  })
})
