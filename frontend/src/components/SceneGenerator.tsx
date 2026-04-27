import { useState, useEffect, useCallback, useRef } from 'react'
import { X, Loader2, Play, CheckCircle2, FileText } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { sceneGenerationApi } from '@/services/api'

interface PlotCardItem {
  id: string
  title: string
  content?: string
  generation_status: string
  word_count_target: number
  word_count_actual: number
  generation_order: number
}

interface SceneGeneratorProps {
  chapterOutlineId: string
  chapterTitle: string
  onClose: () => void
  onComplete?: () => void
}

export function SceneGenerator({ chapterOutlineId, chapterTitle, onClose, onComplete }: SceneGeneratorProps) {
  const [plotCards, setPlotCards] = useState<PlotCardItem[]>([])
  const [loading, setLoading] = useState(true)
  const [generatingId, setGeneratingId] = useState<string | null>(null)
  const [generatedContent, setGeneratedContent] = useState<Record<string, string>>({})
  const abortRef = useRef<AbortController | null>(null)

  const loadPlotCards = useCallback(async () => {
    setLoading(true)
    try {
      const res = await sceneGenerationApi.getPlotCards(chapterOutlineId)
      setPlotCards((res.plot_cards || []).sort((a, b) => a.generation_order - b.generation_order))
    } catch {
      toast.error('加载剧情卡片失败')
    } finally {
      setLoading(false)
    }
  }, [chapterOutlineId])

  useEffect(() => { loadPlotCards() }, [loadPlotCards])

  useEffect(() => {
    return () => { abortRef.current?.abort() }
  }, [])

  const handleGenerateScene = async (card: PlotCardItem) => {
    setGeneratingId(card.id)
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    let content = ''

    try {
      await sceneGenerationApi.generateSceneStream(
        {
          chapter_outline_id: chapterOutlineId,
          plot_card_id: card.id,
          previous_generated_content: generatedContent[card.id] || undefined,
        },
        {
          signal: controller.signal,
          onChunk: (chunk) => {
            content += chunk
            setGeneratedContent(prev => ({ ...prev, [card.id]: content }))
          }
        }
      )

      if (!controller.signal.aborted) {
        toast.success(`Scene generated: ${card.title}`)
        await loadPlotCards()
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        toast.error((err as Error).message || 'Scene generation failed')
      }
    } finally {
      setGeneratingId(null)
    }
  }

  const statusIcon = (card: PlotCardItem) => {
    if (generatingId === card.id) return <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
    if (generatedContent[card.id]) return <CheckCircle2 className="w-4 h-4 text-green-500" />
    return <FileText className="w-4 h-4 text-content-tertiary" />
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="bg-white rounded-modal shadow-xl w-full max-w-2xl mx-4 max-h-[85vh] flex flex-col animate-scale-in" onClick={e => e.stopPropagation()}>
        {/* 标题 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-surface-border shrink-0">
          <div>
            <h3 className="text-base font-bold text-content">场景生成</h3>
            <p className="text-xs text-content-secondary mt-0.5">{chapterTitle} — 按剧情卡片分段生成</p>
          </div>
          <button onClick={onClose} className="p-1 rounded-btn text-content-secondary hover:bg-surface-hover transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 内容 */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
          {loading ? (
            <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-content-secondary" /></div>
          ) : plotCards.length === 0 ? (
            <div className="text-center py-12 text-content-secondary text-sm">
              该章纲没有关联剧情卡片，请先在故事大纲页关联剧情卡片后再使用场景生成
            </div>
          ) : (
            plotCards.map(card => (
              <div key={card.id} className="border border-surface-border rounded-card p-4 space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    {statusIcon(card)}
                    <h4 className="text-sm font-semibold text-content truncate">{card.title}</h4>
                    <span className="text-xs text-content-secondary shrink-0">#{card.generation_order + 1}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-content-secondary">
                      {generatedContent[card.id] ? `${generatedContent[card.id].length} 字` : `目标 ${card.word_count_target} 字`}
                    </span>
                    <button
                      onClick={() => handleGenerateScene(card)}
                      disabled={!!generatingId}
                      className={cn(
                        'inline-flex items-center gap-1 px-3 py-1.5 text-xs rounded-btn transition-colors disabled:opacity-50',
                        generatedContent[card.id]
                          ? 'border border-surface-border text-content-secondary hover:bg-surface-hover'
                          : 'bg-brand text-white hover:bg-brand-600'
                      )}
                    >
                      {generatingId === card.id ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Play className="w-3 h-3" />
                      )}
                      {generatedContent[card.id] ? '重新生成' : '生成'}
                    </button>
                  </div>
                </div>
                {card.content && <p className="text-xs text-content-secondary line-clamp-2">{card.content}</p>}
                {generatedContent[card.id] && (
                  <div className="bg-surface rounded-lg p-3 max-h-40 overflow-y-auto text-sm text-content whitespace-pre-wrap">
                    {generatedContent[card.id]}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* 底部 */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-surface-border shrink-0">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-btn text-content-secondary hover:bg-surface-hover transition-colors">
            关闭
          </button>
          {Object.keys(generatedContent).length > 0 && onComplete && (
            <button
              onClick={() => { onComplete(); onClose() }}
              className="px-4 py-2 text-sm rounded-btn bg-brand text-white hover:bg-brand-600 transition-colors"
            >
              完成并刷新
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
