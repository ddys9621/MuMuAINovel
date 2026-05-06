import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Plus,
  FolderOpen,
  Pen,
  FileText,
  CheckCircle,
  MoreHorizontal,
  Download,
  Upload,
  Settings,
  Trash2,
  Clock,
  BookOpen,
  Sparkles,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  X,
  Minimize2,
  Maximize2,
  StopCircle,
} from 'lucide-react'
import { toast } from 'sonner'
import { useStore } from '@/store/index'
import { useProjectSync } from '@/store/hooks'
import { projectApi, wizardStreamApi } from '@/services/api'
import InspirationDrawer from '@/components/inspiration/InspirationDrawer'
import { MCPSelector } from '@/components/MCPSelector'
import type { Project } from '@/types'

/* ─── 常量 ─── */

const STATUS_MAP: Record<Project['status'], { label: string; color: string; bar: string }> = {
  planning: { label: '规划中', color: 'bg-orange-100 text-orange-700', bar: 'bg-orange-400' },
  writing: { label: '创作中', color: 'bg-emerald-100 text-emerald-700', bar: 'bg-emerald-500' },
  revising: { label: '修改中', color: 'bg-amber-100 text-amber-700', bar: 'bg-amber-500' },
  completed: { label: '已完成', color: 'bg-violet-100 text-violet-700', bar: 'bg-violet-500' },
}

const COVER_STYLES = [
  {
    wrap: 'from-[#ff845c] via-[#ff6a45] to-[#ffb066]',
    glow: 'shadow-[0_22px_45px_-28px_rgba(255,106,69,0.75)]',
  },
  {
    wrap: 'from-[#ffb36a] via-[#ff9350] to-[#ffd98c]',
    glow: 'shadow-[0_22px_45px_-28px_rgba(255,147,80,0.65)]',
  },
  {
    wrap: 'from-[#f08a5d] via-[#f45d48] to-[#ffcf92]',
    glow: 'shadow-[0_22px_45px_-28px_rgba(240,93,72,0.7)]',
  },
  {
    wrap: 'from-[#ff8761] via-[#ff7250] to-[#ffd2a8]',
    glow: 'shadow-[0_22px_45px_-28px_rgba(255,114,80,0.72)]',
  },
] as const

/* ─── 工具函数 ─── */

function formatWords(n: number) {
  if (n >= 10000) return `${(n / 10000).toFixed(1)} 万`
  return `${n}`
}

