// Mở văn bản gốc từ trích dẫn: tải tệp kèm JWT (liên kết thường không gửi được header), mở
// trong tab mới; PDF nhảy tới đúng trang bằng "#page=N" (trình xem PDF của trình duyệt hỗ trợ).

import { authHeaders, toApiError } from './api'

/** Đuôi URL để trình xem PDF mở đúng trang; tệp khác (DOCX, TXT) không có khái niệm trang. */
export function pageFragment(contentType: string | null, page: number | null): string {
  return contentType?.startsWith('application/pdf') && page != null && page > 0
    ? `#page=${page}`
    : ''
}

export async function openDocument(vanBanId: number, page: number | null): Promise<void> {
  // Mở tab NGAY trong lúc bấm (sau await thì trình duyệt chặn popup), rồi trỏ tới tệp khi tải xong
  const tab = window.open('', '_blank')
  try {
    const response = await fetch(`/api/documents/${vanBanId}/file`, { headers: authHeaders() })
    if (!response.ok) throw await toApiError(response)
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const target = url + pageFragment(response.headers.get('content-type'), page)
    if (tab) tab.location.href = target
    else window.location.assign(target)
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (err) {
    tab?.close()
    throw err
  }
}
