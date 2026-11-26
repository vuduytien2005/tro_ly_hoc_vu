import { describe, expect, it } from 'vitest'
import type { Stats } from './adminTypes'
import { csvCell, statsFileName, statsToCsv } from './statsCsv'

const stats: Stats = {
  tu: '2026-11-01',
  den: '2026-11-02',
  so_hoi_thoai: 3,
  so_cau_hoi: 10,
  so_danh_gia: 4,
  so_huu_ich: 3,
  ti_le_huu_ich: 0.75,
  thoi_gian_phan_hoi_tb_ms: 2400,
  so_luot_goi_cong_cu: 12,
  top_cong_cu: [{ ten_cong_cu: 'get_transcript', so_lan: 5, so_loi: 1 }],
  theo_ngay: [
    { ngay: '2026-11-01', so_cau_hoi: 4 },
    { ngay: '2026-11-02', so_cau_hoi: 6 },
  ],
  cau_bi_che: [],
  an_toan: {
    trang_thai_goi: { thanh_cong: 9, loi: 1, bi_tu_choi: 1, cho_xac_nhan: 1, da_huy: 0 },
    hanh_dong: { cho: 0, cho_bo_sung: 0, da_xac_nhan: 1, da_huy: 0, het_han: 0 },
    so_lan_chan_ma_sv: 2,
    so_cau_kiem_chung: 3,
    so_menh_de: 8,
    so_co_can_cu: 7,
    ti_le_co_can_cu: 0.875,
  },
}

describe('csvCell', () => {
  it('bọc ngoặc kép khi có dấu phẩy, ngoặc kép hoặc xuống dòng', () => {
    expect(csvCell('abc')).toBe('abc')
    expect(csvCell('a,b')).toBe('"a,b"')
    expect(csvCell('nói "có"')).toBe('"nói ""có"""')
    expect(csvCell('a\nb')).toBe('"a\nb"')
    expect(csvCell(null)).toBe('')
    expect(csvCell(12)).toBe('12')
  })
  it('chặn công thức Excel ở đầu ô', () => {
    expect(csvCell('=1+1')).toBe("'=1+1")
  })
})

describe('statsToCsv', () => {
  const csv = statsToCsv(stats)
  const lines = csv.split('\r\n')

  it('có BOM, khoảng ngày và các nhóm số liệu', () => {
    expect(csv.startsWith('﻿')).toBe(true)
    expect(lines).toContain('Từ ngày,2026-11-01')
    expect(lines).toContain('Tỉ lệ hữu ích (%),75')
    expect(lines).toContain('Lần LLM tự điền mã SV (bị ghi đè),2')
    expect(lines).toContain('Tỉ lệ ý có căn cứ (%),87.5')
    expect(lines).toContain('get_transcript,5,1')
    expect(lines).toContain('2026-11-02,6')
  })

  it('tỉ lệ chưa có dữ liệu để trống', () => {
    const empty = statsToCsv({ ...stats, ti_le_huu_ich: null })
    expect(empty.split('\r\n')).toContain('Tỉ lệ hữu ích (%),')
  })
})

describe('statsFileName', () => {
  it('ghi khoảng ngày vào tên tệp', () => {
    expect(statsFileName(stats)).toBe('thong-ke_2026-11-01_2026-11-02.csv')
  })
})
