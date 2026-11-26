import { describe, expect, it } from 'vitest'
import type { StaffRequest } from './adminTypes'
import {
  GAP_SOURCES,
  type Gap,
  draftProblem,
  filterEntries,
  similarEntries,
  type KnowledgeEntry,
  gapToDraft,
  isKnowledgeCitation,
  personalInfoProblem,
  requestToDraft,
} from './knowledge'

const gap = (over: Partial<Gap>): Gap => ({
  nguon: 'khong_can_cu',
  thoi_gian: '2026-11-25T09:00:00+07:00',
  cau_hoi: null,
  noi_dung: '',
  ly_do: null,
  tra_loi_can_bo: null,
  tin_nhan_id: null,
  ma_don: null,
  phong_ban: null,
  trang_thai: null,
  da_vao_kho: false,
  ...over,
})

describe('personalInfoProblem (khớp backend knowledge.personal_info_problem)', () => {
  it.each([
    ['Mã SV22001 hỏi về học bổng', 'mã sinh viên'],
    ['liên hệ an.nguyen@truong.example', 'địa chỉ email'],
    ['gọi 0912 345 678', 'số điện thoại'],
    ['+84 912345678', 'số điện thoại'],
  ])('%s -> %s', (text, label) => {
    expect(personalInfoProblem(text)).toBe(label)
  })

  it.each(['Lệ phí là 50.000 đồng, nộp trước 15/12/2026', 'Điều 12 khoản 3 quy chế 2023'])(
    'không báo nhầm: %s',
    (text) => {
      expect(personalInfoProblem(text)).toBeNull()
    },
  )
})

describe('draftProblem', () => {
  const ok = {
    cau_hoi: 'Ký túc xá đóng cửa lúc mấy giờ?',
    tra_loi: 'Lúc 23 giờ.',
    phong_ban: 'ctsv',
  }
  it('chấp nhận bản nháp hợp lệ', () => expect(draftProblem(ok)).toBeNull())
  it('câu hỏi quá ngắn / thiếu trả lời', () => {
    expect(draftProblem({ ...ok, cau_hoi: 'KTX?' })).toMatch(/Câu hỏi/)
    expect(draftProblem({ ...ok, tra_loi: '  ' })).toMatch(/Câu trả lời/)
  })
  it('chặn thông tin cá nhân, nêu rõ ở ô nào', () => {
    expect(draftProblem({ ...ok, cau_hoi: 'Em SV22001 hỏi KTX mấy giờ đóng?' })).toBe(
      'Câu hỏi có mã sinh viên — hãy bỏ thông tin cá nhân (kho trả cho mọi sinh viên).',
    )
  })
})

describe('gapToDraft', () => {
  it('ý thiếu căn cứ: dùng câu hỏi của sinh viên, liên kết tin nhắn', () => {
    const d = gapToDraft(
      gap({ cau_hoi: 'KTX đóng cửa mấy giờ?', noi_dung: 'KTX đóng 22h.', tin_nhan_id: 42 }),
    )
    expect(d).toEqual({
      cau_hoi: 'KTX đóng cửa mấy giờ?',
      tra_loi: '',
      phong_ban: 'khac',
      tin_nhan_id: 42,
      ma_don: null,
    })
  })
  it('câu hỏi gửi cán bộ: điền sẵn câu trả lời và phòng ban', () => {
    const d = gapToDraft(
      gap({
        nguon: 'hoi_can_bo',
        cau_hoi: 'Thư viện mở Chủ nhật?',
        noi_dung: 'Thư viện mở Chủ nhật?',
        tra_loi_can_bo: 'Mở 8–17 giờ.',
        phong_ban: 'ctsv',
        ma_don: 'HD-1',
      }),
    )
    expect(d).toMatchObject({ tra_loi: 'Mở 8–17 giờ.', phong_ban: 'ctsv', ma_don: 'HD-1' })
  })
  it('không có câu hỏi trước đó -> dùng nội dung', () => {
    expect(gapToDraft(gap({ noi_dung: 'Học phí kỳ hè miễn phí.' })).cau_hoi).toBe(
      'Học phí kỳ hè miễn phí.',
    )
  })
})

