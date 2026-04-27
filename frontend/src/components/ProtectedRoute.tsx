import { useState, useEffect, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { authApi } from '@/services/api'
import { PageLoading } from '@/components/ui/PageLoading'
import { sessionManager } from '@/utils/sessionManager'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [authenticated, setAuthenticated] = useState(false)
  const location = useLocation()

  useEffect(() => {
    let cancelled = false

    authApi.getCurrentUser()
      .then(() => {
        if (cancelled) return
        sessionManager.start()
        setAuthenticated(true)
      })
      .catch(() => {
        if (cancelled) return
        sessionManager.stop()
        setAuthenticated(false)
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  if (loading) return <PageLoading />
  if (!authenticated) {
    return <Navigate to={`/login?redirect=${encodeURIComponent(location.pathname)}`} replace />
  }
  return <>{children}</>
}
