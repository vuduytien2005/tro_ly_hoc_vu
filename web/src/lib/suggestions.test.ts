import { describe, expect, it } from 'vitest'
import type { Overview, TranscriptRow } from './overview'
import { DEFAULT_SUGGESTIONS, MAX_SUGGESTIONS, suggestionsFor } from './suggestions'

const row = (ma_hp: string, ten_hp: string, diem_chu: string, hoc_ky: string): TranscriptRow => ({
  ma_hp,
  ten_hp,
  tin_chi: 3,
  hoc_ky,
  diem_tong_ket: diem_chu === 'F' ? 3 : 8,
  diem_chu,
  lan_hoc: 1,
})

const base: Overview = {
  ho_so: { ho_ten: 'A', lop: 'L', nganh: 'CNPM', khoa: 'K22', trang_thai: 'dang_hoc' },
  bang_diem: {
    ket_qua: [row('IT001', 'Nhập môn lập trình', 'B', '2023-2024-HK1')],
    gpa_tich_luy: 3,
    tin_chi_tich_luy: 20,
    canh_bao_hoc_vu: false,
  },
  tot_nghiep: null,
  thoi_khoa_bieu: null,
  lich_thi: null,
  hoc_phi: null,
  nguon_loi: [],
  tam_dung: [],
}

const texts = (o: Overview | undefined) => suggestionsFor(o).map((s) => s.text)

describe('suggestionsFor', () => {
  it('chưa có dữ liệu -> bộ gợi ý mặc định, không đánh dấu cá nhân', () => {
    const s = suggestionsFor(undefined)
    expect(s.map((x) => x.text)).toEqual(DEFAULT_SUGGESTIONS.slice(0, MAX_SUGGESTIONS))
    expect(s.every((x) => !x.personal)).toBe(true)
  })

  it('luôn đủ số gợi ý, không trùng', () => {
    const t = texts(base)
    expect(t).toHaveLength(MAX_SUGGESTIONS)
    expect(new Set(t).size).toBe(t.length)
  })

  it('cảnh báo học vụ đứng đầu, kèm môn F chưa học lại', () => {
    const s = suggestionsFor({
      ...base,
      bang_diem: {
        ket_qua: [
          row('IT001', 'Nhập môn lập trình', 'F', '2023-2024-HK1'),
          row('IT002', 'Lập trình hướng đối tượng', 'F', '2024-2025-HK1'),
          row('IT002', 'Lập trình hướng đối tượng', 'C', '2025-2026-HK1'), // đã học lại đạt
        ],
        gpa_tich_luy: 1,
        tin_chi_tich_luy: 6,
        canh_bao_hoc_vu: true,
      },
    })
    expect(s[0].text).toContain('cảnh báo học vụ')
    expect(s[0].personal).toBe(true)
    expect(s.map((x) => x.text)).toContain('Em học lại môn Nhập môn lập trình thế nào?')
    expect(s.some((x) => x.text.includes('Lập trình hướng đối tượng'))).toBe(false)
  })

  it('nợ học phí, bảo lưu, đủ điều kiện tốt nghiệp đều có câu riêng', () => {
    const t = texts({
      ...base,
      ho_so: { ...base.ho_so!, trang_thai: 'bao_luu' },
      hoc_phi: {
        hoc_ky: '2026-2027-HK1',
        phai_nop: 1,
        da_nop: 0,
        con_no: 1,
        han_nop: null,
        trang_thai: 'chua_nop',
      },
      tot_nghiep: {
        tong_tin_chi_yeu_cau: 38,
        tin_chi_tich_luy: 38,
        gpa: 3,
        gpa_toi_thieu: 2,
        hoc_phan_con_thieu: [],
        chung_chi: { ngoai_ngu: true },
        du_dieu_kien: true,
      },
    })
    expect(t.some((x) => x.includes('học phí'))).toBe(true)
    expect(t.some((x) => x.includes('bảo lưu'))).toBe(true)
    expect(t.some((x) => x.includes('xét tốt nghiệp'))).toBe(true)
  })

  it('thiếu chứng chỉ (chưa đủ điều kiện) hỏi về chứng chỉ', () => {
    const t = texts({
      ...base,
      tot_nghiep: {
        tong_tin_chi_yeu_cau: 38,
        tin_chi_tich_luy: 38,
        gpa: 3,
        gpa_toi_thieu: 2,
        hoc_phan_con_thieu: [],
        chung_chi: { ngoai_ngu: false, gdtc: true },
        du_dieu_kien: false,
      },
    })
    expect(t[0]).toContain('chứng chỉ')
  })

  it('GPA cao gợi ý học bổng; tân sinh viên gợi ý câu nhập môn', () => {
    expect(texts({ ...base, bang_diem: { ...base.bang_diem!, gpa_tich_luy: 3.7 } })[0]).toContain(
      'học bổng',
    )
    const fresh = texts({ ...base, bang_diem: { ...base.bang_diem!, ket_qua: [] } })
    expect(fresh[0]).toContain('tín chỉ')
  })
})
