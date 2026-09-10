import { useEffect, useState, type FormEvent } from 'react'
import { Mail, Lock, KeyRound, User, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { authApi } from '@/services/api'

const FIELD_ICON_CLASS =
  'pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-content-tertiary transition-colors peer-focus:text-brand'

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

interface EmailAuthFormProps {
  /** 上方有登录方式切换条时收紧间距 */
  compact?: boolean
  registerEnabled: boolean
  onSuccess: () => void
}

type Mode = 'login' | 'register'

/** 邮箱密码登录 + 邮箱验证码注册（注册入口由后台「邮箱注册」开关决定） */
export function EmailAuthForm({ compact = false, registerEnabled, onSuccess }: EmailAuthFormProps) {
  const [mode, setMode] = useState<Mode>('login')
  const [loading, setLoading] = useState(false)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [code, setCode] = useState('')

  const [sendingCode, setSendingCode] = useState(false)
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    if (cooldown <= 0) return
    const timer = window.setTimeout(() => setCooldown((s) => s - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [cooldown])

  // 后台把注册关掉后，停留在注册态的表单退回登录态
  useEffect(() => {
    if (!registerEnabled) setMode('login')
  }, [registerEnabled])

  const emailValid = EMAIL_RE.test(email.trim())

  const handleSendCode = async () => {
    if (!emailValid) {
      toast.error('请输入正确的邮箱地址')
      return
    }
    setSendingCode(true)
    try {
      const res = await authApi.emailSendCode(email.trim())
      toast.success(res.message || '验证码已发送，请查收邮件')
      setCooldown(res.cooldown_seconds || 60)
    } catch {
      // api 拦截器已处理 toast
    } finally {
      setSendingCode(false)
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!emailValid) {
      toast.error('请输入正确的邮箱地址')
      return
    }
    if (password.length < 6) {
      toast.error('密码至少 6 个字符')
      return
    }
    if (mode === 'register') {
      if (!/^\d{6}$/.test(code.trim())) {
        toast.error('请输入 6 位数字验证码')
        return
      }
      if (password !== confirmPassword) {
        toast.error('两次输入的密码不一致')
        return
      }
    }

    setLoading(true)
    try {
      const res =
        mode === 'register'
          ? await authApi.emailRegister({
              email: email.trim(),
              code: code.trim(),
              password,
              display_name: displayName.trim() || undefined,
            })
          : await authApi.emailLogin(email.trim(), password)
      if (res.success) {
        toast.success(mode === 'register' ? '注册成功' : '登录成功')
        onSuccess()
      }
    } catch {
      // api 拦截器已处理 toast
    } finally {
      setLoading(false)
    }
  }

  const isRegister = mode === 'register'

  return (
    <form onSubmit={handleSubmit} className={compact ? 'mt-5' : 'mt-8'}>
      <div className="space-y-3">
        <div className="relative">
          <label htmlFor="email" className="sr-only">
            邮箱
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="邮箱"
            autoComplete="email"
            className="hh-field peer h-12 pl-11"
          />
          <Mail className={FIELD_ICON_CLASS} />
        </div>

        {isRegister && (
          <>
            <div className="relative flex gap-2">
              <div className="relative flex-1">
                <label htmlFor="email-code" className="sr-only">
                  验证码
                </label>
                <input
                  id="email-code"
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                  placeholder="6 位验证码"
                  autoComplete="one-time-code"
                  className="hh-field peer h-12 pl-11"
                />
                <KeyRound className={FIELD_ICON_CLASS} />
              </div>
              <button
                type="button"
                onClick={handleSendCode}
                disabled={sendingCode || cooldown > 0 || !emailValid}
                className="hh-btn-secondary h-12 shrink-0 whitespace-nowrap px-4"
              >
                {sendingCode ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : cooldown > 0 ? (
                  `${cooldown}s 后重发`
                ) : (
                  '获取验证码'
                )}
              </button>
            </div>

            <div className="relative">
              <label htmlFor="display-name" className="sr-only">
                昵称
              </label>
              <input
                id="display-name"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="昵称（可选，默认取邮箱前缀）"
                maxLength={50}
                autoComplete="nickname"
                className="hh-field peer h-12 pl-11"
              />
              <User className={FIELD_ICON_CLASS} />
            </div>
          </>
        )}

        <div className="relative">
          <label htmlFor="email-password" className="sr-only">
            密码
          </label>
          <input
            id="email-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={isRegister ? '设置密码（至少 6 位）' : '密码'}
            autoComplete={isRegister ? 'new-password' : 'current-password'}
            className="hh-field peer h-12 pl-11"
          />
          <Lock className={FIELD_ICON_CLASS} />
        </div>

        {isRegister && (
          <div className="relative">
            <label htmlFor="email-password-confirm" className="sr-only">
              确认密码
            </label>
            <input
              id="email-password-confirm"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="再次输入密码"
              autoComplete="new-password"
              className="hh-field peer h-12 pl-11"
            />
            <Lock className={FIELD_ICON_CLASS} />
          </div>
        )}
      </div>

      <button type="submit" disabled={loading} className="hh-btn-primary mt-6 h-12 w-full text-[15px]">
        {loading ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" />
            {isRegister ? '注册中…' : '登录中…'}
          </>
        ) : isRegister ? (
          '注册并登录'
        ) : (
          '登录'
        )}
      </button>

      <p className="mt-5 text-center text-xs text-content-tertiary">
        {registerEnabled ? (
          isRegister ? (
            <>
              已有账号？
              <button type="button" onClick={() => setMode('login')} className="ml-1 text-brand hover:underline">
                去登录
              </button>
            </>
          ) : (
            <>
              还没有账号？
              <button type="button" onClick={() => setMode('register')} className="ml-1 text-brand hover:underline">
                邮箱注册
              </button>
            </>
          )
        ) : (
          '当前未开放邮箱注册，仅已有账号可登录'
        )}
      </p>
    </form>
  )
}
