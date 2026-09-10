/** 系统更新（GET/POST /api/system/update/*），与后端 app/services/update_service.py 的数据类一一对应 */

export type RunMode = 'exe' | 'docker' | 'source'

export const RUN_MODE_LABEL: Record<RunMode, string> = {
  exe: 'Windows 安装版',
  docker: 'Docker 容器',
  source: '源码运行',
}

export interface ReleaseInfo {
  version: string
  tag: string
  name: string
  notes: string
  published_at: string | null
  html_url: string
  installer_url: string | null
  installer_name: string | null
  installer_size: number | null
}

export interface GitInfo {
  available: boolean
  branch: string | null
  commit: string | null
  remote_commit: string | null
  ahead: number
  behind: number
  commits: Array<{ sha: string; message: string }>
  changed_files: number
  backend_deps_changed: boolean
  frontend_changed: boolean
  dirty: boolean
  error: string | null
}

export interface UpdateCheckResult {
  enabled: boolean
  run_mode: RunMode
  current_version: string
  latest: ReleaseInfo | null
  has_update: boolean
  git: GitInfo | null
  can_apply: boolean
  apply_hint: string
  checked_at: string | null
  cached: boolean
  error: string | null
}

export type UpdateStepState = 'pending' | 'running' | 'success' | 'failed' | 'skipped'

export interface UpdateStep {
  key: string
  label: string
  state: UpdateStepState
  output: string
}

export type UpdateJobState = 'idle' | 'running' | 'success' | 'failed' | 'exiting'

export interface UpdateJobStatus {
  mode: RunMode | null
  status: UpdateJobState
  steps: UpdateStep[]
  progress: { downloaded: number; total: number | null } | null
  message: string | null
  error: string | null
  restart_required: boolean
  started_at?: string | null
  finished_at?: string | null
}

/** 用于"同一版本只提醒一次"的去重键：源码模式看远端提交，其余看 Release 版本 */
export function updateKeyOf(result: UpdateCheckResult | null): string | null {
  if (!result || !result.has_update) return null
  if (result.run_mode === 'source' && result.git?.remote_commit) return `commit:${result.git.remote_commit}`
  return result.latest ? `release:${result.latest.version}` : null
}
