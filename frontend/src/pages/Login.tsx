import { useState, useEffect, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Check,
  User,
  Lock,
  Loader2,
  Sparkles,
  Smartphone,
  Library,
} from 'lucide-react'
import { toast } from 'sonner'
import { authApi } from '@/services/api'
import { BrandLogo } from '@/components/ui/BrandLogo'

const FEATURES = [
  '世界设定、角色档案与章节素材统一归档',
  '从灵感记录到正式项目，创作入口清晰可控',
  '项目进度、更新时间与状态变化一目了然',
  '仅使用本地账号密码登录',
] as const

const SCENES = [
  {
    icon: Library,
    title: '项目总览清晰',
    desc: '快速回到最近推进的作品，保持创作连续性。',
  },
  {
    icon: Sparkles,
    title: '创作结构完整',
    desc: '世界观、角色、大纲与章节内容可以持续沉淀。',
  },
  {
    icon: Smartphone,
    title: '登录流程顺滑',
    desc: '打开即登录，直接回到当前正在创作的工作台。',
  },
] as const

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
      <div className="fixed inset-0 flex items-center justify-center bg-transparent px-4">
        <div className="fanqie-soft-card flex min-w-[240px] flex-col items-center gap-4 px-8 py-10 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-brand/10 text-brand">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
          <div>
            <p className="text-base font-semibold text-content">正在校验登录状态</p>
            <p className="mt-1 text-sm text-content-secondary">稍后即可进入 HH小说创作</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#fff9f5] px-4 py-4 md:px-6 md:py-6">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,121,80,0.18),transparent_26%),radial-gradient(circle_at_bottom_right,rgba(255,198,127,0.14),transparent_30%)]" />
      <div className="pointer-events-none absolute left-1/2 top-0 h-64 w-64 -translate-x-1/2 rounded-full bg-brand/8 blur-3xl" />

      <div className="relative mx-auto flex min-h-[calc(100vh-2rem)] max-w-[1600px] overflow-hidden rounded-[36px] border border-white/70 bg-white/60 shadow-[0_42px_120px_-56px_rgba(132,63,29,0.4)] backdrop-blur-xl md:min-h-[calc(100vh-3rem)] md:flex-row">
        <section className="relative hidden w-[55%] overflow-hidden bg-[linear-gradient(140deg,#ff7f59_0%,#ff9a63_32%,#ffbe7d_72%,#ffe3bc_100%)] px-10 py-10 text-white md:flex md:flex-col lg:px-14 lg:py-12">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_18%_18%,rgba(255,255,255,0.3),transparent_20%),radial-gradient(circle_at_78%_14%,rgba(255,244,230,0.3),transparent_22%),linear-gradient(180deg,rgba(255,255,255,0.04),rgba(108,45,12,0.12))]" />
          <div className="absolute -left-20 bottom-0 h-60 w-60 rounded-full bg-white/10 blur-3xl" />
          <div className="absolute right-8 top-12 h-40 w-40 rounded-full bg-white/20 blur-3xl" />

          <div className="relative z-10 flex items-center justify-between gap-4">
            <div className="inline-flex items-center gap-3 rounded-pill border border-white/20 bg-white/10 px-4 py-2 text-sm font-medium backdrop-blur-sm">
              <BrandLogo size="sm" className="h-7 w-7 rounded-xl shadow-none ring-1 ring-white/20" textClassName="text-[11px]" />
              <span>HH小说创作</span>
            </div>
            <div className="rounded-pill border border-white/16 bg-white/10 px-3 py-1.5 text-xs font-medium text-white/90 backdrop-blur-sm">
              专业小说创作平台
            </div>
          </div>

          <div className="relative z-10 mt-12 max-w-[620px]">
            <div className="inline-flex items-center gap-2 rounded-pill bg-white/14 px-3 py-1.5 text-xs font-medium backdrop-blur-sm">
              <Sparkles className="h-3.5 w-3.5" />
              开始你的小说创作
            </div>
            <h1 className="mt-5 text-4xl font-semibold leading-tight lg:text-[54px] lg:leading-[1.06]">
              从设定到章节，
              <br />
              让创作持续推进。
            </h1>
            <p className="mt-5 max-w-[560px] text-base leading-7 text-white/90 lg:text-lg">
              HH小说创作为长篇写作提供清晰的结构化工作台，帮助你统一管理世界观、角色设定、大纲规划与章节内容。
            </p>

            <div className="mt-6 flex flex-wrap gap-2.5 text-sm text-white/92">
              <span className="rounded-pill border border-white/16 bg-white/10 px-3 py-1.5 backdrop-blur-sm">世界设定</span>
              <span className="rounded-pill border border-white/16 bg-white/10 px-3 py-1.5 backdrop-blur-sm">角色管理</span>
              <span className="rounded-pill border border-white/16 bg-white/10 px-3 py-1.5 backdrop-blur-sm">大纲规划</span>
              <span className="rounded-pill border border-white/16 bg-white/10 px-3 py-1.5 backdrop-blur-sm">章节创作</span>
            </div>
          </div>

          <div className="relative z-10 mt-10 grid gap-3 lg:grid-cols-2">
            {FEATURES.map((text) => (
              <div key={text} className="rounded-[24px] border border-white/16 bg-white/10 p-4 backdrop-blur-sm shadow-[0_24px_50px_-36px_rgba(94,37,10,0.55)]">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-white/14">
                    <Check className="h-4 w-4" />
                  </span>
                  <p className="text-sm leading-6 text-white/92">{text}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="relative z-10 mt-auto grid gap-3 pt-10 lg:grid-cols-3">
            {SCENES.map(({ icon: Icon, title, desc }, index) => (
              <div key={title} className={`rounded-[24px] border border-white/16 bg-white/12 p-4 backdrop-blur-sm ${index === 1 ? 'lg:-translate-y-3' : ''}`}>
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/16">
                  <Icon className="h-5 w-5" />
                </div>
                <h2 className="mt-4 text-base font-semibold">{title}</h2>
                <p className="mt-2 text-sm leading-6 text-white/82">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="relative flex flex-1 items-center justify-center bg-[linear-gradient(180deg,rgba(255,252,248,0.92)_0%,rgba(255,246,239,0.98)_100%)] px-5 py-10 md:px-8 lg:px-12">
          <div className="absolute inset-x-10 top-0 h-24 rounded-full bg-brand/10 blur-3xl" />
          <div className="relative z-10 w-full max-w-[460px]">
            <div className="mb-8 flex items-center gap-3 md:hidden">
              <BrandLogo size="lg" />
              <div>
                <p className="text-base font-semibold text-content">HH小说创作</p>
                <p className="text-sm text-content-secondary">专业小说创作平台</p>
              </div>
            </div>

            <div className="fanqie-soft-card p-6 md:p-8">
              <div className="mb-8">
                <div className="fanqie-chip border-brand/10 bg-brand/5 text-brand">欢迎回来</div>
                <h2 className="mt-4 text-[30px] font-semibold leading-tight text-content">登录 HH小说创作</h2>
                <p className="mt-3 text-sm leading-6 text-content-secondary">
                  使用本地账号登录并继续创作。
                </p>
                <div className="mt-5 flex flex-wrap gap-2">
                  <span className="rounded-pill bg-white px-3 py-1.5 text-xs font-medium text-content-secondary shadow-xs">结构化创作</span>
                  <span className="rounded-pill bg-white px-3 py-1.5 text-xs font-medium text-content-secondary shadow-xs">项目集中管理</span>
                  <span className="rounded-pill bg-white px-3 py-1.5 text-xs font-medium text-content-secondary shadow-xs">安全访问</span>
                </div>
              </div>

              {localAuthEnabled && (
                <form onSubmit={handleLocalLogin} className="space-y-5">
                  <div>
                    <label htmlFor="username" className="mb-2 block text-sm font-medium text-content">
                      用户名
                    </label>
                    <div className="relative">
                      <User className="pointer-events-none absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-content-tertiary" />
                      <input
                        id="username"
                        type="text"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        placeholder="请输入用户名"
                        autoComplete="username"
                        className="h-12 w-full rounded-[18px] pl-12 pr-4 text-sm"
                      />
                    </div>
                  </div>

                  <div>
                    <label htmlFor="password" className="mb-2 block text-sm font-medium text-content">
                      密码
                    </label>
                    <div className="relative">
                      <Lock className="pointer-events-none absolute left-4 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-content-tertiary" />
                      <input
                        id="password"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="请输入密码"
                        autoComplete="current-password"
                        className="h-12 w-full rounded-[18px] pl-12 pr-4 text-sm"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="fanqie-primary-btn h-12 w-full text-[15px] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        登录中…
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" />
                        进入创作工作台
                      </>
                    )}
                  </button>
                </form>
              )}

              {!localAuthEnabled && (
                <p className="rounded-[18px] bg-white/80 px-4 py-3 text-center text-sm text-content-secondary">
                  暂未开启本地登录，请联系管理员
                </p>
              )}

              {localAuthEnabled && (
                <div className="mt-6 rounded-[20px] border border-brand/10 bg-brand/5 px-4 py-4 text-sm text-content-secondary">
                  <p className="font-medium text-content">首次登录会自动创建账号</p>
                  <div className="mt-2 space-y-1.5 text-xs leading-5 text-content-secondary">
                    <p>• 登录后可继续访问已有项目与创作内容</p>
                    <p>• 仅支持本地账号密码登录</p>
                    <p>• 进入后可直接回到项目列表继续创作</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
