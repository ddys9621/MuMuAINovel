import { useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, KeyRound, Loader2, Mail, Save, Send } from 'lucide-react'
import { toast } from 'sonner'
import { adminApi } from '@/services/api'
import type { AuthSettingsUpdate, AuthSettingsView, SmtpEncryption } from '@/types'

const inputCls =
  'w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors disabled:bg-surface-hover/50 disabled:cursor-not-allowed'
const labelCls = 'block text-sm text-content-secondary mb-1'

const ENCRYPTION_OPTIONS: Array<{ value: SmtpEncryption; label: string }> = [
  { value: 'ssl', label: 'SSL/TLS（常用 465）' },
  { value: 'starttls', label: 'STARTTLS（常用 587）' },
  { value: 'none', label: '不加密（常用 25）' },
]

/** 表单态：秘密字段是「本次要写入的新值」，空串 = 不修改；端口用字符串承接输入框 */
interface FormState {
  linuxdo_login_enabled: boolean
  linuxdo_register_enabled: boolean
  linuxdo_client_id: string
  linuxdo_client_secret: string
  linuxdo_redirect_uri: string
  email_login_enabled: boolean
  email_register_enabled: boolean
  smtp_host: string
  smtp_port: string
  smtp_encryption: SmtpEncryption
  smtp_username: string
  smtp_password: string
  smtp_from: string
}

function toForm(view: AuthSettingsView): FormState {
  return {
    linuxdo_login_enabled: view.linuxdo_login_enabled,
    linuxdo_register_enabled: view.linuxdo_register_enabled,
    linuxdo_client_id: view.linuxdo_client_id,
    linuxdo_client_secret: '',
    linuxdo_redirect_uri: view.linuxdo_redirect_uri,
    email_login_enabled: view.email_login_enabled,
    email_register_enabled: view.email_register_enabled,
    smtp_host: view.smtp_host,
    smtp_port: String(view.smtp_port),
    smtp_encryption: view.smtp_encryption,
    smtp_username: view.smtp_username,
    smtp_password: '',
    smtp_from: view.smtp_from,
  }
}

function toUpdate(form: FormState): AuthSettingsUpdate | null {
  const port = Number(form.smtp_port)
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    toast.error('SMTP 端口需为 1-65535 的整数')
    return null
  }
  const update: AuthSettingsUpdate = {
    linuxdo_login_enabled: form.linuxdo_login_enabled,
    linuxdo_register_enabled: form.linuxdo_register_enabled,
    linuxdo_client_id: form.linuxdo_client_id.trim(),
    linuxdo_redirect_uri: form.linuxdo_redirect_uri.trim(),
    email_login_enabled: form.email_login_enabled,
    email_register_enabled: form.email_register_enabled,
    smtp_host: form.smtp_host.trim(),
    smtp_port: port,
    smtp_encryption: form.smtp_encryption,
    smtp_username: form.smtp_username.trim(),
    smtp_from: form.smtp_from.trim(),
  }
  // 秘密字段留空表示不修改，不传给后端
  if (form.linuxdo_client_secret.trim()) update.linuxdo_client_secret = form.linuxdo_client_secret.trim()
  if (form.smtp_password) update.smtp_password = form.smtp_password
  return update
}

