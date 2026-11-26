import { describe, expect, it } from 'vitest'
import { lastDaysRange, pendingGapCount, serverRows } from './adminOverview'
import type { Gap } from './knowledge'

describe('lastDaysRange', () => {
  it('7 ngày gần nhất tính cả hôm nay, theo ngày Việt Nam', () => {
    // 23:30 ngày 26 giờ VN = 16:30 ngày 26 UTC; 00:30 ngày 27 VN = 17:30 ngày 26 UTC
    expect(lastDaysRange(7, new Date('2026-11-26T16:30:00Z'))).toEqual({
      tu: '2026-11-20',
      den: '2026-11-26',
    })
    expect(lastDaysRange(7, new Date('2026-11-26T17:30:00Z'))).toEqual({
      tu: '2026-11-21',
      den: '2026-11-27',
    })
  })
})

describe('serverRows', () => {
  it('trạng thái từng MCP server: hoạt động / tắt / gián đoạn, gián đoạn lên đầu', () => {
    const rows = serverRows({ dao_tao: 'ok', thu_vien: 'tắt', quy_che: 'không kết nối được' })
    expect(rows.map((r) => [r.name, r.state])).toEqual([
      ['quy_che', 'loi'],
      ['dao_tao', 'ok'],
      ['thu_vien', 'tat'],
    ])
    expect(rows[0].label).toBe('Tra cứu quy chế')
  })
})

describe('pendingGapCount', () => {
  const gap = (da_vao_kho: boolean): Gap => ({
    nguon: 'khong_can_cu',
    thoi_gian: '2026-11-26T08:00:00+07:00',
    cau_hoi: 'x',
    noi_dung: 'x',
    ly_do: null,
    tra_loi_can_bo: null,
    tin_nhan_id: 1,
    ma_don: null,
    phong_ban: null,
    trang_thai: null,
    da_vao_kho,
  })

  it('chỉ đếm lỗ hổng chưa được đưa vào kho hỏi đáp', () => {
    expect(pendingGapCount([gap(false), gap(true), gap(false)])).toBe(2)
  })
})
