/**
 * 设置页「关于与更新」面板：当前版本 / 运行方式 / 检查更新 / 一键更新（按运行形态分支）。
 *
 * - exe：下载安装包 → 启动安装向导 → 应用自退出（进度条 + 退出提示）
 * - source：展示落后提交，一键 git pull（+ pip / npm）→ 分步进度 → 提示重启
 * - docker：容器内不能自更新，给出宿主机命令 + 一键复制
 * 检查更新 / 一键更新仅管理员可用（后端同样限制）；非管理员只看到当前版本与运行方式。
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleDashed,
  Copy,
  Download,
  ExternalLink,
  GitBranch,
  Loader2,
  RefreshCw,
  Rocket,
  SkipForward,
  XCircle,
} from 'lucide-react'
import { toast } from 'sonner'

import { systemUpdateApi } from '@/services/api'
import { useUpdateStore } from '@/store/updateStore'
import { RUN_MODE_LABEL, type UpdateJobStatus, type UpdateStep } from '@/types/system_update'
import { cn } from '@/lib/utils'

const POLL_MS = 1500

function formatBytes(n: number | null | undefined): string {
  if (!n || n <= 0) return '—'
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}

function StepIcon({ state }: { state: UpdateStep['state'] }) {
  switch (state) {
    case 'running':
      return <Loader2 className="h-4 w-4 animate-spin text-brand" />
    case 'success':
      return <CheckCircle2 className="h-4 w-4 text-green-600" />
    case 'failed':
      return <XCircle className="h-4 w-4 text-red-500" />
    case 'skipped':
      return <SkipForward className="h-4 w-4 text-amber-500" />
    default:
      return <CircleDashed className="h-4 w-4 text-content-tertiary" />
  }
}

function StepList({ steps }: { steps: UpdateStep[] }) {
  const [open, setOpen] = useState<Record<string, boolean>>({})
  if (!steps.length) return null
  return (
    <ul className="divide-y divide-surface-border/80 border border-surface-border text-sm">
      {steps.map((s) => {
        const expanded = open[s.key] ?? (s.state === 'running' || s.state === 'failed')
        return (
          <li key={s.key} className="px-3 py-2">
            <button
              type="button"
              className="flex w-full items-center gap-2 text-left"
              onClick={() => setOpen((prev) => ({ ...prev, [s.key]: !expanded }))}
            >
              <StepIcon state={s.state} />
              <span className="flex-1 text-content">{s.label}</span>
              {s.output && (expanded ? <ChevronUp className="h-4 w-4 text-content-tertiary" /> : <ChevronDown className="h-4 w-4 text-content-tertiary" />)}
            </button>
            {expanded && s.output && (
              <pre className="mt-2 max-h-48 overflow-auto bg-surface px-3 py-2 font-mono text-[11px] leading-5 text-content-secondary whitespace-pre-wrap">
                {s.output}
              </pre>
            )}
          </li>
        )
      })}
    </ul>
  )
}

export function UpdatePanel() {
  const info = useUpdateStore((s) => s.info)
  const result = useUpdateStore((s) => s.result)
  const checking = useUpdateStore((s) => s.checking)
  const autoCheck = useUpdateStore((s) => s.autoCheck)
  const setAutoCheck = useUpdateStore((s) => s.setAutoCheck)
  const loadInfo = useUpdateStore((s) => s.loadInfo)
  const runCheck = useUpdateStore((s) => s.runCheck)
  const canManage = !!info?.can_manage

  const [job, setJob] = useState<UpdateJobStatus | null>(null)
  const [applying, setApplying] = useState(false)
  const [notesOpen, setNotesOpen] = useState(false)
  const pollRef = useRef<number | null>(null)

  useEffect(() => {
    if (!info) void loadInfo()
  }, [info, loadInfo])

  // 只有管理员才拉检查结果与更新任务状态（后端对非管理员返回 403）
  useEffect(() => {
    if (!canManage) return
    if (!useUpdateStore.getState().result) void runCheck(false)
    systemUpdateApi.status().then(setJob).catch(() => { /* 服务重启中等：不展示任务 */ })
  }, [canManage, runCheck])

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      window.clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  useEffect(() => {
    if (job?.status !== 'running') {
      stopPolling()
      return
    }
    if (pollRef.current) return
    pollRef.current = window.setInterval(async () => {
      try {
        const next = await systemUpdateApi.status()
        setJob(next)
        if (next.status === 'success') {
          toast.success(next.message || '更新完成')
          void runCheck(true)
        } else if (next.status === 'failed') {
          toast.error(next.error || '更新失败')
        }
      } catch {
        /* 服务重启中（源码模式 uvicorn --reload）：下一轮再试 */
      }
    }, POLL_MS)
    return stopPolling
  }, [job?.status, runCheck, stopPolling])

  const handleCheck = useCallback(async () => {
    const r = await runCheck(true)
    if (!r) return
    if (r.error) toast.warning(r.error)
    else if (!r.has_update) toast.success('已是最新版本')
  }, [runCheck])

  const handleApply = useCallback(async () => {
    setApplying(true)
    try {
      const status = await systemUpdateApi.apply()
      setJob(status)
      if (status.status === 'exiting') {
        toast.info(status.message || '安装程序已启动，应用即将退出')
      }
    } catch {
      /* 拦截器已 toast */
    } finally {
      setApplying(false)
    }
  }, [])

  const copyHint = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.success('命令已复制')
    } catch {
      toast.error('复制失败，请手动选择文本')
    }
  }, [])

  const mode = result?.run_mode
  const git = result?.git ?? null
  const latest = result?.latest ?? null
  const jobBusy = job?.status === 'running' || job?.status === 'exiting'
  const progressPct =
    job?.progress && job.progress.total ? Math.min(100, Math.round((job.progress.downloaded / job.progress.total) * 100)) : null

  if (!canManage) {
    // 非管理员：只展示版本与运行方式，不联网、不显示检查/更新入口
    return (
      <section className="bg-white rounded-card shadow-card p-6">
        <h2 className="text-lg font-semibold text-content">关于</h2>
        <p className="mt-1 text-sm text-content-secondary">
          当前版本 <span className="font-medium text-content">v{info?.current_version ?? '…'}</span>
          {info?.run_mode && <> · {RUN_MODE_LABEL[info.run_mode]}</>}
        </p>
        <p className="mt-2 text-xs text-content-tertiary">检查更新与一键升级由管理员在此页面操作。</p>
      </section>
    )
  }

  return (
    <section className="bg-white rounded-card shadow-card p-6">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-content">关于与更新</h2>
          <p className="mt-1 text-sm text-content-secondary">
            当前版本 <span className="font-medium text-content">v{result?.current_version ?? info?.current_version ?? '…'}</span>
            {mode && <> · {RUN_MODE_LABEL[mode]}</>}
            {mode === 'source' && git?.branch && (
              <span className="ml-1 inline-flex items-center gap-1 text-content-tertiary">
                <GitBranch className="h-3.5 w-3.5" />
                {git.branch}
                {git.commit ? `@${git.commit}` : ''}
              </span>
            )}
          </p>
          {result?.checked_at && (
            <p className="mt-0.5 text-xs text-content-tertiary">
              上次检查：{formatTime(result.checked_at)}
              {result.cached ? '（缓存）' : ''}
            </p>
          )}
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-btn border border-surface-border hover:bg-surface-hover transition-colors disabled:opacity-50"
          onClick={handleCheck}
          disabled={checking || result?.enabled === false}
        >
          {checking ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          检查更新
        </button>
      </div>

      <label className="mb-4 flex cursor-pointer items-center gap-2 text-sm text-content-secondary">
        <input type="checkbox" className="accent-brand" checked={autoCheck} onChange={(e) => setAutoCheck(e.target.checked)} />
        启动时自动检查更新（每天最多一次，发现新版本时在侧栏「设置」处提示）
      </label>

      {result?.enabled === false && (
        <p className="text-sm text-content-tertiary">{result.apply_hint}</p>
      )}

      {result?.error && (
        <p className="mb-3 flex items-start gap-2 text-sm text-amber-600">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          {result.error}
        </p>
      )}

      {result && result.enabled && !result.has_update && !result.error && (
        <p className="flex items-center gap-2 text-sm text-green-600">
          <CheckCircle2 className="h-4 w-4" />
          {result.apply_hint || '已是最新版本'}
        </p>
      )}

      {result?.has_update && (
        <div className="space-y-4">
          {/* 新版本信息 */}
          {latest && mode !== 'source' && (
            <div className="border border-brand/30 bg-brand/5 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="flex items-center gap-2 text-sm font-medium text-content">
                  <Rocket className="h-4 w-4 text-brand" />
                  发现新版本 v{latest.version}
                  {latest.published_at && (
                    <span className="text-xs font-normal text-content-tertiary">发布于 {formatTime(latest.published_at)}</span>
                  )}
                </p>
                <a
                  href={latest.html_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-brand hover:underline"
                >
                  查看发布页 <ExternalLink className="h-3 w-3" />
                </a>
              </div>
              {latest.notes && (
                <div className="mt-2">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 text-xs text-content-secondary hover:text-content"
                    onClick={() => setNotesOpen((v) => !v)}
                  >
                    {notesOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                    更新说明
                  </button>
                  {notesOpen && (
                    <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap font-sans text-xs leading-5 text-content-secondary">
                      {latest.notes}
                    </pre>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 源码模式：落后提交 */}
          {mode === 'source' && git && (
            <div className="border border-brand/30 bg-brand/5 p-4">
              <p className="flex items-center gap-2 text-sm font-medium text-content">
                <GitBranch className="h-4 w-4 text-brand" />
                远端 origin/{git.branch} 领先 {git.behind} 个提交
                {git.ahead > 0 && <span className="text-xs font-normal text-content-tertiary">（本地另有 {git.ahead} 个未推送提交）</span>}
              </p>
              {git.commits.length > 0 && (
                <ul className="mt-2 max-h-48 space-y-1 overflow-auto font-mono text-xs text-content-secondary">
                  {git.commits.map((c) => (
                    <li key={c.sha} className="truncate">
                      <span className="text-content-tertiary">{c.sha}</span> {c.message}
                    </li>
                  ))}
                  {git.behind > git.commits.length && <li className="text-content-tertiary">…还有 {git.behind - git.commits.length} 个</li>}
                </ul>
              )}
              <p className="mt-2 text-xs text-content-tertiary">
                变更 {git.changed_files} 个文件
                {git.backend_deps_changed ? ' · 后端依赖有变' : ''}
                {git.frontend_changed ? ' · 前端有变' : ''}
              </p>
            </div>
          )}

          {/* 操作区 */}
          {mode === 'docker' && (
            <div>
              <p className="mb-2 text-sm text-content-secondary">{result.apply_hint.split('\n')[0]}</p>
              <div className="relative">
                <pre className="overflow-auto bg-surface px-3 py-2 pr-24 font-mono text-xs leading-6 text-content">
                  {result.apply_hint.split('\n').slice(1).filter((l) => !l.startsWith('（')).join('\n')}
                </pre>
                <button
                  type="button"
                  className="absolute right-2 top-2 inline-flex items-center gap-1 border border-surface-border bg-white px-2 py-1 text-xs hover:bg-surface-hover"
                  onClick={() => copyHint(result.apply_hint.split('\n').slice(1).filter((l) => !l.startsWith('（')).join('\n'))}
                >
                  <Copy className="h-3 w-3" /> 复制命令
                </button>
              </div>
              <p className="mt-1 text-xs text-content-tertiary">{result.apply_hint.split('\n').find((l) => l.startsWith('（'))}</p>
            </div>
          )}

          {mode !== 'docker' && (
            <div className="space-y-3">
              {!result.can_apply && (
                <p className="flex items-start gap-2 text-sm text-amber-600">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span className="whitespace-pre-wrap">{result.apply_hint}</span>
                </p>
              )}
              {result.can_apply && !jobBusy && job?.status !== 'success' && (
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    className="inline-flex items-center gap-1.5 px-5 py-2.5 text-sm font-medium rounded-btn bg-brand hover:bg-brand-600 text-white transition-colors disabled:opacity-50"
                    onClick={handleApply}
                    disabled={applying}
                  >
                    {applying ? <Loader2 className="h-4 w-4 animate-spin" /> : mode === 'exe' ? <Download className="h-4 w-4" /> : <Rocket className="h-4 w-4" />}
                    {mode === 'exe' ? `下载并安装 v${latest?.version ?? ''}` : '一键更新'}
                  </button>
                  <span className="text-xs text-content-tertiary">
                    {mode === 'exe' ? `安装包 ${formatBytes(latest?.installer_size)} · ${result.apply_hint}` : result.apply_hint}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 任务进度（exe 下载 / source 分步） */}
      {job && job.status !== 'idle' && (
        <div className="mt-4 space-y-3">
          {job.mode === 'exe' && job.progress && job.status === 'running' && (
            <div>
              <div className="mb-1 flex justify-between text-xs text-content-secondary">
                <span>{job.message || '正在下载…'}</span>
                <span className="tabular-nums">
                  {formatBytes(job.progress.downloaded)} / {formatBytes(job.progress.total)}
                  {progressPct != null ? ` (${progressPct}%)` : ''}
                </span>
              </div>
              <div className="h-2 w-full bg-surface">
                <div className="h-2 bg-brand transition-all" style={{ width: `${progressPct ?? 5}%` }} />
              </div>
            </div>
          )}
          {job.mode === 'source' && <StepList steps={job.steps} />}
          {job.status === 'exiting' && (
            <p className="flex items-start gap-2 border border-brand/30 bg-brand/5 p-3 text-sm text-content">
              <Rocket className="mt-0.5 h-4 w-4 shrink-0 text-brand" />
              {job.message || '安装程序已启动，应用即将退出'}
            </p>
          )}
          {job.status === 'success' && (
            <p className="flex items-start gap-2 border border-green-200 bg-green-50 p-3 text-sm text-green-700">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
              {job.message || '更新完成'}
            </p>
          )}
          {job.status === 'failed' && (
            <p className="flex items-start gap-2 border border-red-200 bg-red-50 p-3 text-sm text-red-600">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span className={cn('whitespace-pre-wrap')}>{job.error || '更新失败'}</span>
            </p>
          )}
        </div>
      )}
    </section>
  )
}
