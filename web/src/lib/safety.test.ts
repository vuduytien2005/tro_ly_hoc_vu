import { describe, expect, it } from 'vitest'
import { ACTION_SEGMENTS, CALL_SEGMENTS, confirmRate, toSegments } from './safety'

describe('toSegments', () => {
  it('bỏ trạng thái bằng 0, tính phần trăm theo tổng, giữ thứ tự định nghĩa', () => {
    const segs = toSegments({ thanh_cong: 3, loi: 0, bi_tu_choi: 1 }, CALL_SEGMENTS)
    expect(segs.map((s) => s.key)).toEqual(['thanh_cong', 'bi_tu_choi'])
    expect(segs.map((s) => s.pct)).toEqual([75, 25])
    expect(segs[0].label).toBe('Thành công')
  })
  it('rỗng khi tổng bằng 0', () => {
    expect(toSegments({ cho: 0, da_huy: 0 }, ACTION_SEGMENTS)).toEqual([])
  })
})

describe('confirmRate', () => {
  it('chỉ tính hành động đã kết thúc (xác nhận / hủy / hết hạn)', () => {
    expect(confirmRate({ cho: 5, cho_bo_sung: 1, da_xac_nhan: 3, da_huy: 1, het_han: 0 })).toBe(
      0.75,
    )
  })
  it('null khi chưa có hành động nào kết thúc', () => {
    expect(
      confirmRate({ cho: 2, cho_bo_sung: 0, da_xac_nhan: 0, da_huy: 0, het_han: 0 }),
    ).toBeNull()
  })
})
