import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { AUTO_CHECK_INTERVAL_MS, UPDATE_STORAGE_KEYS, useUpdateStore } from '@/store/updateStore'
import { updateKeyOf } from '@/types/system_update'

/**
 * 进入应用先拉当前版本（侧栏常驻显示）；启动时自动检查更新：每 24 小时最多一次（后端另有 10 分钟缓存），
 * 发现新版本弹一次提示并点亮侧栏红点。同一个新版本只提醒一次（localStorage 记录 notifiedKey）；
 * 用户在设置页关闭自动检查后只显示版本号、不再联网。
 */
export function useUpdateAutoCheck() {
  const navigate = useNavigate()
  const autoCheck = useUpdateStore((s) => s.autoCheck)
  const runCheck = useUpdateStore((s) => s.runCheck)
  const loadInfo = useUpdateStore((s) => s.loadInfo)
  const ran = useRef(false)

  useEffect(() => {
    if (ran.current) return
    ran.current = true
    void loadInfo()
  }, [loadInfo])

  const checked = useRef(false)
  useEffect(() => {
    if (!autoCheck || checked.current) return
    checked.current = true

    let last = 0
    try {
      last = Number(localStorage.getItem(UPDATE_STORAGE_KEYS.lastCheckAt) || 0)
    } catch {
      /* ignore */
    }
    if (Date.now() - last < AUTO_CHECK_INTERVAL_MS) return

    runCheck(false).then((result) => {
      const key = updateKeyOf(result)
      if (!result || !key || !result.enabled) return
      let notified: string | null = null
      try {
        notified = localStorage.getItem(UPDATE_STORAGE_KEYS.notifiedKey)
      } catch {
        /* ignore */
      }
      if (notified === key) return
      try {
        localStorage.setItem(UPDATE_STORAGE_KEYS.notifiedKey, key)
      } catch {
        /* ignore */
      }
      const label = result.run_mode === 'source'
        ? `源码落后远端 ${result.git?.behind ?? 0} 个提交`
        : `发现新版本 v${result.latest?.version ?? ''}`
      toast.info(label, {
        description: '前往「设置 → 关于与更新」查看详情',
        action: { label: '查看', onClick: () => navigate('/settings') },
        duration: 8000,
      })
    })
  }, [autoCheck, runCheck, navigate])
}
