import { useState, useEffect, type FormEvent, type ReactNode } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { User, Lock, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { authApi } from '@/services/api'
import { BrandLogo } from '@/components/ui/BrandLogo'

const FIELD_ICON_CLASS =
  'pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-content-tertiary transition-colors peer-focus:text-brand'

function LoginShell({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden px-4 py-10">
      <div className="hh-orb left-[calc(50%-460px)] top-[calc(50%-460px)] h-[520px] w-[520px] bg-brand/20 animate-float-soft" />
      <div className="hh-orb left-[calc(50%-60px)] top-[calc(50%-40px)] h-[560px] w-[560px] bg-brand-400/25" />

      <div className="hh-glass z-10 w-full max-w-[400px] px-8 py-10 md:px-10">{children}</div>
    </div>
  )
}

export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const redirectTo = searchParams.get('redirect') || '/'

  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(true)
  const [localAuthEnabled, setLocalAuthEnabled] = useState(false)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  useEffect(() => {
    const init = async () => {
      try {
        await authApi.getCurrentUser()
        navigate(redirectTo, { replace: true })
        return
      } catch {
        // 未登录，继续
      }

      try {
        const config = await authApi.getAuthConfig()
        setLocalAuthEnabled(config.local_auth_enabled)
      } catch {
        toast.error('获取认证配置失败')
      } finally {
        setChecking(false)
      }
    }

    init()
  }, [navigate, redirectTo])

  const handleLocalLogin = async (e: FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) {
      toast.error('请输入用户名和密码')
      return
    }

    setLoading(true)
    try {
      const res = await authApi.localLogin(username, password)
      if (res.success) {
        toast.success('登录成功')
        navigate(redirectTo, { replace: true })
      }
    } catch {
      // api 拦截器已处理 toast
    } finally {
      setLoading(false)
    }
  }

  if (checking) {
    return (
      <LoginShell>
        <div className="flex flex-col items-center gap-4 py-4 text-center">
          <Loader2 className="h-6 w-6 animate-spin text-brand" />
          <p className="text-sm text-content-secondary">正在校验登录状态…</p>
        </div>
      </LoginShell>
    )
  }

  return (
    <LoginShell>
      <div className="flex flex-col items-center text-center">
        <BrandLogo size="lg" />
        <h1 className="mt-5 text-2xl font-semibold tracking-tight text-content">HH小说创作</h1>
        <p className="mt-1.5 text-sm text-content-secondary">登录以继续创作</p>
      </div>

      {localAuthEnabled ? (
        <form onSubmit={handleLocalLogin} className="mt-8">
          <div className="space-y-3">
            <div className="relative">
              <label htmlFor="username" className="sr-only">
                用户名
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="用户名"
                autoComplete="username"
                className="hh-field peer h-12 pl-11"
              />
              <User className={FIELD_ICON_CLASS} />
            </div>

            <div className="relative">
              <label htmlFor="password" className="sr-only">
                密码
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="密码"
                autoComplete="current-password"
                className="hh-field peer h-12 pl-11"
              />
              <Lock className={FIELD_ICON_CLASS} />
            </div>
          </div>

          <button type="submit" disabled={loading} className="hh-btn-primary mt-6 h-12 w-full text-[15px]">
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                登录中…
              </>
            ) : (
              '登录'
            )}
          </button>

          <p className="mt-5 text-center text-xs text-content-tertiary">首次登录将自动创建账号</p>
        </form>
      ) : (
        <p className="hh-subpanel mt-8 px-4 py-3 text-center text-sm text-content-secondary">
          暂未开启本地登录，请联系管理员
        </p>
      )}
    </LoginShell>
  )
}
