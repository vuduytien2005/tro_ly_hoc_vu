import { describe, expect, it } from 'vitest'
import { linkCitations } from './format'
import type { Citation, Verification } from './types'
import { markUnverified, unverifiedIndex, verificationSummary } from './verification'

const TEXT = 'Em phải đăng ký học lại [1]. Học lại tối đa 2 lần [2].'

function v(...claims: [string, 'co_can_cu' | 'khong_co_can_cu'][]): Verification {
  return {
    tong: claims.length,
    co_can_cu: claims.filter(([, k]) => k === 'co_can_cu').length,
    y: claims.map(([cau, ket_luan]) => ({ cau, ket_luan, doan: [], ly_do: 'Không có trong văn bản' })),
    mo_hinh: 'x',
    thoi_gian_ms: 1,
  }
}

const citation = (so: number): Citation => ({
  so,
  doan_id: so,
  van_ban_id: 1,
  van_ban: 'Quy chế',
  phien_ban: null,
  dieu: null,
  khoan: null,
  trang: null,
  trich_doan: null,
})

describe('markUnverified', () => {
  it('gạch đúng ý không có căn cứ, ý có căn cứ giữ nguyên', () => {
    const out = markUnverified(TEXT, v(['Em phải đăng ký học lại [1].', 'co_can_cu'], ['Học lại tối đa 2 lần [2].', 'khong_co_can_cu']))
    expect(out).toBe('Em phải đăng ký học lại [1]. [Học lại tối đa 2 lần](#unverified-1) [2].')
  })
  it('keeps citations: [n] vẫn thành nút trích dẫn sau linkCitations', () => {
    const out = linkCitations(
      markUnverified(TEXT, v(['Học lại tối đa 2 lần [2].', 'khong_co_can_cu'])),
      [citation(1), citation(2)],
    )
    expect(out).toContain('[Học lại tối đa 2 lần](#unverified-0)')
    expect(out).toContain(String.raw`[\[2\]](#cite-2)`)
  })
  it('ý không tìm thấy trong câu trả lời hoặc chứa ký tự markdown -> không đổi', () => {
    expect(markUnverified(TEXT, v(['Câu không có thật.', 'khong_co_can_cu']))).toBe(TEXT)
    const md = 'Điều kiện: **GPA ≥ 2.0** [1].'
    expect(markUnverified(md, v(['Điều kiện: **GPA ≥ 2.0** [1].', 'khong_co_can_cu']))).toBe(md)
  })
  it('không có kết quả -> giữ nguyên', () => {
    expect(markUnverified(TEXT, null)).toBe(TEXT)
  })
})

describe('unverifiedIndex', () => {
  it('đọc số thứ tự ý từ liên kết', () => {
    expect(unverifiedIndex('#unverified-3')).toBe(3)
    expect(unverifiedIndex('#cite-3')).toBeNull()
  })
})

describe('verificationSummary', () => {
  it('không có ý nào cần kiểm chứng (vd "văn bản không đề cập") -> không hiện nhãn', () => {
    expect(verificationSummary(v())).toBeNull()
  })
  it('đủ căn cứ -> ok', () => {
    expect(verificationSummary(v(['a', 'co_can_cu']))).toEqual({ label: 'Đã kiểm chứng 1/1 ý với văn bản', ok: true })
  })
  it('thiếu căn cứ -> cảnh báo', () => {
    expect(verificationSummary(v(['a', 'co_can_cu'], ['b', 'khong_co_can_cu']))).toEqual({
      label: 'Đã kiểm chứng 1/2 ý với văn bản',
      ok: false,
    })
  })
})
