// "Thủ tục của em": báo đơn vừa được cán bộ xử lý (đổi trạng thái) kể từ lần sinh viên xem trước.
// Chỉ lưu ở trình duyệt (localStorage, theo từng mã sinh viên): không cần bảng/API mới, mất khi
// xóa dữ liệu trình duyệt thì chỉ là không còn huy hiệu — không ảnh hưởng dữ liệu đơn.

import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useSyncExternalStore } from 'react'
import { api } from './api'
import type { RequestListResponse } from './types'

/** ma_don -> ma_trang_thai lúc sinh viên xem lần cuối. */
export type SeenStatuses = Record<string, string>

interface StatusOf {
  ma_don: string
  ma_trang_thai: string
}

/**
 * Đơn đổi trạng thái so với lần xem trước. `seen` = null (chưa lưu lần nào) -> không báo gì.
 * Đơn chưa từng thấy mà vẫn "mới tạo" là đơn em vừa gửi -> không tính.
 */
export function updatedRequests(list: StatusOf[], seen: SeenStatuses | null): Set<string> {
  const out = new Set<string>()
  if (seen == null) return out
  for (const d of list) {
    const before = seen[d.ma_don]
    if (before === undefined ? d.ma_trang_thai !== 'moi_tao' : before !== d.ma_trang_thai) {
      out.add(d.ma_don)
    }
  }
  return out
}

export function snapshot(list: StatusOf[]): SeenStatuses {
  return Object.fromEntries(list.map((d) => [d.ma_don, d.ma_trang_thai]))
}

/** Ghi nhận đã xem các đơn trong `list`, giữ nguyên các đơn khác. */
export function markSeen(seen: SeenStatuses | null, list: StatusOf[]): SeenStatuses {
  return { ...(seen ?? {}), ...snapshot(list) }
}

// ----- Lưu trữ (localStorage) + thông báo cho mọi component đang dùng -----

const listeners = new Set<() => void>()
const cache = new Map<string, SeenStatuses | null>()
const storageKey = (maSv: string) => `tlhv.don-da-xem.${maSv}`

function read(maSv: string): SeenStatuses | null {
  if (!cache.has(maSv)) {
    let value: SeenStatuses | null = null
    try {
      const raw = window.localStorage.getItem(storageKey(maSv))
      value = raw ? (JSON.parse(raw) as SeenStatuses) : null
    } catch {
      value = null
    }
    cache.set(maSv, value)
  }
  return cache.get(maSv) ?? null
}

function write(maSv: string, value: SeenStatuses): void {
  cache.set(maSv, value)
  try {
    window.localStorage.setItem(storageKey(maSv), JSON.stringify(value))
  } catch {
    // Trình duyệt chặn lưu trữ: vẫn dùng được trong phiên này
  }
  listeners.forEach((l) => l())
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export const MY_REQUESTS_KEY = ['my-requests', '']

/**
 * Đơn mới được xử lý của sinh viên đang đăng nhập. Dùng chung khóa truy vấn với danh sách
 * "Tất cả" ở trang Thủ tục; tải lại mỗi 60 giây để huy hiệu menu tự hiện.
 */
export function useRequestUpdates(maSv: string | null | undefined) {
  const list = useQuery({
    queryKey: MY_REQUESTS_KEY,
    queryFn: () => api<RequestListResponse>('/api/my/requests'),
    enabled: !!maSv,
    refetchInterval: 60_000,
    retry: false,
  })
  const seen = useSyncExternalStore(subscribe, () => (maSv ? read(maSv) : null))
  const don = list.data?.don

  // Lần đầu: ghi nhận im lặng mọi đơn hiện có (không báo cả loạt đơn cũ là "mới")
  useEffect(() => {
    if (maSv && don && read(maSv) == null) write(maSv, snapshot(don))
  }, [maSv, don])

  const updated = don ? updatedRequests(don, seen) : new Set<string>()
  const markRead = useCallback(
    (maDon?: string) => {
      if (!maSv || !don) return
      const items = maDon ? don.filter((d) => d.ma_don === maDon) : don
      write(maSv, markSeen(read(maSv), items))
    },
    [maSv, don],
  )
  return { updated, markRead }
}
