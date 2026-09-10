import { create } from 'zustand'
import { systemUpdateApi } from '@/services/api'
import type { UpdateCheckResult } from '@/types/system_update'

/** 偏好与去重信息存 localStorage（按浏览器），不进数据库 */
export const UPDATE_STORAGE_KEYS = {
  autoCheck: 'mumu.update.autoCheck',
  lastCheckAt: 'mumu.update.lastCheckAt',
  notifiedKey: 'mumu.update.notifiedKey',
} as const

export const AUTO_CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000

function readAutoCheck(): boolean {
  try {
    return localStorage.getItem(UPDATE_STORAGE_KEYS.autoCheck) !== 'false'
  } catch {
    return true
  }
}

interface UpdateState {
  result: UpdateCheckResult | null
  checking: boolean
  hasUpdate: boolean
  autoCheck: boolean
  setAutoCheck: (enabled: boolean) => void
  /** 调后端检查；失败（网络/未登录）时静默返回 null，由调用方决定是否提示 */
  runCheck: (force?: boolean) => Promise<UpdateCheckResult | null>
}

export const useUpdateStore = create<UpdateState>((set) => ({
  result: null,
  checking: false,
  hasUpdate: false,
  autoCheck: readAutoCheck(),

  setAutoCheck: (enabled) => {
    try {
      localStorage.setItem(UPDATE_STORAGE_KEYS.autoCheck, String(enabled))
    } catch {
      /* 隐私模式等写不进 localStorage：仅本次会话生效 */
    }
    set({ autoCheck: enabled })
  },

  runCheck: async (force = false) => {
    set({ checking: true })
    try {
      const result = await systemUpdateApi.check(force)
      try {
        localStorage.setItem(UPDATE_STORAGE_KEYS.lastCheckAt, String(Date.now()))
      } catch {
        /* ignore */
      }
      set({ result, hasUpdate: !!result.has_update, checking: false })
      return result
    } catch {
      set({ checking: false })
      return null
    }
  },
}))
