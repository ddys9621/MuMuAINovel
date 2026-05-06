import { useState, useEffect, useCallback, useRef } from 'react';
import { Plus, Pencil, Trash2, Zap, X, Loader2, RefreshCw, Layers, Search, Film, Eye, ChevronUp, Download, LayoutGrid } from 'lucide-react';
import { toast } from 'sonner';
import { useStore } from '@/store';
import { useChapterSync } from '@/store/hooks';
import { chapterApi, writingStyleApi, chapterOutlineLinkApi } from '@/services/api';
import { SSEPostClient } from '@/utils/sseClient';
import type { Chapter, ChapterCanGenerateResponse, ChapterGenerateRequest, PlotCardWithLinks, WritingStyle } from '@/types';
import { SceneGenerator } from '@/components/SceneGenerator';
import { MCPSelector } from '@/components/MCPSelector';

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  draft: { label: '草稿', cls: 'bg-gray-100 text-gray-500' },
  writing: { label: '生成中', cls: 'bg-blue-50 text-blue-600' },
  completed: { label: '已完成', cls: 'bg-emerald-50 text-emerald-600' },
};

interface FormData {
  title: string;
  chapter_number: number;
  content: string;
}

interface StreamState {
  chapterId: string;
  chapterTitle: string;
  progress: number;
  message: string;
  content: string;
  mode: 'single' | 'batch';
}

interface BatchStatusState {
  status: 'running' | 'completed' | 'cancelled' | 'error';
  total: number;
  completed: number;
  progress: number;
  currentChapterId: string | null;
  currentChapterNumber: number | null;
  currentChapterTitle: string | null;
  message: string;
  skippedCount: number;
  errorMessage?: string;
}

const ANALYSIS_POLL_INTERVAL_MS = 1500;
// 前端等待时间要略大于后端自动恢复阈值，避免后端仍在分析时前端先误判超时
const ANALYSIS_TIMEOUT_MS = 6 * 60 * 1000;

