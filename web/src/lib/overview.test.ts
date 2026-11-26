import { describe, expect, it } from 'vitest'
import {
  buildAlerts,
  creditPercent,
  formatVnd,
  groupBySemester,
  semesterLabel,
  type Overview,
  type TranscriptRow,
} from './overview'

const row = (ma_hp: string, hoc_ky: string, diem_chu = 'B', tin_chi = 3): TranscriptRow => ({
  ma_hp,
  ten_hp: ma_hp,
  tin_chi,
  hoc_ky,
  diem_tong_ket: 7,
  diem_chu,
  lan_hoc: 1,
})

const empty: Overview = {
  ho_so: null,
  bang_diem: null,
  tot_nghiep: null,
  thoi_khoa_bieu: null,
  lich_thi: null,
  hoc_phi: null,
  nguon_loi: [],
  tam_dung: [],
}

describe('formatVnd', () => {
  it('dùng dấu chấm ngăn nghìn và đơn vị đ', () => {
    expect(formatVnd(5_000_000)).toBe('5.000.000 đ')
    expect(formatVnd(0)).toBe('0 đ')
  })
})

describe('semesterLabel', () => {
  it('đổi mã học kỳ sang dạng dễ đọc', () => {
    expect(semesterLabel('2025-2026-HK1')).toBe('HK1 năm học 2025-2026')
    expect(semesterLabel('khac')).toBe('khac')
  })
})

describe('groupBySemester', () => {
  it('nhóm theo học kỳ, mới nhất trước, cộng tín chỉ', () => {
    const groups = groupBySemester([
      row('A', '2023-2024-HK1'),
      row('B', '2024-2025-HK2', 'A', 4),
      row('C', '2024-2025-HK2'),
    ])
    expect(groups.map((g) => g.hoc_ky)).toEqual(['2024-2025-HK2', '2023-2024-HK1'])
    expect(groups[0].tin_chi).toBe(7)
    expect(groups[0].rows.map((r) => r.ma_hp)).toEqual(['B', 'C'])
  })
})

describe('creditPercent', () => {
  it('giới hạn 0–100 và an toàn khi yêu cầu = 0', () => {
    expect(creditPercent(19, 38)).toBe(50)
    expect(creditPercent(50, 38)).toBe(100)
    expect(creditPercent(5, 0)).toBe(0)
  })
})

describe('buildAlerts', () => {
  it('không có gì đáng báo thì rỗng', () => {
    expect(buildAlerts(empty)).toEqual([])
  })

  it('cảnh báo học vụ và nợ học phí là khẩn, kèm câu hỏi cho trợ lý', () => {
    const alerts = buildAlerts({
      ...empty,
      bang_diem: {
        ket_qua: [],
        gpa_tich_luy: 1,
        tin_chi_tich_luy: 6,
        canh_bao_hoc_vu: true,
      },
      hoc_phi: {
        hoc_ky: '2026-2027-HK1',
        phai_nop: 7_000_000,
        da_nop: 0,
        con_no: 7_000_000,
        han_nop: '2026-10-15',
        trang_thai: 'chua_nop',
      },
    })
    expect(alerts.map((a) => a.muc_do)).toEqual(['khan', 'khan'])
    expect(alerts[0].tieu_de).toContain('cảnh báo học vụ')
    expect(alerts[1].chi_tiet).toContain('7.000.000 đ')
    expect(alerts.every((a) => a.cau_hoi.length > 0)).toBe(true)
  })

  it('đủ điều kiện tốt nghiệp là tin tốt; thiếu chứng chỉ là cần chú ý', () => {
    const grad = {
      tong_tin_chi_yeu_cau: 38,
      tin_chi_tich_luy: 38,
      gpa: 3.4,
      gpa_toi_thieu: 2,
      hoc_phan_con_thieu: [],
      chung_chi: { ngoai_ngu: true, gdtc: true, gdqp: true },
      du_dieu_kien: true,
    }
    expect(buildAlerts({ ...empty, tot_nghiep: grad }).map((a) => a.muc_do)).toEqual(['tot'])
    const missing = buildAlerts({
      ...empty,
      tot_nghiep: {
        ...grad,
        du_dieu_kien: false,
        chung_chi: { ...grad.chung_chi, ngoai_ngu: false },
      },
    })
    expect(missing).toHaveLength(1)
    expect(missing[0].muc_do).toBe('chu_y')
    expect(missing[0].chi_tiet).toContain('ngoại ngữ')
  })
})
