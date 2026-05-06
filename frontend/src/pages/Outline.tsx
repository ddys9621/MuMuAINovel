import { useEffect, useState } from 'react'
import { Plus, Pencil, Trash2, FileText, Loader2, Sparkles, LayoutGrid, GitBranch, BookOpen, BarChart3, Check, ChevronDown, ChevronUp, Link2, Eye } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { useStore } from '@/store/index'
import { useOutlineSync } from '@/store/hooks'
import { usePlotCardSync, usePlotLineSync, useChapterOutlineSync } from '@/store/plotHooks'
import { wizardStreamApi, outlineApi, chapterOutlineLinkApi, plotLineApi } from '@/services/api'
import { MCPSelector } from '@/components/MCPSelector'
import { Modal as UiModal, type ModalSize } from '@/components/ui/Modal'
import type {
  Outline, OutlineCreate, OutlineUpdate,
  PlotCard, PlotCardCreate, PlotCardUpdate,
  PlotLine, PlotLineCreate, PlotLineUpdate,
  PlotLineProgress, TimelineData, TimelineBeat,
  PlotCardGenerateRequest, PlotLineGenerateRequest,
  ChapterOutline, ChapterOutlineCreate, ChapterOutlineUpdate,
  ChapterOutlineBatchCreateRequest, ChapterOutlineGenerateRequest,
} from '@/types'

type TabKey = 'outlines' | 'plotCards' | 'plotLines' | 'chapterOutlines' | 'overview'

const TABS: { key: TabKey; label: string; icon: React.ElementType }[] = [
  { key: 'outlines', label: '故事大纲', icon: FileText },
  { key: 'plotCards', label: '剧情卡片', icon: LayoutGrid },
  { key: 'plotLines', label: '剧情线', icon: GitBranch },
  { key: 'chapterOutlines', label: '章纲', icon: BookOpen },
  { key: 'overview', label: '关联总览', icon: BarChart3 },
]

const PLOT_LINE_TYPE_LABELS: Record<string, string> = {
  main: '主线',
  sub: '支线',
  character: '角色线',
  foreshadow: '伏笔线',
  other: '其他',
}

const PLOT_LINE_TYPE_ALIASES: Record<string, string> = {
  main: 'main',
  '主线': 'main',
  sub: 'sub',
  '支线': 'sub',
  character: 'character',
  '角色线': 'character',
  foreshadow: 'foreshadow',
  '伏笔线': 'foreshadow',
  other: 'other',
  '其他': 'other',
}

const PLOT_LINE_TYPE_COLORS: Record<string, string> = {
  main: 'bg-blue-100 text-blue-700',
  sub: 'bg-amber-100 text-amber-700',
  character: 'bg-purple-100 text-purple-700',
  foreshadow: 'bg-orange-100 text-orange-700',
  other: 'bg-gray-100 text-gray-700',
}

const normalizePlotLineType = (type?: string | null) => {
  const value = type?.trim()
  if (!value) return 'main'
  return PLOT_LINE_TYPE_ALIASES[value] || value
}

const getPlotLineTypeLabel = (type?: string | null) => {
  const normalized = normalizePlotLineType(type)
  return PLOT_LINE_TYPE_LABELS[normalized] || normalized
}

const getPlotLineTypeColor = (type?: string | null) => {
  const normalized = normalizePlotLineType(type)
  return PLOT_LINE_TYPE_COLORS[normalized] || PLOT_LINE_TYPE_COLORS.other
}


export default function OutlinePage() {
  const { currentProject, outlines } = useStore()
  const projectId = currentProject?.id
  const [activeTab, setActiveTab] = useState<TabKey>('outlines')
  const [loading, setLoading] = useState(false)

  // hooks
  const { refreshOutlines, createOutline, updateOutline, deleteOutline, activateOutline } = useOutlineSync()
  const { plotCards, refreshPlotCards, createPlotCard, updatePlotCard, deletePlotCard, generatePlotCards } = usePlotCardSync()
  const { plotLines, refreshPlotLines, createPlotLine, updatePlotLine: updatePlotLineData, deletePlotLine, generatePlotLines } = usePlotLineSync()
  const { chapterOutlines, refreshChapterOutlines, createChapterOutline, updateChapterOutline: updateChapterOutlineData, deleteChapterOutline, batchCreateChapterOutlines, generateChapterOutlines } = useChapterOutlineSync()

  // 初始化加载
  useEffect(() => {
    if (!projectId) return
    setLoading(true)
    Promise.all([
      refreshOutlines(),
      refreshPlotCards(projectId),
      refreshPlotLines(projectId),
      refreshChapterOutlines(projectId),
    ]).finally(() => setLoading(false))
  }, [projectId, refreshChapterOutlines, refreshOutlines, refreshPlotCards, refreshPlotLines])

  // ==================== Tab 容器 ====================
  return (
    <div className="space-y-6">
      {/* Tab 栏 */}
      <div className="flex border-b border-surface-border mb-6">
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors inline-flex items-center gap-1.5",
              activeTab === tab.key
                ? "border-brand text-brand"
                : "border-transparent text-content-secondary hover:text-content"
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-content-secondary" /></div>
      ) : (
        <>
          {activeTab === 'outlines' && <OutlinesView outlines={outlines} projectId={projectId} createOutline={createOutline} updateOutline={updateOutline} deleteOutline={deleteOutline} activateOutline={activateOutline} refreshOutlines={refreshOutlines} />}
          {activeTab === 'plotCards' && <PlotCardsView plotCards={plotCards} projectId={projectId} outlines={outlines} createPlotCard={createPlotCard} updatePlotCard={updatePlotCard} deletePlotCard={deletePlotCard} generatePlotCards={generatePlotCards} />}
          {activeTab === 'plotLines' && <PlotLinesView plotLines={plotLines} plotCards={plotCards} projectId={projectId} outlines={outlines} createPlotLine={createPlotLine} updatePlotLine={updatePlotLineData} deletePlotLine={deletePlotLine} generatePlotLines={generatePlotLines} />}
          {activeTab === 'chapterOutlines' && <ChapterOutlinesView chapterOutlines={chapterOutlines} projectId={projectId} createChapterOutline={createChapterOutline} updateChapterOutline={updateChapterOutlineData} deleteChapterOutline={deleteChapterOutline} batchCreateChapterOutlines={batchCreateChapterOutlines} generateChapterOutlines={generateChapterOutlines} plotLines={plotLines} />}
          {activeTab === 'overview' && <OverviewPanel plotCards={plotCards} plotLines={plotLines} chapterOutlines={chapterOutlines} />}
        </>
      )}
    </div>
  )
}

// ==================== 通用弹窗壳（薄壳，转发到全局 Modal） ====================
function Modal({ title, onClose, children, size = 'xl' }: { title: string; onClose: () => void; children: React.ReactNode; size?: ModalSize }) {
  return (
    <UiModal title={title} onClose={onClose} size={size}>
      {children}
    </UiModal>
  )
}

