import { LogOut, ShieldCheck } from 'lucide-react'
import { useAuth } from '../lib/auth'

/** Giữ chỗ — trang quản trị làm ở Giai đoạn 8. */
export default function AdminPlaceholder() {
  const { user, logout } = useAuth()
  return (
    <div className="flex min-h-full items-center justify-center p-4">
      <div className="max-w-md rounded-2xl border border-line bg-white p-8 text-center">
        <ShieldCheck className="mx-auto mb-3 text-primary" size={36} />
        <h1 className="mb-2 text-lg font-semibold text-navy">Trang quản trị</h1>
        <p className="mb-6 text-sm text-slate-500">
          Xin chào {user?.ho_ten}. Giao diện quản trị (tài liệu, MCP &amp; quyền, nhật ký, thống kê)
          sẽ có ở giai đoạn tiếp theo.
        </p>
        <button
          onClick={logout}
          className="inline-flex h-11 items-center gap-2 rounded-[10px] border border-line px-4 hover:bg-page"
        >
          <LogOut size={18} /> Đăng xuất
        </button>
      </div>
    </div>
  )
}
