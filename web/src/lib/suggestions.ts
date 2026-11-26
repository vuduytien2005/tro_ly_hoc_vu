// Gợi ý câu hỏi ở màn hình chat trống: ưu tiên tình trạng của chính sinh viên (từ /api/my/overview),
// thiếu thì bù bằng câu mặc định. Mỗi câu có một chủ đề để không gợi ý hai câu cùng ý.
import type { Overview } from './overview'

export interface Suggestion {
  text: string
  /** true = chọn theo tình trạng của em (hiện nhãn "Dành cho em"). */
  personal: boolean
}

export const MAX_SUGGESTIONS = 4
const SCHOLARSHIP_GPA = 3.6

type Topic =
  | 'canh_bao'
  | 'tot_nghiep'
  | 'hoc_phi'
  | 'bao_luu'
  | 'hoc_lai'
  | 'hoc_bong'
  | 'tin_chi'
  | 'lich_thi'
  | 'giay_to'

const DEFAULTS: { topic: Topic; text: string }[] = [
  { topic: 'tot_nghiep', text: 'Em còn thiếu gì để tốt nghiệp?' },
  { topic: 'lich_thi', text: 'Lịch thi của em' },
  { topic: 'hoc_lai', text: 'Học lại môn bị F thế nào?' },
  { topic: 'giay_to', text: 'Xin giấy xác nhận sinh viên' },
]

export const DEFAULT_SUGGESTIONS = DEFAULTS.map((d) => d.text)

/** Học phần bị F mà chưa có lần học nào đạt (theo thứ tự trong bảng điểm). */
function failedNotRetaken(o: Overview): string[] {
  const rows = o.bang_diem?.ket_qua ?? []
  const passed = new Set(rows.filter((r) => r.diem_chu && r.diem_chu !== 'F').map((r) => r.ma_hp))
  const names: string[] = []
  for (const r of rows) {
    if (r.diem_chu === 'F' && !passed.has(r.ma_hp) && !names.includes(r.ten_hp))
      names.push(r.ten_hp)
  }
  return names
}

function personalFor(o: Overview): { topic: Topic; text: string }[] {
  const out: { topic: Topic; text: string }[] = []
  const t = o.bang_diem
  const g = o.tot_nghiep
  if (t?.canh_bao_hoc_vu) {
    out.push({
      topic: 'canh_bao',
      text: 'Em bị cảnh báo học vụ thì phải làm gì để thoát cảnh báo?',
    })
  }
  if (g && !g.du_dieu_kien && Object.values(g.chung_chi).some((ok) => !ok)) {
    out.push({ topic: 'tot_nghiep', text: 'Em còn thiếu chứng chỉ gì để tốt nghiệp, nộp ở đâu?' })
  }
  if (g?.du_dieu_kien) {
    out.push({
      topic: 'tot_nghiep',
      text: 'Em đủ điều kiện tốt nghiệp rồi, thủ tục xét tốt nghiệp thế nào?',
    })
  }
  if (o.hoc_phi && o.hoc_phi.con_no > 0) {
    out.push({ topic: 'hoc_phi', text: 'Em còn nợ học phí bao nhiêu, hạn nộp khi nào?' })
  }
  if (o.ho_so?.trang_thai === 'bao_luu') {
    out.push({ topic: 'bao_luu', text: 'Em đang bảo lưu, muốn đi học lại thì làm thủ tục gì?' })
  }
  const [failed] = failedNotRetaken(o)
  if (failed) out.push({ topic: 'hoc_lai', text: `Em học lại môn ${failed} thế nào?` })
  if (t && !t.canh_bao_hoc_vu && t.gpa_tich_luy >= SCHOLARSHIP_GPA) {
    out.push({ topic: 'hoc_bong', text: 'Em có đủ điều kiện nhận học bổng khuyến khích không?' })
  }
  if (t && t.ket_qua.length === 0) {
    out.push({ topic: 'tin_chi', text: 'Một tín chỉ tương đương bao nhiêu tiết học?' })
  }
  return out
}

export function suggestionsFor(o: Overview | undefined): Suggestion[] {
  const chosen: Suggestion[] = []
  const topics = new Set<Topic>()
  for (const p of o ? personalFor(o) : []) {
    if (chosen.length >= MAX_SUGGESTIONS) break
    chosen.push({ text: p.text, personal: true })
    topics.add(p.topic)
  }
  for (const d of DEFAULTS) {
    if (chosen.length >= MAX_SUGGESTIONS) break
    if (topics.has(d.topic)) continue
    chosen.push({ text: d.text, personal: false })
    topics.add(d.topic)
  }
  return chosen
}
