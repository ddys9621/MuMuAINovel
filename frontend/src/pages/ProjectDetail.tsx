import { useEffect, useState, useMemo } from 'react'
import { useParams, useNavigate, useLocation, Outlet, NavLink } from 'react-router-dom'
import {
  ArrowLeft,
  Globe,
  Shield,
  Users,
  GitBranch,
  FileText,
  BookOpen,
  BarChart3,
  Palette,
  Menu,
  X,
  PanelLeftClose,
  PanelLeft,
  Brain,
  Wrench,
  Loader2,
  Sparkles,
} from 'lucide-react'
import { toast } from 'sonner'
import { useStore } from '@/store/index'
import { projectApi } from '@/services/api'
import { useCharacterSync, useOutlineSync, useChapterSync } from '@/store/hooks'
import { PageLoading } from '@/components/ui/PageLoading'

const NAV_ITEMS = [
  { label: '世界设定', icon: Globe, path: 'world-setting' },
  { label: '世界规则', icon: Shield, path: 'world-rules' },
  { label: '角色与组织', icon: Users, path: 'characters' },
  { label: '关系管理', icon: GitBranch, path: 'relationships' },
  { label: '故事大纲', icon: FileText, path: 'outline' },
  { label: '章节管理', icon: BookOpen, path: 'chapters' },
  { label: '剧情分析', icon: BarChart3, path: 'chapter-analysis' },
  { label: '写作风格', icon: Palette, path: 'writing-styles' },
  { label: '记忆系统', icon: Brain, path: 'memories' },
] as const

const PROJECT_STATUS_META = {
  planning: { label: '规划中', className: 'bg-orange-100 text-orange-700' },
  writing: { label: '创作中', className: 'bg-emerald-100 text-emerald-700' },
  revising: { label: '修改中', className: 'bg-amber-100 text-amber-700' },
  completed: { label: '已完成', className: 'bg-violet-100 text-violet-700' },
} as const

