// Kiểu dữ liệu API quản trị (docs/04-api.md, mục Quản trị).

export type DocStatus = 'dang_xu_ly' | 'da_lap_chi_muc' | 'loi'

export interface DocumentItem {
  id: number
  ten: string
  loai: string
  phien_ban: string
  ap_dung_tu_khoa: number | null
  ap_dung_den_khoa: number | null
  ngay_hieu_luc: string | null
  ten_tep: string
  trang_thai: DocStatus
  chien_luoc_chunk: string
  so_doan: number
  loi: string | null
  created_at: string
  updated_at: string
}

export interface Chunk {
  id: number
  thu_tu: number
  chuong: string | null
  dieu: string | null
  khoan: string | null
  trang: number | null
  so_token: number | null
  noi_dung: string
}

export interface ChunkPage {
  tong: number
  trang_so: number
  so_moi_trang: number
  doan: Chunk[]
}

export interface RagHit {
  so: number
  doan_id: number
  van_ban_id: number
  van_ban: string
  phien_ban: string
  chuong: string | null
  dieu: string | null
  khoan: string | null
  trang: number | null
  noi_dung: string
  diem: number
  hang_vector: number | null
  hang_tu_khoa: number | null
  diem_rerank: number | null
}

export interface RagSearchResult {
  thoi_gian_ms: number
  ghi_chu: string[]
  doan: RagHit[]
}

export interface Tool {
  id: number
  ten: string
  mo_ta: string
  muc_rui_ro: 'doc' | 'ghi' | 'nhay_cam'
  can_xac_nhan: boolean
  bat: boolean
  co_tren_server: boolean
  title: string | null
  mo_ta_day_du: string | null
  tham_so: Record<string, unknown> | null
  chi_doc_theo_server: boolean | null
  duyet: 'da_duyet' | 'moi' | 'thay_doi'
}

export interface McpServerItem {
  id: number
  ten: string
  mo_ta: string
  dia_chi: string
  bat: boolean
  trang_thai: string
  cong_cu: Tool[]
  cong_cu_bi_bo_qua: { ten: string; trung_voi: string }[]
}

export interface ToolPreview {
  ten: string
  title: string | null
  mo_ta: string
  tham_so: Record<string, unknown>
  chi_doc_theo_server: boolean | null
  trung_ten_voi: string | null
}

export interface McpCheckResult {
  cong_cu: ToolPreview[]
}

export interface AuditLog {
  id: number
  created_at: string
  nguoi_dung: { id: number; ho_ten: string; email: string }
  hoi_thoai_id: number | null
  mcp_server: string
  ten_cong_cu: string
  trang_thai: string
  ly_do: string | null
  thoi_gian_ms: number | null
  tham_so: Record<string, unknown>
  tham_so_llm: Record<string, unknown> | null
  da_tiem_ngu_canh: boolean
}

export interface AuditLogDetail extends AuditLog {
  ket_qua: unknown
}

export interface AuditLogPage {
  tong: number
  trang_so: number
  so_moi_trang: number
  luot_goi: AuditLog[]
}

export interface Stats {
  tu: string
  den: string
  so_hoi_thoai: number
  so_cau_hoi: number
  so_danh_gia: number
  so_huu_ich: number
  ti_le_huu_ich: number | null
  thoi_gian_phan_hoi_tb_ms: number | null
  so_luot_goi_cong_cu: number
  top_cong_cu: { ten_cong_cu: string; so_lan: number; so_loi: number }[]
  theo_ngay: { ngay: string; so_cau_hoi: number }[]
  cau_bi_che: {
    tin_nhan_id: number
    hoi_thoai_id: number
    nguoi_dung: string
    cau_hoi: string | null
    cau_tra_loi: string
    gop_y: string | null
    created_at: string
  }[]
}

export const DOC_TYPES: Record<string, string> = {
  quy_che: 'Quy chế',
  so_tay: 'Sổ tay',
  quy_dinh: 'Quy định',
  huong_dan: 'Hướng dẫn',
  thong_bao: 'Thông báo',
}

export const CHUNK_STRATEGIES: Record<string, string> = {
  theo_dieu: 'Theo Điều/Khoản',
  co_dinh: 'Cố định',
  ngu_nghia: 'Ngữ nghĩa',
}

export const RISK_LABELS: Record<string, string> = {
  doc: 'Đọc',
  ghi: 'Ghi',
  nhay_cam: 'Nhạy cảm',
}

export const CALL_STATUS: Record<string, { label: string; className: string }> = {
  thanh_cong: { label: 'Thành công', className: 'bg-ok-bg text-ok' },
  loi: { label: 'Lỗi', className: 'bg-err-bg text-err' },
  bi_tu_choi: { label: 'Bị từ chối', className: 'bg-warn-bg text-warn' },
  cho_xac_nhan: { label: 'Chờ xác nhận', className: 'bg-primary/10 text-primary' },
  da_huy: { label: 'Đã hủy', className: 'bg-slate-100 text-slate-600' },
}

// ----- Tài khoản (AD-09) -----
export interface Account {
  id: number
  email: string
  ho_ten: string
  vai_tro: 'sinh_vien' | 'admin'
  ma_sv: string | null
  ma_khoa: string | null
  dang_hoat_dong: boolean
  created_at: string
}

export interface AccountPage {
  tong: number
  trang_so: number
  so_moi_trang: number
  nguoi_dung: Account[]
}

export const ROLE_LABELS: Record<string, string> = {
  sinh_vien: 'Sinh viên',
  admin: 'Quản trị',
}

// ----- Hồ sơ sinh viên trên QLSV (AD-10) -----
// type (không phải interface) để gán được cho Record<string, string> (changedFields)
export type StudentFields = {
  ho_ten: string
  email: string
  ngay_sinh: string
  gioi_tinh: string
  ma_nganh: string
  ma_khoa: string
  lop: string
  trang_thai: string
}

export interface StudentRecord {
  ma_sv: string
  ho_ten: string
  email: string
  ngay_sinh: string
  gioi_tinh: string
  lop: string
  ma_nganh: string
  nganh: string
  khoa: string
  trang_thai: string
  tai_khoan: { id: number; dang_hoat_dong: boolean } | null
}

export interface StudentPage {
  tong: number
  trang_so: number
  so_moi_trang: number
  sinh_vien: StudentRecord[]
}

export interface Program {
  ma_nganh: string
  ten_nganh: string
  ma_khoa: string
}

export interface StudentCreateResult {
  sinh_vien: StudentRecord
  tai_khoan: Account | null
  canh_bao: string | null
}

export const GENDER_LABELS: Record<string, string> = { nam: 'Nam', nu: 'Nữ', khac: 'Khác' }

export const STUDENT_STATUS: Record<string, { label: string; className: string }> = {
  dang_hoc: { label: 'Đang học', className: 'bg-ok-bg text-ok' },
  bao_luu: { label: 'Bảo lưu', className: 'bg-warn-bg text-warn' },
  thoi_hoc: { label: 'Thôi học', className: 'bg-err-bg text-err' },
  tot_nghiep: { label: 'Tốt nghiệp', className: 'bg-primary/10 text-primary' },
}