export default function Chapters() {
  const { currentProject, chapters } = useStore();
  const { refreshChapters, createChapter, updateChapter, deleteChapter } = useChapterSync();

  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormData>({ title: '', chapter_number: 1, content: '' });
  const [submitting, setSubmitting] = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);

  // 流式生成状态
  const [streamState, setStreamState] = useState<StreamState | null>(null);
  const sseClientRef = useRef<SSEPostClient | null>(null);
  const [streamDone, setStreamDone] = useState(false);
  const [relatedCards, setRelatedCards] = useState<PlotCardWithLinks[]>([]);
  const [loadingCards, setLoadingCards] = useState(false);
  const streamContentRef = useRef<HTMLTextAreaElement>(null);

  // 批量生成
  const [showBatchModal, setShowBatchModal] = useState(false);
  const [batchFrom, setBatchFrom] = useState(1);
  const [batchTo, setBatchTo] = useState(1);
  const [batchStatus, setBatchStatus] = useState<BatchStatusState | null>(null);
  const batchCancelRef = useRef(false);

  // 分析中的章节
  const [analyzingIds, setAnalyzingIds] = useState<Set<string>>(new Set());

  // 场景生成
  const [sceneTarget, setSceneTarget] = useState<{ outlineId: string; title: string } | null>(null);

  // 从章纲同步
  const [syncing, setSyncing] = useState(false);

  const handleSyncFromOutlines = async () => {
    if (!currentProject) return;
    setSyncing(true);
    try {
      const res = await chapterApi.syncFromOutlines(currentProject.id);
      if (res.created > 0) {
        toast.success(res.message);
        await refreshChapters();
      } else if (res.total_outlines === 0) {
        toast.info('当前项目还没有章纲，请先在「故事大纲」→「章纲」中创建');
      } else {
        toast.info('所有章纲已有对应章节，无需同步');
      }
    } catch {
      toast.error('同步失败');
    } finally {
      setSyncing(false);
    }
  };

  // AI 生成配置弹窗
  const [showGenModal, setShowGenModal] = useState(false);
  const [genTarget, setGenTarget] = useState<{ chapter: Chapter; isRegenerate: boolean } | null>(null);
  const [genConfig, setGenConfig] = useState({
    style_id: undefined as number | undefined,
    target_word_count: 3000,
    enable_mcp: true,
    selected_plugins: [] as string[],
  });
  const [genCheck, setGenCheck] = useState<ChapterCanGenerateResponse | null>(null);
  const [styles, setStyles] = useState<WritingStyle[]>([]);
  const [stylesLoaded, setStylesLoaded] = useState(false);

  const loadStyles = useCallback(async () => {
    if (stylesLoaded || !currentProject?.id) return;
    try {
      const res = await writingStyleApi.getProjectStyles(currentProject.id);
      setStyles(res.styles || []);
      setStylesLoaded(true);
    } catch { /* ignore */ }
  }, [currentProject?.id, stylesLoaded]);

  const loadRelatedCardsForChapter = useCallback(async (chapter: Chapter) => {
    setRelatedCards([]);
    setLoadingCards(Boolean(chapter.chapter_outline_id));

    if (!chapter.chapter_outline_id) {
      setLoadingCards(false);
      return;
    }

    try {
      const cards = await chapterOutlineLinkApi.getPlotCards(chapter.chapter_outline_id);
      setRelatedCards(cards || []);
    } catch {
      setRelatedCards([]);
    } finally {
      setLoadingCards(false);
    }
  }, []);

  const closeGenerateModal = useCallback(() => {
    setShowGenModal(false);
    setGenTarget(null);
    setGenCheck(null);
    setRelatedCards([]);
    setLoadingCards(false);
  }, []);

  const buildChapterGenerateRequest = useCallback((): ChapterGenerateRequest => ({
    style_id: genConfig.style_id,
    target_word_count: genConfig.target_word_count,
    enable_mcp: genConfig.enable_mcp,
    selected_plugins: genConfig.enable_mcp && genConfig.selected_plugins.length > 0
      ? genConfig.selected_plugins
      : undefined,
  }), [genConfig]);

  const openGenerateModal = useCallback(async (chapter: Chapter, isRegenerate: boolean) => {
    setGenCheck(null);
    setRelatedCards([]);
    setLoadingCards(Boolean(chapter.chapter_outline_id));

    try {
      const check = await chapterApi.checkCanGenerate(chapter.id);
      if (!check.can_generate) {
        toast.error(check.reason || '当前不满足生成条件');
        setLoadingCards(false);
        return;
      }

      setGenCheck(check);
      setGenTarget({ chapter, isRegenerate });
      setShowGenModal(true);
      loadStyles();
      await loadRelatedCardsForChapter(chapter);
    } catch {
      setLoadingCards(false);
      toast.error('生成条件检查失败');
    }
  }, [loadRelatedCardsForChapter, loadStyles]);

  // 内容预览
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState<Record<string, string>>({});
  const [loadingPreview, setLoadingPreview] = useState<string | null>(null);

  const togglePreview = async (chapter: Chapter) => {
    if (batchStatus?.status === 'running' && batchStatus.currentChapterId !== chapter.id) {
      return;
    }
    if (expandedId === chapter.id) { setExpandedId(null); return; }
    setExpandedId(chapter.id);
    if (previewContent[chapter.id]) return;
    setLoadingPreview(chapter.id);
    try {
      const detail = await chapterApi.getChapter(chapter.id);
      setPreviewContent(prev => ({ ...prev, [chapter.id]: detail.content || '暂无内容' }));
    } catch { setPreviewContent(prev => ({ ...prev, [chapter.id]: '加载失败' })); }
    finally { setLoadingPreview(null); }
  };

  useEffect(() => {
    if (currentProject?.id) refreshChapters();
  }, [currentProject?.id, refreshChapters]);

  // 清理
  useEffect(() => {
    return () => {
      batchCancelRef.current = true;
      sseClientRef.current?.abort();
    };
  }, []);

  const sorted = [...chapters].sort((a, b) => a.chapter_number - b.chapter_number);

  const openAdd = useCallback(() => {
    setGenTarget(null);
    setGenCheck(null);
    setRelatedCards([]);
    setEditingId(null);
    setForm({ title: '', chapter_number: sorted.length > 0 ? sorted[sorted.length - 1].chapter_number + 1 : 1, content: '' });
    setShowModal(true);
  }, [sorted]);

  const openEdit = useCallback(async (c: Chapter) => {
    setGenTarget(null);
    setGenCheck(null);
    setRelatedCards([]);
    setEditingId(c.id);
    setForm({ title: c.title, chapter_number: c.chapter_number, content: '' });
    setShowModal(true);
    setLoadingContent(true);
    try {
      const detail = await chapterApi.getChapter(c.id);
      setForm(prev => ({ ...prev, content: detail.content || '' }));
    } catch {
      toast.error('加载章节内容失败');
    } finally {
      setLoadingContent(false);
    }
  }, []);

  const handleSubmit = async () => {
    if (!currentProject || !form.title.trim()) return;
    setSubmitting(true);
    try {
      if (editingId) {
        await updateChapter(editingId, { title: form.title, content: form.content || undefined });
        toast.success('章节已更新');
      } else {
        await createChapter({
          project_id: currentProject.id,
          title: form.title,
          chapter_number: form.chapter_number,
          content: form.content || undefined,
        });
        toast.success('章节已创建');
      }
      setShowModal(false);
    } catch {
      toast.error(editingId ? '更新失败' : '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string, title: string) => {
    if (!confirm(`确定删除章节「${title}」吗？`)) return;
    try {
      await deleteChapter(id);
      toast.success('章节已删除');
    } catch {
      toast.error('删除失败');
    }
  };

  // ========== 1. AI 生成前检查 + 2. 流式生成 ==========
  const handleGenerate = async (chapter: Chapter) => {
    await openGenerateModal(chapter, false);
  };

  // ========== 3. 重新生成 ==========
  const handleRegenerate = async (chapter: Chapter) => {
    if (!confirm(`确定重新生成「${chapter.title}」的内容吗？现有内容将被覆盖。`)) return;
    await openGenerateModal(chapter, true);
  };

  const confirmGenerate = async () => {
    if (!genTarget) return;
    const { chapter, isRegenerate } = genTarget;
    const endpoint = isRegenerate
      ? `/api/chapters/${chapter.id}/regenerate-stream`
      : `/api/chapters/${chapter.id}/generate-stream`;
    const requestBody = (isRegenerate
      ? {
          style_id: genConfig.style_id,
          target_word_count: genConfig.target_word_count,
        }
      : buildChapterGenerateRequest()) as Record<string, unknown>;
    setShowGenModal(false);
    setGenCheck(null);
    setStreamDone(false);
    try {
      await startStream({
        chapter,
        url: endpoint,
        requestBody,
        mode: 'single',
      });
    } catch (error) {
      if ((error as DOMException)?.name === 'AbortError') {
        return;
      }
    }
  };

  const startStream = useCallback(async ({
    chapter,
    url,
    requestBody,
    mode,
  }: {
    chapter: Chapter;
    url: string;
    requestBody: Record<string, unknown>;
    mode: 'single' | 'batch';
  }) => {
    sseClientRef.current?.abort();
    setExpandedId(chapter.id);
    setStreamDone(false);
    setPreviewContent(prev => ({ ...prev, [chapter.id]: '' }));
    await loadRelatedCardsForChapter(chapter);

    setStreamState({
      chapterId: chapter.id,
      chapterTitle: chapter.title,
      progress: 0,
      message: mode === 'batch' ? '准备串行生成…' : '准备生成…',
      content: '',
      mode,
    });

    const client = new SSEPostClient(url, requestBody, {
      onProgress: (message, progress) => {
        setStreamState(prev => prev ? { ...prev, message, progress } : null);
        if (mode === 'batch') {
          setBatchStatus(prev => {
            if (!prev || prev.status !== 'running') return prev;
            return {
              ...prev,
              progress: Math.min(((prev.completed + progress / 100) / prev.total) * 100, 99),
              message,
            };
          });
        }
      },
      onChunk: (chunk) => {
        setStreamState(prev => {
          if (!prev) return null;
          const updated = { ...prev, content: prev.content + chunk };
          requestAnimationFrame(() => {
            if (streamContentRef.current) {
              streamContentRef.current.scrollTop = streamContentRef.current.scrollHeight;
            }
          });
          return updated;
        });
      },
    });

    sseClientRef.current = client;
    try {
      await client.connect();
      const finalContent = client.getAccumulatedContent();
      setPreviewContent(prev => ({ ...prev, [chapter.id]: finalContent || prev[chapter.id] || '' }));
      setStreamDone(true);
      await refreshChapters();
      if (mode === 'single') {
        toast.success(`「${chapter.title}」生成完成`);
      }
    } catch (error) {
      if ((error as DOMException)?.name === 'AbortError') {
        throw error;
      }
      toast.error((error as Error)?.message || '生成失败');
      setStreamState(null);
      throw error;
    } finally {
      if (sseClientRef.current === client) {
        sseClientRef.current = null;
      }
    }
  }, [loadRelatedCardsForChapter, refreshChapters]);

  const waitForChapterAnalysis = useCallback(async (chapter: Chapter) => {
    const startAt = Date.now();
    setAnalyzingIds(prev => new Set(prev).add(chapter.id));

    try {
      while (true) {
        if (batchCancelRef.current) {
          throw new DOMException('Request aborted', 'AbortError');
        }

        const status = await chapterApi.getAnalysisStatus(chapter.id);
        const progress = Math.max(0, Math.min(100, status.progress ?? 0));
        const waitingMessage = !status.has_task || status.status === 'none'
          ? `等待第 ${chapter.chapter_number} 章分析任务启动…`
          : `正在分析第 ${chapter.chapter_number} 章（${progress}%）`;

        setBatchStatus(prev => prev && prev.status === 'running' && prev.currentChapterId === chapter.id
          ? { ...prev, message: waitingMessage }
          : prev);
        setStreamState(prev => prev && prev.chapterId === chapter.id
          ? { ...prev, message: waitingMessage, progress: 100 }
          : prev);

        if (status.status === 'completed') {
          await refreshChapters();
          setBatchStatus(prev => prev && prev.status === 'running' && prev.currentChapterId === chapter.id
            ? { ...prev, message: `第 ${chapter.chapter_number} 章分析完成，开始整理记忆…` }
            : prev);
          return;
        }

        if (status.status === 'failed') {
          throw new Error(status.error_message || `第 ${chapter.chapter_number} 章分析失败`);
        }

        if (Date.now() - startAt > ANALYSIS_TIMEOUT_MS) {
          throw new Error(`第 ${chapter.chapter_number} 章分析等待超时，请重试`);
        }

        await new Promise(resolve => setTimeout(resolve, ANALYSIS_POLL_INTERVAL_MS));
      }
    } finally {
      setAnalyzingIds(prev => {
        const next = new Set(prev);
        next.delete(chapter.id);
        return next;
      });
    }
  }, [refreshChapters]);

  const closeStreamPanel = () => {
    setStreamState(null);
    setStreamDone(false);
    setRelatedCards([]);
    setGenTarget(null);
    setLoadingCards(false);
  };

  const cancelStream = () => {
    if (batchStatus?.status === 'running') {
      cancelBatch();
      return;
    }
    sseClientRef.current?.abort();
    sseClientRef.current = null;
    setStreamState(null);
    setStreamDone(false);
    setRelatedCards([]);
    setLoadingCards(false);
    toast.info('已取消生成');
  };

  // ========== 4. 批量生成 ==========
  const openBatchModal = () => {
    setBatchFrom(sorted.length > 0 ? sorted[0].chapter_number : 1);
    setBatchTo(sorted.length > 0 ? sorted[sorted.length - 1].chapter_number : 5);
    setShowBatchModal(true);
  };

  const startBatchGenerate = async () => {
    if (!currentProject) return;

    const chaptersInRange = sorted.filter(
      chapter => chapter.chapter_number >= batchFrom && chapter.chapter_number <= batchTo
    );
    const chaptersToGenerate = chaptersInRange.filter(
      chapter => !(chapter.status === 'completed' && chapter.word_count > 0)
    );
    const skippedCount = chaptersInRange.length - chaptersToGenerate.length;

    if (chaptersToGenerate.length === 0) {
      toast.info('所选范围内没有待生成的章节');
      return;
    }

    batchCancelRef.current = false;
    setShowBatchModal(false);
    setBatchStatus({
      status: 'running',
      total: chaptersToGenerate.length,
      completed: 0,
      progress: 0,
      currentChapterId: null,
      currentChapterNumber: null,
      currentChapterTitle: null,
      message: skippedCount > 0 ? `已自动跳过 ${skippedCount} 章已有内容的章节` : '准备开始串行生成…',
      skippedCount,
    });

    if (skippedCount > 0) {
      toast.info(`已自动跳过 ${skippedCount} 章已有内容的章节`);
    }

    try {
      for (let index = 0; index < chaptersToGenerate.length; index += 1) {
        const chapter = chaptersToGenerate[index];

        if (batchCancelRef.current) {
          break;
        }

        setBatchStatus(prev => prev ? {
          ...prev,
          currentChapterId: chapter.id,
          currentChapterNumber: chapter.chapter_number,
          currentChapterTitle: chapter.title,
          message: `正在生成第 ${chapter.chapter_number} 章`,
          progress: (prev.completed / prev.total) * 100,
        } : prev);

        await startStream({
          chapter,
          url: `/api/chapters/${chapter.id}/generate-stream`,
          requestBody: {
            target_word_count: 3000,
            enable_mcp: true,
          },
          mode: 'batch',
        });

        await waitForChapterAnalysis(chapter);

        if (batchCancelRef.current) {
          break;
        }

        setBatchStatus(prev => prev ? {
          ...prev,
          completed: index + 1,
          progress: ((index + 1) / prev.total) * 100,
          message: `已完成 ${index + 1} / ${prev.total} 章`,
        } : prev);
      }

      if (batchCancelRef.current) {
        return;
      }

      setBatchStatus(prev => prev ? {
        ...prev,
        status: 'completed',
        completed: prev.total,
        progress: 100,
        message: `批量串行生成完成，共完成 ${prev.total} 章`,
      } : prev);
      toast.success('批量生成完成');
    } catch (error) {
      if ((error as DOMException)?.name === 'AbortError') {
        return;
      }

      setBatchStatus(prev => prev ? {
        ...prev,
        status: 'error',
        errorMessage: (error as Error)?.message || '批量生成失败',
        message: prev.currentChapterNumber
          ? `第 ${prev.currentChapterNumber} 章生成失败，批量任务已停止`
          : '批量生成失败',
      } : prev);
      toast.error((error as Error)?.message || '批量生成失败');
    }
  };

  const cancelBatch = () => {
    if (!batchStatus || batchStatus.status !== 'running') return;

    batchCancelRef.current = true;
    sseClientRef.current?.abort();
    sseClientRef.current = null;
    setStreamState(null);
    setStreamDone(false);
    setRelatedCards([]);
    setLoadingCards(false);
    setBatchStatus(prev => prev ? {
      ...prev,
      status: 'cancelled',
      message: '已取消批量生成',
    } : prev);
    toast.info('已取消批量生成');
  };

  // ========== 5. 触发分析 ==========
  const handleAnalyze = async (chapter: Chapter) => {
    setAnalyzingIds(prev => new Set(prev).add(chapter.id));
    try {
      await chapterApi.analyzeChapter(chapter.id);
      toast.success(`「${chapter.title}」分析已启动`);
    } catch {
      toast.error('分析启动失败');
    } finally {
      setAnalyzingIds(prev => {
        const next = new Set(prev);
        next.delete(chapter.id);
        return next;
      });
    }
  };

  const batchRunning = batchStatus?.status === 'running';
  const isGenerating = (id: string) => streamState?.chapterId === id && !streamDone;
  const completedPreviousChapters = genCheck?.previous_chapters.filter(chapter => chapter.has_content) ?? [];
  const previousChapterPreview = completedPreviousChapters.slice(-3);
  const relatedCardPreview = relatedCards.slice(0, 3);

  return (
    <div className="animate-fade-in space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-content">章节管理</h1>
          <p className="text-sm text-content-secondary mt-1">
            共 {chapters.length} 章
            {chapters.length > 0 && `，${chapters.reduce((s, c) => s + c.word_count, 0).toLocaleString()} 字`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSyncFromOutlines}
            disabled={syncing}
            className="inline-flex items-center gap-1.5 border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors disabled:opacity-50"
          >
            {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            从章纲同步
          </button>
          <button
            onClick={openBatchModal}
            disabled={batchRunning || (!!streamState && !streamDone)}
            className="inline-flex items-center gap-1.5 border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors disabled:opacity-50"
          >
            <Layers className="w-4 h-4" />
            批量生成
          </button>
          <button
            onClick={openAdd}
            className="inline-flex items-center gap-1.5 bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            新建章节
          </button>
        </div>
      </div>

      {/* 批量生成进度 */}
      {batchStatus && (
        <div className="bg-white border border-surface-border rounded-card px-4 py-3 space-y-3">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm">
                <span className="font-medium text-content">
                  {batchStatus.status === 'running'
                    ? `批量串行生成中 · ${batchStatus.completed}/${batchStatus.total}`
                    : batchStatus.status === 'completed'
                      ? `批量生成完成 · ${batchStatus.total}/${batchStatus.total}`
                      : batchStatus.status === 'cancelled'
                        ? '批量生成已取消'
                        : '批量生成失败'}
                </span>
                <span className="text-content-tertiary">
                  {Math.round(batchStatus.progress)}%
                </span>
              </div>
              <p className="text-xs text-content-secondary">
                {batchStatus.currentChapterNumber
                  ? `当前章节：第 ${batchStatus.currentChapterNumber} 章 · ${batchStatus.currentChapterTitle}`
                  : batchStatus.message}
              </p>
              {batchStatus.skippedCount > 0 && (
                <p className="text-xs text-content-tertiary">
                  已自动跳过 {batchStatus.skippedCount} 章已有内容的章节
                </p>
              )}
              {batchStatus.errorMessage && (
                <p className="text-xs text-red-500">{batchStatus.errorMessage}</p>
              )}
            </div>
            {batchStatus.status === 'running' && (
              <button onClick={cancelBatch} className="text-red-500 hover:text-red-600 text-xs">取消</button>
            )}
          </div>
          <div className="bg-surface-border rounded-full h-2">
            <div
              className={`rounded-full h-2 transition-all duration-300 ${
                batchStatus.status === 'completed'
                  ? 'bg-emerald-500'
                  : batchStatus.status === 'error'
                    ? 'bg-red-500'
                    : 'bg-brand'
              }`}
              style={{ width: `${Math.min(batchStatus.progress, 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* AI 创作面板 */}
      {streamState && (
        <div className="bg-white border border-brand/30 rounded-card shadow-lg overflow-hidden">
          {/* 头部 */}
          <div className="bg-gradient-to-r from-brand/5 to-transparent px-5 py-3 border-b border-surface-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-brand" />
                <span className="font-semibold text-content text-sm">
                  {batchRunning ? '批量串行生成：' : 'AI 创作中：'}{streamState.chapterTitle}
                </span>
                {streamState.mode === 'batch' && (
                  <span className="rounded-full bg-brand/10 px-2 py-0.5 text-[11px] font-medium text-brand">
                    串行队列
                  </span>
                )}
                <span className="text-xs text-content-tertiary">
                  {streamState.content.length.toLocaleString()} 字
                </span>
              </div>
              <div className="flex items-center gap-2">
                {(!streamDone || batchRunning) && (
                  <button onClick={cancelStream} className="text-red-500 hover:text-red-600 text-xs px-2 py-1 border border-red-200 rounded hover:bg-red-50 transition-colors">
                    {batchRunning ? '取消批量' : '取消生成'}
                  </button>
                )}
                {streamDone && !batchRunning && (
                  <button onClick={closeStreamPanel} className="text-content-secondary hover:text-content text-xs px-2 py-1 border border-surface-border rounded hover:bg-surface-hover transition-colors">
                    关闭面板
                  </button>
                )}
              </div>
            </div>
            {/* 进度条 */}
            <div className="bg-surface-border rounded-full h-1.5 mt-2">
              <div
                className={`h-1.5 rounded-full transition-all duration-300 ${streamDone ? 'bg-emerald-500' : 'bg-brand'}`}
                style={{ width: `${Math.min(streamState.progress, 100)}%` }}
              />
            </div>
            <p className="text-xs text-content-tertiary mt-1">{streamState.message}</p>
          </div>

          {/* 内容区域 */}
          <div className="flex" style={{ minHeight: '400px' }}>
            {/* 左侧：关联卡片 */}
            {(relatedCards.length > 0 || loadingCards) && (
              <div className="w-64 flex-shrink-0 border-r border-surface-border bg-surface/50 p-3 overflow-y-auto" style={{ maxHeight: '500px' }}>
                <div className="flex items-center gap-1.5 mb-2">
                  <LayoutGrid className="w-3.5 h-3.5 text-content-tertiary" />
                  <span className="text-xs font-medium text-content-secondary">关联剧情卡片</span>
                </div>
                {loadingCards ? (
                  <div className="flex items-center gap-1.5 text-xs text-content-tertiary py-4 justify-center">
                    <Loader2 className="w-3 h-3 animate-spin" />加载中…
                  </div>
                ) : (
                  <div className="space-y-2">
                    {relatedCards.map(card => (
                      <div key={card.id} className="bg-white rounded border border-surface-border p-2.5">
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand/10 text-brand font-medium">
                            {card.card_type === 'plot' ? '剧情' : card.card_type === 'character' ? '角色' : card.card_type === 'scene' ? '场景' : card.card_type === 'conflict' ? '冲突' : '其他'}
                          </span>
                          <span className="text-xs font-medium text-content truncate">{card.title}</span>
                        </div>
                        <p className="text-[11px] text-content-tertiary leading-relaxed line-clamp-3">
                          {card.content || '无内容'}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 右侧：流式内容编辑区 */}
            <div className="flex-1 flex flex-col">
              <textarea
                ref={streamContentRef}
                value={streamState.content}
                onChange={(e) => {
                  if (streamDone) {
                    setStreamState(prev => prev ? { ...prev, content: e.target.value } : null);
                  }
                }}
                readOnly={!streamDone}
                className="flex-1 w-full p-4 text-sm leading-relaxed resize-none outline-none font-[inherit] text-content"
                style={{ minHeight: '400px' }}
                placeholder={streamDone ? '生成完成，可直接编辑内容…' : 'AI 正在创作中…'}
              />
              {streamDone && (
                <div className="border-t border-surface-border px-4 py-2 flex items-center justify-between bg-surface/50">
                  <span className="text-xs text-content-tertiary">
                    生成完成，可在上方直接编辑。修改后点击「保存修改」更新到数据库。
                  </span>
                  <button
                    onClick={async () => {
                      if (!streamState) return;
                      try {
                        await updateChapter(streamState.chapterId, { content: streamState.content });
                        toast.success('内容已保存');
                        refreshChapters();
                      } catch {
                        toast.error('保存失败');
                      }
                    }}
                    className="bg-brand hover:bg-brand-600 text-white rounded-btn px-3 py-1.5 text-xs transition-colors"
                  >
                    保存修改
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 章节列表 */}
      {sorted.length > 0 ? (
        <div className="space-y-2">
          {sorted.map((c) => {
            const status = STATUS_MAP[c.status] || STATUS_MAP.draft;
            const activeStreamChapter = streamState?.chapterId === c.id;
            const generating = isGenerating(c.id);
            const currentBatchChapter = batchRunning && batchStatus?.currentChapterId === c.id;
            const analyzing = analyzingIds.has(c.id);
            return (
              <div
                key={c.id}
                className={`bg-white border rounded-card px-4 py-3 transition-all ${
                  currentBatchChapter
                    ? 'border-brand/40 shadow-card'
                    : 'border-surface-border hover:shadow-card'
                }`}
              >
                <div className="flex items-center gap-4">
                  {/* 序号 */}
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-surface flex items-center justify-center text-sm font-semibold text-content-secondary">
                    {c.chapter_number}
                  </div>
                  {/* 信息 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-content text-sm truncate">{c.title}</span>
                      <span className={`flex-shrink-0 text-xs px-2 py-0.5 rounded-full ${status.cls}`}>
                        {status.label}
                      </span>
                      {currentBatchChapter && (
                        <span className="flex-shrink-0 text-[11px] px-2 py-0.5 rounded-full bg-brand/10 text-brand">
                          串行生成中
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-content-tertiary mt-0.5">
                      {c.word_count > 0 ? `${c.word_count.toLocaleString()} 字` : '暂无内容'}
                    </p>
                  </div>
                  {/* 预览按钮 */}
                  {c.word_count > 0 && (
                    <button
                      onClick={() => togglePreview(c)}
                      disabled={batchRunning && batchStatus?.currentChapterId !== c.id}
                      className="p-1.5 text-content-tertiary hover:text-content rounded transition-colors flex-shrink-0"
                      title="预览内容"
                    >
                      {expandedId === c.id ? <ChevronUp className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  )}
                  {/* 操作 */}
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={() => openEdit(c)}
                      className="p-1.5 text-content-tertiary hover:text-brand rounded transition-colors"
                      title="编辑"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>

                    {/* AI 生成 / 重新生成 */}
                    {c.status === 'completed' && c.word_count > 0 ? (
                      <button
                        onClick={() => handleRegenerate(c)}
                        disabled={generating || batchRunning || (!!streamState && !streamDone)}
                        className="p-1.5 text-content-tertiary hover:text-orange-600 rounded transition-colors disabled:opacity-50"
                        title="重新生成"
                      >
                        {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                      </button>
                    ) : (
                      <button
                        onClick={() => handleGenerate(c)}
                        disabled={generating || batchRunning || (!!streamState && !streamDone)}
                        className="p-1.5 text-content-tertiary hover:text-blue-600 rounded transition-colors disabled:opacity-50"
                        title="AI 生成"
                      >
                        {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                      </button>
                    )}

                    {/* 场景生成（需要章纲关联） */}
                    {c.chapter_outline_id && (
                      <button
                        onClick={() => setSceneTarget({ outlineId: c.chapter_outline_id!, title: c.title })}
                        className="p-1.5 text-content-tertiary hover:text-emerald-600 rounded transition-colors"
                        title="场景生成"
                      >
                        <Film className="w-4 h-4" />
                      </button>
                    )}

                    {/* 分析（仅已完成章节） */}
                    {c.status === 'completed' && (
                      <button
                        onClick={() => handleAnalyze(c)}
                        disabled={analyzing}
                        className="p-1.5 text-content-tertiary hover:text-purple-600 rounded transition-colors disabled:opacity-50"
                        title="分析"
                      >
                        {analyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                      </button>
                    )}

                    <button
                      onClick={() => handleDelete(c.id, c.title)}
                      className="p-1.5 text-content-tertiary hover:text-red-600 rounded transition-colors"
                      title="删除"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                {/* 内容预览区 */}
                {expandedId === c.id && (
                  <div className="mt-2 pt-2 border-t border-surface-border">
                    {activeStreamChapter ? (
                      <div className="space-y-3 px-2 py-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium text-brand">
                            {batchRunning ? '正在按顺序生成本章…' : streamDone ? '本章生成完成' : '正在生成本章…'}
                          </span>
                          <span className="text-content-tertiary">
                            {Math.round(streamState?.progress ?? 0)}%
                          </span>
                        </div>
                        <div className="bg-surface-border rounded-full h-1.5">
                          <div
                            className={`h-1.5 rounded-full transition-all duration-300 ${streamDone ? 'bg-emerald-500' : 'bg-brand'}`}
                            style={{ width: `${Math.min(streamState?.progress ?? 0, 100)}%` }}
                          />
                        </div>
                        <p className="text-xs text-content-secondary">
                          {streamState?.message || 'AI 正在创作中…'}
                        </p>
                        <div className="text-sm text-content-secondary whitespace-pre-wrap max-h-72 overflow-y-auto leading-relaxed rounded-xl bg-surface/40 px-3 py-3">
                          {streamState?.content || 'AI 正在创作中…'}
                        </div>
                      </div>
                    ) : loadingPreview === c.id ? (
                      <div className="flex items-center gap-2 text-xs text-content-secondary py-2"><Loader2 className="w-3 h-3 animate-spin" />加载中...</div>
                    ) : (
                      <div className="text-sm text-content-secondary whitespace-pre-wrap max-h-60 overflow-y-auto leading-relaxed px-2 py-1">
                        {previewContent[c.id] || '暂无内容'}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        <div className="text-center py-16 space-y-4">
          <p className="text-content-secondary text-sm">还没有章节</p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={handleSyncFromOutlines}
              disabled={syncing}
              className="inline-flex items-center gap-1.5 bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm transition-colors disabled:opacity-50"
            >
              {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              从章纲同步
            </button>
            <span className="text-content-tertiary text-xs">或</span>
            <button
              onClick={openAdd}
              className="inline-flex items-center gap-1.5 border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors"
            >
              <Plus className="w-4 h-4" />
              手动新建
            </button>
          </div>
        </div>
      )}

      {/* 新建/编辑弹窗 */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-modal shadow-xl w-full max-w-3xl mx-4 animate-scale-in max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-6 pt-5 pb-3 flex-shrink-0">
              <h2 className="text-lg font-bold text-content">
                {editingId ? '编辑章节' : '新建章节'}
              </h2>
              <button onClick={() => setShowModal(false)} className="text-content-tertiary hover:text-content">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="px-6 pb-6 space-y-4 overflow-y-auto flex-1">
              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-content mb-1">章节标题</label>
                  <input
                    value={form.title}
                    onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
                    placeholder="输入章节标题"
                    className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
                  />
                </div>
                {!editingId && (
                  <div className="w-28">
                    <label className="block text-sm font-medium text-content mb-1">章节序号</label>
                    <input
                      type="number"
                      min={1}
                      value={form.chapter_number}
                      onChange={(e) => setForm((p) => ({ ...p, chapter_number: Number(e.target.value) }))}
                      className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
                    />
                  </div>
                )}
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-sm font-medium text-content">正文内容</label>
                  {loadingContent && (
                    <span className="text-xs text-content-tertiary inline-flex items-center gap-1">
                      <Loader2 className="w-3 h-3 animate-spin" />加载中…
                    </span>
                  )}
                  {form.content && (
                    <span className="text-xs text-content-tertiary">
                      {form.content.length.toLocaleString()} 字
                    </span>
                  )}
                </div>
                <textarea
                  value={form.content}
                  onChange={(e) => setForm((p) => ({ ...p, content: e.target.value }))}
                  placeholder="输入或粘贴章节正文内容…"
                  rows={16}
                  className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none resize-y leading-relaxed font-[inherit]"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setShowModal(false)}
                  className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={submitting || !form.title.trim()}
                  className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm transition-colors disabled:opacity-50"
                >
                  {submitting ? '保存中…' : '保存'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 场景生成弹窗 */}
      {sceneTarget && (
        <SceneGenerator
          chapterOutlineId={sceneTarget.outlineId}
          chapterTitle={sceneTarget.title}
          onClose={() => setSceneTarget(null)}
          onComplete={() => refreshChapters()}
        />
      )}

      {/* 批量生成弹窗 */}
      {/* AI 生成配置弹窗 */}
      {showGenModal && genTarget && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 px-4 py-8 sm:py-12">
          <div className="relative my-auto bg-white shadow-xl w-full max-w-2xl mx-4 animate-scale-in max-h-[calc(100vh-4rem)] flex flex-col">
            <div className="flex items-center justify-between px-6 pt-5 pb-3 flex-shrink-0 border-b border-surface-border">
              <h2 className="text-lg font-bold text-content">
                {genTarget.isRegenerate ? '重新生成' : 'AI 生成'}：{genTarget.chapter.title}
              </h2>
              <button onClick={closeGenerateModal} className="text-content-tertiary hover:text-content">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="px-6 py-5 space-y-4 overflow-y-auto flex-1">
              <div>
                <label className="block text-sm font-medium text-content mb-1">写作风格</label>
                <select
                  value={genConfig.style_id ?? ''}
                  onChange={(e) => setGenConfig(prev => ({
                    ...prev,
                    style_id: e.target.value ? Number(e.target.value) : undefined,
                  }))}
                  className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
                >
                  <option value="">不使用风格（默认）</option>
                  {styles.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-content mb-1">
                  目标字数：{genConfig.target_word_count.toLocaleString()} 字
                </label>
                <input
                  type="range"
                  min={500}
                  max={10000}
                  step={500}
                  value={genConfig.target_word_count}
                  onChange={(e) => setGenConfig(prev => ({ ...prev, target_word_count: Number(e.target.value) }))}
                  className="w-full accent-brand"
                />
                <div className="flex justify-between text-xs text-content-tertiary mt-1">
                  <span>500</span>
                  <span>3000</span>
                  <span>5000</span>
                  <span>10000</span>
                </div>
              </div>
              <MCPSelector
                value={{ enable: genConfig.enable_mcp, selected: genConfig.selected_plugins }}
                onChange={(val) => setGenConfig(prev => ({
                  ...prev,
                  enable_mcp: val.enable,
                  selected_plugins: val.selected,
                }))}
              />
              <div className="rounded-card border border-surface-border bg-surface/40 p-3 space-y-3">
                <div>
                  <p className="text-sm font-medium text-content">本次生成会参考的内容</p>
                  <p className="text-xs text-content-tertiary mt-1">
                    后端会自动组合章纲、前文、关联剧情卡片、项目设定和可选 MCP 检索结果来生成正文。
                  </p>
                </div>
                <div className="space-y-2 text-xs text-content-secondary">
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-medium text-content">章纲与项目设定</span>
                    <span>{genTarget.chapter.chapter_outline_id ? '已关联章纲' : '未关联章纲'}</span>
                  </div>
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-medium text-content">前文承接</span>
                    <span>
                      {completedPreviousChapters.length > 0
                        ? `已纳入 ${completedPreviousChapters.length} 章前文`
                        : '首章或暂无可参考前文'}
                    </span>
                  </div>
                  {previousChapterPreview.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {previousChapterPreview.map(chapter => (
                        <span key={chapter.id} className="rounded-full bg-white border border-surface-border px-2 py-0.5 text-[11px] text-content-secondary">
                          第 {chapter.chapter_number} 章：{chapter.title}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-medium text-content">关联剧情卡片</span>
                    <span>{loadingCards ? '加载中…' : relatedCards.length > 0 ? `${relatedCards.length} 张` : '暂无关联卡片'}</span>
                  </div>
                  {relatedCardPreview.length > 0 && (
                    <div className="space-y-1.5">
                      {relatedCardPreview.map(card => (
                        <div key={card.id} className="rounded border border-surface-border bg-white px-2 py-1.5">
                          <div className="text-[11px] font-medium text-content">{card.title}</div>
                          <div className="text-[11px] text-content-tertiary line-clamp-2 mt-0.5">
                            {card.content || '无卡片描述'}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="flex items-start justify-between gap-3">
                    <span className="font-medium text-content">MCP 外部参考</span>
                    <span>
                      {genConfig.enable_mcp
                        ? (genConfig.selected_plugins.length > 0
                          ? `已选 ${genConfig.selected_plugins.length} 个插件`
                          : '已启用，使用默认检索策略')
                        : '未启用'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2 px-6 py-3 border-t border-surface-border bg-white flex-shrink-0">
              <button
                onClick={closeGenerateModal}
                className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors"
              >
                取消
              </button>
              <button
                onClick={confirmGenerate}
                className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm transition-colors"
              >
                开始生成
              </button>
            </div>
          </div>
        </div>
      )}

      {showBatchModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-modal shadow-xl w-full max-w-sm mx-4 animate-scale-in">
            <div className="flex items-center justify-between px-6 pt-5 pb-3">
              <h2 className="text-lg font-bold text-content">批量生成</h2>
              <button onClick={() => setShowBatchModal(false)} className="text-content-tertiary hover:text-content">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="px-6 pb-6 space-y-4">
              <p className="text-sm text-content-secondary">
                选择要批量生成的章节范围（按章节序号）
              </p>
              <div className="rounded-card border border-surface-border bg-surface/40 px-3 py-2 text-xs text-content-secondary leading-6">
                系统会按章节顺序自动串行生成，并自动展开当前章节显示流式内容与进度。
                已有内容的章节会自动跳过，避免覆盖现有正文。
              </div>
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <label className="block text-sm font-medium text-content mb-1">起始章节</label>
                  <input
                    type="number"
                    min={sorted.length > 0 ? sorted[0].chapter_number : 1}
                    max={batchTo}
                    value={batchFrom}
                    onChange={(e) => setBatchFrom(Number(e.target.value))}
                    className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
                  />
                </div>
                <span className="text-content-tertiary mt-5">—</span>
                <div className="flex-1">
                  <label className="block text-sm font-medium text-content mb-1">结束章节</label>
                  <input
                    type="number"
                    min={batchFrom}
                    max={sorted.length > 0 ? sorted[sorted.length - 1].chapter_number : 1}
                    value={batchTo}
                    onChange={(e) => setBatchTo(Number(e.target.value))}
                    className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setShowBatchModal(false)}
                  className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={startBatchGenerate}
                  className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm transition-colors"
                >
                  开始生成
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
