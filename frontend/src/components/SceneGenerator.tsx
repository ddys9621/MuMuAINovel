import { useState, useEffect, useCallback, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X, Loader2, Play, CheckCircle2, FileText } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { sceneGenerationApi } from '@/services/api'
import {
  ReferencePackSelector,
  DEFAULT_SELECTOR_VALUE,
  type ReferencePackSelectorValue,
} from '@/components/ReferencePackSelector'

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
  /** R8：项目 ID（可选），提供后可在弹框里选择拆书参考包 */
  projectId?: string
  onClose: () => void
  onComplete?: () => void
}

export function SceneGenerator({ chapterOutlineId, chapterTitle, projectId, onClose, onComplete }: SceneGeneratorProps) {
  const [plotCards, setPlotCards] = useState<PlotCardItem[]>([])
  const [loading, setLoading] = useState(true)
  const [generatingId, setGeneratingId] = useState<string | null>(null)
  const [generatedContent, setGeneratedContent] = useState<Record<string, string>>({})
  // R8：拆书参考包选择器状态（弹框内共用，每个卡片生成时均使用当前值）
  const [refPack, setRefPack] = useState<ReferencePackSelectorValue>(DEFAULT_SELECTOR_VALUE)
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
          // R8：仅 enabled 时透传拆书参考包参数
          ...(refPack.enabled ? {
            pack_ids: refPack.packIds.length > 0 ? refPack.packIds : undefined,
            dimensions: refPack.dimensions.length > 0 ? refPack.dimensions : undefined,
            strength: refPack.strength,
          } : {}),
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
    if (generatingId === card.id) return <Loader2 className="h-4 w-4 shrink-0 animate-spin text-brand" />
    if (generatedContent[card.id]) return <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
    return <FileText className="h-4 w-4 shrink-0 text-content-tertiary" />
  }

  return createPortal(
    <div className="hh-modal-mask">
      <div className="hh-modal max-w-[720px]" onClick={e => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="hh-modal-head">
          <div className="min-w-0">
            <p className="hh-eyebrow">AI 生成</p>
            <h2 className="mt-2 text-xl font-semibold tracking-tight text-content">场景生成</h2>
            <p className="mt-1 text-sm leading-6 text-content-secondary">
              {chapterTitle} — 按剧情卡片分段生成，每张卡片可单独生成或重写。
            </p>
          </div>
          <button onClick={onClose} className="hh-icon-btn-plain -mr-2 -mt-1" aria-label="关闭">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="hh-modal-body space-y-4">
          {/* R8 拆书参考包选择（项目内弹框级别，所有场景卡片共享配置） */}
          {projectId && (
            <ReferencePackSelector
              projectId={projectId}
              value={refPack}
              onChange={setRefPack}
              hint="本弹框内生成的所有场景共用该参考配置"
              disabledTitle="使用拆书参考包作为对标"
            />
          )}

          {loading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-brand" />
            </div>
          ) : plotCards.length === 0 ? (
            <div className="hh-subpanel flex flex-col items-center px-6 py-12 text-center">
              <span className="flex h-14 w-14 items-center justify-center bg-brand/10 text-brand">
                <FileText className="h-7 w-7" />
              </span>
              <h3 className="mt-5 text-base font-semibold tracking-tight text-content">还没有关联剧情卡片</h3>
              <p className="mt-2 max-w-md text-sm leading-6 text-content-secondary">
                该章纲没有关联剧情卡片，请先在故事大纲页关联剧情卡片后再使用场景生成
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {plotCards.map(card => (
                <article key={card.id} className="hh-subpanel space-y-2 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                      {statusIcon(card)}
                      <h4 className="truncate text-sm font-semibold text-content">{card.title}</h4>
                      <span className="shrink-0 text-xs text-content-tertiary tabular-nums">#{card.generation_order + 1}</span>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <span className="text-xs text-content-tertiary tabular-nums">
                        {generatedContent[card.id] ? `${generatedContent[card.id].length} 字` : `目标 ${card.word_count_target} 字`}
                      </span>
                      <button
                        onClick={() => handleGenerateScene(card)}
                        disabled={!!generatingId}
                        className={cn('hh-btn-sm', generatedContent[card.id] ? 'hh-btn-secondary' : 'hh-btn-primary')}
                      >
                        {generatingId === card.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Play className="h-3.5 w-3.5" />
                        )}
                        {generatedContent[card.id] ? '重新生成' : '生成'}
                      </button>
                    </div>
                  </div>
                  {card.content && <p className="line-clamp-2 text-xs leading-5 text-content-secondary">{card.content}</p>}
                  {generatedContent[card.id] && (
                    <div className="max-h-40 overflow-y-auto whitespace-pre-wrap bg-surface-hover p-3 text-sm leading-6 text-content">
                      {generatedContent[card.id]}
                    </div>
                  )}
                </article>
              ))}
            </div>
          )}
        </div>

        <div className="hh-modal-foot">
          <button onClick={onClose} className="hh-btn-ghost">
            关闭
          </button>
          {Object.keys(generatedContent).length > 0 && onComplete && (
            <button onClick={() => { onComplete(); onClose() }} className="hh-btn-primary">
              完成并刷新
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