// ==================== Tab 1: 故事大纲 ====================
function OutlinesView({ outlines, projectId, createOutline, updateOutline, deleteOutline, activateOutline, refreshOutlines }: {
  outlines: Outline[]
  projectId?: string
  createOutline: (data: OutlineCreate) => Promise<Outline>
  updateOutline: (id: string, data: OutlineUpdate) => Promise<Outline>
  deleteOutline: (id: string) => Promise<void>
  activateOutline: (id: string) => Promise<Outline>
  refreshOutlines: () => Promise<Outline[]>
}) {
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<Outline | null>(null)
  const [form, setForm] = useState({ title: '', premise: '', golden_finger: '', selling_points: '', power_system: '', main_tropes: '', ultimate_goal: '', opening_hook: '' })
  const [generating, setGenerating] = useState(false)
  const [showGenModal, setShowGenModal] = useState(false)
  const [genForm, setGenForm] = useState({ narrative_perspective: '第三人称', chapter_count: 30, target_words: 100000, requirements: '' })
  const [genEnableMcp, setGenEnableMcp] = useState(false)
  const [genPlugins, setGenPlugins] = useState<string[]>([])
  const [viewingOutline, setViewingOutline] = useState<Outline | null>(null)
  const [expandedOutlineId, setExpandedOutlineId] = useState<string | null>(null)
  const [linkedPlotLines, setLinkedPlotLines] = useState<Record<string, Array<{ id: string; title: string; description?: string; line_type?: string }>>>({})
  const [loadingLinks, setLoadingLinks] = useState<string | null>(null)

  const togglePlotLines = async (outlineId: string) => {
    if (expandedOutlineId === outlineId) { setExpandedOutlineId(null); return }
    setExpandedOutlineId(outlineId)
    if (linkedPlotLines[outlineId]) return
    setLoadingLinks(outlineId)
    try {
      const lines = await outlineApi.getPlotLines(outlineId)
      setLinkedPlotLines(prev => ({ ...prev, [outlineId]: lines }))
    } catch { /* ignore failed relation preview */ }
    finally { setLoadingLinks(null) }
  }

  const openCreate = () => { setEditing(null); setForm({ title: '', premise: '', golden_finger: '', selling_points: '', power_system: '', main_tropes: '', ultimate_goal: '', opening_hook: '' }); setShowModal(true) }
  const openEdit = (o: Outline) => {
    const f = { title: o.title, premise: o.content, golden_finger: '', selling_points: '', power_system: '', main_tropes: '', ultimate_goal: '', opening_hook: '' };
    try {
      const parsed = JSON.parse(o.content);
      if (typeof parsed === 'object') {
        f.premise = parsed.premise || '';
        f.golden_finger = parsed.golden_finger || '';
        f.selling_points = Array.isArray(parsed.selling_points) ? parsed.selling_points.join('、') : (parsed.selling_points || '');
        f.power_system = parsed.power_system || '';
        f.main_tropes = Array.isArray(parsed.main_tropes) ? parsed.main_tropes.join('、') : (parsed.main_tropes || '');
        f.ultimate_goal = parsed.ultimate_goal || '';
        f.opening_hook = parsed.opening_hook || '';
      }
    } catch { /* keep raw outline content when it is not JSON */ }
    setEditing(o); setForm(f); setShowModal(true);
  }

  const handleAIGenerate = async () => {
    if (!projectId) return
    setGenerating(true)
    setShowGenModal(false)
    try {
      await wizardStreamApi.generateCompleteOutlineStream(
        {
          project_id: projectId,
          narrative_perspective: genForm.narrative_perspective,
          chapter_count: genForm.chapter_count,
          target_words: genForm.target_words,
          requirements: genForm.requirements.trim() || undefined,
          enable_mcp: genEnableMcp,
          selected_plugins: genPlugins,
        },
        {
          onProgress: (msg) => { toast.info(msg, { id: 'outline-gen' }) },
          onResult: () => { toast.success('故事大纲生成完成', { id: 'outline-gen' }); refreshOutlines() },
          onError: (err) => { toast.error(`生成失败: ${err}`, { id: 'outline-gen' }) },
        }
      )
    } catch { toast.error('AI 生成故事大纲失败') } finally { setGenerating(false) }
  }

  const handleSubmit = async () => {
    if (!projectId) return
    if (!form.title.trim()) { toast.error('请填写标题'); return }
    const contentJson = JSON.stringify({
      premise: form.premise,
      golden_finger: form.golden_finger,
      selling_points: form.selling_points.split(/[、,，]/).map(s => s.trim()).filter(Boolean),
      power_system: form.power_system,
      main_tropes: form.main_tropes.split(/[、,，]/).map(s => s.trim()).filter(Boolean),
      ultimate_goal: form.ultimate_goal,
      opening_hook: form.opening_hook,
    });
    try {
      if (editing) {
        await updateOutline(editing.id, { title: form.title, content: contentJson, version: editing.version })
      } else {
        await createOutline({ project_id: projectId, title: form.title, content: contentJson, order_index: outlines.length })
        toast.success('大纲已创建')
      }
      setShowModal(false)
    } catch { /* hook 已 toast */ }
  }

  const handleDelete = async (o: Outline) => {
    if (!confirm(`确定删除「${o.title}」？`)) return
    try { await deleteOutline(o.id); toast.success('大纲已删除') } catch { /* hook 已 toast */ }
  }

  const handleActivate = async (o: Outline) => {
    try { await activateOutline(o.id); toast.success('已设为活跃版本'); refreshOutlines() } catch { /* hook 已 toast */ }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-content">故事大纲</h2>
        <div className="flex gap-2">
          <button onClick={() => setShowGenModal(true)} disabled={generating} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-3 py-2 text-sm transition-colors inline-flex items-center gap-1.5 disabled:opacity-50">
            {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            AI 生成
          </button>
          <button onClick={openCreate} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5">
            <Plus className="w-4 h-4" />新建大纲
          </button>
        </div>
      </div>

      {outlines.length === 0 ? (
        <div className="text-center py-12 text-content-secondary text-sm">暂无大纲，点击上方按钮创建</div>
      ) : (
        <div className="space-y-3">
          {outlines.map(o => (
            <div key={o.id} className="bg-white border border-surface-border rounded-card p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-content-secondary shrink-0" />
                    <h3 className="text-sm font-semibold text-content truncate">{o.title}</h3>
                    {o.is_active && <span className="text-xs bg-green-100 text-green-700 rounded px-1.5 py-0.5">活跃</span>}
                    {o.version != null && <span className="text-xs text-content-secondary">v{o.version}</span>}
                  </div>
                  {o.content && <p className="text-xs text-content-secondary mt-1.5 line-clamp-3 whitespace-pre-wrap">{(() => {
                    try { const parsed = JSON.parse(o.content); return typeof parsed === 'object' ? (parsed.premise || parsed.content || JSON.stringify(parsed, null, 2)) : o.content; } catch { return o.content; }
                  })()}</p>}
                  <button
                    onClick={() => togglePlotLines(o.id)}
                    className="inline-flex items-center gap-1 mt-2 text-xs text-brand hover:text-brand-600 transition-colors"
                  >
                    <GitBranch className="w-3 h-3" />
                    关联剧情线
                    {expandedOutlineId === o.id ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </button>
                </div>
                <div className="flex gap-1 shrink-0">
                  {!o.is_active && (
                    <button onClick={() => handleActivate(o)} className="text-xs border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-2 py-1 transition-colors inline-flex items-center gap-1">
                      <Check className="w-3 h-3" />激活
                    </button>
                  )}
                  <button onClick={() => setViewingOutline(o)} className="p-1.5 rounded hover:bg-surface-hover text-content-secondary transition-colors" title="查看全文"><Eye className="w-3.5 h-3.5" /></button>
                  <button onClick={() => openEdit(o)} className="p-1.5 rounded hover:bg-surface-hover text-content-secondary transition-colors" title="编辑"><Pencil className="w-3.5 h-3.5" /></button>
                  <button onClick={() => handleDelete(o)} className="p-1.5 rounded hover:bg-red-50 text-content-secondary hover:text-red-500 transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
              {expandedOutlineId === o.id && (
                <div className="mt-3 pt-3 border-t border-surface-border">
                  {loadingLinks === o.id ? (
                    <div className="flex items-center gap-2 text-xs text-content-secondary"><Loader2 className="w-3 h-3 animate-spin" />加载中...</div>
                  ) : (linkedPlotLines[o.id] || []).length === 0 ? (
                    <p className="text-xs text-content-tertiary">暂无关联剧情线</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {(linkedPlotLines[o.id] || []).map(pl => (
                        <span key={pl.id} className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-700 rounded px-2 py-1">
                          <GitBranch className="w-3 h-3" />
                          {pl.title}
                          {pl.line_type && <span className="text-blue-400">({getPlotLineTypeLabel(pl.line_type)})</span>}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showGenModal && (
        <Modal title="AI 生成故事大纲" onClose={() => setShowGenModal(false)}>
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-sm text-content-secondary mb-1">叙事视角</label>
                <select value={genForm.narrative_perspective} onChange={e => setGenForm(f => ({ ...f, narrative_perspective: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none bg-white">
                  <option value="第一人称">第一人称</option>
                  <option value="第三人称">第三人称</option>
                  <option value="全知视角">全知视角</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-content-secondary mb-1">章节数</label>
                <input type="number" value={genForm.chapter_count} onChange={e => setGenForm(f => ({ ...f, chapter_count: Number(e.target.value) }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none" />
              </div>
              <div>
                <label className="block text-sm text-content-secondary mb-1">目标字数</label>
                <input type="number" value={genForm.target_words} onChange={e => setGenForm(f => ({ ...f, target_words: Number(e.target.value) }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none" />
              </div>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">额外要求（可选）</label>
              <textarea value={genForm.requirements} onChange={e => setGenForm(f => ({ ...f, requirements: e.target.value }))} placeholder="对大纲的特殊要求..." rows={2} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none resize-none" />
            </div>
            <MCPSelector value={{ enable: genEnableMcp, selected: genPlugins }} onChange={({ enable, selected }) => { setGenEnableMcp(enable); setGenPlugins(selected) }} />
          </div>
          <div className="sticky bottom-0 -mx-6 -mb-5 mt-4 flex justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 backdrop-blur-sm">
            <button onClick={() => setShowGenModal(false)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm">取消</button>
            <button onClick={handleAIGenerate} disabled={generating} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5 disabled:opacity-50">
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              开始生成
            </button>
          </div>
        </Modal>
      )}

      {showModal && (
        <Modal title={editing ? '编辑大纲' : '新建大纲'} onClose={() => setShowModal(false)} size="xl">
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-content-secondary mb-1">标题</label>
              <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">故事梗概 (premise)</label>
              <textarea value={form.premise} onChange={e => setForm(f => ({ ...f, premise: e.target.value }))} rows={4} placeholder="5-8句话概括整个故事..." className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none resize-none" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">金手指设定 (golden_finger)</label>
              <input value={form.golden_finger} onChange={e => setForm(f => ({ ...f, golden_finger: e.target.value }))} placeholder="主角的核心优势" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-content-secondary mb-1">核心卖点 (selling_points)</label>
                <input value={form.selling_points} onChange={e => setForm(f => ({ ...f, selling_points: e.target.value }))} placeholder="用顿号分隔，如：废材逆袭、打脸" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none" />
              </div>
              <div>
                <label className="block text-sm text-content-secondary mb-1">主要套路 (main_tropes)</label>
                <input value={form.main_tropes} onChange={e => setForm(f => ({ ...f, main_tropes: e.target.value }))} placeholder="用顿号分隔，如：宗门大比、夺宝" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none" />
              </div>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">升级路线 (power_system)</label>
              <input value={form.power_system} onChange={e => setForm(f => ({ ...f, power_system: e.target.value }))} placeholder="用→连接各阶段" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">终极目标 (ultimate_goal)</label>
              <input value={form.ultimate_goal} onChange={e => setForm(f => ({ ...f, ultimate_goal: e.target.value }))} placeholder="主角最终会达成什么" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">开篇钩子 (opening_hook)</label>
              <input value={form.opening_hook} onChange={e => setForm(f => ({ ...f, opening_hook: e.target.value }))} placeholder="第一章如何吸引读者" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none" />
            </div>
          </div>
          <div className="sticky bottom-0 -mx-6 -mb-5 mt-4 flex justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 backdrop-blur-sm">
            <button onClick={() => setShowModal(false)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm">取消</button>
            <button onClick={handleSubmit} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors">确定</button>
          </div>
        </Modal>
      )}

      {viewingOutline && (() => {
        let parsed: Record<string, unknown> | null = null;
        try { const p = JSON.parse(viewingOutline.content); if (typeof p === 'object' && p !== null) parsed = p as Record<string, unknown>; } catch { /* render raw outline content */ }
        const labels: Array<[string, string]> = [
          ['premise', '故事梗概'],
          ['golden_finger', '金手指设定'],
          ['selling_points', '核心卖点'],
          ['power_system', '升级路线'],
          ['main_tropes', '主要套路'],
          ['ultimate_goal', '终极目标'],
          ['opening_hook', '开篇钩子'],
        ];
        const renderValue = (v: unknown) => {
          if (Array.isArray(v)) return v.join('、');
          if (typeof v === 'string') return v;
          return JSON.stringify(v);
        };
        return (
          <Modal title={`查看大纲：${viewingOutline.title}`} onClose={() => setViewingOutline(null)} size="2xl">
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs text-content-secondary">
                {viewingOutline.is_active && <span className="bg-green-100 text-green-700 rounded px-1.5 py-0.5">活跃</span>}
                {viewingOutline.version != null && <span>版本 v{viewingOutline.version}</span>}
                <span>创建于 {new Date(viewingOutline.created_at).toLocaleString()}</span>
              </div>
              <div className="space-y-3">
                {parsed ? labels.map(([key, label]) => {
                  const val = parsed![key];
                  if (!val) return null;
                  return (
                    <div key={key} className="bg-surface-hover/50 border border-surface-border rounded-btn p-3">
                      <div className="text-xs font-semibold text-brand mb-1">{label}</div>
                      <div className="text-sm whitespace-pre-wrap leading-relaxed">{renderValue(val)}</div>
                    </div>
                  );
                }) : (
                  <div className="bg-surface-hover/50 border border-surface-border rounded-btn p-4 text-sm whitespace-pre-wrap leading-relaxed">
                    {viewingOutline.content}
                  </div>
                )}
              </div>
            </div>
            <div className="sticky bottom-0 -mx-6 -mb-5 mt-4 flex justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 backdrop-blur-sm">
              <button onClick={() => { setViewingOutline(null); openEdit(viewingOutline); }} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm inline-flex items-center gap-1.5">
                <Pencil className="w-3.5 h-3.5" />编辑
              </button>
              <button onClick={() => setViewingOutline(null)} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors">关闭</button>
            </div>
          </Modal>
        );
      })()}
    </div>
  )
}
// ==================== Tab 2: 剧情卡片 ====================
function PlotCardsView({ plotCards, projectId, outlines, createPlotCard, updatePlotCard, deletePlotCard, generatePlotCards }: {
  plotCards: PlotCard[]
  projectId?: string
  outlines: Outline[]
  createPlotCard: (data: PlotCardCreate) => Promise<PlotCard>
  updatePlotCard: (id: string, data: PlotCardUpdate) => Promise<PlotCard>
  deletePlotCard: (id: string) => Promise<void>
  generatePlotCards: (data: PlotCardGenerateRequest) => Promise<PlotCard[]>
}) {
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<PlotCard | null>(null)
  const [form, setForm] = useState({ title: '', content: '', card_type: '起因', order_index: 0 })
  const [generating, setGenerating] = useState(false)
  const [showGenModal, setShowGenModal] = useState(false)
  const [genForm, setGenForm] = useState({ card_type: '起因', count: 5, prompt: '', extend_from_card_id: '' })
  const [genEnableMcp, setGenEnableMcp] = useState(false)
  const [genPlugins, setGenPlugins] = useState<string[]>([])

  const CARD_TYPES = ['起因', '经过', '高潮', '结局', '伏笔', '转折', '其他']

  const openCreate = () => { setEditing(null); setForm({ title: '', content: '', card_type: '起因', order_index: plotCards.length }); setShowModal(true) }
  const openEdit = (c: PlotCard) => { setEditing(c); setForm({ title: c.title, content: c.content || '', card_type: c.card_type, order_index: c.order_index ?? 0 }); setShowModal(true) }

  const handleSubmit = async () => {
    if (!projectId) return
    if (!form.title.trim()) { toast.error('请填写标题'); return }
    try {
      if (editing) {
        await updatePlotCard(editing.id, { title: form.title, content: form.content, card_type: form.card_type, order_index: form.order_index })
      } else {
        await createPlotCard({ project_id: projectId, title: form.title, content: form.content, card_type: form.card_type, order_index: form.order_index })
      }
      setShowModal(false)
    } catch { /* hook 已 toast */ }
  }

  const handleGenerate = async () => {
    if (!projectId) return
    const activeOutline = outlines.find(o => o.is_active) || outlines[0]
    if (!activeOutline) { toast.error('请先创建故事大纲'); return }
    setGenerating(true)
    setShowGenModal(false)
    try {
      await generatePlotCards({
        project_id: projectId,
        outline_id: activeOutline.id,
        card_type: genForm.card_type,
        count: genForm.count,
        extend_from_card_id: genForm.extend_from_card_id || undefined,
        prompt: genForm.prompt.trim() || undefined,
        enable_mcp: genEnableMcp,
        selected_plugins: genPlugins,
      })
    } catch { /* hook 已 toast */ } finally { setGenerating(false) }
  }

  const handleDelete = async (c: PlotCard) => {
    if (!confirm(`确定删除「${c.title}」？`)) return
    try { await deletePlotCard(c.id) } catch { /* hook 已 toast */ }
  }

  const typeColor = (t: string) => {
    const map: Record<string, string> = { '起因': 'bg-blue-100 text-blue-700', '经过': 'bg-yellow-100 text-yellow-700', '高潮': 'bg-red-100 text-red-700', '结局': 'bg-green-100 text-green-700', '伏笔': 'bg-purple-100 text-purple-700', '转折': 'bg-orange-100 text-orange-700' }
    return map[t] || 'bg-gray-100 text-gray-700'
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-content">剧情卡片</h2>
        <div className="flex gap-2">
          <button onClick={() => setShowGenModal(true)} disabled={generating} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-3 py-2 text-sm transition-colors inline-flex items-center gap-1.5 disabled:opacity-50">
            {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            AI 生成
          </button>
          <button onClick={openCreate} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5">
            <Plus className="w-4 h-4" />新建卡片
          </button>
        </div>
      </div>

      {plotCards.length === 0 ? (
        <div className="text-center py-12 text-content-secondary text-sm">暂无剧情卡片</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {[...plotCards].sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0)).map(c => (
            <div key={c.id} className="bg-white border border-surface-border rounded-card p-4 flex flex-col gap-2">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-content truncate flex-1">{c.title}</h3>
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => openEdit(c)} className="p-1 rounded hover:bg-surface-hover text-content-secondary transition-colors"><Pencil className="w-3.5 h-3.5" /></button>
                  <button onClick={() => handleDelete(c)} className="p-1 rounded hover:bg-red-50 text-content-secondary hover:text-red-500 transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={cn("text-xs rounded px-1.5 py-0.5", typeColor(c.card_type))}>{c.card_type}</span>
                {c.order_index != null && <span className="text-xs text-content-secondary">#{c.order_index + 1}</span>}
              </div>
              {c.content && <p className="text-xs text-content-secondary line-clamp-3">{c.content}</p>}
            </div>
          ))}
        </div>
      )}

      {showGenModal && (
        <Modal title="AI 生成剧情卡片" onClose={() => setShowGenModal(false)}>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-content-secondary mb-1">卡片类型</label>
                <select value={genForm.card_type} onChange={e => setGenForm(f => ({ ...f, card_type: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none bg-white">
                  {CARD_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm text-content-secondary mb-1">生成数量</label>
                <input type="number" min={1} max={20} value={genForm.count} onChange={e => setGenForm(f => ({ ...f, count: Number(e.target.value) }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none" />
              </div>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">从已有卡片延伸（可选）</label>
              <select value={genForm.extend_from_card_id} onChange={e => setGenForm(f => ({ ...f, extend_from_card_id: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none bg-white">
                <option value="">不指定</option>
                {plotCards.map(c => <option key={c.id} value={c.id}>{c.title} [{c.card_type}]</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">提示词（可选）</label>
              <textarea value={genForm.prompt} onChange={e => setGenForm(f => ({ ...f, prompt: e.target.value }))} placeholder="对剧情卡片的特殊要求..." rows={2} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none resize-none" />
            </div>
            <MCPSelector value={{ enable: genEnableMcp, selected: genPlugins }} onChange={({ enable, selected }) => { setGenEnableMcp(enable); setGenPlugins(selected) }} />
          </div>
          <div className="sticky bottom-0 -mx-6 -mb-5 mt-4 flex justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 backdrop-blur-sm">
            <button onClick={() => setShowGenModal(false)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm">取消</button>
            <button onClick={handleGenerate} disabled={generating} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5 disabled:opacity-50">
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              开始生成
            </button>
          </div>
        </Modal>
      )}

      {showModal && (
        <Modal title={editing ? '编辑剧情卡片' : '新建剧情卡片'} onClose={() => setShowModal(false)}>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-content-secondary mb-1">标题</label>
              <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">类型</label>
              <select value={form.card_type} onChange={e => setForm(f => ({ ...f, card_type: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors bg-white">
                {CARD_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">排序号</label>
              <input type="number" value={form.order_index} onChange={e => setForm(f => ({ ...f, order_index: Number(e.target.value) }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">内容</label>
              <textarea value={form.content} onChange={e => setForm(f => ({ ...f, content: e.target.value }))} rows={5} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors resize-none" />
            </div>
          </div>
          <div className="sticky bottom-0 -mx-6 -mb-5 mt-4 flex justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 backdrop-blur-sm">
            <button onClick={() => setShowModal(false)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm">取消</button>
            <button onClick={handleSubmit} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors">确定</button>
          </div>
        </Modal>
      )}
    </div>
  )
}
// ==================== Tab 3: 剧情线 ====================
type EditableBeat = {
  key: string
  title: string
  description: string
  weight: number
}

function PlotLinesView({ plotLines, projectId, outlines, plotCards, createPlotLine, updatePlotLine, deletePlotLine, generatePlotLines }: {
  plotLines: PlotLine[]
  projectId?: string
  outlines: Outline[]
  plotCards: PlotCard[]
  createPlotLine: (data: PlotLineCreate) => Promise<PlotLine>
  updatePlotLine: (id: string, data: PlotLineUpdate) => Promise<PlotLine>
  deletePlotLine: (id: string) => Promise<void>
  generatePlotLines: (data: PlotLineGenerateRequest) => Promise<PlotLine[]>
}) {
  const defaultLineType = normalizePlotLineType(plotLines[0]?.line_type)
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<PlotLine | null>(null)
  const [viewing, setViewing] = useState<PlotLine | null>(null)
  const [viewingProgress, setViewingProgress] = useState<PlotLineProgress | null>(null)
  const [loadingProgress, setLoadingProgress] = useState(false)
  const [form, setForm] = useState({ title: '', description: '', line_type: defaultLineType, estimated_chapters: 0, beats: [] as EditableBeat[] })
  const [generating, setGenerating] = useState(false)
  const [showGenModal, setShowGenModal] = useState(false)
  const [genForm, setGenForm] = useState({ line_type: defaultLineType, count: 3, prompt: '', based_on_lines: [] as string[], based_on_cards: [] as string[] })
  const [genEnableMcp, setGenEnableMcp] = useState(false)
  const [genPlugins, setGenPlugins] = useState<string[]>([])

  const presetLineTypes = ['main', 'sub', 'character', 'foreshadow', 'other']
  const lineTypes = Array.from(new Set([
    ...presetLineTypes,
    ...plotLines.map(line => normalizePlotLineType(line.line_type)),
    normalizePlotLineType(form.line_type),
    normalizePlotLineType(genForm.line_type),
  ].filter(Boolean)))


  const toEditableBeats = (line: PlotLine | null): EditableBeat[] => {
    const beats = Array.isArray(line?.timeline_data?.beats) ? line.timeline_data.beats : []
    return beats
      .slice()
      .sort((a: TimelineBeat, b: TimelineBeat) => a.index - b.index)
      .map((beat: TimelineBeat, index: number) => ({
        key: beat.key || `beat_${index + 1}`,
        title: beat.title || '',
        description: beat.description || '',
        weight: Number.isFinite(Number(beat.weight)) ? Number(beat.weight) : 0,
      }))
  }

  const buildTimelineData = (beats: EditableBeat[]): TimelineData | undefined => {
    const cleaned = beats
      .map((beat, index) => ({
        index: index + 1,
        key: beat.key.trim() || `beat_${index + 1}`,
        title: beat.title.trim(),
        description: beat.description.trim() || undefined,
        weight: Number(beat.weight),
      }))
      .filter(beat => beat.title)

    return cleaned.length > 0 ? { beats: cleaned } : undefined
  }

  const totalWeight = form.beats.reduce((sum, beat) => sum + (Number(beat.weight) || 0), 0)
  const weightIsValid = form.beats.length === 0 || Math.abs(totalWeight - 1) < 0.01

  const rebalanceBeats = (beats: EditableBeat[]) => {
    if (beats.length === 0) return []
    const evenWeight = Number((1 / beats.length).toFixed(2))
    const next = beats.map((beat, index) => ({
      ...beat,
      weight: index === beats.length - 1
        ? Number((1 - evenWeight * (beats.length - 1)).toFixed(2))
        : evenWeight,
    }))
    return next
  }

  const openCreate = () => {
    setEditing(null)
    setForm({ title: '', description: '', line_type: defaultLineType, estimated_chapters: 0, beats: [] })
    setShowModal(true)
  }

  const openEdit = (line: PlotLine) => {
    setEditing(line)
    setForm({
      title: line.title,
      description: line.description || '',
      line_type: normalizePlotLineType(line.line_type),
      estimated_chapters: line.estimated_chapters ?? 0,
      beats: toEditableBeats(line),
    })
    setShowModal(true)
  }

  const openView = async (line: PlotLine) => {
    setViewing(line)
    setViewingProgress(null)
    setLoadingProgress(true)
    try {
      const progress = await plotLineApi.getPlotLineProgress(line.id)
      setViewingProgress(progress)
    } catch (error) {
      console.error('加载剧情线进度失败:', error)
      toast.error('加载剧情线详情失败')
    } finally {
      setLoadingProgress(false)
    }
  }

  const handleBeatChange = (index: number, field: keyof EditableBeat, value: string | number) => {
    setForm(prev => ({
      ...prev,
      beats: prev.beats.map((beat, beatIndex) => beatIndex === index ? { ...beat, [field]: field === 'weight' ? Number(value) : value } : beat),
    }))
  }

  const handleAddBeat = () => {
    setForm(prev => ({
      ...prev,
      beats: rebalanceBeats([
        ...prev.beats,
        {
          key: `beat_${prev.beats.length + 1}`,
          title: '',
          description: '',
          weight: 0,
        },
      ]),
    }))
  }

  const handleRemoveBeat = (index: number) => {
    setForm(prev => ({
      ...prev,
      beats: rebalanceBeats(prev.beats.filter((_, beatIndex) => beatIndex !== index)),
    }))
  }

  const handleSubmit = async () => {
    if (!projectId) return
    if (!form.title.trim()) { toast.error('请填写名称'); return }
    if (form.beats.some(beat => !beat.title.trim())) { toast.error('请先补全所有节点标题'); return }
    if (!weightIsValid) { toast.error('节点权重总和必须接近 1.00'); return }

    const timelineData = buildTimelineData(form.beats)
    try {
      if (editing) {
        await updatePlotLine(editing.id, {
          title: form.title,
          description: form.description,
          line_type: normalizePlotLineType(form.line_type),
          estimated_chapters: form.estimated_chapters || undefined,
          timeline_data: timelineData,
        })
      } else {
        await createPlotLine({
          project_id: projectId,
          title: form.title,
          description: form.description,
          line_type: normalizePlotLineType(form.line_type),
          estimated_chapters: form.estimated_chapters || undefined,
          timeline_data: timelineData,
        })
      }
      setShowModal(false)
    } catch { /* hook 已 toast */ }
  }

  const handleGenerate = async () => {
    if (!projectId) return
    const activeOutline = outlines.find(o => o.is_active) || outlines[0]
    setGenerating(true)
    setShowGenModal(false)
    try {
      await generatePlotLines({
        project_id: projectId,
        story_outline_id: activeOutline?.id,
        line_type: normalizePlotLineType(genForm.line_type),
        count: genForm.count,
        based_on_lines: genForm.based_on_lines.length ? genForm.based_on_lines : undefined,
        based_on_cards: genForm.based_on_cards.length ? genForm.based_on_cards : undefined,
        prompt: genForm.prompt.trim() || undefined,
        extend_existing: false,
        enable_mcp: genEnableMcp,
        selected_plugins: genPlugins,
      })
    } catch { /* hook 已 toast */ } finally { setGenerating(false) }
  }

  const handleDelete = async (l: PlotLine) => {
    if (!confirm(`确定删除「${l.title}」？`)) return
    try { await deletePlotLine(l.id) } catch { /* hook 已 toast */ }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-content">剧情线</h2>
        <div className="flex gap-2">
          <button onClick={() => setShowGenModal(true)} disabled={generating} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-3 py-2 text-sm transition-colors inline-flex items-center gap-1.5 disabled:opacity-50">
            {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            AI 生成
          </button>
          <button onClick={openCreate} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5">
            <Plus className="w-4 h-4" />新建剧情线
          </button>
        </div>
      </div>

      {plotLines.length === 0 ? (
        <div className="text-center py-12 text-content-secondary text-sm">暂无剧情线</div>
      ) : (
        <div className="space-y-3">
          {plotLines.map(l => (
            <div key={l.id} className="bg-white border border-surface-border rounded-card p-4 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <GitBranch className="w-4 h-4 text-content-secondary shrink-0" />
                    <h3 className="text-sm font-semibold text-content truncate">{l.title}</h3>
                    <span className={cn("text-xs rounded px-1.5 py-0.5", getPlotLineTypeColor(l.line_type))}>{getPlotLineTypeLabel(l.line_type)}</span>
                  </div>
                  {l.description && <p className="text-xs text-content-secondary mt-1.5 line-clamp-2">{l.description}</p>}
                  <div className="flex items-center gap-3 mt-2 text-xs text-content-secondary">
                    {l.plot_card_count != null && <span>关联卡片: {l.plot_card_count}</span>}
                    {l.chapter_outline_count != null && <span>关联章纲: {l.chapter_outline_count}</span>}
                    {l.estimated_chapters != null && l.estimated_chapters > 0 && <span>预计章节: {l.estimated_chapters}</span>}
                  </div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => openView(l)} className="p-1.5 rounded hover:bg-surface-hover text-content-secondary transition-colors" title="查看详情"><Eye className="w-3.5 h-3.5" /></button>
                  <button onClick={() => openEdit(l)} className="p-1.5 rounded hover:bg-surface-hover text-content-secondary transition-colors" title="编辑剧情线与节点"><Pencil className="w-3.5 h-3.5" /></button>
                  <button onClick={() => handleDelete(l)} className="p-1.5 rounded hover:bg-red-50 text-content-secondary hover:text-red-500 transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
              {Array.isArray(l.timeline_data?.beats) && l.timeline_data.beats.length > 0 ? (
                <div className="rounded-btn border border-surface-border bg-surface/40 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-medium text-content">剧情节点</p>
                    <span className="text-xs text-content-secondary">{l.timeline_data.beats.length} 个</span>
                  </div>
                  <div className="mt-2 space-y-2">
                    {l.timeline_data.beats.slice(0, 4).map((beat: TimelineBeat) => (
                      <div key={`${l.id}-${beat.index}`} className="rounded-btn bg-white border border-surface-border px-3 py-2">
                        <div className="flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-xs font-medium text-content truncate">节点 {beat.index} · {beat.title}</p>
                            {beat.description && <p className="text-xs text-content-secondary mt-1 line-clamp-2">{beat.description}</p>}
                          </div>
                          <span className="text-[11px] text-content-secondary shrink-0">权重 {(Number(beat.weight) * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                    ))}
                    {l.timeline_data.beats.length > 4 && (
                      <p className="text-xs text-content-tertiary">还有 {l.timeline_data.beats.length - 4} 个节点，点右侧小眼睛可查看全部。</p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="rounded-btn border border-dashed border-surface-border px-3 py-2 text-xs text-content-tertiary">
                  暂无节点，点击右侧铅笔可直接补充剧情节点。
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showGenModal && (
        <Modal title="AI 生成剧情线" onClose={() => setShowGenModal(false)}>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-content-secondary mb-1">剧情线类型</label>
                <select value={genForm.line_type} onChange={e => setGenForm(f => ({ ...f, line_type: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none bg-white">
                  {lineTypes.map(t => <option key={t} value={t}>{getPlotLineTypeLabel(t)}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm text-content-secondary mb-1">生成数量</label>
                <input type="number" min={1} max={10} value={genForm.count} onChange={e => setGenForm(f => ({ ...f, count: Number(e.target.value) }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none" />
              </div>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">基于已有剧情线（可选，保持连贯性）</label>
              <div className="border border-surface-border rounded-btn p-2 max-h-32 overflow-y-auto space-y-1">
                {plotLines.length > 0 ? plotLines.map(pl => (
                  <label key={pl.id} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-surface-hover rounded px-1 py-0.5">
                    <input type="checkbox" checked={genForm.based_on_lines.includes(pl.id)} onChange={e => {
                      setGenForm(f => ({ ...f, based_on_lines: e.target.checked ? [...f.based_on_lines, pl.id] : f.based_on_lines.filter(id => id !== pl.id) }))
                    }} className="w-3.5 h-3.5" />
                    <span>{pl.title}</span>
                    <span className="text-xs text-content-secondary">[{getPlotLineTypeLabel(pl.line_type)}]</span>
                  </label>
                )) : <p className="text-xs text-content-secondary py-1">暂无已有剧情线</p>}
              </div>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">基于剧情卡片（可选）</label>
              <div className="border border-surface-border rounded-btn p-2 max-h-32 overflow-y-auto space-y-1">
                {plotCards.length > 0 ? plotCards.map(pc => (
                  <label key={pc.id} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-surface-hover rounded px-1 py-0.5">
                    <input type="checkbox" checked={genForm.based_on_cards.includes(pc.id)} onChange={e => {
                      setGenForm(f => ({ ...f, based_on_cards: e.target.checked ? [...f.based_on_cards, pc.id] : f.based_on_cards.filter(id => id !== pc.id) }))
                    }} className="w-3.5 h-3.5" />
                    <span>{pc.title}</span>
                    <span className="text-xs text-content-secondary">[{pc.card_type}]</span>
                  </label>
                )) : <p className="text-xs text-content-secondary py-1">暂无剧情卡片</p>}
              </div>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">提示词（可选）</label>
              <textarea value={genForm.prompt} onChange={e => setGenForm(f => ({ ...f, prompt: e.target.value }))} placeholder="对剧情线的特殊要求..." rows={2} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none resize-none" />
            </div>
            <MCPSelector value={{ enable: genEnableMcp, selected: genPlugins }} onChange={({ enable, selected }) => { setGenEnableMcp(enable); setGenPlugins(selected) }} />
          </div>
          <div className="sticky bottom-0 -mx-6 -mb-5 mt-4 flex justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 backdrop-blur-sm">
            <button onClick={() => setShowGenModal(false)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm">取消</button>
            <button onClick={handleGenerate} disabled={generating} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5 disabled:opacity-50">
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              开始生成
            </button>
          </div>
        </Modal>
      )}

      {showModal && (
        <Modal title={editing ? '编辑剧情线' : '新建剧情线'} onClose={() => setShowModal(false)} size="2xl">
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-content-secondary mb-1">名称</label>
              <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">类型</label>
              <select value={form.line_type} onChange={e => setForm(f => ({ ...f, line_type: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors bg-white">
                {lineTypes.map(t => <option key={t} value={t}>{getPlotLineTypeLabel(t)}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">预计章节数</label>
              <input type="number" value={form.estimated_chapters} onChange={e => setForm(f => ({ ...f, estimated_chapters: Number(e.target.value) }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">描述</label>
              <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={4} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors resize-none" />
            </div>
            <div className="rounded-card border border-surface-border p-3 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-content">剧情节点</p>
                  <p className="text-xs text-content-secondary mt-1">可直接编辑节点标题、描述和权重，权重总和需要接近 1.00。</p>
                </div>
                <div className="flex items-center gap-2">
                  {form.beats.length > 1 && (
                    <button onClick={() => setForm(prev => ({ ...prev, beats: rebalanceBeats(prev.beats) }))} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-3 py-2 text-xs transition-colors">
                      平均分配权重
                    </button>
                  )}
                  <button onClick={handleAddBeat} className="bg-surface-hover hover:bg-surface-border/70 text-content rounded-btn px-3 py-2 text-xs transition-colors inline-flex items-center gap-1.5">
                    <Plus className="w-3.5 h-3.5" />添加节点
                  </button>
                </div>
              </div>

              {form.beats.length === 0 ? (
                <div className="rounded-btn border border-dashed border-surface-border px-3 py-4 text-xs text-content-tertiary">
                  还没有节点。添加后就能在列表里看到节点摘要，也能在小眼睛里看完整进度。
                </div>
              ) : (
                <div className="space-y-3 max-h-[42vh] overflow-y-auto pr-1">
                  {form.beats.map((beat, index) => (
                    <div key={`beat-editor-${index}`} className="rounded-btn border border-surface-border p-3 space-y-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-content">节点 {index + 1}</p>
                        <button onClick={() => handleRemoveBeat(index)} className="p-1.5 rounded hover:bg-red-50 text-content-secondary hover:text-red-500 transition-colors" title="删除节点">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs text-content-secondary mb-1">节点标题</label>
                          <input value={beat.title} onChange={e => handleBeatChange(index, 'title', e.target.value)} placeholder={`例如：节点 ${index + 1}`} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
                        </div>
                        <div>
                          <label className="block text-xs text-content-secondary mb-1">节点标识</label>
                          <input value={beat.key} onChange={e => handleBeatChange(index, 'key', e.target.value)} placeholder={`beat_${index + 1}`} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
                        </div>
                      </div>
                      <div>
                        <label className="block text-xs text-content-secondary mb-1">节点描述</label>
                        <textarea value={beat.description} onChange={e => handleBeatChange(index, 'description', e.target.value)} rows={3} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors resize-none" />
                      </div>
                      <div>
                        <label className="block text-xs text-content-secondary mb-1">权重</label>
                        <input type="number" min={0} max={1} step={0.01} value={beat.weight} onChange={e => handleBeatChange(index, 'weight', e.target.value)} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className={cn('rounded-btn px-3 py-2 text-xs', weightIsValid ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-amber-50 text-amber-700 border border-amber-200')}>
                当前权重总和：{totalWeight.toFixed(2)}{weightIsValid ? '，可以保存。' : '，请调整到 1.00 附近。'}
              </div>
            </div>
          </div>
          <div className="sticky bottom-0 -mx-6 -mb-5 mt-4 flex justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 backdrop-blur-sm">
            <button onClick={() => setShowModal(false)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm">取消</button>
            <button onClick={handleSubmit} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors">确定</button>
          </div>
        </Modal>
      )}

      {viewing && (
        <Modal title={`剧情线详情：${viewing.title}`} onClose={() => { setViewing(null); setViewingProgress(null) }} size="2xl">
          <div className="space-y-5">
            {/* 顶部元信息栏 */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <span className={cn('rounded-full px-3 py-1 text-xs font-medium', getPlotLineTypeColor(viewing.line_type))}>{getPlotLineTypeLabel(viewing.line_type)}</span>
              <div className="flex items-center gap-4 text-xs text-content-secondary">
                {viewing.estimated_chapters != null && viewing.estimated_chapters > 0 && (
                  <span className="inline-flex items-center gap-1"><BookOpen className="w-3.5 h-3.5" />预计 {viewing.estimated_chapters} 章</span>
                )}
                <span className="inline-flex items-center gap-1"><Link2 className="w-3.5 h-3.5" />章纲 {viewing.chapter_outline_count ?? 0}</span>
                <span className="inline-flex items-center gap-1"><LayoutGrid className="w-3.5 h-3.5" />卡片 {viewing.plot_card_count ?? 0}</span>
              </div>
            </div>

            {/* 剧情简介 */}
            {viewing.description && (
              <div className="rounded-lg border border-surface-border bg-gradient-to-br from-surface/60 to-surface-hover/30 p-4">
                <p className="text-xs font-medium text-content-secondary mb-2 uppercase tracking-wider">剧情简介</p>
                <p className="text-sm text-content leading-relaxed whitespace-pre-wrap">{viewing.description}</p>
              </div>
            )}

            {/* 整体进度概览 */}
            {!loadingProgress && viewingProgress?.has_beats && (
              <div className="rounded-lg bg-gradient-to-r from-brand/5 via-brand/10 to-brand/5 border border-brand/20 p-4">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-sm font-semibold text-content">整体进度</p>
                  <span className="text-lg font-bold text-brand">{((viewingProgress.total_progress || 0) * 100).toFixed(1)}%</span>
                </div>
                <div className="h-2.5 rounded-full bg-white/80 overflow-hidden shadow-inner">
                  <div className="h-full rounded-full bg-gradient-to-r from-brand to-brand-600 transition-all duration-500" style={{ width: `${Math.max(0, Math.min(100, (viewingProgress.total_progress || 0) * 100))}%` }} />
                </div>
                <p className="text-xs text-content-secondary mt-2">已关联 {viewingProgress.linked_chapters_count} 个章纲 · 共 {viewingProgress.beats.length} 个节点</p>
              </div>
            )}

            {/* 节点列表 */}
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-content">节点详情</p>
                {loadingProgress && <Loader2 className="w-4 h-4 animate-spin text-content-secondary" />}
              </div>

              {loadingProgress ? (
                <div className="flex items-center justify-center py-8">
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 className="w-6 h-6 animate-spin text-brand" />
                    <span className="text-xs text-content-secondary">加载节点进度中…</span>
                  </div>
                </div>
              ) : viewingProgress?.has_beats ? (
                <div className="grid grid-cols-1 gap-3 max-h-[50vh] overflow-y-auto pr-1">
                  {viewingProgress.beats.map(beat => {
                    const isCompleted = beat.status === 'completed'
                    const isInProgress = beat.status === 'in_progress'
                    const statusDot = isCompleted
                      ? 'bg-emerald-500'
                      : isInProgress
                        ? 'bg-blue-500 animate-pulse'
                        : 'bg-gray-300'
                    const statusText = isCompleted ? '已完成' : isInProgress ? '进行中' : '未开始'
                    const cardBorder = isCompleted
                      ? 'border-emerald-200'
                      : isInProgress
                        ? 'border-blue-200'
                        : 'border-surface-border'
                    const barColor = isCompleted
                      ? 'bg-gradient-to-r from-emerald-400 to-emerald-500'
                      : isInProgress
                        ? 'bg-gradient-to-r from-blue-400 to-blue-500'
                        : 'bg-gray-200'

                    return (
                      <div key={`progress-${beat.index}`} className={cn('rounded-lg border bg-white p-4 transition-shadow hover:shadow-sm', cardBorder)}>
                        <div className="flex items-start gap-3">
                          {/* 序号指示器 */}
                          <div className="flex flex-col items-center gap-1 pt-0.5">
                            <span className="flex items-center justify-center w-7 h-7 rounded-full bg-surface-hover text-xs font-bold text-content">{beat.index}</span>
                            <span className={cn('w-2 h-2 rounded-full shrink-0', statusDot)} />
                          </div>
                          {/* 内容 */}
                          <div className="flex-1 min-w-0 space-y-2">
                            <div className="flex items-start justify-between gap-2">
                              <div className="min-w-0">
                                <p className="text-sm font-semibold text-content truncate">{beat.title}</p>
                                {beat.description && <p className="text-xs text-content-secondary mt-1 leading-relaxed line-clamp-3">{beat.description}</p>}
                              </div>
                              <span className={cn(
                                'shrink-0 text-[11px] font-medium rounded-full px-2 py-0.5',
                                isCompleted ? 'bg-emerald-100 text-emerald-700'
                                  : isInProgress ? 'bg-blue-100 text-blue-700'
                                    : 'bg-gray-100 text-gray-500'
                              )}>{statusText}</span>
                            </div>
                            {/* 进度条 */}
                            <div>
                              <div className="flex items-center justify-between text-[11px] text-content-secondary mb-1">
                                <span>覆盖度</span>
                                <span className="font-medium">{(beat.coverage * 100).toFixed(0)}%</span>
                              </div>
                              <div className="h-1.5 rounded-full bg-surface-hover overflow-hidden">
                                <div className={cn('h-full rounded-full transition-all duration-500', barColor)} style={{ width: `${Math.max(0, Math.min(100, beat.coverage * 100))}%` }} />
                              </div>
                            </div>
                            {/* 底部元信息 */}
                            <div className="flex items-center gap-3 text-[11px] text-content-tertiary">
                              <span>标识 {beat.key || `beat_${beat.index}`}</span>
                              <span>·</span>
                              <span>权重 {(beat.weight * 100).toFixed(0)}%</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-10 rounded-lg border border-dashed border-surface-border bg-surface/20">
                  <GitBranch className="w-8 h-8 text-content-tertiary mb-2" />
                  <p className="text-sm text-content-secondary">{viewingProgress?.message || '暂无节点数据'}</p>
                  <p className="text-xs text-content-tertiary mt-1">点击下方「编辑节点」可添加剧情节点</p>
                </div>
              )}
            </div>
          </div>
          <div className="sticky bottom-0 -mx-6 -mb-5 mt-4 flex justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 backdrop-blur-sm">
            <button onClick={() => { const current = viewing; setViewing(null); setViewingProgress(null); if (current) openEdit(current) }} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm inline-flex items-center gap-1.5 transition-colors">
              <Pencil className="w-3.5 h-3.5" />编辑节点
            </button>
            <button onClick={() => { setViewing(null); setViewingProgress(null) }} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors">关闭</button>
          </div>
        </Modal>
      )}
    </div>
  )
}
// ==================== Tab 4: 章纲 ====================
function ChapterOutlinesView({ chapterOutlines, projectId, createChapterOutline, updateChapterOutline, deleteChapterOutline, batchCreateChapterOutlines, generateChapterOutlines, plotLines }: {
  chapterOutlines: ChapterOutline[]
  projectId?: string
  createChapterOutline: (data: ChapterOutlineCreate) => Promise<ChapterOutline>
  updateChapterOutline: (id: string, data: ChapterOutlineUpdate) => Promise<ChapterOutline>
  deleteChapterOutline: (id: string) => Promise<void>
  batchCreateChapterOutlines: (data: ChapterOutlineBatchCreateRequest) => Promise<ChapterOutline[]>
  generateChapterOutlines: (data: ChapterOutlineGenerateRequest) => Promise<ChapterOutline[]>
  plotLines: PlotLine[]
}) {
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<ChapterOutline | null>(null)
  const [viewingChapterOutline, setViewingChapterOutline] = useState<ChapterOutline | null>(null)
  const [form, setForm] = useState({ chapter_number: 1, title: '', plot_points: '', scene: '', pov: '', target_word_count: 3000 })
  const [showBatchModal, setShowBatchModal] = useState(false)
  const [batchCount, setBatchCount] = useState(5)
  const [batchCreating, setBatchCreating] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [showGenModal, setShowGenModal] = useState(false)
  const [genForm, setGenForm] = useState({ chapter_count: 5, target_word_count: 3000, prompt: '', plot_line_id: '', auto_generate_plot_cards: true })
  const [genEnableMcp, setGenEnableMcp] = useState(false)
  const [genPlugins, setGenPlugins] = useState<string[]>([])

  // 关联管理
  const [expandedLinkId, setExpandedLinkId] = useState<string | null>(null)
  const [linkedLines, setLinkedLines] = useState<Record<string, Array<{ id: string; title: string; line_type?: string }>>>({})
  const [loadingLink, setLoadingLink] = useState<string | null>(null)
  const [showLinkModal, setShowLinkModal] = useState<string | null>(null)
  const [selectedLinkIds, setSelectedLinkIds] = useState<string[]>([])
  const [linkSaving, setLinkSaving] = useState(false)

  const toggleLinks = async (coId: string) => {
    if (expandedLinkId === coId) { setExpandedLinkId(null); return }
    setExpandedLinkId(coId)
    if (linkedLines[coId]) return
    setLoadingLink(coId)
    try {
      const lines = await chapterOutlineLinkApi.getPlotLines(coId)
      setLinkedLines(prev => ({ ...prev, [coId]: lines.map(l => ({ id: l.id, title: l.title, line_type: l.line_type })) }))
    } catch { /* ignore failed relation preview */ }
    finally { setLoadingLink(null) }
  }

  const handleUnlink = async (coId: string, lineId: string) => {
    try {
      await chapterOutlineLinkApi.unlinkPlotLines(coId, [lineId])
      setLinkedLines(prev => ({ ...prev, [coId]: (prev[coId] || []).filter(l => l.id !== lineId) }))
      toast.success('已取消关联')
    } catch { toast.error('取消关联失败') }
  }

  const openLinkModal = (coId: string) => {
    setShowLinkModal(coId)
    setSelectedLinkIds([])
  }

  const handleLink = async () => {
    if (!showLinkModal || selectedLinkIds.length === 0) return
    setLinkSaving(true)
    try {
      await chapterOutlineLinkApi.linkPlotLines(showLinkModal, { plot_line_ids: selectedLinkIds })
      const lines = await chapterOutlineLinkApi.getPlotLines(showLinkModal)
      setLinkedLines(prev => ({ ...prev, [showLinkModal!]: lines.map(l => ({ id: l.id, title: l.title, line_type: l.line_type })) }))
      setShowLinkModal(null)
      toast.success('关联成功')
    } catch { toast.error('关联失败') }
    finally { setLinkSaving(false) }
  }

  const sorted = [...chapterOutlines].sort((a, b) => a.chapter_number - b.chapter_number)

  const openCreate = () => {
    setEditing(null)
    const nextNum = sorted.length > 0 ? sorted[sorted.length - 1].chapter_number + 1 : 1
    setForm({ chapter_number: nextNum, title: '', plot_points: '', scene: '', pov: '', target_word_count: 3000 })
    setShowModal(true)
  }
  const openEdit = (co: ChapterOutline) => {
    setEditing(co)
    setForm({ chapter_number: co.chapter_number, title: co.title, plot_points: co.plot_points || '', scene: co.scene || '', pov: co.pov || '', target_word_count: co.target_word_count })
    setShowModal(true)
  }

  const handleSubmit = async () => {
    if (!projectId) return
    if (!form.title.trim()) { toast.error('请填写标题'); return }
    try {
      if (editing) {
        await updateChapterOutline(editing.id, { chapter_number: form.chapter_number, title: form.title, plot_points: form.plot_points || undefined, scene: form.scene || undefined, pov: form.pov || undefined, target_word_count: form.target_word_count })
      } else {
        await createChapterOutline({ project_id: projectId, chapter_number: form.chapter_number, title: form.title, plot_points: form.plot_points || undefined, scene: form.scene || undefined, pov: form.pov || undefined, target_word_count: form.target_word_count })
      }
      setShowModal(false)
    } catch { /* hook 已 toast */ }
  }

  const handleBatchCreate = async () => {
    if (!projectId || batchCount < 1) return
    setBatchCreating(true)
    try {
      const startNum = sorted.length > 0 ? sorted[sorted.length - 1].chapter_number + 1 : 1
      const outlines: ChapterOutlineCreate[] = Array.from({ length: batchCount }, (_, i) => ({
        project_id: projectId,
        chapter_number: startNum + i,
        title: `第${startNum + i}章`,
        target_word_count: 3000,
      }))
      await batchCreateChapterOutlines({ project_id: projectId, outlines })
      setShowBatchModal(false)
    } catch { /* hook 已 toast */ } finally { setBatchCreating(false) }
  }

  const handleGenerate = async () => {
    if (!projectId) return
    const startNum = sorted.length > 0 ? sorted[sorted.length - 1].chapter_number + 1 : 1
    setGenerating(true)
    setShowGenModal(false)
    try {
      await generateChapterOutlines({
        project_id: projectId,
        start_chapter: startNum,
        chapter_count: genForm.chapter_count,
        target_word_count: genForm.target_word_count,
        based_on_outline: true,
        plot_line_id: genForm.plot_line_id || undefined,
        auto_generate_plot_cards: genForm.auto_generate_plot_cards,
        prompt: genForm.prompt.trim() || undefined,
        enable_mcp: genEnableMcp,
        selected_plugins: genPlugins,
      })
    } catch { /* hook 已 toast */ } finally { setGenerating(false) }
  }

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }
  const toggleSelectAll = () => {
    setSelectedIds(prev => prev.size === chapterOutlines.length ? new Set() : new Set(chapterOutlines.map(co => co.id)))
  }
  const handleDelete = (co: ChapterOutline) => {
    setSelectedIds(new Set([co.id]))
    setConfirmDelete(true)
  }
  const handleDeleteSelected = () => {
    if (selectedIds.size === 0) { toast.error('请先选择要删除的章纲'); return }
    setConfirmDelete(true)
  }
  const executeDelete = async () => {
    setDeleting(true)
    try {
      for (const id of selectedIds) await deleteChapterOutline(id)
      toast.success(`已删除 ${selectedIds.size} 个章纲`)
      setSelectedIds(new Set())
    } catch { toast.error('删除失败') }
    finally { setDeleting(false); setConfirmDelete(false) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-content">章纲</h2>
        <div className="flex gap-2">
          <button onClick={() => setShowGenModal(true)} disabled={generating} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-3 py-2 text-sm transition-colors inline-flex items-center gap-1.5 disabled:opacity-50">
            {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            AI 生成
          </button>
          {chapterOutlines.length > 0 && (
            <button onClick={handleDeleteSelected} disabled={selectedIds.size === 0} className="border border-red-200 text-red-500 hover:bg-red-50 rounded-btn px-3 py-2 text-sm transition-colors inline-flex items-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed">
              <Trash2 className="w-4 h-4" />删除{selectedIds.size > 0 ? ` (${selectedIds.size})` : ''}
            </button>
          )}
          <button onClick={() => setShowBatchModal(true)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-3 py-2 text-sm transition-colors inline-flex items-center gap-1.5">
            <Plus className="w-4 h-4" />批量创建
          </button>
          <button onClick={openCreate} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5">
            <Plus className="w-4 h-4" />新建章纲
          </button>
        </div>
      </div>

      {sorted.length === 0 ? (
        <div className="text-center py-12 text-content-secondary text-sm">暂无章纲</div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-2 px-1">
            <input type="checkbox" checked={selectedIds.size === chapterOutlines.length && chapterOutlines.length > 0} onChange={toggleSelectAll} className="w-4 h-4 accent-brand" />
            <span className="text-xs text-content-secondary">{selectedIds.size > 0 ? `已选 ${selectedIds.size}/${chapterOutlines.length}` : '全选'}</span>
          </div>
          {sorted.map(co => (
            <div key={co.id} className={`bg-white border rounded-card p-4 transition-colors ${selectedIds.has(co.id) ? 'border-brand/40 bg-brand/5' : 'border-surface-border'}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <input type="checkbox" checked={selectedIds.has(co.id)} onChange={() => toggleSelect(co.id)} className="w-4 h-4 accent-brand mt-0.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono bg-surface-hover text-content-secondary rounded px-1.5 py-0.5 shrink-0">#{co.chapter_number}</span>
                    <h3 className="text-sm font-semibold text-content truncate">{co.title}</h3>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1.5 text-xs text-content-secondary">
                    {co.scene && <span>场景: {co.scene}</span>}
                    {co.pov && <span>视角: {co.pov}</span>}
                    <span>目标字数: {co.target_word_count}</span>
                    {co.plot_line_count != null && <span>关联剧情线: {co.plot_line_count}</span>}
                  </div>
                  {co.plot_points && <p className="text-xs text-content-secondary mt-1.5 line-clamp-2">{co.plot_points}</p>}
                  {co.key_events && co.key_events.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {co.key_events.map((ev, i) => (
                        <span key={i} className="text-xs bg-surface-hover text-content-secondary rounded px-1.5 py-0.5">{ev}</span>
                      ))}
                    </div>
                  )}
                  <button onClick={() => toggleLinks(co.id)} className="inline-flex items-center gap-1 mt-2 text-xs text-brand hover:text-brand-600 transition-colors">
                    <Link2 className="w-3 h-3" />关联剧情线
                    {expandedLinkId === co.id ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </button>
                  </div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => setViewingChapterOutline(co)} className="p-1.5 rounded hover:bg-surface-hover text-content-secondary transition-colors" title="查看章纲详情"><Eye className="w-3.5 h-3.5" /></button>
                  <button onClick={() => openEdit(co)} className="p-1.5 rounded hover:bg-surface-hover text-content-secondary transition-colors"><Pencil className="w-3.5 h-3.5" /></button>
                  <button onClick={() => handleDelete(co)} className="p-1.5 rounded hover:bg-red-50 text-content-secondary hover:text-red-500 transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
              {expandedLinkId === co.id && (
                <div className="mt-3 pt-3 border-t border-surface-border">
                  {loadingLink === co.id ? (
                    <div className="flex items-center gap-2 text-xs text-content-secondary"><Loader2 className="w-3 h-3 animate-spin" />加载中...</div>
                  ) : (
                    <>
                      {(linkedLines[co.id] || []).length > 0 ? (
                        <div className="flex flex-wrap gap-2 mb-2">
                          {(linkedLines[co.id] || []).map(pl => (
                            <span key={pl.id} className="inline-flex items-center gap-1 text-xs bg-blue-50 text-blue-700 rounded px-2 py-1">
                              <GitBranch className="w-3 h-3" />{pl.title}
                              <button onClick={() => handleUnlink(co.id, pl.id)} className="ml-1 text-blue-400 hover:text-red-500" title="取消关联">&times;</button>
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-content-tertiary mb-2">暂无关联剧情线</p>
                      )}
                      <button onClick={() => openLinkModal(co.id)} className="inline-flex items-center gap-1 text-xs text-brand hover:text-brand-600">
                        <Plus className="w-3 h-3" />添加关联
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* AI 生成章纲弹窗 */}
      {showGenModal && (
        <Modal title="AI 生成章纲" onClose={() => setShowGenModal(false)}>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-content-secondary mb-1">生成数量</label>
                <input type="number" min={1} max={50} value={genForm.chapter_count} onChange={e => setGenForm(f => ({ ...f, chapter_count: Number(e.target.value) }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none" />
              </div>
              <div>
                <label className="block text-sm text-content-secondary mb-1">每章目标字数</label>
                <input type="number" min={500} value={genForm.target_word_count} onChange={e => setGenForm(f => ({ ...f, target_word_count: Number(e.target.value) }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none" />
              </div>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">关联剧情线（可选）</label>
              <select value={genForm.plot_line_id} onChange={e => setGenForm(f => ({ ...f, plot_line_id: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none bg-white">
                <option value="">不指定（自动基于大纲生成）</option>
                {plotLines.map(pl => (
                  <option key={pl.id} value={pl.id}>{pl.title}{pl.line_type ? ` [${getPlotLineTypeLabel(pl.line_type)}]` : ''}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">提示词（可选）</label>
              <textarea value={genForm.prompt} onChange={e => setGenForm(f => ({ ...f, prompt: e.target.value }))} placeholder="对章纲的特殊要求..." rows={2} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand outline-none resize-none" />
            </div>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={genForm.auto_generate_plot_cards} onChange={e => setGenForm(f => ({ ...f, auto_generate_plot_cards: e.target.checked }))} className="w-4 h-4" />
              <span>同时自动生成关联剧情卡片</span>
            </label>
            <MCPSelector value={{ enable: genEnableMcp, selected: genPlugins }} onChange={({ enable, selected }) => { setGenEnableMcp(enable); setGenPlugins(selected) }} />
            <p className="text-xs text-content-secondary">将从第 {sorted.length > 0 ? sorted[sorted.length - 1].chapter_number + 1 : 1} 章开始生成。</p>
          </div>
          <div className="sticky bottom-0 -mx-6 -mb-5 mt-4 flex justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 backdrop-blur-sm">
            <button onClick={() => setShowGenModal(false)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm">取消</button>
            <button onClick={handleGenerate} disabled={generating} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5 disabled:opacity-50">
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              开始生成
            </button>
          </div>
        </Modal>
      )}

      {/* 创建/编辑弹窗 */}
      {showModal && (
        <Modal title={editing ? '编辑章纲' : '新建章纲'} onClose={() => setShowModal(false)} size="xl">
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-content-secondary mb-1">章节序号</label>
                <input type="number" value={form.chapter_number} onChange={e => setForm(f => ({ ...f, chapter_number: Number(e.target.value) }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
              </div>
              <div>
                <label className="block text-sm text-content-secondary mb-1">目标字数</label>
                <input type="number" value={form.target_word_count} onChange={e => setForm(f => ({ ...f, target_word_count: Number(e.target.value) }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
              </div>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">标题</label>
              <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-content-secondary mb-1">场景</label>
                <input value={form.scene} onChange={e => setForm(f => ({ ...f, scene: e.target.value }))} placeholder="如：拳击场→后台" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
              </div>
              <div>
                <label className="block text-sm text-content-secondary mb-1">视角角色</label>
                <input value={form.pov} onChange={e => setForm(f => ({ ...f, pov: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
              </div>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">剧情要点</label>
              <textarea value={form.plot_points} onChange={e => setForm(f => ({ ...f, plot_points: e.target.value }))} rows={4} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors resize-none" />
            </div>
          </div>
          <div className="sticky bottom-0 -mx-6 -mb-5 mt-4 flex justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 backdrop-blur-sm">
            <button onClick={() => setShowModal(false)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm">取消</button>
            <button onClick={handleSubmit} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors">确定</button>
          </div>
        </Modal>
      )}

      {/* 删除确认弹窗 */}
      {confirmDelete && (
        <Modal title="确认删除" onClose={() => setConfirmDelete(false)}>
          <div className="space-y-3">
            <p className="text-sm text-content">
              确定删除选中的 {selectedIds.size} 个章纲？此操作不可撤销。
            </p>
            <div className="text-xs text-content-secondary space-y-0.5 max-h-32 overflow-y-auto">
              {chapterOutlines.filter(co => selectedIds.has(co.id)).map(co => (
                <div key={co.id}>• 第{co.chapter_number}章：{co.title}</div>
              ))}
            </div>
          </div>
          <div className="sticky bottom-0 -mx-6 -mb-5 mt-4 flex justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 backdrop-blur-sm">
            <button onClick={() => setConfirmDelete(false)} disabled={deleting} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm">取消</button>
            <button onClick={executeDelete} disabled={deleting} className="bg-red-500 hover:bg-red-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5 disabled:opacity-50">
              {deleting && <Loader2 className="w-4 h-4 animate-spin" />}
              确认删除 ({selectedIds.size})
            </button>
          </div>
        </Modal>
      )}

      {/* 批量创建弹窗 */}
      {showBatchModal && (
        <Modal title="批量创建章纲" onClose={() => setShowBatchModal(false)}>
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-content-secondary mb-1">创建数量</label>
              <input type="number" min={1} max={50} value={batchCount} onChange={e => setBatchCount(Number(e.target.value))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <p className="text-xs text-content-secondary">将从第 {sorted.length > 0 ? sorted[sorted.length - 1].chapter_number + 1 : 1} 章开始，自动编号创建 {batchCount} 个章纲。</p>
          </div>
          <div className="sticky bottom-0 -mx-6 -mb-5 mt-4 flex justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 backdrop-blur-sm">
            <button onClick={() => setShowBatchModal(false)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm">取消</button>
            <button onClick={handleBatchCreate} disabled={batchCreating} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5 disabled:opacity-50">
              {batchCreating && <Loader2 className="w-4 h-4 animate-spin" />}
              确定创建
            </button>
          </div>
        </Modal>
      )}

      {/* 关联剧情线选择弹窗 */}
      {showLinkModal && (
        <Modal title="关联剧情线" onClose={() => setShowLinkModal(null)}>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {plotLines.length === 0 ? (
              <p className="text-sm text-content-secondary">暂无可选剧情线，请先创建剧情线</p>
            ) : (
              plotLines.map(pl => {
                const alreadyLinked = (linkedLines[showLinkModal] || []).some(l => l.id === pl.id)
                const selected = selectedLinkIds.includes(pl.id)
                return (
                  <label key={pl.id} className={cn(
                    "flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-colors text-sm",
                    alreadyLinked ? "bg-surface-hover opacity-50 cursor-not-allowed" : selected ? "bg-brand/10 border border-brand" : "hover:bg-surface-hover border border-transparent"
                  )}>
                    <input
                      type="checkbox"
                      checked={selected || alreadyLinked}
                      disabled={alreadyLinked}
                      onChange={() => {
                        if (alreadyLinked) return
                        setSelectedLinkIds(prev => prev.includes(pl.id) ? prev.filter(id => id !== pl.id) : [...prev, pl.id])
                      }}
                      className="rounded"
                    />
                    <GitBranch className="w-3.5 h-3.5 text-content-secondary shrink-0" />
                    <span className="truncate">{pl.title}</span>
                    <span className="text-xs text-content-tertiary shrink-0">{getPlotLineTypeLabel(pl.line_type)}</span>
                    {alreadyLinked && <span className="text-xs text-content-tertiary ml-auto">已关联</span>}
                  </label>
                )
              })
            )}
          </div>
          <div className="sticky bottom-0 -mx-6 -mb-5 mt-4 flex justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 backdrop-blur-sm">
            <button onClick={() => setShowLinkModal(null)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm">取消</button>
            <button onClick={handleLink} disabled={linkSaving || selectedLinkIds.length === 0} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5 disabled:opacity-50">
              {linkSaving && <Loader2 className="w-4 h-4 animate-spin" />}
              确定关联 ({selectedLinkIds.length})
            </button>
          </div>
        </Modal>
      )}

      {viewingChapterOutline && (
        <Modal title={`章纲详情：第${viewingChapterOutline.chapter_number}章`} onClose={() => setViewingChapterOutline(null)} size="xl">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-content-secondary">
              <span className="bg-surface-hover rounded px-2 py-1">#{viewingChapterOutline.chapter_number}</span>
              {viewingChapterOutline.scene && <span>场景：{viewingChapterOutline.scene}</span>}
              {viewingChapterOutline.pov && <span>视角：{viewingChapterOutline.pov}</span>}
              <span>目标字数：{viewingChapterOutline.target_word_count}</span>
              <span>关联剧情线：{viewingChapterOutline.plot_line_count ?? 0}</span>
            </div>
            <div className="rounded-btn border border-surface-border bg-surface/40 p-3">
              <p className="text-xs text-content-secondary mb-1">标题</p>
              <p className="text-sm font-medium text-content">{viewingChapterOutline.title}</p>
            </div>
            <div className="rounded-btn border border-surface-border bg-surface/40 p-3">
              <p className="text-xs text-content-secondary mb-1">剧情要点</p>
              <p className="text-sm text-content whitespace-pre-wrap">{viewingChapterOutline.plot_points || '暂无内容'}</p>
            </div>
            {viewingChapterOutline.key_events && viewingChapterOutline.key_events.length > 0 && (
              <div className="rounded-btn border border-surface-border bg-surface/40 p-3">
                <p className="text-xs text-content-secondary mb-2">关键事件</p>
                <div className="flex flex-wrap gap-1.5">
                  {viewingChapterOutline.key_events.map((event, index) => (
                    <span key={`key-event-${index}`} className="text-xs bg-white border border-surface-border rounded px-2 py-1 text-content-secondary">
                      {event}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
          <div className="sticky bottom-0 -mx-6 -mb-5 mt-4 flex justify-end gap-2 border-t border-surface-border bg-white/95 px-6 py-3 backdrop-blur-sm">
            <button onClick={() => { const current = viewingChapterOutline; setViewingChapterOutline(null); if (current) openEdit(current) }} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm inline-flex items-center gap-1.5">
              <Pencil className="w-3.5 h-3.5" />编辑
            </button>
            <button onClick={() => setViewingChapterOutline(null)} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors">关闭</button>
          </div>
        </Modal>
      )}
    </div>
  )
}
// ==================== Tab 5: 关联总览 ====================
function OverviewPanel({ plotCards, plotLines, chapterOutlines }: {
  plotCards: PlotCard[]
  plotLines: PlotLine[]
  chapterOutlines: ChapterOutline[]
}) {
  const totalCardLinks = plotCards.reduce((sum, c) => sum + (c.plot_line_count ?? 0) + (c.chapter_outline_count ?? 0), 0)
  const totalLineLinks = plotLines.reduce((sum, l) => sum + (l.chapter_outline_count ?? 0) + (l.plot_card_count ?? 0), 0)
  const totalRelations = totalCardLinks + totalLineLinks

  const stats = [
    { label: '剧情卡片', value: plotCards.length, color: 'bg-blue-50 text-blue-700 border-blue-200' },
    { label: '剧情线', value: plotLines.length, color: 'bg-purple-50 text-purple-700 border-purple-200' },
    { label: '章纲', value: chapterOutlines.length, color: 'bg-green-50 text-green-700 border-green-200' },
    { label: '关联关系', value: totalRelations, color: 'bg-orange-50 text-orange-700 border-orange-200' },
  ]

  // 简易关联网络图：节点 = 剧情线 + 章纲，用 SVG 绘制
  const sortedCO = [...chapterOutlines].sort((a, b) => a.chapter_number - b.chapter_number)
  const nodeCount = plotLines.length + sortedCO.length
  const svgW = 700, svgH = Math.max(300, nodeCount * 18)
  const lineX = 120, coX = svgW - 120
  const lineNodes = plotLines.map((l, i) => ({
    id: l.id, label: l.title, type: 'line' as const,
    x: lineX, y: 40 + i * (svgH - 80) / Math.max(plotLines.length - 1, 1),
    linkCount: l.chapter_outline_count ?? 0,
  }))
  const coNodes = sortedCO.map((co, i) => ({
    id: co.id, label: `#${co.chapter_number} ${co.title}`, type: 'co' as const,
    x: coX, y: 40 + i * (svgH - 80) / Math.max(sortedCO.length - 1, 1),
    linkCount: co.plot_line_count ?? 0,
  }))

  return (
    <div className="space-y-6">
      <h2 className="text-base font-semibold text-content">关联总览</h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map(s => (
          <div key={s.label} className={cn("border rounded-card p-5 text-center", s.color)}>
            <div className="text-3xl font-bold">{s.value}</div>
            <div className="text-sm mt-1 opacity-80">{s.label}</div>
          </div>
        ))}
      </div>

      {/* 关联网络图 */}
      {plotLines.length > 0 && sortedCO.length > 0 && (
        <div className="bg-white border border-surface-border rounded-card p-4 space-y-3">
          <h3 className="text-sm font-semibold text-content">关联网络图</h3>
          <p className="text-xs text-content-secondary">左侧为剧情线，右侧为章纲。圆圈大小代表关联数量。</p>
          <div className="overflow-x-auto">
            <svg width={svgW} height={svgH} className="mx-auto">
              {/* 连线占位：根据关联数量画虚线 */}
              {lineNodes.map(ln => coNodes.filter(cn => cn.linkCount > 0 || ln.linkCount > 0).slice(0, ln.linkCount || 1).map((cn, ci) => (
                <line key={`${ln.id}-${cn.id}-${ci}`} x1={ln.x + 8} y1={ln.y} x2={cn.x - 8} y2={cn.y}
                  stroke="#d1d5db" strokeWidth={1} strokeDasharray="4,3" opacity={0.5} />
              )))}
              {/* 剧情线节点 */}
              {lineNodes.map(n => (
                <g key={n.id}>
                  <circle cx={n.x} cy={n.y} r={Math.max(6, Math.min(14, 6 + n.linkCount * 2))} fill="#8b5cf6" opacity={0.8} />
                  <text x={n.x - 14} y={n.y + 4} textAnchor="end" fontSize={11} fill="#6b7280" className="select-none">{n.label}</text>
                </g>
              ))}
              {/* 章纲节点 */}
              {coNodes.map(n => (
                <g key={n.id}>
                  <circle cx={n.x} cy={n.y} r={Math.max(6, Math.min(14, 6 + n.linkCount * 2))} fill="#10b981" opacity={0.8} />
                  <text x={n.x + 14} y={n.y + 4} textAnchor="start" fontSize={11} fill="#6b7280" className="select-none">{n.label}</text>
                </g>
              ))}
              {/* 图例 */}
              <circle cx={20} cy={svgH - 20} r={6} fill="#8b5cf6" />
              <text x={32} y={svgH - 16} fontSize={10} fill="#6b7280">剧情线</text>
              <circle cx={90} cy={svgH - 20} r={6} fill="#10b981" />
              <text x={102} y={svgH - 16} fontSize={10} fill="#6b7280">章纲</text>
            </svg>
          </div>
        </div>
      )}

      {/* 剧情线概览 */}
      {plotLines.length > 0 && (
        <div className="bg-white border border-surface-border rounded-card p-4 space-y-3">
          <h3 className="text-sm font-semibold text-content">剧情线分布</h3>
          <div className="space-y-2">
            {plotLines.map(l => (
              <div key={l.id} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <GitBranch className="w-3.5 h-3.5 text-content-secondary" />
                  <span className="text-content">{l.title}</span>
                  <span className="text-xs text-content-secondary">({getPlotLineTypeLabel(l.line_type)})</span>
                </div>
                <div className="flex items-center gap-3 text-xs text-content-secondary">
                  <span>卡片 {l.plot_card_count ?? 0}</span>
                  <span>章纲 {l.chapter_outline_count ?? 0}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 章纲覆盖 */}
      {chapterOutlines.length > 0 && (
        <div className="bg-white border border-surface-border rounded-card p-4 space-y-3">
          <h3 className="text-sm font-semibold text-content">章纲覆盖</h3>
          <div className="flex flex-wrap gap-1.5">
            {sortedCO.map(co => (
              <span key={co.id} className={cn(
                "text-xs rounded px-2 py-1",
                (co.plot_line_count ?? 0) > 0 ? "bg-green-50 text-green-700" : "bg-surface-hover text-content-secondary"
              )}>
                #{co.chapter_number} {co.title}
                {(co.plot_line_count ?? 0) > 0 && <span className="ml-1 opacity-60">({co.plot_line_count}线)</span>}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
