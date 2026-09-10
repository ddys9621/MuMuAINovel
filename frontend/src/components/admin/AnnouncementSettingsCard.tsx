import { useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronUp, Eye, ImagePlus, Loader2, Megaphone, Save, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { adminApi } from '@/services/api'
import { AnnouncementModal } from '@/components/AnnouncementModal'
import type { AnnouncementFrequency, AnnouncementSettingsView, AnnouncementUpdate } from '@/types'

const inputCls =
  'w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors disabled:bg-surface-hover/50 disabled:cursor-not-allowed'
const labelCls = 'block text-sm text-content-secondary mb-1'
const ghostBtnCls =
  'shrink-0 inline-flex items-center gap-1.5 border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-3 py-2 text-xs whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed'

const FREQUENCY_OPTIONS: Array<{ value: AnnouncementFrequency; label: string; hint: string }> = [
  { value: 'once', label: '只弹一次', hint: '内容不改就不再弹；改了标题/正文/图片等会再弹一次' },
  { value: 'daily', label: '每天一次', hint: '每天首次进入弹一次' },
  { value: 'always', label: '每次打开', hint: '每个浏览器会话（关掉标签页再开）弹一次' },
]

/** 表单态：时间用 datetime-local 的本地字符串承接，保存时转 ISO（UTC） */
interface FormState {
  enabled: boolean
  badge: string
  title: string
  content: string
  image_url: string
  button_text: string
  link_text: string
  link_url: string
  frequency: AnnouncementFrequency
  start_at: string
  end_at: string
}

/** ISO（UTC）→ datetime-local 需要的 "YYYY-MM-DDTHH:mm"（本地时区） */
function isoToLocalInput(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** datetime-local 字符串（本地时区）→ ISO（UTC）；空 = 清空 */
function localInputToIso(value: string): string {
  return value ? new Date(value).toISOString() : ''
}

function toForm(view: AnnouncementSettingsView): FormState {
  return {
    enabled: view.enabled,
    badge: view.badge,
    title: view.title,
    content: view.content,
    image_url: view.image_url,
    button_text: view.button_text,
    link_text: view.link_text,
    link_url: view.link_url,
    frequency: view.frequency,
    start_at: isoToLocalInput(view.start_at),
    end_at: isoToLocalInput(view.end_at),
  }
}

function toUpdate(form: FormState): AnnouncementUpdate | null {
  if (form.start_at && form.end_at && new Date(form.start_at) > new Date(form.end_at)) {
    toast.error('开始时间不能晚于结束时间')
    return null
  }
  if (form.link_url.trim() && !/^(https?:\/\/|\/)/.test(form.link_url.trim())) {
    toast.error('链接地址需以 http:// 、https:// 或 / 开头')
    return null
  }
  return {
    enabled: form.enabled,
    badge: form.badge.trim(),
    title: form.title.trim(),
    content: form.content.trim(),
    image_url: form.image_url.trim(),
    button_text: form.button_text.trim(),
    link_text: form.link_text.trim(),
    link_url: form.link_url.trim(),
    frequency: form.frequency,
    start_at: localInputToIso(form.start_at),
    end_at: localInputToIso(form.end_at),
  }
}

function statusText(view: AnnouncementSettingsView): string {
  if (!view.enabled) return '已关闭'
  const now = Date.now()
  if (view.start_at && new Date(view.start_at).getTime() > now) return `未到开始时间（${new Date(view.start_at).toLocaleString()} 起）`
  if (view.end_at && new Date(view.end_at).getTime() < now) return `已过期（${new Date(view.end_at).toLocaleString()} 止）`
  return '生效中'
}

export function AnnouncementSettingsCard() {
  const [view, setView] = useState<AnnouncementSettingsView | null>(null)
  const [form, setForm] = useState<FormState | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    adminApi
      .getAnnouncement()
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
      const v = await adminApi.updateAnnouncement(update)
      setView(v)
      setForm(toForm(v))
      toast.success('公告弹窗设置已保存')
    } catch { /* api 层已 toast */ } finally { setSaving(false) }
  }

  const handleUpload = async (file: File | undefined) => {
    if (!file) return
    if (file.size > 2 * 1024 * 1024) { toast.error('图片不能超过 2MB'); return }
    setUploading(true)
    try {
      // 上传即写入配置（后端顺手清理被替换的旧图），这里同步表单里的图片地址
      const res = await adminApi.uploadAnnouncementImage(file)
      patch({ image_url: res.image_url })
      setView((v) => (v ? { ...v, image_url: res.image_url } : v))
      toast.success('图片已上传')
    } catch { /* api 层已 toast */ } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  if (!view || !form) {
    return (
      <div className="bg-white border border-surface-border rounded-card px-5 py-4 flex items-center gap-2 text-sm text-content-secondary">
        <Loader2 className="w-4 h-4 animate-spin" />
        正在加载公告弹窗设置…
      </div>
    )
  }

  const frequencyLabel = FREQUENCY_OPTIONS.find((o) => o.value === view.frequency)?.label ?? view.frequency
  const dirty = JSON.stringify(form) !== JSON.stringify(toForm(view))

  return (
    <div className="bg-white border border-surface-border rounded-card">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left hover:bg-surface-hover/40 transition-colors"
      >
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-content">公告弹窗</h2>
          <p className="mt-1 text-xs text-content-secondary truncate">
            {statusText(view)} · {frequencyLabel} · 「{view.title || '（无标题）'}」— 用户登录后弹出
          </p>
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 shrink-0 text-content-secondary" /> : <ChevronDown className="w-4 h-4 shrink-0 text-content-secondary" />}
      </button>

      {expanded && (
        <div className="border-t border-surface-border px-5 py-5 space-y-5">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <label className="flex items-center gap-2 text-sm text-content cursor-pointer">
              <input type="checkbox" checked={form.enabled} onChange={(e) => patch({ enabled: e.target.checked })} className="rounded" />
              启用公告弹窗
            </label>
            <span className="text-xs text-content-tertiary">当前状态：{statusText(view)}</span>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            {/* 内容 */}
            <section className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-content">
                <Megaphone className="w-4 h-4 text-brand" />
                内容
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className={labelCls}>小标签</label>
                  <input value={form.badge} onChange={(e) => patch({ badge: e.target.value })} maxLength={30} placeholder="留空不显示" className={inputCls} />
                </div>
                <div className="col-span-2">
                  <label className={labelCls}>标题</label>
                  <input value={form.title} onChange={(e) => patch({ title: e.target.value })} maxLength={60} className={inputCls} />
                </div>
              </div>
              <div>
                <label className={labelCls}>正文（支持换行）</label>
                <textarea value={form.content} onChange={(e) => patch({ content: e.target.value })} maxLength={2000} rows={5} className={`${inputCls} resize-y`} />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className={labelCls}>按钮文字</label>
                  <input value={form.button_text} onChange={(e) => patch({ button_text: e.target.value })} maxLength={20} placeholder="我知道了" className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>链接文字（可选）</label>
                  <input value={form.link_text} onChange={(e) => patch({ link_text: e.target.value })} maxLength={40} placeholder="了解更多" className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>链接地址（可选）</label>
                  <input value={form.link_url} onChange={(e) => patch({ link_url: e.target.value })} maxLength={500} placeholder="https://…" className={inputCls} />
                </div>
              </div>
            </section>

            {/* 图片 + 时间 + 频率 */}
            <section className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-content">
                <ImagePlus className="w-4 h-4 text-brand" />
                图片与展示规则
              </div>
              <div>
                <label className={labelCls}>图片（上传 ≤2MB 的 jpg/png/gif/webp，或直接填图片地址；留空不显示）</label>
                <div className="flex gap-2">
                  <input value={form.image_url} onChange={(e) => patch({ image_url: e.target.value })} maxLength={500} placeholder="/dev-group-qr.jpg" className={inputCls} />
                  <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/gif,image/webp" className="hidden" onChange={(e) => handleUpload(e.target.files?.[0])} />
                  <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading} className={ghostBtnCls}>
                    {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ImagePlus className="w-3.5 h-3.5" />}
                    上传
                  </button>
                  {form.image_url && (
                    <button type="button" onClick={() => patch({ image_url: '' })} title="不显示图片" className={ghostBtnCls}>
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
                {form.image_url && (
                  <div className="mt-2 inline-block border border-surface-border bg-white p-2">
                    <img src={form.image_url} alt="公告图片预览" className="max-h-28 max-w-[200px] object-contain" />
                  </div>
                )}
              </div>
              <div>
                <label className={labelCls}>显示频率</label>
                <select value={form.frequency} onChange={(e) => patch({ frequency: e.target.value as AnnouncementFrequency })} className={inputCls}>
                  {FREQUENCY_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-content-tertiary">{FREQUENCY_OPTIONS.find((o) => o.value === form.frequency)?.hint}</p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className={labelCls}>开始时间（可选）</label>
                  <input type="datetime-local" value={form.start_at} onChange={(e) => patch({ start_at: e.target.value })} className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>结束时间（可选）</label>
                  <input type="datetime-local" value={form.end_at} onChange={(e) => patch({ end_at: e.target.value })} className={inputCls} />
                </div>
              </div>
              <p className="text-xs text-content-tertiary">不填开始/结束时间则一直显示；按你本机时区填写，服务器按绝对时间判定。</p>
            </section>
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-surface-border pt-4">
            <button type="button" onClick={() => setPreviewing(true)} className={ghostBtnCls}>
              <Eye className="w-3.5 h-3.5" />
              预览当前填写效果
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !dirty}
              className="inline-flex items-center gap-1.5 bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              保存
            </button>
          </div>
        </div>
      )}

      {previewing && <AnnouncementModal announcement={form} onClose={() => setPreviewing(false)} preview />}
    </div>
  )
}
