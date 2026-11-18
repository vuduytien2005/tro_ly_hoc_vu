import { describe, expect, it } from 'vitest'
import { SseParser } from './sse'

const enc = new TextEncoder()

describe('SseParser', () => {
  it('tách nhiều sự kiện trong một khối', () => {
    const p = new SseParser()
    const events = p.push(
      enc.encode('event: token\ndata: {"text":"Chào"}\n\nevent: done\ndata: {"tin_nhan_id":5}\n\n'),
    )
    expect(events).toEqual([
      { event: 'token', data: { text: 'Chào' } },
      { event: 'done', data: { tin_nhan_id: 5 } },
    ])
  })

  it('ghép sự kiện bị cắt ngang giữa các khối mạng', () => {
    const p = new SseParser()
    expect(p.push(enc.encode('event: tool_start\ndata: {"ten":"get_'))).toEqual([])
    expect(p.push(enc.encode('transcript","nhan":"x"}\n'))).toEqual([])
    expect(p.push(enc.encode('\n'))).toEqual([
      { event: 'tool_start', data: { ten: 'get_transcript', nhan: 'x' } },
    ])
  })

  it('không làm hỏng chữ tiếng Việt bị cắt giữa các byte UTF-8', () => {
    const bytes = enc.encode('event: token\ndata: {"text":"Học lại"}\n\n')
    const cut = bytes.indexOf(0xe1) + 1 // giữa ký tự "ọ" (3 byte)
    const p = new SseParser()
    expect(p.push(bytes.slice(0, cut))).toEqual([])
    expect(p.push(bytes.slice(cut))).toEqual([{ event: 'token', data: { text: 'Học lại' } }])
  })

  it('chấp nhận CRLF, bỏ qua dòng chú thích và khối không có data', () => {
    const p = new SseParser()
    const events = p.push(enc.encode(': ping\r\n\r\nevent: done\r\ndata: {"tin_nhan_id":1}\r\n\r\n'))
    expect(events).toEqual([{ event: 'done', data: { tin_nhan_id: 1 } }])
  })

  it('flush trả sự kiện cuối không có dòng trống kết thúc', () => {
    const p = new SseParser()
    expect(p.push(enc.encode('event: done\ndata: {"tin_nhan_id":9}'))).toEqual([])
    expect(p.flush()).toEqual([{ event: 'done', data: { tin_nhan_id: 9 } }])
  })
})
