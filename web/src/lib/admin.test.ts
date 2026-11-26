import { describe, expect, it } from 'vitest'
import {
  countBadge,
  changedFields,
  cohortRange,
  formatMs,
  formatPercent,
  injectedKeys,
  passwordProblem,
  reviewBadge,
  toQuery,
} from './admin'

describe('cohortRange', () => {
  it('mô tả phạm vi khóa áp dụng', () => {
    expect(cohortRange(null, null)).toBe('Mọi khóa')
    expect(cohortRange(22, null)).toBe('Từ K22')
    expect(cohortRange(null, 21)).toBe('Đến K21')
    expect(cohortRange(20, 23)).toBe('K20 – K23')
    expect(cohortRange(22, 22)).toBe('K22')
  })
})

describe('injectedKeys', () => {
  it('phát hiện ma_sv do hệ thống điền hoặc ghi đè', () => {
    expect(injectedKeys({ hoc_ky: null }, { ma_sv: 'SV22001', hoc_ky: null })).toEqual(
      new Set(['ma_sv']),
    )
    expect(injectedKeys({ ma_sv: 'SV99999' }, { ma_sv: 'SV22001' })).toEqual(new Set(['ma_sv']))
    expect(injectedKeys({ a: [1, 2] }, { a: [1, 2] }).size).toBe(0)
    expect(injectedKeys(null, { ma_sv: 'x' }).size).toBe(0)
  })
})

describe('định dạng', () => {
  it('toQuery bỏ giá trị rỗng', () => {
    expect(toQuery({ a: 1, b: '', c: null, d: 'x y' })).toBe('?a=1&d=x+y')
    expect(toQuery({ a: undefined })).toBe('')
  })

  it('phần trăm và thời gian', () => {
    expect(formatPercent(0.8571)).toBe('85.7%')
    expect(formatPercent(null)).toBe('—')
    expect(formatMs(850)).toBe('850 ms')
    expect(formatMs(2345)).toBe('2.3 giây')
  })
})

describe('passwordProblem', () => {
  it('khớp quy tắc mật khẩu của backend', () => {
    expect(passwordProblem('TamThoi123')).toBeNull()
    expect(passwordProblem('Mậtkhẩu1')).toBeNull()
    expect(passwordProblem('Ab1')).toMatch(/8 ký tự/)
    expect(passwordProblem('12345678')).toMatch(/chữ cái/)
    expect(passwordProblem('chikhongcoso')).toMatch(/chữ số/)
    expect(passwordProblem('a1' + 'ệ'.repeat(30))).toMatch(/quá dài/)
  })
})
describe('changedFields', () => {
  it('chỉ trả trường đã sửa, bỏ khoảng trắng', () => {
    const before = { ho_ten: 'An', lop: 'KTPM2022', ma_khoa: 'K22' }
    expect(changedFields(before, { ho_ten: ' An ', lop: 'KTPM2023', ma_khoa: 'K22' })).toEqual({
      lop: 'KTPM2023',
    })
    expect(changedFields(before, before)).toEqual({})
  })
})
describe('reviewBadge', () => {
  it('nhãn duyệt mô tả công cụ MCP', () => {
    expect(reviewBadge('moi')).toEqual({ text: 'Mới — cần duyệt', tone: 'new' })
    expect(reviewBadge('thay_doi')).toEqual({
      text: 'Mô tả đã thay đổi — cần duyệt lại',
      tone: 'changed',
    })
    expect(reviewBadge('da_duyet')).toBeNull()
  })
})

describe('countBadge', () => {
  it('ẩn khi 0 hoặc chưa tải, tối đa 99+', () => {
    expect(countBadge(undefined)).toBe('')
    expect(countBadge(0)).toBe('')
    expect(countBadge(7)).toBe('7')
    expect(countBadge(150)).toBe('99+')
  })
})
