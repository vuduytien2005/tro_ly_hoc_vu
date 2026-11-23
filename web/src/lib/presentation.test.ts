import { describe, expect, it } from 'vitest'
import { traceLines } from './presentation'
import type { TraceStep } from './types'

function step(llm: Record<string, unknown> | null, filled: Record<string, unknown>): TraceStep {
  return {
    id: 1,
    thoi_diem: '2026-11-20T09:00:00+07:00',
    ten_cong_cu: 'register_course',
    nhan: 'Đăng ký học phần',
    mcp_server: 'dao_tao',
    tham_so_llm: llm,
    tham_so_he_thong_dien: filled,
    trang_thai: 'cho_xac_nhan',
    ly_do: null,
    thoi_gian_ms: 12,
  }
}

describe('traceLines', () => {
  it('tách tham số LLM gửi và tham số hệ thống điền', () => {
    const r = traceLines(step({ ma_lop: 'IT004.02' }, { ma_sv: 'SV22001' }))
    expect(r.llm).toBe('ma_lop=IT004.02')
    expect(r.system).toEqual([{ key: 'ma_sv', value: 'SV22001' }])
  })

  it('ghi lại giá trị LLM gửi khi bị ghi đè', () => {
    const r = traceLines(step({ ma_sv: 'SV22002' }, { ma_sv: 'SV22001' }))
    expect(r.system[0].overridden).toBe('SV22002')
    expect(r.llm).toBe('ma_sv=SV22002')
  })

  it('hệ thống tự gọi -> llm null', () => {
    expect(traceLines(step(null, { ma_sv: 'SV22001' })).llm).toBeNull()
  })

  it('mảng hiển thị nối bằng dấu phẩy', () => {
    expect(traceLines(step({ ma_lop: ['IT004.02', 'SE201.01'] }, {})).llm).toBe(
      'ma_lop=IT004.02, SE201.01',
    )
  })

  it('LLM không gửi tham số nào -> chuỗi rỗng thành "(không có)"', () => {
    expect(traceLines(step({}, { ma_sv: 'SV22001' })).llm).toBe('(không có)')
  })
})
