import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  User as UserIcon,
  LogOut,
  KeyRound,
  Shield,
  X,
  Eye,
  EyeOff,
  Menu,
  ChevronDown,
  Sparkles,
  BookOpenText,
} from 'lucide-react'
import { toast } from 'sonner'
import { authApi } from '@/services/api'
import type { User } from '@/types'

interface HeaderProps {
  onMenuClick?: () => void
}

const ROUTE_META: Array<{ match: RegExp; title: string; subtitle: string }> = [
  { match: /^\/projects?$/, title: '我的项目', subtitle: '统一查看作品、更新时间与当前创作进度。' },
  { match: /^\/settings$/, title: '创作设置', subtitle: '调整模型、参数与偏好，让创作方式更贴合你的流程。' },
  { match: /^\/mcp-plugins$/, title: '插件工坊', subtitle: '扩展工具能力，让写作流程更完整。' },
  { match: /^\/user-management$/, title: '成员管理', subtitle: '统一查看用户权限与协作状态。' },
]

export function Header({ onMenuClick }: HeaderProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const [user, setUser] = useState<User | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [passwordModalOpen, setPasswordModalOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    authApi.getCurrentUser()
      .then(setUser)
      .catch(() => { /* 静默处理，未登录时不显示用户信息 */ })
  }, [])

  useEffect(() => {
    if (!menuOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [menuOpen])

  const handleLogout = useCallback(async () => {
    try {
      await authApi.logout()
      toast.success('已退出登录')
      navigate('/login')
    } catch {
      toast.error('退出失败，请重试')
    }
  }, [navigate])

  const openPasswordModal = () => {
    setMenuOpen(false)
    setPasswordModalOpen(true)
  }

  const pageMeta = useMemo(() => {
    return ROUTE_META.find((item) => item.match.test(location.pathname)) ?? {
      title: '创作工作台',
      subtitle: '围绕项目、设定与章节构建更清晰的创作空间。',
    }
  }, [location.pathname])

  return (
    <header className="relative z-20 border-b border-white/70 bg-white/65 px-4 py-3 backdrop-blur-xl md:px-6">
      <div className="absolute inset-x-10 top-0 h-20 rounded-full bg-brand/8 blur-3xl" />
      <div className="relative flex items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3 md:gap-4">
          <button
            onClick={onMenuClick}
            className="fanqie-toolbar-btn h-11 w-11 p-0 md:hidden"
            aria-label="切换侧栏"
          >
            <Menu className="h-5 w-5" />
          </button>

          <div className="hidden h-11 w-11 items-center justify-center rounded-2xl bg-brand/10 text-brand md:flex">
            <BookOpenText className="h-5 w-5" />
          </div>

          <div className="min-w-0">
            <div className="mb-1 flex items-center gap-2">
              <span className="fanqie-chip border-brand/10 bg-brand/5 text-brand">HH小说创作</span>
              <span className="hidden text-xs text-content-tertiary md:inline">/</span>
              <span className="hidden text-xs text-content-secondary md:inline">{pageMeta.title}</span>
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold text-content md:text-[22px]">{pageMeta.title}</h1>
              <p className="hidden truncate text-sm text-content-secondary md:block">{pageMeta.subtitle}</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2.5 md:gap-3">
          <div className="hidden items-center gap-2 rounded-pill border border-brand/15 bg-brand/5 px-3 py-2 text-sm text-content-secondary md:flex">
            <Sparkles className="h-4 w-4 text-brand" />
            保持创作节奏
          </div>

          <div className="relative" ref={menuRef}>
            <button
              onClick={() => setMenuOpen((prev) => !prev)}
              className="flex items-center gap-2 rounded-pill border border-white/80 bg-white/80 py-1.5 pl-1.5 pr-2 shadow-xs hover:bg-white"
            >
              {user?.avatar_url ? (
                <img src={user.avatar_url} alt="" className="h-9 w-9 rounded-full object-cover ring-2 ring-brand/10" />
              ) : (
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand/10 text-brand">
                  <UserIcon className="h-[18px] w-[18px]" />
                </span>
              )}
              <div className="hidden text-left md:block">
                <p className="max-w-[120px] truncate text-sm font-medium text-content">{user?.display_name || '用户'}</p>
                <p className="text-xs text-content-tertiary">{user?.is_admin ? '管理员权限' : '创作者'}</p>
              </div>
              <ChevronDown className="h-4 w-4 text-content-tertiary" />
            </button>

            {menuOpen && (
              <div className="absolute right-0 top-full z-50 mt-3 w-[260px] overflow-hidden rounded-[24px] border border-white/80 bg-white/95 shadow-lg backdrop-blur-md animate-slide-down">
                <div className="border-b border-surface-border px-4 py-4">
                  <div className="flex items-center gap-3">
                    {user?.avatar_url ? (
                      <img src={user.avatar_url} alt="" className="h-11 w-11 rounded-full object-cover ring-2 ring-brand/10" />
                    ) : (
                      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-brand/10 text-brand">
                        <UserIcon className="h-5 w-5" />
                      </span>
                    )}
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-sm font-semibold text-content">{user?.display_name || '用户'}</p>
                        {user?.is_admin && (
                          <span className="inline-flex items-center gap-1 rounded-pill bg-brand/10 px-2 py-0.5 text-[10px] font-semibold text-brand">
                            <Shield className="h-3 w-3" />
                            管理员
                          </span>
                        )}
                      </div>
                      <p className="truncate text-xs text-content-tertiary">{user?.username || '未命名用户'}</p>
                    </div>
                  </div>
                </div>

                <div className="p-2">
                  <button
                    onClick={openPasswordModal}
                    className="flex w-full items-center gap-3 rounded-[18px] px-3 py-3 text-sm text-content hover:bg-surface-hover"
                  >
                    <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-brand/10 text-brand">
                      <KeyRound className="h-[18px] w-[18px]" />
                    </span>
                    修改密码
                  </button>
                  <button
                    onClick={handleLogout}
                    className="flex w-full items-center gap-3 rounded-[18px] px-3 py-3 text-sm text-red-500 hover:bg-red-50"
                  >
                    <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-red-50 text-red-500">
                      <LogOut className="h-[18px] w-[18px]" />
                    </span>
                    退出登录
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {passwordModalOpen && (
        <PasswordModal onClose={() => setPasswordModalOpen(false)} />
      )}
    </header>
  )
}

function PasswordModal({ onClose }: { onClose: () => void }) {
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(true)
  const [hasPassword, setHasPassword] = useState(false)

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showNew, setShowNew] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  useEffect(() => {
    authApi.getPasswordStatus()
      .then((res) => setHasPassword(res.has_custom_password))
      .catch(() => toast.error('获取密码状态失败'))
      .finally(() => setChecking(false))
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (newPassword.length < 6) {
      toast.error('新密码至少 6 个字符')
      return
    }
    if (newPassword !== confirmPassword) {
      toast.error('两次输入的密码不一致')
      return
    }

    setLoading(true)
    try {
      await authApi.setPassword(newPassword)
      toast.success('密码修改成功')
      onClose()
    } catch {
      toast.error('密码修改失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4" onClick={onClose}>
      <div className="absolute inset-0 bg-[#2d130d]/50 backdrop-blur-sm" />

      <div
        className="relative w-full max-w-[430px] overflow-hidden rounded-modal border border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.96)_0%,rgba(255,247,240,0.98)_100%)] shadow-xl animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-surface-border px-6 py-5">
          <div className="mb-2 inline-flex items-center gap-2 rounded-pill bg-brand/10 px-3 py-1 text-xs font-medium text-brand">
            <Sparkles className="h-3.5 w-3.5" />
            安全中心
          </div>
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-content">{hasPassword ? '修改密码' : '设置密码'}</h3>
              <p className="mt-1 text-sm text-content-secondary">为你的创作账号设置更安全的访问方式。</p>
            </div>
            <button
              onClick={onClose}
              className="fanqie-toolbar-btn h-10 w-10 p-0"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {checking ? (
          <div className="px-6 py-12 text-center text-sm text-content-secondary">正在检查密码状态...</div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="space-y-4 px-6 py-5">
              <PasswordField
                label="新密码"
                value={newPassword}
                onChange={setNewPassword}
                visible={showNew}
                onToggle={() => setShowNew((v) => !v)}
                placeholder="至少 6 个字符"
              />
              <PasswordField
                label="确认密码"
                value={confirmPassword}
                onChange={setConfirmPassword}
                visible={showConfirm}
                onToggle={() => setShowConfirm((v) => !v)}
                placeholder="再次输入新密码"
              />
            </div>

            <div className="flex justify-end gap-3 border-t border-surface-border px-6 py-4">
              <button
                type="button"
                onClick={onClose}
                className="fanqie-secondary-btn"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={loading}
                className="fanqie-primary-btn disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? '提交中...' : '确认保存'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

function PasswordField({
  label,
  value,
  onChange,
  visible,
  onToggle,
  placeholder,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  visible: boolean
  onToggle: () => void
  placeholder?: string
}) {
  return (
    <div>
      <label className="mb-2 block text-sm font-medium text-content">{label}</label>
      <div className="relative">
        <input
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          required
          className="h-12 w-full rounded-[18px] px-4 pr-11 text-sm"
        />
        <button
          type="button"
          onClick={onToggle}
          className="absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full text-content-tertiary hover:bg-surface-hover hover:text-content-secondary"
        >
          {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </div>
  )
}
