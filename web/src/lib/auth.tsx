// Trạng thái đăng nhập: cookie HttpOnly do backend đặt (JavaScript không thấy token), thông tin
// người dùng lấy từ /api/auth/me. Trước 23/11/2026 token nằm trong localStorage (đọc được nếu
// web bị XSS) — đã chuyển sang cookie HttpOnly + chống CSRF.

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { api, hasSession } from './api'
import type { LoginResponse, Role, User } from './types'

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const me = useQuery({
    queryKey: ['me'],
    queryFn: () => api<User>('/api/auth/me'),
    enabled: hasSession(),
    retry: false,
    staleTime: Infinity,
  })

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api<LoginResponse>('/api/auth/login', {
        method: 'POST',
        json: { email, mat_khau: password },
      })
      // Cookie phiên đã được backend đặt; KHÔNG lưu res.access_token
      // Xóa dữ liệu của phiên trước nhưng GIỮ query ['me']: AuthProvider đang theo dõi
      // đúng đối tượng query này. clear() sẽ xóa nó, setQueryData tạo query mới mà
      // AuthProvider không nghe -> user vẫn null -> bị đẩy về /login.
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== 'me' })
      queryClient.setQueryData(['me'], res.nguoi_dung)
      return res.nguoi_dung
    },
    [queryClient],
  )

  const logout = useCallback(() => {
    // Cookie HttpOnly chỉ backend xóa được
    api('/api/auth/logout', { method: 'POST' })
      .catch(() => undefined)
      .finally(() => {
        queryClient.clear()
        window.location.assign('/login')
      })
  }, [queryClient])

  const value = useMemo<AuthState>(
    () => ({
      user: me.data ?? null,
      loading: hasSession() && me.isPending,
      login,
      logout,
    }),
    [me.data, me.isPending, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth phải nằm trong AuthProvider')
  return ctx
}

export function homeFor(role: Role): string {
  return role === 'admin' ? '/admin' : '/chat'
}

/** Chặn route: chưa đăng nhập -> /login; sai vai trò -> trang chủ của vai trò đó. */
export function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return <div className="flex h-full items-center justify-center text-slate-500">Đang tải…</div>
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (user.vai_tro !== role) return <Navigate to={homeFor(user.vai_tro)} replace />
  return <>{children}</>
}
