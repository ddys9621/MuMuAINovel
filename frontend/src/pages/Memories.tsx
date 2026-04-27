import { useEffect, useState, useCallback } from 'react'
import {
  Brain, Search, Loader2, Trash2, BookOpen, Eye,
  BarChart3, AlertTriangle, Filter, RefreshCw,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { useStore } from '@/store/index'
import { memoryApi } from '@/services/api'

type TabKey = 'memories' | 'foreshadows' | 'stats'

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: 'memories', label: '记忆列表', icon: Brain },
  { key: 'foreshadows', label: '伏笔追踪', icon: Eye },
  { key: 'stats', label: '统计总览', icon: BarChart3 },
]

const MEMORY_TYPES = ['全部', 'hook', 'foreshadow', 'plot_point', 'character_state', 'scene', 'emotion']
const STAT_LABELS: Record<string, string> = {
  total_count: '记忆总数',
  foreshadow_count: '伏笔数量',
  foreshadow_resolved: '已回收伏笔',
  by_type: '按类型统计',
  by_chapter: '按章节统计',
}
const MEMORY_TYPE_LABELS: Record<string, string> = {
  hook: '钩子',
  foreshadow: '伏笔',
  plot_point: '情节点',
  character_state: '角色状态',
  scene: '场景',
  emotion: '情绪',
  unknown: '未知类型',
}

export default function MemoriesPage() {
  const { currentProject, chapters } = useStore()
  const projectId = currentProject?.id
  const [activeTab, setActiveTab] = useState<TabKey>('memories')

  if (!projectId) return <div className="text-center py-12 text-content-secondary text-sm">请先选择项目</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 mb-2">
        <Brain className="w-5 h-5 text-brand" />
        <h1 className="text-lg font-bold text-content">记忆系统</h1>
      </div>

      <div className="flex border-b border-surface-border mb-6">
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors inline-flex items-center gap-1.5',
              activeTab === tab.key
                ? 'border-brand text-brand'
                : 'border-transparent text-content-secondary hover:text-content'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'memories' && <MemoriesTab projectId={projectId} chapters={chapters} />}
      {activeTab === 'foreshadows' && <ForeshadowsTab projectId={projectId} chapters={chapters} />}
      {activeTab === 'stats' && <StatsTab projectId={projectId} />}
    </div>
  )
}

/* ─── Tab 1: 记忆列表 ─── */

