import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router'
import StudentLayout from './components/StudentLayout'
import { RequireRole, homeFor, useAuth } from './lib/auth'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'
import ProceduresPage from './pages/ProceduresPage'

// Trang quản trị tải riêng (có thư viện biểu đồ) -> sinh viên không phải tải phần này
const AdminLayout = lazy(() => import('./components/AdminLayout'))
const DocumentsPage = lazy(() => import('./pages/admin/DocumentsPage'))
const RetrievalPage = lazy(() => import('./pages/admin/RetrievalPage'))
const McpPage = lazy(() => import('./pages/admin/McpPage'))
const AuditPage = lazy(() => import('./pages/admin/AuditPage'))
const StatsPage = lazy(() => import('./pages/admin/StatsPage'))
const AccountsPage = lazy(() => import('./pages/admin/AccountsPage'))
const StudentsPage = lazy(() => import('./pages/admin/StudentsPage'))

function Home() {
  const { user, loading } = useAuth()
  if (loading) return null
  return <Navigate to={user ? homeFor(user.vai_tro) : '/login'} replace />
}

const loading = (
  <div className="flex h-full items-center justify-center text-slate-500">Đang tải…</div>
)

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireRole role="sinh_vien">
            <StudentLayout />
          </RequireRole>
        }
      >
        {/* Một route cho cả /chat và /chat/:id: tạo hội thoại mới không làm remount trang
            -> luồng SSE của câu hỏi đầu tiên không bị cắt. */}
        <Route path="/chat/:id?" element={<ChatPage />} />
        <Route path="/thu-tuc" element={<ProceduresPage />} />
      </Route>
      {/* Sinh viên vào /admin -> RequireRole chuyển về /chat */}
      <Route
        path="/admin"
        element={
          <RequireRole role="admin">
            <Suspense fallback={loading}>
              <AdminLayout />
            </Suspense>
          </RequireRole>
        }
      >
        <Route index element={<Navigate to="/admin/tai-lieu" replace />} />
        <Route path="tai-lieu" element={<DocumentsPage />} />
        <Route path="thu-truy-xuat" element={<RetrievalPage />} />
        <Route path="mcp" element={<McpPage />} />
        <Route path="nhat-ky" element={<AuditPage />} />
        <Route path="thong-ke" element={<StatsPage />} />
        <Route path="tai-khoan" element={<AccountsPage />} />
        <Route path="sinh-vien" element={<StudentsPage />} />
        <Route path="*" element={<Navigate to="/admin/tai-lieu" replace />} />
      </Route>
      <Route path="*" element={<Home />} />
    </Routes>
  )
}
