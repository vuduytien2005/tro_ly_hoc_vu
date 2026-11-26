/** Lỗi khi tải phần mã của trang theo kiểu lazy (thường do vừa build lại: tên tệp đổi mã băm). */
const CHUNK_ERROR =
  /dynamically imported module|Importing a module script failed|error loading dynamically imported/i

/** Thông báo tiếng Việt cho khung báo lỗi: không lộ chi tiết kỹ thuật cho người dùng. */
export function crashMessage(error: unknown): string {
  const text = error instanceof Error ? error.message : String(error)
  if (CHUNK_ERROR.test(text)) {
    return 'Trang vừa được cập nhật phiên bản mới. Em tải lại trang để tiếp tục nhé.'
  }
  return 'Trang này gặp sự cố ngoài ý muốn. Em thử tải lại trang hoặc chuyển sang mục khác.'
}
