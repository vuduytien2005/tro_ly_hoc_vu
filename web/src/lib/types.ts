import type { FormSchema } from './elicitation'

// Kiểu dữ liệu khớp docs/04-api.md (assistant_api).

export type Role = 'sinh_vien' | 'admin'

export interface User {
  id: number
  email: string
  ho_ten: string
  vai_tro: Role
  ma_sv: string | null
  ma_khoa: string | null
}

export interface LoginResponse {
  access_token: string
  token_type: string
  het_han_luc: string
  nguoi_dung: User
}

export interface Conversation {
  id: number
  tieu_de: string
  kenh: string
  created_at: string
  updated_at: string
}

export interface Citation {
  so: number
  doan_id: number | null
  van_ban_id: number | null
  van_ban: string | null
  phien_ban: string | null
  dieu: string | null
  khoan: string | null
  trang: number | null
  trich_doan: string | null
}

export interface Message {
  id: number
  vai_tro: 'user' | 'assistant'
  noi_dung: string
  trich_dan: Citation[] | null
  danh_gia: 1 | -1 | null
  created_at: string
}

export interface PendingAction {
  ma: string
  ten_cong_cu: string
  mo_ta: string
  het_han_luc: string
  /** MCP elicitation: server cần sinh viên điền thêm biểu mẫu sau khi bấm Xác nhận. */
  bo_sung?: { thong_diep: string; schema: FormSchema } | null
}

export interface MessagesResponse {
  tin_nhan: Message[]
  hanh_dong_cho_xac_nhan: PendingAction[]
}

// ----- Sự kiện SSE (docs/02 mục 5) -----
export type AgentEvent =
  | { event: 'token'; data: { text: string } }
  | { event: 'tool_start'; data: { ten: string; nhan: string } }
  | { event: 'tool_end'; data: { ten: string; trang_thai: string } }
  | { event: 'citations'; data: Citation[] }
  | { event: 'pending_action'; data: PendingAction }
  | { event: 'done'; data: { tin_nhan_id: number } }
  | { event: 'error'; data: { detail: string; code: string } }

// ----- Thủ tục của em -----
export interface RequestSummary {
  ma_don: string
  loai_don: string
  trang_thai: string
  ma_trang_thai: string
  tao_boi: string
  ngay_tao: string
  ngay_cap_nhat?: string
}

export interface RequestListResponse {
  don: RequestSummary[]
  thong_bao: string
}

export interface RequestDetail {
  ma_don: string
  loai_don: string
  noi_dung: Record<string, unknown>
  trang_thai: string
  ma_trang_thai: string
  tao_boi: string
  ghi_chu_xu_ly: string | null
  ngay_tao: string
  cap_nhat_luc: string
  thong_bao: string
}

// ----- Chế độ trình bày: GET /api/conversations/{id}/trace -----
export interface TraceStep {
  id: number
  thoi_diem: string
  ten_cong_cu: string
  nhan: string
  mcp_server: string
  tham_so_llm: Record<string, unknown> | null // null = hệ thống tự gọi
  tham_so_he_thong_dien: Record<string, unknown>
  trang_thai: string
  ly_do: string | null
  thoi_gian_ms: number | null
}

export interface TraceResponse {
  luot_goi: TraceStep[]
}

// ---- Nhắc việc (/api/my/reminders) ----
export interface Reminder {
  loai: 'hoc_phi' | 'lich_thi' | 'sach' | 'don'
  muc_do: 'khan' | 'sap_toi'
  tieu_de: string
  chi_tiet: string
  han: string
  con_ngay: number
  cau_hoi: string
}

export interface RemindersResponse {
  ngay: string
  nhac_viec: Reminder[]
  nguon_loi: string[]
}