export function LoginSettingsCard() {
  const [view, setView] = useState<AuthSettingsView | null>(null)
  const [form, setForm] = useState<FormState | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testTo, setTestTo] = useState('')
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    adminApi
      .getAuthSettings()
      .then((v) => {
        setView(v)
        setForm(toForm(v))
      })
      .catch(() => { /* api 层已 toast */ })
  }, [])

  const patch = (changes: Partial<FormState>) => setForm((f) => (f ? { ...f, ...changes } : f))

  const handleSave = async () => {
    if (!form) return
    const update = toUpdate(form)
    if (!update) return
    setSaving(true)
    try {
      const v = await adminApi.updateAuthSettings(update)
      setView(v)
      setForm(toForm(v))
      toast.success('登录方式设置已保存')
    } catch { /* api 层已 toast */ } finally { setSaving(false) }
  }

  const handleTestEmail = async () => {
    if (!testTo.trim()) { toast.error('请输入测试收件邮箱'); return }
    setTesting(true)
    try {
      const res = await adminApi.sendTestEmail(testTo.trim())
      toast.success(res.message || '测试邮件已发送')
    } catch { /* api 层已 toast */ } finally { setTesting(false) }
  }

  const defaultRedirect = `${window.location.origin}/api/auth/linuxdo/callback`

  if (!view || !form) {
    return (
      <div className="bg-white border border-surface-border rounded-card px-5 py-4 flex items-center gap-2 text-sm text-content-secondary">
        <Loader2 className="w-4 h-4 animate-spin" />
        正在加载登录方式设置…
      </div>
    )
  }

  const linuxdoReady = !!(form.linuxdo_client_id.trim() && form.linuxdo_redirect_uri.trim() && (view.linuxdo_client_secret_set || form.linuxdo_client_secret.trim()))
  const smtpReady = !!(form.smtp_host.trim() && form.smtp_from.trim())

  const summary = [
    `Linux.do 登录 ${view.linuxdo_login_enabled ? '开' : '关'}`,
    `Linux.do 注册 ${view.linuxdo_register_enabled ? '开' : '关'}`,
    `邮箱登录 ${view.email_login_enabled ? '开' : '关'}`,
    `邮箱注册 ${view.email_register_enabled ? '开' : '关'}`,
  ]

  return (
    <div className="bg-white border border-surface-border rounded-card">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left hover:bg-surface-hover/40 transition-colors"
      >
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-content">登录方式设置</h2>
          <p className="mt-1 text-xs text-content-secondary truncate">{summary.join(' · ')}（账号密码登录由 .env 控制）</p>
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 shrink-0 text-content-secondary" /> : <ChevronDown className="w-4 h-4 shrink-0 text-content-secondary" />}
      </button>

      {expanded && (
        <div className="border-t border-surface-border px-5 py-5 space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Linux.do */}
            <section className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-content">
                <KeyRound className="w-4 h-4 text-brand" />
                Linux.do OAuth
              </div>
              <div className="flex flex-wrap gap-x-6 gap-y-2">
                <label className="flex items-center gap-2 text-sm text-content cursor-pointer">
                  <input type="checkbox" checked={form.linuxdo_login_enabled} onChange={(e) => patch({ linuxdo_login_enabled: e.target.checked, ...(e.target.checked ? {} : { linuxdo_register_enabled: false }) })} className="rounded" />
                  允许 Linux.do 登录
                </label>
                <label className={`flex items-center gap-2 text-sm cursor-pointer ${form.linuxdo_login_enabled ? 'text-content' : 'text-content-tertiary cursor-not-allowed'}`} title={form.linuxdo_login_enabled ? '' : '先开启 Linux.do 登录'}>
                  <input type="checkbox" disabled={!form.linuxdo_login_enabled} checked={form.linuxdo_register_enabled} onChange={(e) => patch({ linuxdo_register_enabled: e.target.checked })} className="rounded" />
                  允许新用户通过 Linux.do 注册
                </label>
              </div>
              {form.linuxdo_login_enabled && !linuxdoReady && (
                <p className="text-xs text-orange-500">Client ID / Client Secret / 回调地址未填写完整，Linux.do 登录不会生效。</p>
              )}
              <div>
                <label className={labelCls}>Client ID</label>
                <input value={form.linuxdo_client_id} onChange={(e) => patch({ linuxdo_client_id: e.target.value })} className={inputCls} autoComplete="off" />
              </div>
              <div>
                <label className={labelCls}>Client Secret</label>
                <input
                  type="password"
                  value={form.linuxdo_client_secret}
                  onChange={(e) => patch({ linuxdo_client_secret: e.target.value })}
                  placeholder={view.linuxdo_client_secret_set ? '已设置，留空则不修改' : '未设置'}
                  className={inputCls}
                  autoComplete="new-password"
                />
              </div>
              <div>
                <label className={labelCls}>回调地址（需与 Linux.do 应用后台登记的一致）</label>
                <div className="flex gap-2">
                  <input value={form.linuxdo_redirect_uri} onChange={(e) => patch({ linuxdo_redirect_uri: e.target.value })} placeholder={defaultRedirect} className={inputCls} autoComplete="off" />
                  <button type="button" onClick={() => patch({ linuxdo_redirect_uri: defaultRedirect })} className="shrink-0 border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-3 py-2 text-xs whitespace-nowrap">
                    用当前地址
                  </button>
                </div>
              </div>
            </section>

            {/* 邮箱 */}
            <section className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-content">
                <Mail className="w-4 h-4 text-brand" />
                邮箱登录 / 注册（SMTP）
              </div>
              <div className="flex flex-wrap gap-x-6 gap-y-2">
                <label className="flex items-center gap-2 text-sm text-content cursor-pointer">
                  <input type="checkbox" checked={form.email_login_enabled} onChange={(e) => patch({ email_login_enabled: e.target.checked, ...(e.target.checked ? {} : { email_register_enabled: false }) })} className="rounded" />
                  允许邮箱密码登录
                </label>
                <label className={`flex items-center gap-2 text-sm cursor-pointer ${form.email_login_enabled ? 'text-content' : 'text-content-tertiary cursor-not-allowed'}`} title={form.email_login_enabled ? '' : '先开启邮箱登录'}>
                  <input type="checkbox" disabled={!form.email_login_enabled} checked={form.email_register_enabled} onChange={(e) => patch({ email_register_enabled: e.target.checked })} className="rounded" />
                  允许邮箱验证码注册
                </label>
              </div>
              {form.email_register_enabled && !smtpReady && (
                <p className="text-xs text-orange-500">SMTP 服务器与发件人未填写，无法发送验证码，邮箱注册不会生效。</p>
              )}
              <div className="grid grid-cols-3 gap-2">
                <div className="col-span-2">
                  <label className={labelCls}>SMTP 服务器</label>
                  <input value={form.smtp_host} onChange={(e) => patch({ smtp_host: e.target.value })} placeholder="smtp.example.com" className={inputCls} autoComplete="off" />
                </div>
                <div>
                  <label className={labelCls}>端口</label>
                  <input type="number" min={1} max={65535} value={form.smtp_port} onChange={(e) => patch({ smtp_port: e.target.value })} className={inputCls} />
                </div>
              </div>
              <div>
                <label className={labelCls}>加密方式</label>
                <select value={form.smtp_encryption} onChange={(e) => patch({ smtp_encryption: e.target.value as SmtpEncryption })} className={inputCls}>
                  {ENCRYPTION_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className={labelCls}>SMTP 账号</label>
                  <input value={form.smtp_username} onChange={(e) => patch({ smtp_username: e.target.value })} placeholder="可留空（免认证中继）" className={inputCls} autoComplete="off" />
                </div>
                <div>
                  <label className={labelCls}>SMTP 密码 / 授权码</label>
                  <input
                    type="password"
                    value={form.smtp_password}
                    onChange={(e) => patch({ smtp_password: e.target.value })}
                    placeholder={view.smtp_password_set ? '已设置，留空则不修改' : '未设置'}
                    className={inputCls}
                    autoComplete="new-password"
                  />
                </div>
              </div>
              <div>
                <label className={labelCls}>发件人邮箱</label>
                <input value={form.smtp_from} onChange={(e) => patch({ smtp_from: e.target.value })} placeholder="noreply@example.com" className={inputCls} autoComplete="off" />
              </div>
              <div>
                <label className={labelCls}>发送测试邮件（使用已保存的 SMTP 配置）</label>
                <div className="flex gap-2">
                  <input type="email" value={testTo} onChange={(e) => setTestTo(e.target.value)} placeholder="收件邮箱" className={inputCls} />
                  <button
                    type="button"
                    onClick={handleTestEmail}
                    disabled={testing || !view.smtp_host || !view.smtp_from}
                    title={view.smtp_host && view.smtp_from ? '' : '请先保存 SMTP 配置'}
                    className="shrink-0 inline-flex items-center gap-1.5 border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-3 py-2 text-xs whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                    发送
                  </button>
                </div>
              </div>
            </section>
          </div>

          <div className="flex items-center justify-between gap-4 pt-2 border-t border-surface-border">
            <p className="text-xs text-content-tertiary">
              关闭「注册」后老用户仍可登录，只是不再创建新账号；关闭「登录」则该方式全部不可用。
            </p>
            <button
              onClick={handleSave}
              disabled={saving}
              className="shrink-0 inline-flex items-center gap-1.5 bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors disabled:opacity-60"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              保存设置
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
