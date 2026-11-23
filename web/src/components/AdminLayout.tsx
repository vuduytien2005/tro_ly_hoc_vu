import {
  BarChart3,
  FileCheck,
  GraduationCap,
  FileText,
  LogOut,
  Menu,
  ScrollText,
  Search,
  ShieldCheck,
  Users,
  Wrench,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'
import { useAuth } from '../lib/auth'
import { useFontScale } from '../lib/presentation'
import { FontButtons } from './FontButtons'

const LINKS = [
  { to: '/admin/tai-lieu', label: 'Tài liệu', icon: FileText },
  { to: '/admin/thu-truy-xuat', label: 'Thử truy xuất', icon: Search },
  { to: '/admin/mcp', label: 'MCP & quyền', icon: Wrench },
  { to: '/admin/nhat-ky', label: 'Nhật ký', icon: ScrollText },
  { to: '/admin/thong-ke', label: 'Thống kê', icon: BarChart3 },
  { to: '/admin/tai-khoan', label: 'Tài khoản', icon: Users },
  { to: '/admin/sinh-vien', label: 'Sinh viên (QLSV)', icon: GraduationCap },
  { to: '/admin/don-tu', label: 'Đơn từ', icon: FileCheck },
]

export default function AdminLayout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  // Menu trượt (màn hình nhỏ) gắn với trang đang mở -> chuyển trang là tự đóng
  const [openOn, setOpenOn] = useState<string | null>(null)
  const open = openOn === location.pathname
  const [fontScale, setFontScale] = useFontScale()

  return (
    <div className="flex h-full">
      {open && (
        <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={() => setOpenOn(null)} />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 transform flex-col bg-navy text-slate-200 transition-transform md:static md:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center gap-3 px-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 text-accent">
            <ShieldCheck size={20} />
          </div>
          <span className="flex-1 font-semibold text-white">Quản trị</span>
          <button
            onClick={() => setOpenOn(null)}
            aria-label="Đóng menu"
            className="flex h-11 w-11 items-center justify-center rounded-[10px] hover:bg-white/10 md:hidden"
          >
            <X size={20} />
          </button>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {LINKS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex h-11 items-center gap-3 rounded-[10px] px-3 text-sm hover:bg-white/10 ${
                  isActive ? 'bg-white/15 font-medium text-white' : ''
                }`
              }
            >
              <Icon size={18} /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-3 border-t border-white/10 p-3">
          <div className="min-w-0 flex-1 px-2">
            <p className="truncate text-sm font-medium text-white">{user?.ho_ten}</p>
            <p className="truncate text-xs text-slate-400">{user?.email}</p>
          </div>
          <button
            onClick={logout}
            aria-label="Đăng xuất"
            title="Đăng xuất"
            className="flex h-11 w-11 items-center justify-center rounded-[10px] hover:bg-white/10"
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center gap-3 border-b border-line bg-white px-3 md:hidden">
          <button
            onClick={() => setOpenOn(location.pathname)}
            aria-label="Mở menu"
            className="flex h-11 w-11 items-center justify-center rounded-[10px] hover:bg-page"
          >
            <Menu size={22} />
          </button>
          <span className="font-semibold text-navy">Quản trị</span>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-6xl px-3 py-6 sm:px-6">
            {/* Phóng chữ khi trình chiếu (dùng chung cỡ chữ với chế độ trình bày ở trang chat) */}
            <div className="-mt-3 mb-2 flex justify-end">
              <FontButtons scale={fontScale} onScale={setFontScale} />
            </div>
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
