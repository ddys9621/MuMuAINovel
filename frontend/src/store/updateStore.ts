import { create } from 'zustand'
import api, { systemUpdateApi } from '@/services/api'
import type { RunMode, UpdateCheckResult } from '@/types/system_update'

/** 偏好与去重信息存 localStorage（按浏览器），不进数据库 */
export const UPDATE_STORAGE_KEYS = {
  autoCheck: 'mumu.update.autoCheck',
  lastCheckAt: 'mumu.update.lastCheckAt',
  notifiedKey: 'mumu.update.notifiedKey',
  lastResult: 'mumu.update.lastResult',
} as const

export const AUTO_CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000

interface UpdateInfo {
  current_version: string
  run_mode: RunMode
}

function readAutoCheck(): boolean {
  try {
    return localStorage.getItem(UPDATE_STORAGE_KEYS.autoCheck) !== 'false'
  } catch {
    return true
  }
}

/** 上次检查结果落盘：刷新页面后侧栏仍能显示"有新版本"，不必每次都联网 */
function readPersistedResult(): UpdateCheckResult | null {
  try {
    const raw = localStorage.getItem(UPDATE_STORAGE_KEYS.lastResult)
    if (!raw) return null
    const parsed = JSON.parse(raw) as UpdateCheckResult
    return parsed && typeof parsed === 'object' && 'has_update' in parsed ? parsed : null
  } catch {
    return null
  }
}

function persistResult(result: UpdateCheckResult | null) {
  try {
    if (result) localStorage.setItem(UPDATE_STORAGE_KEYS.lastResult, JSON.stringify(result))
    else localStorage.removeItem(UPDATE_STORAGE_KEYS.lastResult)
  } catch {
    /* ignore */
  }
}

interface UpdateState {
  /** 当前版本 / 运行形态（不联网，进入应用即加载） */
  info: UpdateInfo | null
  result: UpdateCheckResult | null
  checking: boolean
  hasUpdate: boolean
  autoCheck: boolean
  setAutoCheck: (enabled: boolean) => void
  /** 拉当前版本；若本地缓存的检查结果来自另一个版本（已升级过），作废该结果 */
  loadInfo: () => Promise<UpdateInfo | null>
  /** 调后端检查；失败（网络/未登录）时静默返回 null，由调用方决定是否提示 */
  runCheck: (force?: boolean) => Promise<UpdateCheckResult | null>
}

const persisted = readPersistedResult()

export const useUpdateStore = create<UpdateState>((set, get) => ({
  info: null,
  result: persisted,
  checking: false,
  hasUpdate: !!persisted?.has_update,
  autoCheck: readAutoCheck(),

  setAutoCheck: (enabled) => {
    try {
      localStorage.setItem(UPDATE_STORAGE_KEYS.autoCheck, String(enabled))
    } catch {
      /* 隐私模式等写不进 localStorage：仅本次会话生效 */
    }
    set({ autoCheck: enabled })
  },

  loadInfo: async () => {
    try {
      const info = await api.get<unknown, UpdateInfo>('/system/update/info')
      const stale = get().result
      if (stale && stale.current_version !== info.current_version) {
        persistResult(null)
        set({ info, result: null, hasUpdate: false })
      } else {
        set({ info })
      }
      return info
    } catch {
      return null
    }
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
      persistResult(result)
      set({ result, hasUpdate: !!result.has_update, checking: false })
      return result
    } catch {
      set({ checking: false })
      return null
    }
  },
}))