function formatDate(iso: string) {
  const d = new Date(iso)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} 天前`
  return d.toLocaleDateString('zh-CN')
}

function getCoverStyle(seed: string) {
  const value = [...seed].reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return COVER_STYLES[value % COVER_STYLES.length]
}

const TITLE_WRAPPERS: Record<string, string> = {
  '《': '》',
  '「': '」',
  '『': '』',
  '【': '】',
  '（': '）',
  '(': ')',
  '[': ']',
  '{': '}',
  '“': '”',
  '‘': '’',
  '"': '"',
  "'": "'",
}

function getDisplayTitle(title: string) {
  let value = title.trim()

  while (value.length > 1) {
    const chars = Array.from(value)
    const first = chars[0]
    const last = chars[chars.length - 1]

    if (TITLE_WRAPPERS[first] !== last) break
    value = chars.slice(1, -1).join('').trim()
  }

  return value || title.trim() || '未命名项目'
}

function getCoverLetter(title: string) {
  const displayTitle = getDisplayTitle(title).replace(/^[《》「」『』【】〈〉（）()[\]{}“”‘’"'`\s]+/, '')
  const chars = Array.from(displayTitle)

  return (
    chars.find((char) => /[A-Za-z0-9\u4e00-\u9fa5]/.test(char)) ??
    chars.find((char) => !/[\s《》「」『』【】〈〉（）()[\]{}“”‘’"'`~!@#$%^&*+=|\\/:;,.!?，。！？；：、-]/.test(char)) ??
    '书'
  )
}

/* ─── 骨架屏 ─── */

function SkeletonCards() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="fanqie-soft-card overflow-hidden p-4">
          <div className="mb-4 h-32 rounded-[24px] bg-gradient-to-br from-brand/20 via-orange-100 to-gold/20 animate-pulse" />
          <div className="space-y-3">
            <div className="h-5 bg-orange-100 rounded animate-pulse w-3/4" />
            <div className="space-y-1.5">
              <div className="h-3.5 bg-orange-50 rounded animate-pulse" />
              <div className="h-3.5 bg-orange-50 rounded animate-pulse w-2/3" />
            </div>
            <div className="h-5 bg-orange-50 rounded-full animate-pulse w-16" />
            <div className="flex justify-between pt-2">
              <div className="h-3 bg-orange-50 rounded animate-pulse w-20" />
              <div className="h-3 bg-orange-50 rounded animate-pulse w-24" />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

/* ─── 空状态 ─── */

function EmptyState({ onCreate, onInspiration }: { onCreate: () => void; onInspiration: () => void }) {
  return (
    <div className="fanqie-soft-card flex flex-col items-center justify-center px-6 py-20 text-center">
      <div className="mb-6 flex h-24 w-24 items-center justify-center rounded-[30px] bg-gradient-to-br from-brand/15 via-orange-100 to-gold/20 text-brand shadow-card">
        <BookOpen className="h-11 w-11" />
      </div>
      <div className="fanqie-chip mb-4 border-brand/10 bg-brand/5 text-brand">你的书架还是空的</div>
      <h3 className="mb-2 text-[28px] font-semibold text-content">创建第一个小说项目</h3>
      <p className="mb-8 max-w-[480px] text-sm leading-7 text-content-secondary">从一个灵感或完整项目开始，逐步沉淀设定、角色与章节内容，建立属于你的创作宇宙。</p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <button
          onClick={onInspiration}
          className="fanqie-primary-btn px-5"
        >
          <Sparkles className="w-4 h-4" />
          灵感创作
        </button>
        <button
          onClick={onCreate}
          className="fanqie-secondary-btn px-5"
        >
          <Plus className="w-4 h-4" />
          快速新建
        </button>
      </div>
    </div>
  )
}

/* ─── 项目卡片 ─── */

function ProjectCard({
  project,
  onClick,
  onDelete,
}: {
  project: Project
  onClick: () => void
  onDelete: () => void
}) {
  const status = STATUS_MAP[project.status] ?? STATUS_MAP.planning
  const cover = getCoverStyle(project.title)
  const tags = project.genre?.split(/[,，、/]/).filter(Boolean).slice(0, 3) ?? []
  const displayTitle = getDisplayTitle(project.title)
  const coverLetter = getCoverLetter(project.title)

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
      className="fanqie-soft-card group cursor-pointer overflow-hidden transition-all hover:-translate-y-1 hover:shadow-md"
    >
      <div className={`relative overflow-hidden rounded-[26px] bg-gradient-to-br ${cover.wrap} ${cover.glow}`}>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.24),transparent_26%)]" />
        <div className="relative flex min-h-[152px] flex-col justify-between p-5 text-white">
          <div className="flex items-start justify-between gap-3">
            <span className="inline-flex items-center rounded-pill bg-white/15 px-3 py-1 text-xs font-medium backdrop-blur-sm">
              {status.label}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDelete()
              }}
              className="opacity-0 group-hover:opacity-100 flex h-9 w-9 items-center justify-center rounded-full bg-white/18 text-white backdrop-blur-sm transition-all hover:bg-white/28"
              title="删除项目"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
          <div>
            <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-[18px] bg-white/14 text-2xl font-semibold backdrop-blur-sm">
              {coverLetter}
            </div>
            <h3 className="line-clamp-2 text-lg font-semibold leading-snug text-white">{displayTitle}</h3>
            <p className="mt-1 text-xs text-white/80">最近更新 · {formatDate(project.updated_at)}</p>
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-3 p-4">
        <p className="line-clamp-2 min-h-[2.75rem] text-sm leading-6 text-content-secondary">
          {project.description || '还没有添加项目简介，点击进入后继续补充你的世界观、剧情和角色设定。'}
        </p>

        {tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {tags.map((g) => (
              <span
                key={g}
                className="rounded-pill bg-[#fff1e8] px-2.5 py-1 text-xs font-medium text-[#a9572f]"
              >
                {g.trim()}
              </span>
            ))}
          </div>
        )}

        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-[18px] bg-white/80 px-3 py-3">
            <p className="text-[11px] uppercase tracking-[0.16em] text-content-tertiary">累计字数</p>
            <p className="mt-1 flex items-center gap-1 text-sm font-semibold text-content">
              <FileText className="h-4 w-4 text-brand" />
              {formatWords(project.current_words)} 字
            </p>
          </div>
          <div className="rounded-[18px] bg-white/80 px-3 py-3">
            <p className="text-[11px] uppercase tracking-[0.16em] text-content-tertiary">项目状态</p>
            <p className={`mt-1 inline-flex rounded-pill px-2.5 py-1 text-xs font-medium ${status.color}`}>
              {status.label}
            </p>
          </div>
        </div>

        <div className="border-t border-surface-border-light pt-3 text-xs text-content-tertiary">
          <div className="mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" />
              {formatDate(project.updated_at)}
            </span>
            <span>点击进入项目</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-[#f9ebe2]">
            <div className={`h-full rounded-full ${status.bar}`} style={{ width: project.status === 'completed' ? '100%' : project.status === 'writing' ? '72%' : project.status === 'revising' ? '84%' : '38%' }} />
          </div>
        </div>
      </div>
    </div>
  )
}

/* ─── 下拉菜单 ─── */

