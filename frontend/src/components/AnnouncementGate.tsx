import { useEffect, useState } from 'react'
import { announcementApi } from '@/services/api'
import type { AnnouncementFrequency, AnnouncementView } from '@/types'
import { AnnouncementModal } from './AnnouncementModal'

const DISMISSED_KEY = 'announcement-dismissed'      // localStorage：{ revision, at }
const SESSION_KEY = 'announcement-dismissed-session' // sessionStorage：本次浏览器会话已关闭的 revision
const LEGACY_KEY = 'community-announcement-v1-dismissed' // 1.2.0 之前写死弹窗的关闭标记，读一次后清掉

interface Dismissed {
  revision: string
  at: number
}

function readDismissed(): Dismissed | null {
  try {
    const raw = window.localStorage.getItem(DISMISSED_KEY)
    return raw ? (JSON.parse(raw) as Dismissed) : null
  } catch {
    return null
  }
}

function sameLocalDay(a: number, b: number): boolean {
  const da = new Date(a)
  const db = new Date(b)
  return da.getFullYear() === db.getFullYear() && da.getMonth() === db.getMonth() && da.getDate() === db.getDate()
}

/** 按频率规则判断这次要不要弹：同一浏览器会话里关过就不再弹，避免在布局间切换时反复弹 */
function shouldShow(revision: string, frequency: AnnouncementFrequency, now = Date.now()): boolean {
  try {
    if (window.sessionStorage.getItem(SESSION_KEY) === revision) return false
  } catch { /* 无 storage 时按未关闭处理 */ }

  const dismissed = readDismissed()
  if (!dismissed || dismissed.revision !== revision) return true
  if (frequency === 'once') return false
  if (frequency === 'daily') return !sameLocalDay(dismissed.at, now)
  return true // always：每个会话一次，由 sessionStorage 兜底
}

function markDismissed(revision: string) {
  try {
    window.localStorage.setItem(DISMISSED_KEY, JSON.stringify({ revision, at: Date.now() } satisfies Dismissed))
    window.sessionStorage.setItem(SESSION_KEY, revision)
  } catch {
    // 存不了就只关本次
  }
}

/** 登录后挂在受保护区域里：拉当前生效公告，按频率决定弹不弹 */
export function AnnouncementGate() {
  const [current, setCurrent] = useState<Extract<AnnouncementView, { active: true }> | null>(null)

  useEffect(() => {
    let cancelled = false
    try { window.localStorage.removeItem(LEGACY_KEY) } catch { /* ignore */ }

    announcementApi
      .get()
      .then((view) => {
        if (cancelled || !view.active) return
        if (shouldShow(view.revision, view.frequency)) setCurrent(view)
      })
      .catch(() => { /* 公告拉不到不影响使用 */ })

    return () => { cancelled = true }
  }, [])

  if (!current) return null

  const close = () => {
    markDismissed(current.revision)
    setCurrent(null)
  }

  return <AnnouncementModal announcement={current} onClose={close} />
}