export default function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  const {
    currentProject,
    setCurrentProject,
    clearProjectData,
    loading,
    setLoading,
    outlines,
    characters,
    chapters,
  } = useStore()

  const { refreshCharacters } = useCharacterSync()
  const { refreshOutlines } = useOutlineSync()
  const { refreshChapters } = useChapterSync()

  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [showRepairPanel, setShowRepairPanel] = useState(false)
  const [repairLoading, setRepairLoading] = useState(false)
  const [repairReport, setRepairReport] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    if (!projectId) return

    let cancelled = false

    const load = async () => {
      try {
        setLoading(true)
        const project = await projectApi.getProject(projectId)
        if (cancelled) return
        setCurrentProject(project)

        await Promise.all([
          refreshOutlines(projectId),
          refreshCharacters(projectId),
          refreshChapters(projectId),
        ])
      } catch {
        if (!cancelled) {
          toast.error('加载项目失败')
          navigate('/')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()

    return () => {
      cancelled = true
      clearProjectData()
      setCurrentProject(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId])

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  const stats = useMemo(() => {
    const totalWords = chapters.reduce((sum, ch) => sum + (ch.word_count ?? 0), 0)
    return {
      outlines: outlines.length,
      characters: characters.length,
      chapters: chapters.length,
      words: totalWords,
    }
  }, [outlines, characters, chapters])

  const formatCount = (n: number) => (n >= 10000 ? `${(n / 10000).toFixed(1)}万` : String(n))

  const currentSection = useMemo(() => {
    return NAV_ITEMS.find((item) => location.pathname.includes(item.path))?.label ?? '创作总览'
  }, [location.pathname])

  const projectStatus = currentProject ? PROJECT_STATUS_META[currentProject.status] : PROJECT_STATUS_META.planning
  const projectTags = currentProject?.genre?.split(/[,，、/]/).filter(Boolean).slice(0, 3) ?? []

  if (loading && !currentProject) return <PageLoading />

  const sidebarContent = (
    <div className="flex h-full flex-col">
      <div className="border-b border-white/10 px-3 pb-4 pt-4">
        <button
          onClick={() => navigate('/')}
          className={`flex items-center gap-2 rounded-[18px] px-3 py-3 text-sm text-sidebar-text transition-colors hover:bg-white/8 hover:text-white ${collapsed ? 'justify-center' : ''}`}
        >
          <ArrowLeft className="h-4 w-4 shrink-0" />
          {!collapsed && <span>返回书架</span>}
        </button>

        {!collapsed && currentProject && (
          <div className="mt-3 rounded-[24px] border border-white/10 bg-white/6 p-4 text-sidebar-text shadow-[0_18px_40px_-30px_rgba(0,0,0,0.55)] backdrop-blur-sm">
            <div className="mb-3 inline-flex items-center gap-2 rounded-pill bg-white/10 px-3 py-1 text-xs text-white/90">
              <Sparkles className="h-3.5 w-3.5 text-brand-200" />
              当前项目
            </div>
            <h2 className="line-clamp-2 text-base font-semibold text-white">{currentProject.title}</h2>
            <p className="mt-2 line-clamp-2 text-sm leading-6 text-sidebar-text/90">{currentProject.description || '继续完善设定、角色、大纲与章节内容。'}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <span className="rounded-pill bg-white/10 px-2.5 py-1 text-[11px] text-sidebar-text/90">世界设定</span>
              <span className="rounded-pill bg-white/10 px-2.5 py-1 text-[11px] text-sidebar-text/90">角色管理</span>
              <span className="rounded-pill bg-white/10 px-2.5 py-1 text-[11px] text-sidebar-text/90">章节推进</span>
            </div>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-1.5 overflow-y-auto px-2 py-4">
        {NAV_ITEMS.map(({ label, icon: Icon, path }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              [
                'group flex items-center gap-3 rounded-[18px] text-sm transition-all',
                collapsed ? 'justify-center px-2 py-3' : 'px-3 py-3',
                isActive
                  ? 'bg-[linear-gradient(90deg,rgba(255,113,72,0.24),rgba(255,189,112,0.16))] text-white shadow-[0_18px_40px_-30px_rgba(255,113,72,0.95)]'
                  : 'text-sidebar-text hover:bg-white/8 hover:text-white',
              ].join(' ')
            }
            title={collapsed ? label : undefined}
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-white/10">
              <Icon className="h-[18px] w-[18px] shrink-0" />
            </span>
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 px-2 py-3">
        <button
          onClick={() => setShowRepairPanel(true)}
          className={`mb-2 flex w-full items-center gap-3 rounded-[18px] px-3 py-3 text-sm text-sidebar-text transition-colors hover:bg-white/8 hover:text-white ${collapsed ? 'justify-center px-2' : ''}`}
          title="数据修复"
        >
          <Wrench className="h-4 w-4 shrink-0" />
          {!collapsed && <span>数据修复</span>}
        </button>
        <button
          onClick={() => setCollapsed((v) => !v)}
          className={`hidden w-full items-center gap-3 rounded-[18px] px-3 py-3 text-sm text-sidebar-text transition-colors hover:bg-white/8 hover:text-white lg:flex ${collapsed ? 'justify-center px-2' : ''}`}
        >
          {collapsed ? <PanelLeft className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
          {!collapsed && <span>收起侧栏</span>}
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex h-screen overflow-hidden bg-transparent">
      <aside
        className={[
          'hidden lg:flex flex-col overflow-hidden border-r border-white/10 bg-[linear-gradient(180deg,#3b1d16_0%,#2d140f_38%,#24110d_100%)] shadow-[18px_0_50px_-36px_rgba(0,0,0,0.7)] shrink-0 transition-[width] duration-200',
          collapsed ? 'w-16' : 'w-64',
        ].join(' ')}
      >
        {sidebarContent}
      </aside>

      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-[#2d130d]/50 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside
        className={[
          'fixed inset-y-0 left-0 z-50 w-64 bg-[linear-gradient(180deg,#3b1d16_0%,#2d140f_38%,#24110d_100%)] transform transition-transform duration-200 lg:hidden',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
        ].join(' ')}
      >
        {sidebarContent}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-white/70 bg-white/65 px-4 py-3 backdrop-blur-xl md:px-6">
          <div className="mx-auto flex max-w-[1600px] items-center gap-4">
            <button
              className="fanqie-toolbar-btn h-11 w-11 p-0 lg:hidden"
              onClick={() => setMobileOpen((v) => !v)}
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>

            <div className="min-w-0 flex-1">
              <div className="mb-1 flex items-center gap-2">
                <span className="fanqie-chip border-brand/10 bg-brand/5 text-brand">项目工作台</span>
                <span className={`inline-flex rounded-pill px-3 py-1 text-xs font-medium ${projectStatus.className}`}>{projectStatus.label}</span>
              </div>
              <div className="flex flex-col gap-1 md:flex-row md:items-end md:justify-between">
                <div className="min-w-0">
                  <h1 className="truncate text-lg font-semibold text-content md:text-[24px]">{currentProject?.title ?? '加载中…'}</h1>
                  <p className="truncate text-sm text-content-secondary">当前页面 · {currentSection}</p>
                </div>
                <div className="hidden flex-wrap items-center gap-2 text-xs text-content-secondary md:flex">
                  <span className="fanqie-chip">大纲 {stats.outlines}</span>
                  <span className="fanqie-chip">角色 {stats.characters}</span>
                  <span className="fanqie-chip">章节 {stats.chapters}</span>
                  <span className="fanqie-chip">字数 {formatCount(stats.words)}</span>
                </div>
              </div>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto px-4 pb-5 pt-4 md:px-6 md:pb-6 md:pt-5">
          <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4">
            <section className="hh-hero-shell px-6 py-6">
              <div className="absolute -right-10 top-0 h-32 w-32 rounded-full bg-white/18 blur-3xl" />
              <div className="absolute -left-10 bottom-0 h-32 w-32 rounded-full bg-white/14 blur-3xl" />
              <div className="relative z-10 flex flex-col gap-5 lg:flex-row lg:items-stretch lg:justify-between">
                <div className="max-w-[820px]">
                  <div className="hh-hero-eyebrow">
                    <Sparkles className="h-3.5 w-3.5" />
                    项目概览
                  </div>
                  <h2 className="mt-4 line-clamp-2 text-[28px] font-semibold leading-tight md:text-[34px]">
                    {currentProject?.title || '当前项目'}
                  </h2>
                  <p className="mt-3 max-w-[720px] line-clamp-3 text-sm leading-7 text-white/88 md:text-base">
                    {currentProject?.description || '项目简介还未填写。你可以直接进入对应模块继续完善世界设定、角色、组织与章节内容。'}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <span className="hh-hero-tag">当前页面：{currentSection}</span>
                    {currentProject?.theme && <span className="hh-hero-tag">主题：{currentProject.theme}</span>}
                    {(projectTags.length > 0) && projectTags.map((tag) => (
                      <span key={tag} className="hh-hero-tag">{tag.trim()}</span>
                    ))}
                  </div>
                </div>

                <div className="w-full lg:max-w-[420px]">
                  <div className="hh-hero-sidecard">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-white">创作进度</p>
                        <p className="mt-1 text-xs text-white/72">围绕设定、角色、章节持续推进当前项目</p>
                      </div>
                      <span className={`inline-flex rounded-pill px-3 py-1 text-xs font-medium ${projectStatus.className} bg-white/90`}>
                        {projectStatus.label}
                      </span>
                    </div>
                    <div className="mt-4 grid grid-cols-2 gap-3">
                      <div className="hh-hero-metric">
                        <p className="text-xs text-white/70">大纲</p>
                        <p className="mt-2 text-2xl font-semibold">{stats.outlines}</p>
                      </div>
                      <div className="hh-hero-metric">
                        <p className="text-xs text-white/70">角色</p>
                        <p className="mt-2 text-2xl font-semibold">{stats.characters}</p>
                      </div>
                      <div className="hh-hero-metric">
                        <p className="text-xs text-white/70">章节</p>
                        <p className="mt-2 text-2xl font-semibold">{stats.chapters}</p>
                      </div>
                      <div className="hh-hero-metric">
                        <p className="text-xs text-white/70">字数</p>
                        <p className="mt-2 text-2xl font-semibold">{formatCount(stats.words)}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="fanqie-card min-h-[calc(100vh-320px)] p-4 md:p-6">
              <Outlet />
            </section>
          </div>
        </main>
      </div>

      {showRepairPanel && projectId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#2d130d]/45 px-4 backdrop-blur-sm" onClick={() => setShowRepairPanel(false)}>
          <div className="w-full max-w-md rounded-modal border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.97)_0%,rgba(255,247,240,0.98)_100%)] shadow-xl animate-scale-in" onClick={(e) => e.stopPropagation()}>
            <div className="border-b border-surface-border px-6 pb-4 pt-5">
              <div className="mb-2 inline-flex items-center gap-2 rounded-pill bg-brand/10 px-3 py-1 text-xs font-medium text-brand">
                <Wrench className="h-3.5 w-3.5" />
                数据修复
              </div>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold text-content">数据一致性修复</h2>
                  <p className="mt-1 text-sm text-content-secondary">检查并修复项目数据中的不一致问题。</p>
                </div>
                <button onClick={() => setShowRepairPanel(false)} className="fanqie-toolbar-btn h-10 w-10 p-0"><X className="h-4 w-4" /></button>
              </div>
            </div>
            <div className="space-y-3 px-6 py-5">
              <button
                onClick={async () => {
                  setRepairLoading(true)
                  try {
                    const res = await projectApi.checkConsistency(projectId)
                    setRepairReport(res)
                    toast.success('一致性检查完成')
                  } catch {
                    toast.error('检查失败')
                  } finally {
                    setRepairLoading(false)
                  }
                }}
                disabled={repairLoading}
                className="fanqie-primary-btn w-full disabled:cursor-not-allowed disabled:opacity-50"
              >
                {repairLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wrench className="h-4 w-4" />}
                检查并自动修复
              </button>
              <button
                onClick={async () => {
                  try {
                    const res = await projectApi.fixOrganizations(projectId)
                    toast.success(`组织修复: ${res.fixed_count}/${res.total_count}`)
                  } catch {
                    toast.error('修复失败')
                  }
                }}
                className="fanqie-secondary-btn w-full"
              >
                修复组织记录
              </button>
              <button
                onClick={async () => {
                  try {
                    const res = await projectApi.fixMemberCounts(projectId)
                    toast.success(`计数修复: ${res.fixed_count}/${res.total_count}`)
                  } catch {
                    toast.error('修复失败')
                  }
                }}
                className="fanqie-secondary-btn w-full"
              >
                修复成员计数
              </button>
              {repairReport && (
                <div className="max-h-44 overflow-y-auto rounded-[20px] bg-white/80 p-3 text-xs text-content-secondary whitespace-pre-wrap">
                  {JSON.stringify(repairReport, null, 2)}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
