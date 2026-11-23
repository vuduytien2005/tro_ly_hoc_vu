// Hàm thuần cho chuông nhắc việc (có test).

import type { Reminder } from "./types";

/** Chữ trên huy hiệu: rỗng khi không có gì, tối đa "9+". */
export function badgeText(items: Reminder[] | undefined): string {
  const n = items?.length ?? 0;
  if (n === 0) return "";
  return n > 9 ? "9+" : String(n);
}

/** Huy hiệu đỏ khi có ít nhất một việc khẩn, cam khi chỉ có việc sắp tới. */
export function hasUrgent(items: Reminder[] | undefined): boolean {
  return items?.some((r) => r.muc_do === "khan") ?? false;
}

/** State gửi kèm khi chuyển sang /chat để đặt sẵn câu hỏi vào ô nhập. */
export interface ChatPrefillState {
  prefill: string;
}

export function readPrefill(state: unknown): string | null {
  if (state && typeof state === "object" && "prefill" in state) {
    const v = (state as { prefill: unknown }).prefill;
    return typeof v === "string" && v.trim() ? v : null;
  }
  return null;
}
