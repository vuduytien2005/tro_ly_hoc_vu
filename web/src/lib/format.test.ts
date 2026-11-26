import { describe, expect, it } from 'vitest'
import {
  citationLocation,
  citationNumber,
  formatRemaining,
  linkCitations,
  unansweredQuestion,
} from './format'
import type { Citation, Message } from './types'

const cite = (so: number): Citation => ({
  so,
  doan_id: so,
  van_ban_id: 1,
  van_ban: 'Quy chế đào tạo',
  phien_ban: '2022',
  dieu: 'Điều 12',
  khoan: 'Khoản 2',
  trang: 5,
  trich_doan: '...',
})

describe('linkCitations', () => {
  it('chỉ đổi các [n] có trong danh sách nguồn', () => {
    expect(linkCitations('Phải học lại [1], xem thêm [3].', [cite(1)])).toBe(
      'Phải học lại [\\[1\\]](#cite-1), xem thêm [3].',
    )
  })

  it('giữ nguyên liên kết markdown [n](url) và văn bản khi không có nguồn', () => {
    expect(linkCitations('[1](http://x)', [cite(1)])).toBe('[1](http://x)')
    expect(linkCitations('Theo [1]', [])).toBe('Theo [1]')
    expect(linkCitations('Theo [1]', null)).toBe('Theo [1]')
  })

  it('đọc lại số trích dẫn từ href', () => {
    expect(citationNumber('#cite-12')).toBe(12)
    expect(citationNumber('https://a.b')).toBeNull()
    expect(citationNumber(undefined)).toBeNull()
  })

  it('ghép vị trí Điều, Khoản, trang', () => {
    expect(citationLocation(cite(1))).toBe('Điều 12, Khoản 2, trang 5')
    expect(citationLocation({ ...cite(1), khoan: null, trang: null })).toBe('Điều 12')
  })
})

describe('formatRemaining', () => {
  it('định dạng mm:ss, làm tròn lên, không âm', () => {
    expect(formatRemaining(581_000)).toBe('09:41')
    expect(formatRemaining(600_000)).toBe('10:00')
    expect(formatRemaining(400)).toBe('00:01')
    expect(formatRemaining(-5000)).toBe('00:00')
  })
})

describe('unansweredQuestion', () => {
  let n = 0
  const msg = (vai_tro: Message['vai_tro'], noi_dung: string): Message => ({
    id: ++n,
    vai_tro,
    noi_dung,
    trich_dan: null,
    danh_gia: null,
    created_at: '2026-11-25T16:32:00+07:00',
  })

  it('câu hỏi cuối chưa có trả lời (lượt bị lỗi, vd mô hình hết hạn mức) -> trả về câu hỏi', () => {
    expect(
      unansweredQuestion([msg('user', 'Chào'), msg('assistant', 'Chào em'), msg('user', 'GPA?')]),
    ).toBe('GPA?')
    // tin trợ lý rỗng (chỉ gọi công cụ rồi đứt) không tính là đã trả lời
    expect(unansweredQuestion([msg('user', 'Lịch thi'), msg('assistant', '  ')])).toBe('Lịch thi')
  })

  it('đã trả lời, rỗng, hoặc tin Xác nhận / Hủy (không gửi lại được) -> null', () => {
    expect(unansweredQuestion([])).toBeNull()
    expect(unansweredQuestion([msg('user', 'Hỏi'), msg('assistant', 'Đáp')])).toBeNull()
    expect(unansweredQuestion([msg('user', 'Xác nhận: Nộp đơn')])).toBeNull()
    expect(unansweredQuestion([msg('user', 'Hủy: Nộp đơn')])).toBeNull()
  })
})
