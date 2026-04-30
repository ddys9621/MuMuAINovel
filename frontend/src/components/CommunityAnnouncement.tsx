import { useState } from 'react'
import { MessageCircle, X } from 'lucide-react'

const ANNOUNCEMENT_KEY = 'community-announcement-v1-dismissed'

function wasDismissed() {
  if (typeof window === 'undefined') return true

  try {
    return window.localStorage.getItem(ANNOUNCEMENT_KEY) === 'true'
  } catch {
    return false
  }
}

export function CommunityAnnouncement() {
  const [open, setOpen] = useState(() => !wasDismissed())

  const close = () => {
    try {
      window.localStorage.setItem(ANNOUNCEMENT_KEY, 'true')
    } catch {
      // Ignore storage failures; closing the current modal is still enough.
    }

    setOpen(false)
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-[#2d130d]/55 px-4 py-6 backdrop-blur-sm" onClick={close}>
      <div
        className="relative w-full max-w-[420px] overflow-hidden border border-white/75 bg-[linear-gradient(180deg,rgba(255,255,255,0.98)_0%,rgba(255,247,240,0.99)_100%)] shadow-xl animate-scale-in"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-brand via-gold to-brand" />
        <button
          type="button"
          onClick={close}
          className="absolute right-4 top-4 z-10 p-2 text-content-tertiary hover:bg-surface-hover hover:text-content"
          aria-label="关闭公告"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="px-6 pb-6 pt-7">
          <div className="mb-4 inline-flex items-center gap-2 bg-brand/10 px-3 py-1.5 text-xs font-medium text-brand">
            <MessageCircle className="h-3.5 w-3.5" />
            官方交流群
          </div>
          <h2 className="text-xl font-bold text-content">加入交流群</h2>
          <p className="mt-2 text-sm leading-6 text-content-secondary">
            扫码加入开发交流群，获取更新通知、使用答疑和创作交流。
          </p>

          <div className="mt-5 border border-surface-border bg-white p-3 shadow-card">
            <img
              src="/dev-group-qr.jpg"
              alt="官方交流群二维码"
              className="mx-auto aspect-square w-full max-w-[260px] object-contain"
            />
          </div>

          <button type="button" onClick={close} className="fanqie-primary-btn mt-5 w-full">
            我知道了
          </button>
        </div>
      </div>
    </div>
  )
}
