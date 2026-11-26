import { describe, expect, it } from 'vitest'
import { changePasswordProblem } from './account'

describe('changePasswordProblem', () => {
  it('hợp lệ -> null', () => {
    expect(changePasswordProblem('Cu@12345', 'MoiHon2026', 'MoiHon2026')).toBeNull()
  })

  it('báo lỗi theo thứ tự: thiếu mật khẩu hiện tại, yếu, trùng cũ, nhập lại sai', () => {
    expect(changePasswordProblem('', 'MoiHon2026', 'MoiHon2026')).toMatch(/hiện tại/)
    expect(changePasswordProblem('Cu@12345', 'ngan', 'ngan')).toMatch(/8 ký tự/)
    expect(changePasswordProblem('Cu@12345', 'Cu@12345', 'Cu@12345')).toMatch(/khác/)
    expect(changePasswordProblem('Cu@12345', 'MoiHon2026', 'MoiHon2025')).toMatch(/không khớp/)
  })
})
