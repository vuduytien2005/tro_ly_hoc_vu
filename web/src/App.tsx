import { Navigate, Route, Routes } from 'react-router'
import StudentLayout from './components/StudentLayout'
import { RequireRole, homeFor, useAuth } from './lib/auth'
import AdminPlaceholder from './pages/AdminPlaceholder'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'
import ProceduresPage from './pages/ProceduresPage'

function Home() {
  const { user, loading } = useAuth()
  if (loading) return null
  return <Navigate to={user ? homeFor(user.vai_tro) : '/login'} replace />
}

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
      <Route
        path="/admin/*"
        element={
          <RequireRole role="admin">
            <AdminPlaceholder />
          </RequireRole>
        }
      />
      <Route path="*" element={<Home />} />
    </Routes>
  )
}
