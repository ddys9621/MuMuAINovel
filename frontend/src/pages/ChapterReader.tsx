import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Loader2,
  ChevronLeft,
  ChevronRight,
  PanelRightOpen,
  PanelRightClose,
  BarChart3,
  Users,
  Heart,
  Star,
  AlertCircle,
  BookOpenText,
  Sparkles,
  Eye,
  Clock,
  Link2,
  ShieldAlert,
  ChevronDown,
  MapPin,
  ArrowRight,
} from 'lucide-react'
import { chapterApi } from '@/services/api'
import type { Chapter } from '@/types'
import { normalizeAnalysisData, type NormalizedAnalysisData } from '@/utils/chapterAnalysis'

function NavButton({
  chapter,
  direction,
  onClick,
}: {
  chapter: Chapter | null
  direction: 'prev' | 'next'
  onClick: () => void
}) {
  if (!chapter) return <div />
  return (
    <button
      onClick={onClick}
      className="fanqie-secondary-btn max-w-[220px] justify-start px-3 py-2 text-left"
    >
      {direction === 'prev' && <ChevronLeft className="h-4 w-4" />}
      <span className="truncate">
        {direction === 'prev' ? '上一章' : '下一章'}：{chapter.title}
      </span>
      {direction === 'next' && <ChevronRight className="h-4 w-4" />}
    </button>
  )
}

