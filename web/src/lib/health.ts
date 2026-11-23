// Trạng thái hệ thống từ GET /health (không cần đăng nhập) -> thông báo thân thiện cho sinh viên.

export interface HealthResponse {
  trang_thai: string
  mcp_server: Record<string, string>
  gian_doan?: string[]
  llm_da_cau_hinh: boolean
  llm_co_khoa?: boolean | null
  che_do_trinh_bay?: boolean
}

export interface HealthNotice {
  level: 'warn' | 'error'
  title: string
  detail: string
}

/** Tên MCP server -> nhóm chức năng sinh viên hiểu được. */
export const SERVER_LABELS: Record<string, string> = {
  dao_tao: 'Đào tạo (điểm, lịch thi, đăng ký học phần)',
  ctsv: 'Công tác sinh viên (giấy xác nhận, đơn từ)',
  tai_chinh: 'Học phí',
  quy_che: 'Tra cứu quy chế',
}

export function serverLabel(name: string): string {
  return SERVER_LABELS[name] ?? name
}

/**
 * `health` = null khi không gọi được /health (assistant_api tắt hoặc mất mạng).
 * Trả null khi mọi thứ bình thường -> không hiện banner.
 */
export function healthNotice(health: HealthResponse | null): HealthNotice | null {
  if (health == null) {
    return {
      level: 'error',
      title: 'Mất kết nối máy chủ trợ lý',
      detail: 'Trợ lý tạm thời không phản hồi. Em kiểm tra mạng hoặc thử lại sau ít phút nhé.',
    }
  }
  if (!health.llm_da_cau_hinh || health.llm_co_khoa === false) {
    return {
      level: 'error',
      title: 'Trợ lý chưa sẵn sàng',
      detail: 'Mô hình ngôn ngữ chưa được cấu hình đầy đủ. Vui lòng báo quản trị viên.',
    }
  }
  const down = health.gian_doan ?? []
  if (down.length > 0) {
    return {
      level: 'warn',
      title: 'Một số chức năng đang gián đoạn',
      detail: `${down.map(serverLabel).join('; ')}. Các câu hỏi khác vẫn dùng bình thường, em thử lại phần này sau ít phút nhé.`,
    }
  }
  return null
}

export async function fetchHealth(): Promise<HealthResponse | null> {
  try {
    const response = await fetch('/health', { cache: 'no-store' })
    if (!response.ok) return null
    return (await response.json()) as HealthResponse
  } catch {
    return null
  }
}

/** Lỗi khiến sinh viên nên bấm "Thử lại" (không phải lỗi do yêu cầu sai / không có quyền). */
export function isRetryable(code: string | undefined, status?: number): boolean {
  if (status != null && status >= 500) return true
  return ['LOI_MO_HINH_NGON_NGU', 'LOI_HE_THONG', 'MAT_KET_NOI'].includes(code ?? '')
}