it('requestToDraft lấy câu hỏi, trả lời của cán bộ, phòng ban, mã đơn', () => {
  const req = {
    ma_don: 'HD-2026-0007',
    loai_don: 'hoi_dap',
    noi_dung: { cau_hoi: 'Thư viện mở Chủ nhật?', phong_ban: 'ctsv' },
    trang_thai: 'hoan_tat',
    ghi_chu_xu_ly: 'Mở 8–17 giờ.',
  } as unknown as StaffRequest
  expect(requestToDraft(req)).toEqual({
    cau_hoi: 'Thư viện mở Chủ nhật?',
    tra_loi: 'Mở 8–17 giờ.',
    phong_ban: 'ctsv',
    ma_don: 'HD-2026-0007',
    tin_nhan_id: null,
  })
})

it('isKnowledgeCitation', () => {
  expect(isKnowledgeCitation({ loai: 'hoi_dap' })).toBe(true)
  expect(isKnowledgeCitation({ loai: 'quy_che' })).toBe(false)
  expect(isKnowledgeCitation({})).toBe(false) // tin nhắn cũ chưa có `loai`
})

it('GAP_SOURCES có đủ 4 nguồn của backend (thứ tự hiển thị)', () => {
  expect(Object.keys(GAP_SOURCES)).toEqual([
    'khong_can_cu',
    'khong_tim_thay',
    'hoi_can_bo',
    'danh_gia_xau',
  ])
})

const entry = (
  id: number,
  cau_hoi: string,
  phong_ban = 'dao_tao',
  tra_loi = 'x',
): KnowledgeEntry => ({
  id,
  cau_hoi,
  tra_loi,
  phong_ban,
  ma_don: null,
  tin_nhan_id: null,
  created_at: '2026-11-25T08:00:00+07:00',
  updated_at: '2026-11-25T08:00:00+07:00',
})

describe('filterEntries', () => {
  const list = [
    entry(1, 'Học bổng khuyến khích học tập xét thế nào?', 'ctsv'),
    entry(2, 'Đăng ký học phần muộn được không?', 'dao_tao', 'Liên hệ phòng Đào tạo'),
    entry(3, 'Nộp học phí qua ngân hàng nào?', 'tai_chinh'),
  ]

  it('tìm không dấu, trong cả câu hỏi và câu trả lời', () => {
    expect(filterEntries(list, 'hoc bong', '').map((e) => e.id)).toEqual([1])
    expect(filterEntries(list, 'PHÒNG ĐÀO TẠO', '').map((e) => e.id)).toEqual([2])
  })

  it('lọc theo phòng ban; ô tìm trống -> giữ hết', () => {
    expect(filterEntries(list, '', 'tai_chinh').map((e) => e.id)).toEqual([3])
    expect(filterEntries(list, '  ', '')).toHaveLength(3)
  })
})

describe('similarEntries', () => {
  const list = [
    entry(1, 'Học bổng khuyến khích học tập xét theo điều kiện gì?'),
    entry(2, 'Nộp học phí qua ngân hàng nào?'),
  ]

  it('câu hỏi gần giống mục đã có -> cảnh báo trùng', () => {
    const hits = similarEntries('Điều kiện xét học bổng khuyến khích học tập là gì', list)
    expect(hits.map((e) => e.id)).toEqual([1])
  })

  it('bỏ qua chính mục đang sửa, câu quá ngắn, câu khác hẳn', () => {
    expect(similarEntries(list[0].cau_hoi, list, 1)).toEqual([])
    expect(similarEntries('học bổng', list)).toEqual([])
    expect(similarEntries('Lịch thi cuối kỳ xem ở đâu?', list)).toEqual([])
  })
})
