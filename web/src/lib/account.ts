import { passwordProblem } from './admin'

/** Kiểm tra form đổi mật khẩu trước khi gửi (backend vẫn kiểm tra lại). null = hợp lệ. */
export function changePasswordProblem(
  current: string,
  next: string,
  confirm: string,
): string | null {
  if (!current) return 'Nhập mật khẩu hiện tại.'
  const weak = passwordProblem(next)
  if (weak) return weak
  if (next === current) return 'Mật khẩu mới phải khác mật khẩu hiện tại.'
  if (next !== confirm) return 'Mật khẩu nhập lại không khớp.'
  return null
}
