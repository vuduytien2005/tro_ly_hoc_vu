// Đọc Server-Sent Events từ một request POST (EventSource chỉ hỗ trợ GET và không gửi được
// header Authorization) -> dùng fetch + ReadableStream và tự tách sự kiện.

import { ApiError, authHeaders, toApiError } from './api'
import type { AgentEvent } from './types'

/**
 * Bộ tách SSE theo từng khối dữ liệu nhận được. Mạng có thể cắt ngang bất kỳ đâu (giữa dòng,
 * giữa "\n\n", giữa một ký tự UTF-8 nhiều byte) nên phải đệm phần dở dang.
 */
export class SseParser {
  private readonly decoder = new TextDecoder('utf-8')
  private buffer = ''

  push(chunk: Uint8Array): AgentEvent[] {
    this.buffer += this.decoder.decode(chunk, { stream: true }).replace(/\r\n/g, '\n')
    return this.drain()
  }

  /** Gọi khi luồng kết thúc để lấy sự kiện cuối (nếu server không kết thúc bằng dòng trống). */
  flush(): AgentEvent[] {
    this.buffer += this.decoder.decode()
    if (this.buffer.trim()) this.buffer += '\n\n'
    return this.drain()
  }

  private drain(): AgentEvent[] {
    const events: AgentEvent[] = []
    let end = this.buffer.indexOf('\n\n')
    while (end !== -1) {
      const block = this.buffer.slice(0, end)
      this.buffer = this.buffer.slice(end + 2)
      const parsed = parseBlock(block)
      if (parsed) events.push(parsed)
      end = this.buffer.indexOf('\n\n')
    }
    return events
  }
}

function parseBlock(block: string): AgentEvent | null {
  let event = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith(':')) continue // dòng chú thích / keep-alive
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
  }
  if (data.length === 0) return null
  try {
    return { event, data: JSON.parse(data.join('\n')) } as AgentEvent
  } catch {
    return null
  }
}

/**
 * POST rồi gọi `onEvent` cho từng sự kiện. Lỗi trước khi mở luồng (401/403/404/409...) ném ApiError.
 * Hủy bằng `signal` (vd người dùng chuyển hội thoại).
 */
export async function postSse(
  path: string,
  body: unknown,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response
  try {
    response = await fetch(path, {
      method: 'POST',
      headers: authHeaders({ 'Content-Type': 'application/json', Accept: 'text/event-stream' }),
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (err) {
    if (signal?.aborted) throw err
    throw new ApiError(0, 'MAT_KET_NOI', 'Không kết nối được máy chủ trợ lý. Em kiểm tra mạng rồi thử lại nhé.')
  }
  if (!response.ok || !response.body) throw await toApiError(response)

  const parser = new SseParser()
  const reader = response.body.getReader()
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      parser.push(value).forEach(onEvent)
    }
  } catch (err) {
    if (signal?.aborted) throw err
    throw new ApiError(
      0,
      'MAT_KET_NOI',
      'Mất kết nối khi đang nhận câu trả lời. Phần đã lưu vẫn còn trong cuộc trò chuyện, em thử lại nhé.',
    )
  }
  parser.flush().forEach(onEvent)
}
