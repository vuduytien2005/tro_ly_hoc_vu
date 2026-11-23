import { describe, expect, it } from "vitest";
import { badgeText, hasUrgent, readPrefill } from "./reminders";
import type { Reminder } from "./types";

const r = (muc_do: Reminder["muc_do"]): Reminder => ({
  loai: "sach",
  muc_do,
  tieu_de: "t",
  chi_tiet: "c",
  han: "2026-11-25",
  con_ngay: 2,
  cau_hoi: "q",
});

describe("badgeText", () => {
  it("rỗng khi không có nhắc việc hoặc chưa tải", () => {
    expect(badgeText(undefined)).toBe("");
    expect(badgeText([])).toBe("");
  });
  it("đếm số việc, tối đa 9+", () => {
    expect(badgeText([r("khan"), r("sap_toi")])).toBe("2");
    expect(badgeText(Array.from({ length: 12 }, () => r("sap_toi")))).toBe(
      "9+",
    );
  });
});

describe("hasUrgent", () => {
  it("chỉ đúng khi có việc khẩn", () => {
    expect(hasUrgent([r("sap_toi")])).toBe(false);
    expect(hasUrgent([r("sap_toi"), r("khan")])).toBe(true);
    expect(hasUrgent(undefined)).toBe(false);
  });
});

describe("readPrefill", () => {
  it("đọc câu hỏi soạn sẵn từ state điều hướng", () => {
    expect(readPrefill({ prefill: "Gia hạn sách giúp em" })).toBe(
      "Gia hạn sách giúp em",
    );
  });
  it("bỏ qua state lạ hoặc rỗng", () => {
    expect(readPrefill(null)).toBeNull();
    expect(readPrefill({ prefill: "  " })).toBeNull();
    expect(readPrefill({ prefill: 3 })).toBeNull();
    expect(readPrefill("x")).toBeNull();
  });
});
