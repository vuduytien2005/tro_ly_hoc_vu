import { describe, expect, it } from 'vitest'
import { formErrors, formFields, formPayload, type FormSchema } from './elicitation'

const SCHEMA: FormSchema = {
  type: 'object',
  properties: {
    so_dien_thoai: { type: 'string', title: 'Số điện thoại', pattern: '^0\\d{9}$' },
    email_ca_nhan: { type: 'string', title: 'Email' },
    so_ban: { type: 'integer', title: 'Số bản', minimum: 1, maximum: 5 },
    dong_y: { type: 'boolean', title: 'Đồng ý' },
    noi_nhan: { type: 'string', enum: ['truong', 'buu_dien'] },
  },
  required: ['so_dien_thoai'],
}
const fields = formFields(SCHEMA)

describe('formFields', () => {
  it('lấy nhãn, kiểu ô và trường bắt buộc từ schema của server', () => {
    expect(fields.map((f) => [f.name, f.kind, f.required])).toEqual([
      ['so_dien_thoai', 'text', true],
      ['email_ca_nhan', 'text', false],
      ['so_ban', 'number', false],
      ['dong_y', 'checkbox', false],
      ['noi_nhan', 'select', false],
    ])
    expect(fields[0].label).toBe('Số điện thoại')
    expect(fields[4].label).toBe('noi_nhan') // không có title -> dùng tên trường
  })
})

describe('formErrors', () => {
  it('hợp lệ khi đủ trường bắt buộc, đúng định dạng', () => {
    expect(formErrors(fields, { so_dien_thoai: '0912345678' })).toEqual({})
  })
  it('báo thiếu, sai định dạng, sai số', () => {
    expect(formErrors(fields, { so_dien_thoai: '', so_ban: '9', noi_nhan: 'nha' })).toEqual({
      so_dien_thoai: 'Bắt buộc',
      so_ban: 'Tối đa 5',
      noi_nhan: 'Chọn một giá trị trong danh sách',
    })
    expect(formErrors(fields, { so_dien_thoai: '12345' }).so_dien_thoai).toBe(
      'Không đúng định dạng',
    )
    expect(formErrors(fields, { so_dien_thoai: '0912345678', so_ban: '1.5' }).so_ban).toBe(
      'Phải là số',
    )
  })
})

describe('formPayload', () => {
  it('bỏ ô trống, đổi kiểu số và đúng-sai', () => {
    expect(
      formPayload(fields, { so_dien_thoai: ' 0912345678 ', email_ca_nhan: '', so_ban: '2' }),
    ).toEqual({ so_dien_thoai: '0912345678', so_ban: 2, dong_y: false })
  })
})
