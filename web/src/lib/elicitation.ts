// Biểu mẫu MCP elicitation: MCP server gửi `requestedSchema` (JSON Schema phẳng, chỉ kiểu
// nguyên thủy — chuẩn MCP), web vẽ biểu mẫu ngay trên thẻ xác nhận. Kiểm tra ở đây chỉ để báo
// lỗi sớm; assistant_api và MCP server đều kiểm lại.

export interface FieldSchema {
  type?: 'string' | 'number' | 'integer' | 'boolean'
  title?: string
  description?: string
  pattern?: string
  enum?: string[]
  minLength?: number
  maxLength?: number
  minimum?: number
  maximum?: number
}

export interface FormSchema {
  type: 'object'
  properties: Record<string, FieldSchema>
  required?: string[]
}

export interface FormField {
  name: string
  label: string
  hint: string | null
  kind: 'text' | 'number' | 'checkbox' | 'select'
  required: boolean
  schema: FieldSchema
}

export type FormValues = Record<string, string | boolean>

export function formFields(schema: FormSchema): FormField[] {
  const required = new Set(schema.required ?? [])
  return Object.entries(schema.properties ?? {}).map(([name, s]) => ({
    name,
    label: s.title || name,
    hint: s.description ?? null,
    kind: s.enum
      ? 'select'
      : s.type === 'boolean'
        ? 'checkbox'
        : s.type === 'number' || s.type === 'integer'
          ? 'number'
          : 'text',
    required: required.has(name),
    schema: s,
  }))
}

/** Lỗi theo tên trường; rỗng = hợp lệ. */
export function formErrors(fields: FormField[], values: FormValues): Record<string, string> {
  const errors: Record<string, string> = {}
  for (const f of fields) {
    const raw = values[f.name]
    if (f.kind === 'checkbox') continue
    const text = typeof raw === 'string' ? raw.trim() : ''
    if (!text) {
      if (f.required) errors[f.name] = 'Bắt buộc'
      continue
    }
    const s = f.schema
    if (f.kind === 'number') {
      const n = Number(text)
      if (!Number.isFinite(n) || (s.type === 'integer' && !Number.isInteger(n)))
        errors[f.name] = 'Phải là số'
      else if (s.minimum != null && n < s.minimum) errors[f.name] = `Tối thiểu ${s.minimum}`
      else if (s.maximum != null && n > s.maximum) errors[f.name] = `Tối đa ${s.maximum}`
      continue
    }
    if (s.minLength != null && text.length < s.minLength) errors[f.name] = 'Quá ngắn'
    else if (s.maxLength != null && text.length > s.maxLength) errors[f.name] = 'Quá dài'
    else if (s.pattern && !safeTest(s.pattern, text)) errors[f.name] = 'Không đúng định dạng'
    else if (s.enum && !s.enum.includes(text)) errors[f.name] = 'Chọn một giá trị trong danh sách'
  }
  return errors
}

function safeTest(pattern: string, text: string): boolean {
  try {
    return new RegExp(pattern).test(text)
  } catch {
    return true // mẫu server gửi không dịch được sang JS -> để backend kiểm
  }
}

/** Dữ liệu gửi đi: bỏ ô trống, đổi kiểu số / đúng-sai theo schema. */
export function formPayload(
  fields: FormField[],
  values: FormValues,
): Record<string, string | number | boolean> {
  const out: Record<string, string | number | boolean> = {}
  for (const f of fields) {
    const raw = values[f.name]
    if (f.kind === 'checkbox') {
      out[f.name] = raw === true
      continue
    }
    const text = typeof raw === 'string' ? raw.trim() : ''
    if (!text) continue
    out[f.name] = f.kind === 'number' ? Number(text) : text
  }
  return out
}