function MemoriesTab({ projectId, chapters }: { projectId: string; chapters: Array<{ id: string; title: string; chapter_number: number }> }) {
  const [memories, setMemories] = useState<Array<Record<string, unknown>>>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [typeFilter, setTypeFilter] = useState('全部')
  const [searchQuery, setSearchQuery] = useState('')
  const [searching, setSearching] = useState(false)

  const loadMemories = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = { limit: 100 }
      if (typeFilter !== '全部') params.memory_type = typeFilter
      const res = await memoryApi.getProjectMemories(projectId, params as { memory_type?: string; limit?: number })
      setMemories(res.memories || [])
      setTotal(res.total || 0)
    } catch {
      toast.error('加载记忆失败')
    } finally {
      setLoading(false)
    }
  }, [projectId, typeFilter])

  useEffect(() => { loadMemories() }, [loadMemories])

  const handleSearch = async () => {
    if (!searchQuery.trim()) { loadMemories(); return }
    setSearching(true)
    try {
      const res = await memoryApi.searchMemories(projectId, { query: searchQuery, limit: 50 })
      setMemories(res.memories || [])
      setTotal(res.total || 0)
    } catch {
      toast.error('搜索失败')
    } finally {
      setSearching(false)
    }
  }

  const handleDeleteChapterMemories = async (chapterId: string) => {
    if (!confirm('确定删除该章节的所有记忆？')) return
    try {
      await memoryApi.deleteChapterMemories(projectId, chapterId)
      toast.success('已删除')
      loadMemories()
    } catch {
      toast.error('删除失败')
    }
  }

  const typeColor = (t: string) => {
    const map: Record<string, string> = {
      hook: 'bg-red-100 text-red-700',
      foreshadow: 'bg-purple-100 text-purple-700',
      plot_point: 'bg-blue-100 text-blue-700',
      character_state: 'bg-green-100 text-green-700',
      scene: 'bg-yellow-100 text-yellow-700',
      emotion: 'bg-pink-100 text-pink-700',
    }
    return map[t as string] || 'bg-gray-100 text-gray-700'
  }

  return (
    <div className="space-y-4">
      {/* 搜索与筛选 */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex-1 min-w-[200px] flex gap-2">
          <input
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="语义搜索记忆..."
            className="flex-1 border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors"
          />
          <button onClick={handleSearch} disabled={searching} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-3 py-2 text-sm transition-colors inline-flex items-center gap-1.5 disabled:opacity-50">
            {searching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            搜索
          </button>
        </div>
        <div className="flex items-center gap-1.5">
          <Filter className="w-4 h-4 text-content-secondary" />
          <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)} className="border border-surface-border rounded-btn px-2 py-2 text-sm bg-white focus:border-brand outline-none">
            {MEMORY_TYPES.map(t => <option key={t} value={t}>{t === '全部' ? '全部类型' : t}</option>)}
          </select>
        </div>
        <button onClick={loadMemories} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-3 py-2 text-sm transition-colors inline-flex items-center gap-1.5">
          <RefreshCw className="w-4 h-4" />
          刷新
        </button>
      </div>

      <p className="text-xs text-content-secondary">共 {total} 条记忆</p>

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-content-secondary" /></div>
      ) : memories.length === 0 ? (
        <div className="text-center py-12 text-content-secondary text-sm">暂无记忆数据，请先在章节管理中生成章节并分析</div>
      ) : (
        <div className="space-y-3">
          {memories.map((mem, i) => (
            <div key={(mem.id as string) || i} className="bg-white border border-surface-border rounded-card p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {Boolean(mem.memory_type) && <span className={cn('text-xs rounded px-1.5 py-0.5', typeColor(String(mem.memory_type)))}>{String(mem.memory_type)}</span>}
                    {Boolean(mem.title) && <h3 className="text-sm font-semibold text-content truncate">{String(mem.title)}</h3>}
                    {mem.importance_score != null && <span className="text-xs text-content-secondary">重要度: {String(mem.importance_score)}</span>}
                  </div>
                  {Boolean(mem.content) && <p className="text-xs text-content-secondary mt-1.5 line-clamp-3 whitespace-pre-wrap">{String(mem.content)}</p>}
                  <div className="flex items-center gap-3 mt-2 text-xs text-content-secondary">
                    {mem.story_timeline != null && <span>时间线: 第{String(mem.story_timeline)}章</span>}
                    {Boolean(mem.chapter_id) && (
                      <span>章节: {chapters.find(c => c.id === mem.chapter_id)?.title || String(mem.chapter_id).slice(0, 8)}</span>
                    )}
                  </div>
                </div>
                {Boolean(mem.chapter_id) && (
                  <button
                    onClick={() => handleDeleteChapterMemories(mem.chapter_id as string)}
                    title="删除该章节所有记忆"
                    className="p-1.5 rounded hover:bg-red-50 text-content-secondary hover:text-red-500 transition-colors shrink-0"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ─── Tab 2: 伏笔追踪 ─── */

function ForeshadowsTab({ projectId, chapters }: { projectId: string; chapters: Array<{ id: string; title: string; chapter_number: number }> }) {
  const [foreshadows, setForeshadows] = useState<Array<Record<string, unknown>>>([])
  const [loading, setLoading] = useState(false)
  const [currentChapter, setCurrentChapter] = useState(() => {
    const max = chapters.reduce((m, c) => Math.max(m, c.chapter_number), 0)
    return max || 1
  })

  const loadForeshadows = useCallback(async () => {
    setLoading(true)
    try {
      const res = await memoryApi.getForeshadows(projectId, currentChapter)
      setForeshadows(res.foreshadows || [])
    } catch {
      toast.error('加载伏笔失败')
    } finally {
      setLoading(false)
    }
  }, [projectId, currentChapter])

  useEffect(() => { loadForeshadows() }, [loadForeshadows])

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <label className="text-sm text-content-secondary">当前章节:</label>
        <input
          type="number"
          min={1}
          value={currentChapter}
          onChange={e => setCurrentChapter(Number(e.target.value))}
          className="w-24 border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
        />
        <button onClick={loadForeshadows} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-3 py-2 text-sm transition-colors inline-flex items-center gap-1.5">
          <RefreshCw className="w-4 h-4" />
          查询
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-content-secondary" /></div>
      ) : foreshadows.length === 0 ? (
        <div className="text-center py-12 text-content-secondary text-sm">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-content-tertiary" />
          截至第 {currentChapter} 章，暂无未解决伏笔
        </div>
      ) : (
        <div className="space-y-3">
          {foreshadows.map((f, i) => (
            <div key={i} className="bg-white border border-purple-200 rounded-card p-4">
              <div className="flex items-center gap-2 mb-1">
                <Eye className="w-4 h-4 text-purple-500" />
                {Boolean(f.title) && <h3 className="text-sm font-semibold text-content">{String(f.title)}</h3>}
              </div>
              {Boolean(f.content) && <p className="text-xs text-content-secondary mt-1 whitespace-pre-wrap">{String(f.content)}</p>}
              <div className="flex items-center gap-3 mt-2 text-xs text-content-secondary">
                {f.story_timeline != null && <span>埋设于: 第{String(f.story_timeline)}章</span>}
                {f.importance_score != null && <span>重要度: {String(f.importance_score)}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ─── Tab 3: 统计总览 ─── */

function StatsTab({ projectId }: { projectId: string }) {
  const [stats, setStats] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setLoading(true)
    memoryApi.getStats(projectId)
      .then(res => setStats(res.stats || {}))
      .catch(() => toast.error('加载统计失败'))
      .finally(() => setLoading(false))
  }, [projectId])

  if (loading) return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-content-secondary" /></div>
  if (!stats) return <div className="text-center py-12 text-content-secondary text-sm">暂无统计数据</div>

  const entries = Object.entries(stats)
  const scalarEntries = getScalarEntries(stats)
  const groupedEntries = getGroupedEntries(stats)

  if (typeof stats.error === 'string') {
    return <div className="text-center py-12 text-content-secondary text-sm">{stats.error}</div>
  }

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold text-content">记忆统计</h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {scalarEntries.map(([key, value]) => (
          <div key={key} className="border border-surface-border rounded-card p-5 text-center bg-white">
            <div className="text-3xl font-bold text-brand">{value}</div>
            <div className="text-sm mt-1 text-content-secondary">{STAT_LABELS[key] ?? key}</div>
          </div>
        ))}
      </div>
      {groupedEntries.length > 0 && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {groupedEntries.map(([key, value]) => {
            const items = formatCountMap(key, value)
            return (
              <div key={key} className="border border-surface-border rounded-card p-5 bg-white">
                <div className="flex items-center justify-between gap-3 mb-3">
                  <h3 className="text-sm font-semibold text-content">{STAT_LABELS[key] ?? key}</h3>
                  <span className="text-xs text-content-secondary">{items.length} 项</span>
                </div>
                {items.length === 0 ? (
                  <div className="text-sm text-content-secondary">暂无数据</div>
                ) : (
                  <div className="space-y-2">
                    {items.map(([label, count]) => (
                      <div key={label} className="flex items-center justify-between gap-4 text-sm">
                        <span className="text-content-secondary truncate">{label}</span>
                        <span className="font-semibold text-content shrink-0">{count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
      {entries.length === 0 && (
        <div className="text-center py-8 text-content-secondary text-sm">
          <BookOpen className="w-8 h-8 mx-auto mb-2 text-content-tertiary" />
          暂无统计数据，请先分析章节以生成记忆
        </div>
      )}
    </div>
  )
}

function isCountMap(value: unknown): value is Record<string, number> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function getScalarEntries(stats: Record<string, unknown>) {
  return Object.entries(stats).filter((entry): entry is [string, number] => typeof entry[1] === 'number')
}

function getGroupedEntries(stats: Record<string, unknown>) {
  return Object.entries(stats).filter((entry): entry is [string, Record<string, number>] => isCountMap(entry[1]))
}

function formatCountMap(section: string, value: Record<string, number>) {
  const entries = Object.entries(value)

  if (section === 'by_chapter') {
    return entries.sort((a, b) => Number(a[0]) - Number(b[0])).map(([chapter, count]) => [`第 ${chapter} 章`, count] as const)
  }

  return entries
    .sort((a, b) => b[1] - a[1])
    .map(([label, count]) => [MEMORY_TYPE_LABELS[label] ?? label, count] as const)
}
