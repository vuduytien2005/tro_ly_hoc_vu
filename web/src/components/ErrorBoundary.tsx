import { CircleAlert, RotateCcw } from 'lucide-react'
import { Component, type ErrorInfo, type ReactNode } from 'react'
import { crashMessage } from '../lib/crash'

interface Props {
  /** Đổi giá trị (vd đường dẫn trang) -> xóa lỗi, hiện lại nội dung. */
  resetKey: string
  children: ReactNode
}

interface State {
  error: unknown
  key: string
}

/**
 * Một trang gặp lỗi khi hiển thị -> hiện khung báo lỗi thay cho trang trắng; menu vẫn dùng được,
 * chuyển sang trang khác là tự hết lỗi.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, key: this.props.resetKey }

  static getDerivedStateFromError(error: unknown): Partial<State> {
    return { error: error ?? new Error('Lỗi không rõ') }
  }

  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    return props.resetKey !== state.key ? { error: null, key: props.resetKey } : null
  }

  componentDidCatch(error: unknown, info: ErrorInfo) {
    console.error('Lỗi hiển thị trang', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div
          role="alert"
          className="max-w-md rounded-2xl border border-line bg-white p-6 text-center shadow-sm"
        >
          <CircleAlert className="mx-auto mb-3 text-err" size={32} />
          <p className="mb-4 text-sm text-slate-700">{crashMessage(this.state.error)}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="inline-flex h-10 items-center gap-2 rounded-[10px] bg-primary px-4 text-sm font-medium text-white hover:opacity-90"
          >
            <RotateCcw size={16} /> Tải lại trang
          </button>
        </div>
      </div>
    )
  }
}
