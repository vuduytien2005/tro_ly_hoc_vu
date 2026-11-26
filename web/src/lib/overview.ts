// Trang "Học tập của em": kiểu dữ liệu của /api/my/overview và các hàm thuần để hiển thị.
// Mỗi mục có thể null khi công cụ tương ứng đang tắt hoặc lỗi (xem tam_dung, nguon_loi).
import { api } from './api'

export interface Profile {
  ho_ten: string
  lop: string
  nganh: string
  khoa: string
  trang_thai: string
}

export interface TranscriptRow {
  ma_hp: string
  ten_hp: string
  tin_chi: number
  hoc_ky: string
  diem_tong_ket: number | null
  diem_chu: string | null
  lan_hoc: number
}

export interface Transcript {
  ket_qua: TranscriptRow[]
  gpa_tich_luy: number
  tin_chi_tich_luy: number
  canh_bao_hoc_vu: boolean
}

export interface Graduation {
  tong_tin_chi_yeu_cau: number
  tin_chi_tich_luy: number
  gpa: number
  gpa_toi_thieu: number
  hoc_phan_con_thieu: {
    ma_hp: string
    ten_hp: string
    tin_chi: number
    bat_buoc: boolean
  }[]
  chung_chi: Record<string, boolean>
  du_dieu_kien: boolean
}

export interface Schedule {
  hoc_ky: string
  lop: {
    ma_lop: string
    ten_hp: string
    tin_chi: number
    thu: string
    tiet: string
    phong: string
    giang_vien: string
  }[]
  tong_tin_chi: number
}

export interface ExamSchedule {
  hoc_ky: string
  lich_thi: {
    ma_lop: string
    ten_hp: string
    ngay_thi: string
    gio: string
    phong: string
    hinh_thuc: string
  }[]
}

export interface Tuition {
  hoc_ky: string
  phai_nop: number
  da_nop: number
  con_no: number
  han_nop: string | null
  trang_thai: string
}

export interface Overview {
  ho_so: Profile | null
  bang_diem: Transcript | null
  tot_nghiep: Graduation | null
  thoi_khoa_bieu: Schedule | null
  lich_thi: ExamSchedule | null
  hoc_phi: Tuition | null
  nguon_loi: string[]
  tam_dung: string[]
}

export interface Alert {
  muc_do: 'khan' | 'chu_y' | 'tot'
  tieu_de: string
  chi_tiet: string
  /** Câu hỏi điền sẵn vào khung chat khi bấm "Hỏi trợ lý". */
  cau_hoi: string
}

export const CERTIFICATE_LABELS: Record<string, string> = {
  ngoai_ngu: 'Chứng chỉ ngoại ngữ',
  gdtc: 'Giáo dục thể chất',
  gdqp: 'Giáo dục quốc phòng - an ninh',
}

export const STUDENT_STATUS: Record<string, string> = {
  dang_hoc: 'Đang học',
  bao_luu: 'Đang bảo lưu',
  thoi_hoc: 'Thôi học',
  tot_nghiep: 'Đã tốt nghiệp',
}

export const TUITION_STATUS: Record<string, string> = {
  da_nop: 'Đã nộp đủ',
  nop_mot_phan: 'Nộp một phần',
  chua_nop: 'Chưa nộp',
}

const VND = new Intl.NumberFormat('vi-VN')

export function formatVnd(amount: number): string {
  return `${VND.format(amount)} đ`
}

/** "2025-2026-HK1" -> "HK1 năm học 2025-2026". */
export function semesterLabel(code: string): string {
  const m = /^(\d{4}-\d{4})-(HK\d)$/.exec(code)
  return m ? `${m[2]} năm học ${m[1]}` : code
}

export interface SemesterGroup {
  hoc_ky: string
  rows: TranscriptRow[]
  tin_chi: number
}

/** Nhóm bảng điểm theo học kỳ, học kỳ mới nhất lên đầu (mã học kỳ sắp xếp được theo chuỗi). */
export function groupBySemester(rows: TranscriptRow[]): SemesterGroup[] {
  const map = new Map<string, TranscriptRow[]>()
  for (const r of rows) map.set(r.hoc_ky, [...(map.get(r.hoc_ky) ?? []), r])
  return [...map.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([hoc_ky, list]) => ({
      hoc_ky,
      rows: list,
      tin_chi: list.reduce((sum, r) => sum + r.tin_chi, 0),
    }))
}