function DropdownMenu({
  onImport,
  onExport,
  onExportTxt,
}: {
  onImport: () => void
  onExport: () => void
  onExportTxt: () => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="fanqie-secondary-btn px-3 py-2"
        title="更多操作"
      >
        <MoreHorizontal className="w-5 h-5" />
      </button>
      {open && (
        <div className="absolute right-0 mt-2 z-20 w-44 rounded-[22px] border border-white/80 bg-white/95 p-2 shadow-lg backdrop-blur-sm animate-scale-in">
          <button
            onClick={() => { onImport(); setOpen(false) }}
            className="flex w-full items-center gap-2 rounded-[16px] px-3 py-2.5 text-sm text-content hover:bg-surface-hover"
          >
            <Upload className="w-4 h-4" />
            导入项目
          </button>
          <button
            onClick={() => { onExport(); setOpen(false) }}
            className="flex w-full items-center gap-2 rounded-[16px] px-3 py-2.5 text-sm text-content hover:bg-surface-hover"
          >
            <Download className="w-4 h-4" />
            导出项目
          </button>
          <button
            onClick={() => { onExportTxt(); setOpen(false) }}
            className="flex w-full items-center gap-2 rounded-[16px] px-3 py-2.5 text-sm text-content hover:bg-surface-hover"
          >
            <Download className="w-4 h-4" />
            导出 TXT
          </button>
          <button
            onClick={() => { setOpen(false); window.location.href = '/settings' }}
            className="flex w-full items-center gap-2 rounded-[16px] px-3 py-2.5 text-sm text-content hover:bg-surface-hover"
          >
            <Settings className="w-4 h-4" />
            系统设置
          </button>
        </div>
      )}
    </div>
  )
}

/* ─── 删除确认弹窗 ─── */

function DeleteDialog({
  project,
  onConfirm,
  onCancel,
}: {
  project: Project
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onCancel}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-modal border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96)_0%,rgba(255,247,240,0.98)_100%)] p-6 shadow-xl animate-scale-in"
      >
        <div className="fanqie-chip mb-4 border-red-100 bg-red-50 text-red-500">危险操作</div>
        <h3 className="mb-2 text-xl font-semibold text-content">确认删除</h3>
        <p className="mb-6 text-sm leading-7 text-content-secondary">
          确定要删除项目「{project.title}」吗？此操作不可撤销，项目下的所有数据将被永久删除。
        </p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            className="fanqie-secondary-btn"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            className="inline-flex items-center justify-center rounded-btn bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-600"
          >
            删除
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─── 导入验证弹窗 ─── */

