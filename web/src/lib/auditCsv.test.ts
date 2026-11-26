import { describe, expect, it } from 'vitest'
import type { AuditLog } from './adminTypes'
import { auditFileName, auditToCsv, fetchAllAuditLogs } from './auditCsv'

const log = (over: Partial<AuditLog> = {}): AuditLog => ({
  id: 1,
  created_at: '2026-11-26T01:02:03Z',
  nguoi_dung: { id: 7, ho_ten: 'Sinh viên A', email: 'a@truong.example' },
  hoi_thoai_id: 12,
  mcp_server: 'dao_tao',
  ten_cong_cu: 'get_transcript',
  trang_thai: 'thanh_cong',
  ly_do: null,
  thoi_gian_ms: 85,
  tham_so: { ma_sv: 'SV1', hoc_ky: 'HK1' },
  tham_so_llm: { hoc_ky: 'HK1', ma_sv: 'SV9' },
  da_tiem_ngu_canh: true,
  ...over,
})

describe('auditToCsv', () => {
  it('BOM + tiêu đề + một dòng mỗi lượt; giờ Việt Nam; trạng thái tiếng Việt; JSON tham số', () => {
    const csv = auditToCsv([log()])
    expect(csv.startsWith('﻿')).toBe(true)
    const [head, row] = csv.slice(1).split('\r\n')
    expect(head.split(',')[0]).toBe('Thời gian')
    expect(row).toContain('2026-11-26 08:02:03')
    expect(row).toContain('Thành công')
    expect(row).toContain('get_transcript')
    expect(row).toContain('Có')
    // LLM tự gửi ma_sv -> cột riêng ghi rõ giá trị bị ghi đè
    expect(row).toContain('ma_sv')
    expect(row).toContain('"{""ma_sv"":""SV1"",""hoc_ky"":""HK1""}"')
  })

  it('lượt không có tham số LLM / thời gian -> ô trống', () => {
    const row = auditToCsv([log({ tham_so_llm: null, thoi_gian_ms: null, ly_do: 'x' })])
      .slice(1)
      .split('\r\n')[1]
    expect(row).toContain(',,')
  })
})

describe('auditFileName', () => {
  it('theo khoảng ngày lọc, không lọc thì ghi "tat-ca"', () => {
    expect(auditFileName({ tu: '2026-11-01', den: '2026-11-26' })).toBe(
      'nhat-ky_2026-11-01_2026-11-26.csv',
    )
    expect(auditFileName({ tu: '', den: '' })).toBe('nhat-ky_tat-ca.csv')
  })
})

describe('fetchAllAuditLogs', () => {
  it('lấy lần lượt từng trang 100 lượt đến hết, dừng ở giới hạn', async () => {
    const calls: string[] = []
    const get = async (url: string) => {
      calls.push(url)
      const page = Number(new URL(url, 'http://x').searchParams.get('page'))
      const n = page < 3 ? 100 : 40
      return { tong: 240, trang_so: page, so_moi_trang: 100, luot_goi: Array(n).fill(log()) }
    }
    const all = await fetchAllAuditLogs({ trang_thai: 'loi' }, get)
    expect(all.rows).toHaveLength(240)
    expect(all.truncated).toBe(false)
    expect(calls[0]).toContain('trang_thai=loi')
    expect(calls[0]).toContain('page_size=100')

    const capped = await fetchAllAuditLogs({}, get, 150)
    expect(capped.rows).toHaveLength(150)
    expect(capped.truncated).toBe(true)
  })
})