export function creditPercent(done: number, required: number): number {
  if (required <= 0) return 0
  return Math.max(0, Math.min(100, Math.round((done / required) * 100)))
}

/** Những điều sinh viên cần biết ngay, khẩn trước. */
export function buildAlerts(o: Overview): Alert[] {
  const alerts: Alert[] = []
  if (o.bang_diem?.canh_bao_hoc_vu) {
    alerts.push({
      muc_do: 'khan',
      tieu_de: 'Em đang thuộc diện cảnh báo học vụ',
      chi_tiet: `GPA tích lũy ${o.bang_diem.gpa_tich_luy.toFixed(2)}. Em nên đăng ký học lại các học phần bị F và giảm số tín chỉ đăng ký.`,
      cau_hoi: 'Em bị cảnh báo học vụ thì cần làm gì và được đăng ký tối đa bao nhiêu tín chỉ?',
    })
  }
  if (o.hoc_phi && o.hoc_phi.con_no > 0) {
    const due = o.hoc_phi.han_nop
      ? `, hạn nộp ${o.hoc_phi.han_nop.split('-').reverse().join('/')}`
      : ''
    alerts.push({
      muc_do: 'khan',
      tieu_de: 'Em còn nợ học phí',
      chi_tiet: `Còn nợ ${formatVnd(o.hoc_phi.con_no)} (${semesterLabel(o.hoc_phi.hoc_ky)}${due}).`,
      cau_hoi: 'Em còn nợ học phí bao nhiêu và nộp muộn thì bị xử lý thế nào?',
    })
  }
  const g = o.tot_nghiep
  if (g?.du_dieu_kien) {
    alerts.push({
      muc_do: 'tot',
      tieu_de: 'Em đã đủ điều kiện tốt nghiệp',
      chi_tiet: 'Em có thể theo dõi đợt xét tốt nghiệp gần nhất và chuẩn bị hồ sơ.',
      cau_hoi: 'Em đủ điều kiện tốt nghiệp rồi, thủ tục xét tốt nghiệp gồm những gì?',
    })
  } else if (g) {
    const missing = Object.entries(g.chung_chi)
      .filter(([, ok]) => !ok)
      .map(([k]) => (CERTIFICATE_LABELS[k] ?? k).toLowerCase())
    if (missing.length > 0) {
      alerts.push({
        muc_do: 'chu_y',
        tieu_de: 'Em còn thiếu chứng chỉ để tốt nghiệp',
        chi_tiet: `Chưa có: ${missing.join(', ')}.`,
        cau_hoi: 'Em còn thiếu chứng chỉ gì để tốt nghiệp và nộp ở đâu?',
      })
    }
  }
  return alerts
}

/** Truy vấn dùng chung (trang Học tập + gợi ý ở chat): mỗi lần tải gọi 6 tool -> giữ cache 5 phút. */
export const OVERVIEW_QUERY = {
  queryKey: ['my-overview'],
  queryFn: () => api<Overview>('/api/my/overview'),
  staleTime: 5 * 60_000,
}

export interface GridCell {
  ma_lop: string
  ten_hp: string
  phong: string
  /** Cột 0 = Thứ 2 ... 5 = Thứ 7, 6 = Chủ nhật. */
  col: number
  from: number
  to: number
}

export interface WeekGrid {
  days: string[]
  periods: number
  cells: GridCell[]
}

const WEEKDAYS = ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7']
const MIN_PERIODS = 10

/** Thời khóa biểu dạng lưới tuần. Nhãn thứ / tiết không đọc được -> bỏ qua lớp đó. */
export function weekGrid(classes: Schedule['lop']): WeekGrid {
  const cells: GridCell[] = []
  for (const c of classes) {
    const col = c.thu === 'Chủ nhật' ? 6 : WEEKDAYS.indexOf(c.thu)
    const m = /^(\d+)-(\d+)$/.exec(c.tiet)
    if (col < 0 || !m) continue
    const from = Number(m[1])
    const to = Number(m[2])
    if (from < 1 || to < from) continue
    cells.push({ ma_lop: c.ma_lop, ten_hp: c.ten_hp, phong: c.phong, col, from, to })
  }
  const hasSunday = cells.some((c) => c.col === 6)
  return {
    days: hasSunday ? [...WEEKDAYS, 'Chủ nhật'] : WEEKDAYS,
    periods: Math.max(MIN_PERIODS, ...cells.map((c) => c.to)),
    cells,
  }
}
