import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Check,
  ClipboardList,
  GraduationCap,
  LogOut,
  Menu,
  MessageSquare,
  Pencil,
  Plus,
  Trash2,
  X,
} from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate, useParams } from 'react-router'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { Conversation } from '../lib/types'

export default function StudentLayout() {
  // Menu trượt (màn hình nhỏ) gắn với trang đang mở -> chuyển trang là tự đóng
  const location = useLocation()
  const [openOn, setOpenOn] = useState<string | null>(null)
  const open = openOn === location.pathname
  const setOpen = (value: boolean) => setOpenOn(value ? location.pathname : null)

  return (
    <div className="flex h-full">
      {/* Màn hình nhỏ: sidebar thành menu trượt */}
      {open && (
        <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={() => setOpen(false)} />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-72 transform transition-transform md:static md:translate-x-0 ${
          open ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <Sidebar onClose={() => setOpen(false)} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center gap-3 border-b border-line bg-white px-3 md:hidden">
          <button
            onClick={() => setOpen(true)}
            aria-label="Mở menu"
            className="flex h-11 w-11 items-center justify-center rounded-[10px] hover:bg-page"
          >
            <Menu size={22} />
          </button>
          <span className="font-semibold text-navy">Trợ lý học vụ</span>
        </header>
        <main className="min-h-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function Sidebar({ onClose }: { onClose: () => void }) {
  const { user, logout } = useAuth()
  const conversations = useQuery({
    queryKey: ['conversations'],
    queryFn: () => api<Conversation[]>('/api/conversations'),
  })

  return (
    <div className="flex h-full flex-col bg-navy text-slate-200">
      <div className="flex h-16 items-center gap-3 px-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 text-accent">
          <GraduationCap size={20} />
        </div>
        <span className="flex-1 font-semibold text-white">Trợ lý học vụ</span>
        <button
          onClick={onClose}
          aria-label="Đóng menu"
          className="flex h-11 w-11 items-center justify-center rounded-[10px] hover:bg-white/10 md:hidden"
        >
          <X size={20} />
        </button>
      </div>

      <div className="px-3">
        <Link
          to="/chat"
          className="flex h-11 items-center justify-center gap-2 rounded-[10px] bg-primary font-medium text-white hover:bg-primary-dark"
        >
          <Plus size={18} /> Cuộc trò chuyện mới
        </Link>
      </div>

      <nav className="mt-4 min-h-0 flex-1 overflow-y-auto px-3">
        <p className="px-2 pb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
          Gần đây
        </p>
        {conversations.isPending && <p className="px-2 text-sm text-slate-400">Đang tải…</p>}
        {conversations.data?.length === 0 && (
          <p className="px-2 text-sm text-slate-400">Chưa có cuộc trò chuyện nào.</p>
        )}
        <ul className="space-y-1">
          {conversations.data?.map((c) => <ConversationItem key={c.id} conversation={c} />)}
        </ul>
      </nav>

      <div className="space-y-1 border-t border-white/10 p-3">
        <NavLink
          to="/thu-tuc"
          className={({ isActive }) =>
            `flex h-11 items-center gap-3 rounded-[10px] px-3 hover:bg-white/10 ${
              isActive ? 'bg-white/10 text-white' : ''
            }`
          }
        >
          <ClipboardList size={18} /> Thủ tục của em
        </NavLink>
        <div className="flex items-center gap-3 rounded-[10px] px-3 py-2">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/10 text-sm font-semibold text-white">
            {user?.ho_ten.split(' ').pop()?.[0] ?? '?'}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">{user?.ho_ten}</p>
            <p className="truncate text-xs text-slate-400">
              {user?.ma_sv} · Khóa {user?.ma_khoa}
            </p>
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
      </div>
    </div>
  )
}

function ConversationItem({ conversation }: { conversation: Conversation }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(conversation.tieu_de)
  const active = id === String(conversation.id)

  const rename = useMutation({
    mutationFn: (tieu_de: string) =>
      api<Conversation>(`/api/conversations/${conversation.id}`, {
        method: 'PATCH',
        json: { tieu_de },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['conversations'] }),
  })
  const remove = useMutation({
    mutationFn: () => api<void>(`/api/conversations/${conversation.id}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      if (active) navigate('/chat')
    },
  })

  if (editing) {
    return (
      <li className="flex items-center gap-1 rounded-[10px] bg-white/10 px-2">
        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && title.trim()) {
              rename.mutate(title.trim())
              setEditing(false)
            }
            if (e.key === 'Escape') setEditing(false)
          }}
          className="h-10 min-w-0 flex-1 bg-transparent text-sm text-white outline-none"
          aria-label="Tiêu đề mới"
        />
        <button
          onClick={() => {
            if (title.trim()) rename.mutate(title.trim())
            setEditing(false)
          }}
          aria-label="Lưu tiêu đề"
          className="flex h-10 w-10 items-center justify-center rounded-lg hover:bg-white/10"
        >
          <Check size={16} />
        </button>
      </li>
    )
  }

  return (
    <li
      className={`group flex items-center rounded-[10px] ${active ? 'bg-white/15 text-white' : 'hover:bg-white/10'}`}
    >
      <Link
        to={`/chat/${conversation.id}`}
        className="flex h-11 min-w-0 flex-1 items-center gap-2 px-3 text-sm"
        title={conversation.tieu_de}
      >
        <MessageSquare size={16} className="shrink-0 opacity-70" />
        <span className="truncate">{conversation.tieu_de}</span>
      </Link>
      <div className="flex shrink-0 md:hidden md:group-hover:flex">
        <button
          onClick={() => {
            setTitle(conversation.tieu_de)
            setEditing(true)
          }}
          aria-label="Đổi tên"
          title="Đổi tên"
          className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-white/10"
        >
          <Pencil size={14} />
        </button>
        <button
          onClick={() => {
            if (window.confirm('Xóa cuộc trò chuyện này?')) remove.mutate()
          }}
          aria-label="Xóa"
          title="Xóa"
          className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-white/10"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </li>
  )
}
