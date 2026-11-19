import { useQuery } from '@tanstack/react-query'
import { CircleAlert, TriangleAlert } from 'lucide-react'
import { fetchHealth, healthNotice } from '../../lib/health'

/** Banner trạng thái hệ thống trên trang chat: đọc /health mỗi 30 giây. */
export function StatusBanner() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
    retry: false,
  })
  if (health.isPending) return null
  const notice = healthNotice(health.data ?? null)
  if (!notice) return null

  const isError = notice.level === 'error'
  const Icon = isError ? CircleAlert : TriangleAlert
  return (
    <div
      role="status"
      className={`flex items-start gap-2 border-b px-4 py-2.5 text-sm ${
        isError ? 'border-err/20 bg-err-bg text-err' : 'border-amber-200 bg-amber-50 text-amber-900'
      }`}
    >
      <Icon size={18} className="mt-0.5 shrink-0" />
      <p>
        <span className="font-medium">{notice.title}.</span> {notice.detail}
      </p>
    </div>
  )
}
