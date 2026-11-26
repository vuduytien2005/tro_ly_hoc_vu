import { describe, expect, it } from 'vitest'
import { ACTION_SEGMENTS, CALL_SEGMENTS, confirmRate, modelUsage, toSegments } from './safety'

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

describe('modelUsage', () => {
  it('nhiều câu nhất trước, đánh dấu dự phòng, tỉ lệ dùng dự phòng', () => {
    const u = modelUsage({ 'ollama_chat/qwen2.5:7b': 1, 'gemini/x': 3 }, 'ollama_chat/qwen2.5:7b')
    expect(u.rows).toEqual([
      { model: 'gemini/x', count: 3, share: 0.75, fallback: false },
      { model: 'ollama_chat/qwen2.5:7b', count: 1, share: 0.25, fallback: true },
    ])
    expect(u.total).toBe(4)
    expect(u.fallbackRate).toBe(0.25)
  })

  it('chưa có dữ liệu -> tỉ lệ null; không cấu hình dự phòng -> 0', () => {
    expect(modelUsage({}, 'x').fallbackRate).toBeNull()
    expect(modelUsage({ 'gemini/x': 2 }, null).fallbackRate).toBe(0)
  })
})