function ImportDialog({
  onClose,
  onSuccess,
}: {
  onClose: () => void
  onSuccess: (projectId?: string) => void
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [validating, setValidating] = useState(false)
  const [importing, setImporting] = useState(false)
  const [validation, setValidation] = useState<{
    valid: boolean
    version: string
    project_name?: string
    statistics: Record<string, number>
    errors: string[]
    warnings: string[]
  } | null>(null)

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0]
    if (!selected) return
    setFile(selected)
    setValidation(null)
    setValidating(true)
    try {
      const result = await projectApi.validateImportFile(selected)
      setValidation(result)
    } catch {
      setValidation({
        valid: false,
        version: '',
        statistics: {},
        errors: ['文件验证失败，请检查文件格式'],
        warnings: [],
      })
    } finally {
      setValidating(false)
    }
  }

  const handleImport = async () => {
    if (!file || !validation?.valid) return
    setImporting(true)
    try {
      const result = await projectApi.importProject(file)
      if (result.success) {
        toast.success(result.message || '导入成功')
        onSuccess(result.project_id)
      }
    } catch {
      // api 拦截器已 toast
    } finally {
      setImporting(false)
    }
  }

  const STAT_LABELS: Record<string, string> = {
    characters: '角色',
    chapters: '章节',
    outlines: '大纲',
    plot_cards: '剧情卡片',
    plot_lines: '剧情线',
    chapter_outlines: '章纲',
    writing_styles: '写作风格',
    world_rules: '世界规则',
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md rounded-modal border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.97)_0%,rgba(255,247,240,0.98)_100%)] p-6 shadow-xl animate-scale-in"
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="fanqie-chip mb-2 border-brand/10 bg-brand/5 text-brand">导入验证</div>
            <h3 className="text-lg font-semibold text-content">导入项目</h3>
          </div>
          <button onClick={onClose} className="flex h-9 w-9 items-center justify-center rounded-full hover:bg-surface-hover text-content-tertiary transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 文件选择 */}
        <div className="mb-4">
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            className="hidden"
            onChange={handleFileSelect}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="w-full rounded-[22px] border-2 border-dashed border-surface-border bg-white/75 p-6 text-center hover:border-brand hover:bg-brand-50/30 transition-colors"
          >
            <Upload className="w-8 h-8 mx-auto mb-2 text-content-tertiary" />
            <p className="text-sm text-content-secondary">
              {file ? file.name : '点击选择 JSON 文件'}
            </p>
            {file && (
              <p className="text-xs text-content-tertiary mt-1">
                {(file.size / 1024).toFixed(1)} KB
              </p>
            )}
          </button>
        </div>

        {/* 验证中 */}
        {validating && (
          <div className="flex items-center gap-2 text-sm text-content-secondary py-3">
            <Loader2 className="w-4 h-4 animate-spin" />
            正在验证文件...
          </div>
        )}

        {/* 验证结果 */}
        {validation && !validating && (
          <div className="mb-4 space-y-3">
            {/* 状态标识 */}
            <div className={`flex items-center gap-2 text-sm font-medium ${validation.valid ? 'text-green-600' : 'text-red-600'}`}>
              {validation.valid ? (
                <><CheckCircle2 className="w-4 h-4" />验证通过</>
              ) : (
                <><AlertTriangle className="w-4 h-4" />验证失败</>
              )}
            </div>

            {/* 项目信息 */}
            {validation.project_name && (
              <div className="rounded-[18px] bg-surface p-3">
                <p className="text-sm font-medium text-content">{validation.project_name}</p>
                {validation.version && (
                  <p className="text-xs text-content-tertiary mt-0.5">版本: {validation.version}</p>
                )}
              </div>
            )}

            {/* 数据统计 */}
            {Object.keys(validation.statistics).length > 0 && (
              <div className="rounded-[18px] bg-surface p-3">
                <p className="text-xs text-content-secondary mb-2">数据统计</p>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                  {Object.entries(validation.statistics).map(([key, value]) => (
                    <div key={key} className="flex justify-between text-xs">
                      <span className="text-content-secondary">{STAT_LABELS[key] || key}</span>
                      <span className="text-content font-medium">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 错误信息 */}
            {validation.errors.length > 0 && (
              <div className="rounded-[18px] bg-red-50 p-3 space-y-1">
                {validation.errors.map((err, i) => (
                  <p key={i} className="text-xs text-red-600">• {err}</p>
                ))}
              </div>
            )}

            {/* 警告信息 */}
            {validation.warnings.length > 0 && (
              <div className="rounded-[18px] bg-yellow-50 p-3 space-y-1">
                {validation.warnings.map((warn, i) => (
                  <p key={i} className="text-xs text-yellow-700">• {warn}</p>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            className="fanqie-secondary-btn"
          >
            取消
          </button>
          <button
            onClick={handleImport}
            disabled={!validation?.valid || importing}
            className="fanqie-primary-btn disabled:cursor-not-allowed disabled:opacity-50"
          >
            {importing && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            导入
          </button>
        </div>
      </div>
    </div>
  )
}

/* ─── 主页面 ─── */

export default function ProjectList() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { projects, loading, projectsInitialized } = useStore()
  const { refreshProjects, deleteProject } = useProjectSync()

  const [deletingProject, setDeletingProject] = useState<Project | null>(null)
  const [showImportDialog, setShowImportDialog] = useState(false)
  const [showWizard, setShowWizard] = useState(false)
  const inspirationOpen = searchParams.get('panel') === 'inspiration'

  const openInspirationDrawer = () => {
    const next = new URLSearchParams(searchParams)
    next.set('panel', 'inspiration')
    setSearchParams(next)
  }

  const closeInspirationDrawer = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('panel')
    setSearchParams(next, { replace: true })
  }

  // 初始化加载
  useEffect(() => {
    if (!projectsInitialized) {
      refreshProjects()
    }
  }, [projectsInitialized, refreshProjects])

  // 统计数据
  const stats = useMemo(() => {
    const total = projects.length
    const writing = projects.filter((p) => p.status === 'writing').length
    const totalWords = projects.reduce((sum, p) => sum + (p.current_words || 0), 0)
    const completed = projects.filter((p) => p.status === 'completed').length
    return { total, writing, totalWords, completed }
  }, [projects])

  // 新建项目 — 打开向导弹窗
  const handleCreate = () => {
    setShowWizard(true)
  }

  // 向导创建完成
  const handleWizardSuccess = async (projectId: string) => {
    setShowWizard(false)
    await refreshProjects()
    navigate(`/project/${projectId}`)
  }

  const handleInspirationProjectCreated = async () => {
    await refreshProjects()
  }

  const handleEnterInspiredProject = (projectId: string) => {
    closeInspirationDrawer()
    navigate(`/project/${projectId}`)
  }

  // 删除项目
  const handleDelete = async () => {
    if (!deletingProject) return
    try {
      await deleteProject(deletingProject.id)
      toast.success('项目已删除')
    } catch {
      // api 拦截器已 toast
    } finally {
      setDeletingProject(null)
    }
  }

  // 导入项目
  const handleImport = () => {
    setShowImportDialog(true)
  }

  const handleImportSuccess = async (projectId?: string) => {
    setShowImportDialog(false)
    await refreshProjects()
    if (projectId) {
      navigate(`/project/${projectId}`)
    }
  }

  // 导出 — 如果只有一个项目直接导出，否则提示
  const handleExport = () => {
    if (projects.length === 0) {
      toast.info('暂无可导出的项目')
      return
    }
    if (projects.length === 1) {
      projectApi.exportProjectData(projects[0].id, {})
      return
    }
    toast.info('请进入具体项目后导出')
  }

  // TXT 导出
  const handleExportTxt = () => {
    if (projects.length === 0) {
      toast.info('暂无可导出的项目')
      return
    }
    if (projects.length === 1) {
      projectApi.exportTxt(projects[0].id)
      return
    }
    toast.info('请进入具体项目后导出 TXT')
  }

  // 加载中
  const showSkeleton = loading && !projectsInitialized

  return (
    <div className="animate-fade-in space-y-5">
      <section className="mu-page-header">
        <div className="mu-page-header__row">
          <div className="min-w-0">
            <div className="mu-page-header__eyebrow">
              <Sparkles className="h-3 w-3" />
              作品中心
            </div>
            <h1 className="mu-page-header__title">让项目、灵感与进度井然有序</h1>
            <p className="mu-page-header__subtitle">在同一处查看作品状态与最近更新，快速回到正在推进的项目。</p>
          </div>

          <div className="mu-page-header__actions">
            <button onClick={openInspirationDrawer} className="mu-page-header__btn">
              <Sparkles className="h-4 w-4" />
              灵感创作
            </button>
            <button onClick={handleCreate} className="mu-page-header__btn-primary">
              <Plus className="h-4 w-4" />
              快速新建
            </button>
            <DropdownMenu onImport={handleImport} onExport={handleExport} onExportTxt={handleExportTxt} />
          </div>
        </div>

        <div className="mu-page-header__stats">
          <span className="mu-page-header__stat">
            <FolderOpen className="h-3.5 w-3.5 text-brand" />
            项目总数
            <span className="mu-page-header__stat-value">{stats.total}</span>
          </span>
          <span className="mu-page-header__stat-divider" />
          <span className="mu-page-header__stat">
            <Pen className="h-3.5 w-3.5 text-emerald-500" />
            创作中
            <span className="mu-page-header__stat-value">{stats.writing}</span>
          </span>
          <span className="mu-page-header__stat-divider" />
          <span className="mu-page-header__stat">
            <CheckCircle className="h-3.5 w-3.5 text-violet-500" />
            已完成
            <span className="mu-page-header__stat-value">{stats.completed}</span>
          </span>
          <span className="mu-page-header__stat-divider" />
          <span className="mu-page-header__stat">
            <FileText className="h-3.5 w-3.5 text-amber-500" />
            总字数
            <span className="mu-page-header__stat-value">{formatWords(stats.totalWords)}</span>
          </span>
        </div>
      </section>

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-content">项目书架</h2>
          <p className="mt-1 text-sm text-content-secondary">点击任意卡片即可继续创作，快速回到最近更新的作品。</p>
        </div>
      </div>

      {showSkeleton ? (
        <SkeletonCards />
      ) : projects.length === 0 ? (
        <EmptyState onCreate={handleCreate} onInspiration={openInspirationDrawer} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onClick={() => navigate(`/project/${project.id}`)}
              onDelete={() => setDeletingProject(project)}
            />
          ))}
        </div>
      )}

      <InspirationDrawer
        open={inspirationOpen}
        onClose={closeInspirationDrawer}
        onEnterProject={handleEnterInspiredProject}
        onProjectCreated={handleInspirationProjectCreated}
      />

      {/* 导入验证弹窗 */}
      {showImportDialog && (
        <ImportDialog
          onClose={() => setShowImportDialog(false)}
          onSuccess={handleImportSuccess}
        />
      )}

      {/* 删除确认弹窗 */}
      {deletingProject && (
        <DeleteDialog
          project={deletingProject}
          onConfirm={handleDelete}
          onCancel={() => setDeletingProject(null)}
        />
      )}

      {/* 向导创建弹窗 */}
      {showWizard && (
        <WizardModal
          onClose={() => setShowWizard(false)}
          onSuccess={handleWizardSuccess}
        />
      )}
    </div>
  )
}

/* ─── 向导创建弹窗 ─── */

type WizardPhase = 'form' | 'generating' | 'done'
type GenStep = 'pending' | 'processing' | 'completed' | 'error'

interface WizardForm {
  title: string
  description: string
  theme: string
  genre: string
  narrative_perspective: string
  target_words: number
  chapter_count: number
  character_count: number
  requirements: string
}

const DEFAULT_WIZARD_FORM: WizardForm = {
  title: '',
  description: '',
  theme: '',
  genre: '',
  narrative_perspective: '第三人称',
  target_words: 100000,
  chapter_count: 30,
  character_count: 5,
  requirements: '',
}

const GENRE_OPTIONS = ['玄幻', '奇幻', '武侠', '仙侠', '都市', '现实', '历史', '军事', '游戏', '体育', '科幻', '悬疑', '灵异', '二次元', '言情', '现言', '古言']
const PERSPECTIVE_OPTIONS = ['第一人称', '第三人称', '全知视角']

function WizardModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: (projectId: string) => void }) {
  const [form, setForm] = useState<WizardForm>(DEFAULT_WIZARD_FORM)
  const [phase, setPhase] = useState<WizardPhase>('form')
  const [progress, setProgress] = useState(0)
  const [progressMsg, setProgressMsg] = useState('')
  const [steps, setSteps] = useState<{ world: GenStep; chars: GenStep; outline: GenStep }>({ world: 'pending', chars: 'pending', outline: 'pending' })
  const [projectId, setProjectId] = useState('')
  const [error, setError] = useState('')
  const [minimized, setMinimized] = useState(false)
  const [selectedPlugins, setSelectedPlugins] = useState<string[]>([])
  const [enableMcp, setEnableMcp] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const updateField = <K extends keyof WizardForm>(key: K, value: WizardForm[K]) => {
    setForm(prev => ({ ...prev, [key]: value }))
  }

  const canSubmit = form.title.trim() && form.description.trim()

  const handleStart = async () => {
    if (!canSubmit) return
    setPhase('generating')
    setError('')

    try {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      // Step 1: 世界观
      setSteps(s => ({ ...s, world: 'processing' }))
      setProgressMsg('正在生成世界观...')
      setProgress(5)

      const worldResult = await wizardStreamApi.generateWorldBuildingStream(
        {
          title: form.title.trim(),
          description: form.description.trim(),
          theme: form.theme.trim() || form.title.trim(),
          genre: form.genre || '玄幻',
          narrative_perspective: form.narrative_perspective,
          target_words: form.target_words,
          chapter_count: form.chapter_count,
          character_count: form.character_count,
          enable_mcp: enableMcp,
          selected_plugins: selectedPlugins,
        },
        {
          signal: controller.signal,
          onProgress: (msg, prog) => {
            setProgressMsg(msg)
            setProgress(Math.floor(prog / 3))
          },
          onResult: (result) => {
            setProjectId(result.project_id)
            setSteps(s => ({ ...s, world: 'completed' }))
          },
          onError: (err) => {
            setSteps(s => ({ ...s, world: 'error' }))
            throw new Error(err)
          },
        }
      )

      if (controller.signal.aborted) return
      if (!worldResult?.project_id) throw new Error('项目创建失败')
      const pid = worldResult.project_id

      // Step 2: 角色
      setSteps(s => ({ ...s, chars: 'processing' }))
      setProgressMsg('正在生成角色...')
      setProgress(33)

      await wizardStreamApi.generateCharactersStream(
        {
          project_id: pid,
          count: form.character_count,
          theme: form.theme.trim() || undefined,
          genre: form.genre || undefined,
          requirements: form.requirements.trim() || undefined,
          enable_mcp: enableMcp,
          selected_plugins: selectedPlugins,
        },
        {
          signal: controller.signal,
          onProgress: (msg, prog) => {
            setProgressMsg(msg)
            setProgress(33 + Math.floor(prog / 3))
          },
          onResult: () => setSteps(s => ({ ...s, chars: 'completed' })),
          onError: (err) => {
            setSteps(s => ({ ...s, chars: 'error' }))
            throw new Error(err)
          },
        }
      )

      if (controller.signal.aborted) return

      // Step 3: 大纲
      setSteps(s => ({ ...s, outline: 'processing' }))
      setProgressMsg('正在生成故事大纲...')
      setProgress(66)

      await wizardStreamApi.generateCompleteOutlineStream(
        {
          project_id: pid,
          chapter_count: form.chapter_count,
          narrative_perspective: form.narrative_perspective,
          target_words: form.target_words,
          requirements: form.requirements.trim() || undefined,
          enable_mcp: enableMcp,
          selected_plugins: selectedPlugins,
        },
        {
          signal: controller.signal,
          onProgress: (msg, prog) => {
            setProgressMsg(msg)
            setProgress(66 + Math.floor(prog / 3))
          },
          onResult: () => setSteps(s => ({ ...s, outline: 'completed' })),
          onError: (err) => {
            setSteps(s => ({ ...s, outline: 'error' }))
            throw new Error(err)
          },
        }
      )

      setProgress(100)
      setProgressMsg('项目创建完成！')
      setPhase('done')
      toast.success('项目创建成功！')
    } catch (err) {
      const error = err as { name?: string; message?: string }
      if (error.name === 'AbortError') {
        return
      }
      setError(error.message || 'Creation failed')
      toast.error('Project creation failed: ' + (error.message || 'Unknown error'))
    }
  }

  const stepIcon = (s: GenStep) => {
    if (s === 'completed') return <CheckCircle2 className="w-4 h-4 text-emerald-500" />
    if (s === 'processing') return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
    if (s === 'error') return <AlertTriangle className="w-4 h-4 text-red-500" />
    return <div className="w-4 h-4 rounded-full border-2 border-gray-300" />
  }

  const handleStop = () => {
    abortRef.current?.abort()
    setError('已手动停止生成')
    setProgressMsg('已停止')
    // 如果已经创建了项目，可以进入项目查看已生成的部分
    if (projectId) {
      setPhase('done')
    }
  }

  // 最小化视图
  if (minimized) {
    return (
      <div className="fixed bottom-4 right-4 z-50 w-72 overflow-hidden rounded-[24px] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96)_0%,rgba(255,247,240,0.98)_100%)] shadow-xl animate-fade-in">
        <div className="px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            {phase === 'generating' && <Loader2 className="w-4 h-4 text-brand animate-spin shrink-0" />}
            {phase === 'done' && <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />}
            <span className="text-sm font-medium text-content truncate">
              {phase === 'done' ? '创建完成' : form.title || '生成中...'}
            </span>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button onClick={() => setMinimized(false)} className="p-1 text-content-tertiary hover:text-content transition-colors" title="展开">
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
            {phase === 'generating' && !error && (
              <button onClick={handleStop} className="p-1 text-content-tertiary hover:text-red-500 transition-colors" title="停止">
                <StopCircle className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
        {/* 进度条 */}
        <div className="bg-gray-100 h-1">
          <div className="bg-brand h-1 transition-all duration-500" style={{ width: `${Math.min(progress, 100)}%` }} />
        </div>
        {phase === 'done' && projectId && (
          <div className="px-4 py-2 border-t border-surface-border">
            <button
              onClick={() => onSuccess(projectId)}
              className="w-full text-xs bg-brand text-white rounded-btn py-1.5 hover:bg-brand-600 transition-colors"
            >
              进入项目 →
            </button>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
      <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-[32px] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96)_0%,rgba(255,247,240,0.98)_100%)] shadow-xl">
        {/* 标题栏 */}
        <div className="border-b border-surface-border px-6 py-5">
          <div className="mb-2 inline-flex items-center gap-2 rounded-pill bg-brand/10 px-3 py-1 text-xs font-medium text-brand">
            <Sparkles className="h-3.5 w-3.5" />
            创作向导
          </div>
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-bold text-content">
              {phase === 'form' ? '向导创建项目' : phase === 'generating' ? '正在生成...' : '创建完成'}
            </h2>
          <div className="flex items-center gap-1">
            {/* 缩小按钮（生成中/完成时可用） */}
            {phase !== 'form' && (
              <button onClick={() => setMinimized(true)} className="p-1.5 text-content-tertiary hover:text-content transition-colors" title="缩小到角落">
                <Minimize2 className="w-4 h-4" />
              </button>
            )}
            {/* 停止按钮（生成中且无错误时显示） */}
            {phase === 'generating' && !error && (
              <button onClick={handleStop} className="p-1.5 text-content-tertiary hover:text-red-500 transition-colors" title="停止生成">
                <StopCircle className="w-4 h-4" />
              </button>
            )}
            {/* 关闭按钮（表单阶段 / 有错误时 / 完成时） */}
            {(phase === 'form' || phase === 'done' || error) && (
              <button onClick={onClose} className="p-1.5 text-content-tertiary hover:text-content transition-colors" title="关闭">
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          </div>
        </div>

        <div className="px-6 py-4 space-y-4">
          {phase === 'form' && (
            <>
              {/* 书名 */}
              <div>
                <label className="block text-sm font-medium text-content mb-1">书名 <span className="text-red-500">*</span></label>
                <input
                  value={form.title}
                  onChange={e => updateField('title', e.target.value)}
                  placeholder="输入小说书名"
                  className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
                />
              </div>

              {/* 简介 */}
              <div>
                <label className="block text-sm font-medium text-content mb-1">简介 <span className="text-red-500">*</span></label>
                <textarea
                  value={form.description}
                  onChange={e => updateField('description', e.target.value)}
                  placeholder="简要描述小说的核心故事..."
                  rows={3}
                  className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none resize-none"
                />
              </div>

              {/* 主题 */}
              <div>
                <label className="block text-sm font-medium text-content mb-1">主题</label>
                <input
                  value={form.theme}
                  onChange={e => updateField('theme', e.target.value)}
                  placeholder="如：成长、复仇、爱情..."
                  className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
                />
              </div>

              {/* 类型 */}
              <div>
                <label className="block text-sm font-medium text-content mb-1">类型</label>
                <div className="flex flex-wrap gap-1.5">
                  {GENRE_OPTIONS.map(g => (
                    <button
                      key={g}
                      type="button"
                      onClick={() => updateField('genre', form.genre === g ? '' : g)}
                      className={`text-xs rounded-full px-2.5 py-1 border transition-colors ${
                        form.genre === g
                          ? 'bg-brand text-white border-brand'
                          : 'bg-white text-content-secondary border-surface-border hover:border-brand'
                      }`}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              </div>

              {/* 视角 */}
              <div>
                <label className="block text-sm font-medium text-content mb-1">叙事视角</label>
                <div className="flex gap-2">
                  {PERSPECTIVE_OPTIONS.map(p => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => updateField('narrative_perspective', p)}
                      className={`text-xs rounded-btn px-3 py-1.5 border transition-colors ${
                        form.narrative_perspective === p
                          ? 'bg-brand text-white border-brand'
                          : 'bg-white text-content-secondary border-surface-border hover:border-brand'
                      }`}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>

              {/* 高级选项 */}
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs text-content-secondary mb-1">目标字数</label>
                  <input
                    type="number"
                    value={form.target_words}
                    onChange={e => updateField('target_words', Number(e.target.value))}
                    className="w-full border border-surface-border rounded-btn px-2 py-1.5 text-xs focus:border-brand outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-content-secondary mb-1">章节数</label>
                  <input
                    type="number"
                    value={form.chapter_count}
                    onChange={e => updateField('chapter_count', Number(e.target.value))}
                    className="w-full border border-surface-border rounded-btn px-2 py-1.5 text-xs focus:border-brand outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs text-content-secondary mb-1">角色数</label>
                  <input
                    type="number"
                    value={form.character_count}
                    onChange={e => updateField('character_count', Number(e.target.value))}
                    className="w-full border border-surface-border rounded-btn px-2 py-1.5 text-xs focus:border-brand outline-none"
                  />
                </div>
              </div>

              {/* 额外要求 */}
              <div>
                <label className="block text-sm font-medium text-content mb-1">额外要求</label>
                <textarea
                  value={form.requirements}
                  onChange={e => updateField('requirements', e.target.value)}
                  placeholder="对角色、世界观、大纲的特殊要求（可选）..."
                  rows={2}
                  className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none resize-none"
                />
              </div>

              {/* MCP 插件 */}
              <MCPSelector
                value={{ enable: enableMcp, selected: selectedPlugins }}
                onChange={({ enable, selected }) => {
                  setEnableMcp(enable)
                  setSelectedPlugins(selected)
                }}
              />
            </>
          )}

          {/* 生成进度 */}
          {(phase === 'generating' || phase === 'done') && (
            <div className="space-y-4">
              <div className="space-y-2.5">
                <div className="flex items-center gap-2.5 text-sm">
                  {stepIcon(steps.world)}
                  <span className="text-content">世界观构建</span>
                </div>
                <div className="flex items-center gap-2.5 text-sm">
                  {stepIcon(steps.chars)}
                  <span className="text-content">角色生成</span>
                </div>
                <div className="flex items-center gap-2.5 text-sm">
                  {stepIcon(steps.outline)}
                  <span className="text-content">故事大纲</span>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs text-content-secondary mb-1">
                  <span>{progressMsg}</span>
                  <span>{Math.round(progress)}%</span>
                </div>
                <div className="bg-gray-100 rounded-full h-2">
                  <div
                    className="bg-brand rounded-full h-2 transition-all duration-500"
                    style={{ width: `${Math.min(progress, 100)}%` }}
                  />
                </div>
              </div>

              {error && (
                <div className="text-sm text-red-600 bg-red-50 rounded-btn px-3 py-2">
                  {error}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 底部按钮 */}
        <div className="px-6 py-4 border-t border-surface-border flex justify-end gap-2">
          {phase === 'form' && (
            <>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm rounded-btn border border-surface-border text-content-secondary hover:bg-surface-hover transition-colors"
              >
                取消
              </button>
              <button
                onClick={async () => {
                  if (!form.title.trim()) return
                  try {
                    const created = await projectApi.createProject({
                      title: form.title.trim(),
                      description: form.description.trim() || undefined,
                      theme: form.theme.trim() || undefined,
                      genre: form.genre || undefined,
                      target_words: form.target_words || undefined,
                      narrative_perspective: form.narrative_perspective || undefined,
                      chapter_count: form.chapter_count || undefined,
                      character_count: form.character_count || undefined,
                    })
                    toast.success('项目已创建')
                    onSuccess(created.id)
                  } catch { /* api 拦截器已 toast */ }
                }}
                disabled={!form.title.trim()}
                className="px-4 py-2 text-sm rounded-btn border border-surface-border text-content hover:bg-surface-hover transition-colors disabled:opacity-50"
              >
                直接创建
              </button>
              <button
                onClick={handleStart}
                disabled={!canSubmit}
                className="inline-flex items-center gap-1.5 bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50"
              >
                <Sparkles className="w-4 h-4" />
                AI 生成
              </button>
            </>
          )}
          {phase === 'generating' && !error && (
            <div className="flex items-center gap-3 w-full justify-between">
              <button
                onClick={() => setMinimized(true)}
                className="inline-flex items-center gap-1.5 text-xs text-content-secondary hover:text-content transition-colors"
              >
                <Minimize2 className="w-3.5 h-3.5" />
                缩小到后台
              </button>
              <button
                onClick={handleStop}
                className="inline-flex items-center gap-1.5 text-xs text-red-500 hover:text-red-600 transition-colors"
              >
                <StopCircle className="w-3.5 h-3.5" />
                停止生成
              </button>
            </div>
          )}
          {(phase === 'done' || (phase === 'generating' && error)) && projectId && (
            <button
              onClick={() => onSuccess(projectId)}
              className="bg-brand hover:bg-brand-600 text-white rounded-btn px-5 py-2 text-sm font-medium transition-colors"
            >
              进入项目 →
            </button>
          )}
          {error && !projectId && (
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm rounded-btn border border-surface-border text-content-secondary hover:bg-surface-hover transition-colors"
            >
              关闭
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
