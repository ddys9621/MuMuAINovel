import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { AUTO_CHECK_INTERVAL_MS, UPDATE_STORAGE_KEYS, useUpdateStore } from '@/store/updateStore'
import { updateKeyOf } from '@/types/system_update'

/**
 * 进入应用先拉当前版本（侧栏常驻显示）；管理员且开着自动检查时，启动时自动检查更新：
 * 每 24 小时最多一次（后端另有 10 分钟缓存），发现新版本弹一次提示并点亮侧栏红点。
 * 同一个新版本只提醒一次（localStorage 记录 notifiedKey）。非管理员只加载版本号、不联网检查。
 */
export function useUpdateAutoCheck() {
  const navigate = useNavigate()
  const loadInfo = useUpdateStore((s) => s.loadInfo)
  const runCheck = useUpdateStore((s) => s.runCheck)
  const ran = useRef(false)

  useEffect(() => {
    if (ran.current) return
    ran.current = true

    loadInfo().then((info) => {
      if (!info?.can_manage || !useUpdateStore.getState().autoCheck) return

      let last = 0
      try {
        last = Number(localStorage.getItem(UPDATE_STORAGE_KEYS.lastCheckAt) || 0)
      } catch {
        /* ignore */
      }
      if (Date.now() - last < AUTO_CHECK_INTERVAL_MS) return

      return runCheck(false).then((result) => {
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
    })
  }, [loadInfo, runCheck, navigate])
}
