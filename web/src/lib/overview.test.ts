import { describe, expect, it } from 'vitest'
import {
  buildAlerts,
  creditPercent,
  formatVnd,
  groupBySemester,
  nextSemester,
  semesterOptions,
  semesterLabel,
  weekGrid,
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

describe('weekGrid', () => {
  const cls = (ma_lop: string, thu: string, tiet: string) => ({
    ma_lop,
    ten_hp: ma_lop,
    tin_chi: 3,
    thu,
    tiet,
    phong: 'B1',
    giang_vien: 'GV',
  })

  it('Thứ 2–7, tối thiểu 10 tiết, đặt lớp đúng cột và hàng', () => {
    const g = weekGrid([cls('A', 'Thứ 2', '1-3'), cls('B', 'Thứ 5', '7-9')])
    expect(g.days).toEqual(['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7'])
    expect(g.periods).toBe(10)
    expect(g.cells.map((c) => [c.ma_lop, c.col, c.from, c.to])).toEqual([
      ['A', 0, 1, 3],
      ['B', 3, 7, 9],
    ])
  })

  it('thêm Chủ nhật khi có lớp, mở rộng số tiết, bỏ qua dữ liệu lạ', () => {
    const g = weekGrid([
      cls('C', 'Chủ nhật', '10-12'),
      cls('X', 'Thứ hai', '1-2'),
      cls('Y', 'Thứ 3', 'abc'),
    ])
    expect(g.days.at(-1)).toBe('Chủ nhật')
    expect(g.periods).toBe(12)
    expect(g.cells.map((c) => [c.ma_lop, c.col])).toEqual([['C', 6]])
  })
})

describe('nextSemester / semesterOptions', () => {
  it('HK1 -> HK2 cùng năm; HK2 -> HK1 năm sau', () => {
    expect(nextSemester('2026-2027-HK1')).toBe('2026-2027-HK2')
    expect(nextSemester('2026-2027-HK2')).toBe('2027-2028-HK1')
    expect(nextSemester('la')).toBeNull()
  })

  it('học kỳ sau, hiện tại và các kỳ trong bảng điểm — mới nhất trước, không trùng', () => {
    const opts = semesterOptions('2026-2027-HK1', [
      row('A', '2025-2026-HK1'),
      row('B', '2026-2027-HK1'),
      row('C', '2025-2026-HK2'),
    ])
    expect(opts).toEqual(['2026-2027-HK2', '2026-2027-HK1', '2025-2026-HK2', '2025-2026-HK1'])
  })

  it('chưa biết kỳ hiện tại -> chỉ các kỳ trong bảng điểm', () => {
    expect(semesterOptions(undefined, [row('A', '2025-2026-HK1')])).toEqual(['2025-2026-HK1'])
  })
})
