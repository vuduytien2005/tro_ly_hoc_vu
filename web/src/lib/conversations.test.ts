import { describe, expect, it } from 'vitest'
import {
  answerCopyText,
  charCounter,
  conversationText,
  dayBreaks,
  dayLabel,
  formatTime,
  exportFileName,
  groupConversations,
  normalizeSearch,
} from './conversations'
import type { Citation, Conversation, Message } from './types'

const NOW = new Date('2026-11-26T15:00:00+07:00')
const conv = (id: number, tieu_de: string, updated_at: string): Conversation => ({
  id,
  tieu_de,
  kenh: 'web',
  created_at: updated_at,
  updated_at,
})

describe('normalizeSearch', () => {
  it('bỏ dấu, đ -> d, chữ thường, gộp khoảng trắng', () => {
    expect(normalizeSearch('  Học  PHÍ Đợt 2 ')).toBe('hoc phi dot 2')
  })
})

describe('groupConversations', () => {
  const list = [
    conv(1, 'Lịch thi của em', '2026-11-26T08:00:00+07:00'), // hôm nay
    conv(2, 'Học phí kỳ này', '2026-11-25T23:00:00+07:00'), // hôm qua -> 7 ngày qua
    conv(3, 'Đơn bảo lưu', '2026-11-10T09:00:00+07:00'), // 30 ngày qua
    conv(4, 'Điểm F môn CTDL', '2026-09-01T09:00:00+07:00'), // cũ hơn
    conv(5, 'Hồ sơ của em', '2026-11-26T14:00:00+07:00'), // hôm nay, mới hơn #1
  ]

  it('nhóm theo thời gian cập nhật (giờ Việt Nam), mới nhất trước, bỏ nhóm rỗng', () => {
    const groups = groupConversations(list, '', NOW)
    expect(groups.map((g) => [g.label, g.items.map((c) => c.id)])).toEqual([
      ['Hôm nay', [5, 1]],
      ['7 ngày qua', [2]],
      ['30 ngày qua', [3]],
      ['Cũ hơn', [4]],
    ])
  })

  it('tìm theo tiêu đề không phân biệt dấu / hoa thường', () => {
    const ids = (q: string) =>
      groupConversations(list, q, NOW).flatMap((g) => g.items.map((c) => c.id))
    expect(ids('hoc phi')).toEqual([2])
    expect(ids('ĐIỂM')).toEqual([4])
    expect(ids('don bao')).toEqual([3])
    expect(ids('không có')).toEqual([])
  })
})

describe('conversationText', () => {
  const cite: Citation = {
    so: 1,
    doan_id: 1,
    van_ban_id: 612,
    van_ban: 'Quy chế đào tạo',
    phien_ban: '2021',
    dieu: 'Điều 8',
    khoan: 'Khoản 2',
    trang: 3,
    trich_doan: '...',
  }
  const msg = (
    vai_tro: Message['vai_tro'],
    noi_dung: string,
    trich_dan: Citation[] | null = null,
  ): Message => ({
    id: 1,
    vai_tro,
    noi_dung,
    trich_dan,
    danh_gia: null,
    created_at: '2026-11-26T08:00:00+07:00',
  })

  it('ghi tiêu đề, người hỏi / trợ lý và nguồn trích dẫn của từng câu trả lời', () => {
    const text = conversationText(
      'Điều kiện tốt nghiệp',
      [msg('user', 'Em cần gì để tốt nghiệp?'), msg('assistant', 'Em cần đủ tín chỉ [1].', [cite])],
      NOW,
    )
    expect(text).toContain('Điều kiện tốt nghiệp')
    expect(text).toContain('Em: Em cần gì để tốt nghiệp?')
    expect(text).toContain('Trợ lý: Em cần đủ tín chỉ [1].')
    expect(text).toContain('[1] Quy chế đào tạo (2021) — Điều 8, Khoản 2, trang 3')
    expect(text).toContain('26/11/2026')
  })

  it('bỏ tin rỗng (lượt chỉ gọi công cụ)', () => {
    const text = conversationText('T', [msg('user', 'Hỏi'), msg('assistant', '  ')], NOW)
    expect(text).not.toContain('Trợ lý:')
  })
})

describe('exportFileName', () => {
  it('tiêu đề tiếng Việt -> tên tệp không dấu, an toàn', () => {
    expect(exportFileName('Học phí / kỳ này?')).toBe('tro-chuyen-hoc-phi-ky-nay.txt')
    expect(exportFileName('???')).toBe('tro-chuyen-hoi-thoai.txt')
  })
})

describe('answerCopyText', () => {
  const cite: Citation = {
    so: 1,
    doan_id: 1,
    van_ban_id: 612,
    van_ban: 'Quy chế đào tạo',
    phien_ban: '2021',
    dieu: 'Điều 8',
    khoan: null,
    trang: null,
    trich_doan: null,
  }

  it('bỏ ký hiệu Markdown, giữ gạch đầu dòng, thêm nguồn ở cuối', () => {
    const md =
      '## Kết luận\n**Em chưa đủ** điều kiện [1].\n- Thiếu *3 tín chỉ*\n- Xem [cổng](https://x.vn)'
    expect(answerCopyText(md, [cite])).toBe(
      'Kết luận\nEm chưa đủ điều kiện [1].\n- Thiếu 3 tín chỉ\n- Xem cổng\n\nNguồn:\n[1] Quy chế đào tạo (2021) — Điều 8',
    )
  })

  it('không có trích dẫn -> chỉ nội dung', () => {
    expect(answerCopyText('Chào em', null)).toBe('Chào em')
  })
})

describe('charCounter', () => {
  it('chỉ hiện khi đã dùng từ 90% giới hạn', () => {
    expect(charCounter(100, 2000)).toBeNull()
    expect(charCounter(1800, 2000)).toBe('1800/2000')
    expect(charCounter(2000, 2000)).toBe('2000/2000')
  })
})

describe('dayLabel / formatTime / dayBreaks', () => {
  it('nhãn ngày theo giờ Việt Nam: Hôm nay, Hôm qua, còn lại thứ + ngày', () => {
    expect(dayLabel('2026-11-26T08:00:00+07:00', NOW)).toBe('Hôm nay')
    expect(dayLabel('2026-11-25T23:30:00+07:00', NOW)).toBe('Hôm qua')
    // 00:30 ngày 25 giờ VN = 17:30 ngày 24 giờ UTC -> vẫn là ngày 25
    expect(dayLabel('2026-11-24T17:30:00Z', NOW)).toBe('Hôm qua')
    expect(dayLabel('2026-11-23T09:00:00+07:00', NOW)).toBe('Thứ Hai, 23/11/2026')
    expect(dayLabel('2026-11-22T09:00:00+07:00', NOW)).toBe('Chủ nhật, 22/11/2026')
  })

  it('giờ:phút theo giờ Việt Nam', () => {
    expect(formatTime('2026-11-26T01:05:00Z')).toBe('08:05')
  })

  it('đánh dấu tin đầu tiên của mỗi ngày', () => {
    const at = (id: number, created_at: string) => ({ id, created_at })
    const breaks = dayBreaks([
      at(1, '2026-11-25T09:00:00+07:00'),
      at(2, '2026-11-25T10:00:00+07:00'),
      at(3, '2026-11-26T08:00:00+07:00'),
    ])
    expect([...breaks]).toEqual([1, 3])
  })
})
