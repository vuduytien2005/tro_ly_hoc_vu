// Trang quản trị Sinh viên — khung "Cần chú ý" (GET /api/admin/students/attention).

export type AttentionType = 'canh_bao_hoc_vu' | 'no_hoc_phi' | 'chua_du_dk_tot_nghiep'

export interface AttentionStudent {
  ma_sv: string
  ho_ten: string
  lop: string
  khoa: string
  ly_do: { loai: AttentionType; muc_do: 'khan' | 'chu_y'; chi_tiet: string }[]
}

export interface AttentionList {
  tong: number
  sinh_vien: AttentionStudent[]
}

export const ATTENTION_LABELS: Record<AttentionType, string> = {
  canh_bao_hoc_vu: 'Cảnh báo học vụ',
  no_hoc_phi: 'Nợ học phí',
  chua_du_dk_tot_nghiep: 'Chưa đủ ĐK tốt nghiệp',
}

export function countByType(list: AttentionStudent[]): Record<AttentionType, number> {
  const counts: Record<AttentionType, number> = {
    canh_bao_hoc_vu: 0,
    no_hoc_phi: 0,
    chua_du_dk_tot_nghiep: 0,
  }
  for (const s of list) for (const t of new Set(s.ly_do.map((r) => r.loai))) counts[t] += 1
  return counts
}

export function filterByType(
  list: AttentionStudent[],
  type: AttentionType | '',
): AttentionStudent[] {
  return type ? list.filter((s) => s.ly_do.some((r) => r.loai === type)) : list
}
