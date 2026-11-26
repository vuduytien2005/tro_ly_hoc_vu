import { describe, expect, it } from 'vitest'
import { countByType, filterByType, type AttentionStudent } from './attention'

const sv = (
  ma_sv: string,
  ...loai: AttentionStudent['ly_do'][number]['loai'][]
): AttentionStudent => ({
  ma_sv,
  ho_ten: ma_sv,
  lop: 'L',
  khoa: 'K22',
  ly_do: loai.map((l) => ({ loai: l, muc_do: 'khan', chi_tiet: '' })),
})

const list = [
  sv('A', 'canh_bao_hoc_vu', 'no_hoc_phi'),
  sv('B', 'no_hoc_phi'),
  sv('C', 'chua_du_dk_tot_nghiep'),
]

describe('countByType', () => {
  it('đếm số sinh viên theo từng loại (một SV nhiều lý do được đếm ở mỗi loại)', () => {
    expect(countByType(list)).toEqual({
      canh_bao_hoc_vu: 1,
      no_hoc_phi: 2,
      chua_du_dk_tot_nghiep: 1,
    })
  })
})

describe('filterByType', () => {
  it('rỗng = tất cả; có loại = chỉ SV có lý do đó', () => {
    expect(filterByType(list, '').map((s) => s.ma_sv)).toEqual(['A', 'B', 'C'])
    expect(filterByType(list, 'no_hoc_phi').map((s) => s.ma_sv)).toEqual(['A', 'B'])
  })
})
