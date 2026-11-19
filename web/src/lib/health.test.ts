import { describe, expect, it } from 'vitest'
import { healthNotice, isRetryable, serverLabel, type HealthResponse } from './health'

const ok: HealthResponse = {
  trang_thai: 'ok',
  mcp_server: { dao_tao: 'ok', ctsv: 'ok', tai_chinh: 'ok', quy_che: 'ok' },
  gian_doan: [],
  llm_da_cau_hinh: true,
  llm_co_khoa: true,
}

describe('healthNotice', () => {
  it('không có banner khi mọi thứ bình thường', () => {
    expect(healthNotice(ok)).toBeNull()
  })

  it('không gọi được /health -> mất kết nối máy chủ', () => {
    expect(healthNotice(null)).toMatchObject({ level: 'error', title: 'Mất kết nối máy chủ trợ lý' })
  })

  it('thiếu mô hình hoặc khóa API -> trợ lý chưa sẵn sàng', () => {
    expect(healthNotice({ ...ok, llm_co_khoa: false })?.title).toBe('Trợ lý chưa sẵn sàng')
    expect(healthNotice({ ...ok, llm_da_cau_hinh: false })?.level).toBe('error')
    expect(healthNotice({ ...ok, llm_co_khoa: null })).toBeNull() // nhà cung cấp không xác định
  })

  it('MCP server gián đoạn -> nêu tên nhóm chức năng', () => {
    const notice = healthNotice({ ...ok, gian_doan: ['tai_chinh', 'quy_che'] })
    expect(notice?.level).toBe('warn')
    expect(notice?.detail).toContain('Học phí')
    expect(notice?.detail).toContain('Tra cứu quy chế')
  })

  it('tên server lạ giữ nguyên', () => {
    expect(serverLabel('khac')).toBe('khac')
  })
})

describe('isRetryable', () => {
  it('lỗi mô hình / hệ thống / mạng thì cho thử lại, lỗi quyền thì không', () => {
    expect(isRetryable('LOI_MO_HINH_NGON_NGU')).toBe(true)
    expect(isRetryable('MAT_KET_NOI')).toBe(true)
    expect(isRetryable('HTTP_502', 502)).toBe(true)
    expect(isRetryable('KHONG_DU_QUYEN', 403)).toBe(false)
  })
})
