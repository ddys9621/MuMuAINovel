import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2, CheckCircle, XCircle } from 'lucide-react'
import { authApi } from '@/services/api'

export default function AuthCallback() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('正在处理登录...')

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // LinuxDO OAuth 回调后，后端已通过 cookie 设置了 session
        // 直接获取当前用户信息验证登录状态
        await authApi.getCurrentUser()
        setStatus('success')
        setMessage('登录成功，正在跳转...')
        setTimeout(() => navigate('/', { replace: true }), 1000)
      } catch {
        setStatus('error')
        setMessage('登录失败，请重试')
      }
    }

    handleCallback()
  }, [navigate, searchParams])

  return (
    <div className="min-h-screen flex items-center justify-center bg-white">
      <div className="text-center space-y-4">
        {status === 'loading' && <Loader2 className="w-8 h-8 animate-spin text-brand mx-auto" />}
        {status === 'success' && <CheckCircle className="w-8 h-8 text-green-500 mx-auto" />}
        {status === 'error' && <XCircle className="w-8 h-8 text-red-500 mx-auto" />}
        <p className="text-sm text-content-secondary">{message}</p>
        {status === 'error' && (
          <button onClick={() => navigate('/login', { replace: true })} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm">
            返回登录
          </button>
        )}
      </div>
    </div>
  )
}