function AnalysisSidebar({
  chapterId,
  open,
  onClose,
}: {
  chapterId: string
  open: boolean
  onClose: () => void
}) {
  const [analysis, setAnalysis] = useState<NormalizedAnalysisData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || !chapterId) return
    setLoading(true)
    setError('')
    chapterApi
      .getAnalysis(chapterId)
      .then((data) => setAnalysis(normalizeAnalysisData(data as unknown as Record<string, unknown>)))
      .catch(() => setError('暂无分析数据'))
      .finally(() => setLoading(false))
  }, [open, chapterId])

  const plotAnalysis = analysis?.plot_analysis
  const characterStatus = analysis?.character_status
  const emotionCurve = analysis?.emotion_curve
  const score = analysis?.score
  const narrativeState = analysis?.narrative_state
  const consistencyAudit = analysis?.consistency_audit

  const promises = narrativeState?.promises ?? []
  const timelineEvents = narrativeState?.timeline_events ?? []
  const relationshipGraph = narrativeState?.relationship_graph
  const causalLinks = narrativeState?.causal_links ?? []
  const auditIssues = consistencyAudit?.issues ?? []
  const auditSummary = consistencyAudit?.summary

  const [expandedSection, setExpandedSection] = useState<string | null>(null)
  const toggleSection = (key: string) => setExpandedSection(prev => prev === key ? null : key)

  if (!open) return null

  const severityStyle: Record<string, string> = {
    critical: 'bg-red-100 text-red-700 border-red-200',
    high: 'bg-orange-100 text-orange-700 border-orange-200',
    medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    low: 'bg-gray-100 text-gray-500 border-gray-200',
  }
  const severityLabel: Record<string, string> = {
    critical: '严重',
    high: '高',
    medium: '中',
    low: '低',
  }
  const promiseStatusStyle: Record<string, string> = {
    open: 'bg-blue-100 text-blue-700',
    progressing: 'bg-amber-100 text-amber-700',
    resolved: 'bg-emerald-100 text-emerald-700',
    broken: 'bg-red-100 text-red-700',
  }
  const promiseStatusLabel: Record<string, string> = {
    open: '未解',
    progressing: '推进中',
    resolved: '已回收',
    broken: '已破裂',
  }
  const promiseTypeLabel: Record<string, string> = {
    foreshadow: '伏笔',
    promise: '承诺',
    mystery: '悬念',
    conflict: '冲突',
  }

  return (
    <aside className="w-[340px] shrink-0 border-l border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96)_0%,rgba(255,247,240,0.98)_100%)] shadow-[-18px_0_48px_-36px_rgba(109,56,32,0.35)]">
      <div className="sticky top-0 z-10 border-b border-surface-border bg-white/85 px-5 py-4 backdrop-blur-md">
        <div className="mb-2 inline-flex items-center gap-2 rounded-pill bg-brand/10 px-3 py-1 text-xs font-medium text-brand">
          <Sparkles className="h-3.5 w-3.5" />
          章节洞察
        </div>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-content">章节分析</h3>
            <p className="mt-1 text-xs text-content-secondary">结构、人物、叙事与审计一侧查看</p>
          </div>
          <button onClick={onClose} className="fanqie-toolbar-btn h-10 w-10 p-0">
            <PanelRightClose className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="space-y-4 overflow-y-auto p-5" style={{ maxHeight: 'calc(100vh - 120px)' }}>
        {loading && (
          <div className="flex justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-brand" />
          </div>
        )}

        {error && (
          <div className="fanqie-soft-card flex flex-col items-center py-8 text-content-tertiary">
            <AlertCircle className="mb-3 h-6 w-6 opacity-60" />
            <p className="text-xs">{error}</p>
          </div>
        )}

        {analysis && !loading && (
          <>
            {score != null && (
              <div className="fanqie-soft-card p-4">
                <div className="mb-2 flex items-center gap-2">
                  <Star className="h-4 w-4 text-gold" />
                  <span className="text-xs text-content-secondary">综合评分</span>
                </div>
                <p className="text-3xl font-semibold text-content">{score}<span className="text-sm font-normal text-content-tertiary"> / 10</span></p>
              </div>
            )}

            {plotAnalysis && (
              <div className="fanqie-card p-4">
                <div className="mb-3 flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-brand" />
                  <span className="text-xs font-medium text-content-secondary">情节分析</span>
                </div>
                <p className="text-sm leading-7 text-content whitespace-pre-wrap">{plotAnalysis}</p>
              </div>
            )}

            {characterStatus && characterStatus.length > 0 && (
              <div className="fanqie-card p-4">
                <div className="mb-3 flex items-center gap-2">
                  <Users className="h-4 w-4 text-emerald-600" />
                  <span className="text-xs font-medium text-content-secondary">角色状态</span>
                </div>
                <div className="space-y-2">
                  {characterStatus.map((char, i) => (
                    <div key={i} className="rounded-[18px] bg-surface px-3 py-3">
                      <p className="text-sm font-medium text-content">{char.name || `角色 ${i + 1}`}</p>
                      {char.status && <p className="mt-1 text-xs leading-6 text-content-secondary">{char.status}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {emotionCurve && emotionCurve.length > 0 && (
              <div className="fanqie-card p-4">
                <div className="mb-3 flex items-center gap-2">
                  <Heart className="h-4 w-4 text-rose-500" />
                  <span className="text-xs font-medium text-content-secondary">情感曲线</span>
                </div>
                <div className="space-y-2.5">
                  {emotionCurve.map((point, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className="w-16 shrink-0 truncate text-xs text-content-secondary">{point.label}</span>
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-[#f7e8de]">
                        <div
                          className="h-full rounded-full bg-brand transition-all"
                          style={{ width: `${Math.min(100, Math.max(0, point.value))}%` }}
                        />
                      </div>
                      <span className="w-8 text-right text-xs text-content-tertiary">{point.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ═══ 承诺 / 伏笔追踪 ═══ */}
            {promises.length > 0 && (
              <div className="fanqie-card overflow-hidden">
                <button
                  onClick={() => toggleSection('promises')}
                  className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left transition-colors hover:bg-surface/40"
                >
                  <div className="flex items-center gap-2">
                    <Eye className="h-4 w-4 text-purple-500" />
                    <span className="text-xs font-medium text-content-secondary">承诺 / 伏笔</span>
                    <span className="rounded-full bg-purple-100 px-1.5 py-0.5 text-[10px] font-medium text-purple-600">{promises.length}</span>
                  </div>
                  <ChevronDown className={`h-3.5 w-3.5 text-content-tertiary transition-transform ${expandedSection === 'promises' ? 'rotate-180' : ''}`} />
                </button>
                {expandedSection === 'promises' && (
                  <div className="space-y-2 px-4 pb-4">
                    {promises.map((p, i) => {
                      const status = String(p.status || 'open')
                      const pType = String(p.promise_type || '')
                      const priority = String(p.priority || '')
                      return (
                        <div key={String(p.id || i)} className="rounded-[14px] border border-surface-border bg-surface/30 px-3 py-2.5">
                          <div className="mb-1 flex flex-wrap items-center gap-1.5">
                            {pType && <span className="rounded bg-purple-50 px-1.5 py-0.5 text-[10px] font-medium text-purple-600">{promiseTypeLabel[pType] || pType}</span>}
                            <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${promiseStatusStyle[status] || 'bg-gray-100 text-gray-600'}`}>{promiseStatusLabel[status] || status}</span>
                            {priority === 'critical' && <span className="rounded bg-red-50 px-1.5 py-0.5 text-[10px] font-medium text-red-600">紧急</span>}
                            {priority === 'high' && <span className="rounded bg-orange-50 px-1.5 py-0.5 text-[10px] font-medium text-orange-600">高优</span>}
                          </div>
                          <p className="text-xs font-medium text-content">{String(p.title || '未命名')}</p>
                          {Boolean(p.content) && <p className="mt-1 text-[11px] leading-5 text-content-secondary line-clamp-2">{String(p.content)}</p>}
                          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-content-tertiary">
                            {Boolean(p.owner_character_name) && <span>发起: {String(p.owner_character_name)}</span>}
                            {Boolean(p.target_character_name) && <span>对象: {String(p.target_character_name)}</span>}
                            {p.source_chapter_number != null && <span>第{String(p.source_chapter_number)}章埋设</span>}
                            {p.resolved_chapter_number != null && <span>第{String(p.resolved_chapter_number)}章回收</span>}
                            {p.deadline_chapter != null && <span>期限: 第{String(p.deadline_chapter)}章</span>}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )}

            {/* ═══ 时间轴事件 ═══ */}
            {timelineEvents.length > 0 && (
              <div className="fanqie-card overflow-hidden">
                <button
                  onClick={() => toggleSection('timeline')}
                  className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left transition-colors hover:bg-surface/40"
                >
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-sky-500" />
                    <span className="text-xs font-medium text-content-secondary">时间轴事件</span>
                    <span className="rounded-full bg-sky-100 px-1.5 py-0.5 text-[10px] font-medium text-sky-600">{timelineEvents.length}</span>
                  </div>
                  <ChevronDown className={`h-3.5 w-3.5 text-content-tertiary transition-transform ${expandedSection === 'timeline' ? 'rotate-180' : ''}`} />
                </button>
                {expandedSection === 'timeline' && (
                  <div className="relative px-4 pb-4">
                    <div className="absolute bottom-4 left-[26px] top-0 w-px bg-sky-200" />
                    <div className="space-y-3">
                      {timelineEvents.map((evt, i) => {
                        const actors = (evt.actor_names as string[]) || []
                        const targets = (evt.target_names as string[]) || []
                        return (
                          <div key={String(evt.id || i)} className="relative pl-6">
                            <div className="absolute left-0 top-1 h-2.5 w-2.5 rounded-full border-2 border-sky-400 bg-white" />
                            <div className="rounded-[12px] border border-surface-border bg-surface/30 px-3 py-2">
                              <div className="mb-0.5 flex items-center gap-1.5">
                                {Boolean(evt.event_type) && <span className="rounded bg-sky-50 px-1.5 py-0.5 text-[10px] font-medium text-sky-600">{String(evt.event_type)}</span>}
                                {evt.public_visibility === 'secret' && <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500">秘密</span>}
                              </div>
                              <p className="text-xs font-medium text-content">{String(evt.title || '未命名事件')}</p>
                              {Boolean(evt.description) && <p className="mt-0.5 text-[11px] leading-5 text-content-secondary line-clamp-2">{String(evt.description)}</p>}
                              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-content-tertiary">
                                {Boolean(evt.location) && <span className="inline-flex items-center gap-0.5"><MapPin className="h-2.5 w-2.5" />{String(evt.location)}</span>}
                                {Boolean(evt.time_marker) && <span>{String(evt.time_marker)}</span>}
                                {actors.length > 0 && <span>参与: {actors.join(', ')}</span>}
                                {targets.length > 0 && <span>目标: {targets.join(', ')}</span>}
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ═══ 关系变化图 ═══ */}
            {relationshipGraph && (relationshipGraph.nodes.length > 0 || relationshipGraph.edges.length > 0) && (
              <div className="fanqie-card overflow-hidden">
                <button
                  onClick={() => toggleSection('relationship')}
                  className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left transition-colors hover:bg-surface/40"
                >
                  <div className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-pink-500" />
                    <span className="text-xs font-medium text-content-secondary">关系变化</span>
                    <span className="rounded-full bg-pink-100 px-1.5 py-0.5 text-[10px] font-medium text-pink-600">{relationshipGraph.edges.length}</span>
                  </div>
                  <ChevronDown className={`h-3.5 w-3.5 text-content-tertiary transition-transform ${expandedSection === 'relationship' ? 'rotate-180' : ''}`} />
                </button>
                {expandedSection === 'relationship' && (
                  <div className="space-y-2 px-4 pb-4">
                    {relationshipGraph.edges.map((edge, i) => {
                      const delta = Number(edge.delta || 0)
                      const deltaColor = delta > 0 ? 'text-emerald-600' : delta < 0 ? 'text-red-600' : 'text-gray-500'
                      const deltaSign = delta > 0 ? '+' : ''
                      return (
                        <div key={i} className="rounded-[14px] border border-surface-border bg-surface/30 px-3 py-2.5">
                          <div className="flex items-center gap-1.5 text-xs">
                            <span className="font-medium text-content">{String(edge.source)}</span>
                            <ArrowRight className="h-3 w-3 text-content-tertiary" />
                            <span className="font-medium text-content">{String(edge.target)}</span>
                            <span className={`ml-auto font-semibold ${deltaColor}`}>{deltaSign}{delta}</span>
                          </div>
                          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-content-tertiary">
                            {Boolean(edge.reason) && <span>{String(edge.reason)}</span>}
                            {Boolean(edge.new_status) && <span>状态: {String(edge.new_status)}</span>}
                            {edge.intimacy_level != null && <span>亲密度: {String(edge.intimacy_level)}</span>}
                          </div>
                        </div>
                      )
                    })}
                    {relationshipGraph.edges.length === 0 && relationshipGraph.nodes.length > 0 && (
                      <p className="py-2 text-center text-[11px] text-content-tertiary">本章涉及 {relationshipGraph.nodes.length} 位角色，但无关系变化</p>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ═══ 因果链 ═══ */}
            {causalLinks.length > 0 && (
              <div className="fanqie-card overflow-hidden">
                <button
                  onClick={() => toggleSection('causal')}
                  className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left transition-colors hover:bg-surface/40"
                >
                  <div className="flex items-center gap-2">
                    <Link2 className="h-4 w-4 text-amber-500" />
                    <span className="text-xs font-medium text-content-secondary">因果链</span>
                    <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-600">{causalLinks.length}</span>
                  </div>
                  <ChevronDown className={`h-3.5 w-3.5 text-content-tertiary transition-transform ${expandedSection === 'causal' ? 'rotate-180' : ''}`} />
                </button>
                {expandedSection === 'causal' && (
                  <div className="space-y-2 px-4 pb-4">
                    {causalLinks.map((link, i) => (
                      <div key={i} className="rounded-[14px] border border-surface-border bg-surface/30 px-3 py-2.5">
                        <div className="flex items-center gap-1.5 text-[11px] text-content-secondary">
                          <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-600">
                            重要度 {Number(link.importance || 0)}
                          </span>
                          {Boolean(link.reversible) && <span className="rounded bg-green-50 px-1 py-0.5 text-[10px] text-green-600">可逆</span>}
                        </div>
                        <div className="mt-1.5 space-y-1 text-xs">
                          {Boolean(link.cause) && <p><span className="font-medium text-content">起因：</span><span className="text-content-secondary">{String(link.cause)}</span></p>}
                          {Boolean(link.event) && <p><span className="font-medium text-content">事件：</span><span className="text-content-secondary">{String(link.event)}</span></p>}
                          {Boolean(link.decision) && <p><span className="font-medium text-content">决策：</span><span className="text-content-secondary">{String(link.decision)}</span></p>}
                          {Boolean(link.effect) && <p><span className="font-medium text-content">影响：</span><span className="text-content-secondary">{String(link.effect)}</span></p>}
                        </div>
                        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-content-tertiary">
                          {Array.isArray(link.actor_names) && (link.actor_names as string[]).length > 0 && <span>参与: {(link.actor_names as string[]).join(', ')}</span>}
                          {Array.isArray(link.target_names) && (link.target_names as string[]).length > 0 && <span>目标: {(link.target_names as string[]).join(', ')}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ═══ 一致性审计 ═══ */}
            {auditSummary && auditSummary.total > 0 && (
              <div className="fanqie-card overflow-hidden border-red-200/60">
                <button
                  onClick={() => toggleSection('audit')}
                  className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left transition-colors hover:bg-surface/40"
                >
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="h-4 w-4 text-red-500" />
                    <span className="text-xs font-medium text-content-secondary">一致性审计</span>
                    <span className="rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-medium text-red-600">{auditSummary.total} 项</span>
                  </div>
                  <ChevronDown className={`h-3.5 w-3.5 text-content-tertiary transition-transform ${expandedSection === 'audit' ? 'rotate-180' : ''}`} />
                </button>
                {expandedSection === 'audit' && (
                  <div className="px-4 pb-4">
                    <div className="mb-3 flex flex-wrap gap-2">
                      {auditSummary.critical > 0 && <span className="rounded bg-red-100 px-2 py-0.5 text-[10px] font-semibold text-red-700">严重 {auditSummary.critical}</span>}
                      {auditSummary.high > 0 && <span className="rounded bg-orange-100 px-2 py-0.5 text-[10px] font-semibold text-orange-700">高 {auditSummary.high}</span>}
                      {auditSummary.medium > 0 && <span className="rounded bg-yellow-100 px-2 py-0.5 text-[10px] font-semibold text-yellow-700">中 {auditSummary.medium}</span>}
                      {auditSummary.low > 0 && <span className="rounded bg-gray-100 px-2 py-0.5 text-[10px] font-semibold text-gray-600">低 {auditSummary.low}</span>}
                    </div>
                    <div className="space-y-2">
                      {auditIssues.map((issue, i) => {
                        const sev = String(issue.severity || 'medium')
                        return (
                          <div key={i} className={`rounded-[14px] border px-3 py-2.5 ${severityStyle[sev] || severityStyle.medium}`}>
                            <div className="mb-0.5 flex items-center gap-1.5">
                              <span className="text-[10px] font-semibold">{severityLabel[sev] || sev}</span>
                              {Boolean(issue.issue_type) && <span className="text-[10px] opacity-70">{String(issue.issue_type)}</span>}
                            </div>
                            <p className="text-xs font-medium">{String(issue.title || '未命名问题')}</p>
                            {Boolean(issue.details) && <p className="mt-0.5 text-[11px] leading-5 opacity-80">{String(issue.details)}</p>}
                            <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] opacity-60">
                              {Boolean(issue.character_name) && <span>角色: {String(issue.character_name)}</span>}
                              {issue.reference_chapter_number != null && <span>参考: 第{String(issue.reference_chapter_number)}章</span>}
                              {Boolean(issue.evidence) && <span className="line-clamp-1">证据: {String(issue.evidence)}</span>}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {!plotAnalysis && !characterStatus?.length && !emotionCurve?.length && score == null
              && !promises.length && !timelineEvents.length && !causalLinks.length
              && !(auditSummary && auditSummary.total > 0)
              && !(relationshipGraph && (relationshipGraph.nodes.length > 0 || relationshipGraph.edges.length > 0)) && (
              <p className="py-4 text-center text-xs text-content-tertiary">分析数据为空</p>
            )}
          </>
        )}
      </div>
    </aside>
  )
}

export default function ChapterReader() {
  const { chapterId } = useParams<{ chapterId: string }>()
  const navigate = useNavigate()
  const [chapter, setChapter] = useState<Chapter | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [prevChapter, setPrevChapter] = useState<Chapter | null>(null)
  const [nextChapter, setNextChapter] = useState<Chapter | null>(null)
  const [showAnalysis, setShowAnalysis] = useState(false)

  const loadChapter = useCallback(async (id: string) => {
    setLoading(true)
    setError('')
    try {
      const data = await chapterApi.getChapter(id)
      setChapter(data)
    } catch {
      setError('章节加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadNavigation = useCallback(async (id: string) => {
    try {
      const nav = await chapterApi.getNavigation(id)
      setPrevChapter(nav.previous)
      setNextChapter(nav.next)
    } catch {
      setPrevChapter(null)
      setNextChapter(null)
    }
  }, [])

  useEffect(() => {
    if (!chapterId) return
    loadChapter(chapterId)
    loadNavigation(chapterId)
  }, [chapterId, loadChapter, loadNavigation])

  const navigateTo = (ch: Chapter) => {
    navigate(`/reader/${ch.id}`, { replace: true })
    window.scrollTo(0, 0)
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-transparent px-4">
        <div className="fanqie-soft-card flex min-w-[220px] flex-col items-center gap-4 px-8 py-10 text-center">
          <Loader2 className="h-6 w-6 animate-spin text-brand" />
          <p className="text-sm text-content-secondary">正在加载章节内容...</p>
        </div>
      </div>
    )
  }

  if (error || !chapter) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-transparent px-4">
        <div className="fanqie-soft-card flex max-w-md flex-col items-center px-8 py-10 text-center">
          <AlertCircle className="mb-3 h-8 w-8 text-brand/70" />
          <p className="text-sm text-content-secondary">{error || '章节不存在'}</p>
          <button onClick={() => navigate(-1)} className="fanqie-secondary-btn mt-5">返回</button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-transparent md:px-4 md:py-4">
      <div className="mx-auto flex min-h-screen max-w-[1640px] overflow-hidden rounded-[32px] border border-white/70 bg-white/55 shadow-xl backdrop-blur-xl md:min-h-[calc(100vh-2rem)]">
        <div className="flex min-w-0 flex-1 flex-col bg-[linear-gradient(180deg,rgba(255,250,244,0.92)_0%,rgba(255,246,239,0.98)_100%)]">
          <div className="sticky top-0 z-20 border-b border-white/70 bg-white/70 backdrop-blur-xl">
            <div className="mx-auto flex max-w-[980px] items-center gap-3 px-5 py-4 md:px-8">
              <button onClick={() => navigate(-1)} className="fanqie-toolbar-btn h-11 w-11 p-0">
                <ArrowLeft className="h-4 w-4" />
              </button>

              <div className="min-w-0 flex-1">
                <div className="mb-1 flex items-center gap-2">
                  <span className="fanqie-chip border-brand/10 bg-brand/5 text-brand">沉浸式阅读</span>
                  <span className="hidden text-xs text-content-tertiary md:inline">第 {chapter.chapter_number} 章</span>
                </div>
                <p className="truncate text-lg font-semibold text-content">{chapter.title}</p>
                <p className="truncate text-xs text-content-secondary md:text-sm">{(chapter.word_count || 0).toLocaleString()} 字 · 保持当前章节阅读节奏</p>
              </div>

              <div className="hidden items-center gap-2 md:flex">
                {prevChapter && (
                  <button onClick={() => navigateTo(prevChapter)} className="fanqie-toolbar-btn h-11 w-11 p-0" title={`上一章：${prevChapter.title}`}>
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                )}
                {nextChapter && (
                  <button onClick={() => navigateTo(nextChapter)} className="fanqie-toolbar-btn h-11 w-11 p-0" title={`下一章：${nextChapter.title}`}>
                    <ChevronRight className="h-4 w-4" />
                  </button>
                )}
                <button
                  onClick={() => setShowAnalysis(!showAnalysis)}
                  className={`fanqie-toolbar-btn h-11 w-11 p-0 ${showAnalysis ? 'border-brand/20 bg-brand/10 text-brand' : ''}`}
                  title="章节分析"
                >
                  <PanelRightOpen className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>

          <div className="mx-auto flex w-full max-w-[980px] flex-1 flex-col px-5 pb-10 pt-5 md:px-8 md:pt-6">
            <div className="flex items-center justify-between gap-3 md:hidden">
              <NavButton chapter={prevChapter} direction="prev" onClick={() => prevChapter && navigateTo(prevChapter)} />
              <button
                onClick={() => setShowAnalysis(!showAnalysis)}
                className={`fanqie-toolbar-btn h-11 w-11 shrink-0 p-0 ${showAnalysis ? 'border-brand/20 bg-brand/10 text-brand' : ''}`}
                title="章节分析"
              >
                <PanelRightOpen className="h-4 w-4" />
              </button>
              <NavButton chapter={nextChapter} direction="next" onClick={() => nextChapter && navigateTo(nextChapter)} />
            </div>

            <section className="fanqie-soft-card mt-5 flex-1 px-6 py-8 md:px-10 md:py-10">
              <div className="mb-8 flex items-center gap-3 text-content-secondary">
                <div className="flex h-12 w-12 items-center justify-center rounded-[18px] bg-brand/10 text-brand">
                  <BookOpenText className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-content-tertiary">Chapter Reader</p>
                  <p className="text-sm">当前章节沉浸阅读模式</p>
                </div>
              </div>

              <article className="mx-auto max-w-3xl">
                <h1 className="mb-8 text-3xl font-semibold leading-tight text-content md:text-[36px]">{chapter.title}</h1>
                {chapter.content ? (
                  <div
                    className="whitespace-pre-wrap text-[17px] leading-[2.15] text-content md:text-[18px]"
                    style={{ fontFamily: 'Inter, PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif' }}
                  >
                    {chapter.content}
                  </div>
                ) : (
                  <p className="text-sm text-content-secondary">暂无内容</p>
                )}
              </article>
            </section>

            <div className="mt-6 flex flex-col gap-3 border-t border-surface-border pt-6 md:flex-row md:items-center md:justify-between">
              <NavButton chapter={prevChapter} direction="prev" onClick={() => prevChapter && navigateTo(prevChapter)} />
              <NavButton chapter={nextChapter} direction="next" onClick={() => nextChapter && navigateTo(nextChapter)} />
            </div>
          </div>
        </div>

        {chapterId && (
          <AnalysisSidebar
            chapterId={chapterId}
            open={showAnalysis}
            onClose={() => setShowAnalysis(false)}
          />
        )}
      </div>
    </div>
  )
}
