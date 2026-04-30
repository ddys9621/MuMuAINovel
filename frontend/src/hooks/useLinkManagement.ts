/**
 * 关联管理自定义 Hook
 * 提供统一的关联操作接口和状态管理
 */
import { useState, useCallback, useEffect } from 'react';
import { toast } from 'sonner';
import {
  plotLineLinkApi,
  chapterOutlineLinkApi,
  plotCardLinkApi,
} from '../services/api';
import type {
  PlotLineWithLinks,
  ChapterOutlineWithLinks,
  PlotCardWithLinks,
} from '../types';

interface UseLinkManagementOptions {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}

/**
 * 剧情线关联管理 Hook
 */
export function usePlotLineLinks(lineId: string, options?: UseLinkManagementOptions) {
  const [chapterOutlines, setChapterOutlines] = useState<ChapterOutlineWithLinks[]>([]);
  const [plotCards, setPlotCards] = useState<PlotCardWithLinks[]>([]);
  const [loading, setLoading] = useState(false);
  const onSuccess = options?.onSuccess;
  const onError = options?.onError;

  // 加载关联的章纲
  const loadChapterOutlines = useCallback(async () => {
    if (!lineId) return;
    setLoading(true);
    try {
      const data = await plotLineLinkApi.getChapterOutlines(lineId);
      setChapterOutlines(data);
    } catch (error) {
      toast.error('加载关联章纲失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [lineId, onError]);

  // 加载关联的剧情卡片
  const loadPlotCards = useCallback(async () => {
    if (!lineId) return;
    setLoading(true);
    try {
      const data = await plotLineLinkApi.getPlotCards(lineId);
      setPlotCards(data);
    } catch (error) {
      toast.error('加载关联剧情卡片失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [lineId, onError]);

  // 自动加载关联数据
  useEffect(() => {
    if (lineId) {
      loadChapterOutlines();
      loadPlotCards();
    }
  }, [lineId, loadChapterOutlines, loadPlotCards]);

  // 关联章纲
  const linkChapterOutlines = useCallback(async (
    chapterOutlineIds: string[],
    role: string = 'main'
  ) => {
    setLoading(true);
    try {
      await plotLineLinkApi.linkChapterOutlines(lineId, { chapter_outline_ids: chapterOutlineIds, role });
      toast.success('关联章纲成功');
      await loadChapterOutlines();
      onSuccess?.();
    } catch (error) {
      toast.error('关联章纲失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [lineId, loadChapterOutlines, onError, onSuccess]);

  // 取消章纲关联
  const unlinkChapterOutlines = useCallback(async (chapterOutlineIds: string[]) => {
    setLoading(true);
    try {
      await plotLineLinkApi.unlinkChapterOutlines(lineId, chapterOutlineIds);
      toast.success('取消关联成功');
      await loadChapterOutlines();
      onSuccess?.();
    } catch (error) {
      toast.error('取消关联失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [lineId, loadChapterOutlines, onError, onSuccess]);

  // 关联剧情卡片
  const linkPlotCards = useCallback(async (plotCardIds: string[]) => {
    setLoading(true);
    try {
      await plotLineLinkApi.linkPlotCards(lineId, plotCardIds);
      toast.success('关联剧情卡片成功');
      await loadPlotCards();
      onSuccess?.();
    } catch (error) {
      toast.error('关联剧情卡片失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [lineId, loadPlotCards, onError, onSuccess]);

  // 取消剧情卡片关联
  const unlinkPlotCards = useCallback(async (plotCardIds: string[]) => {
    setLoading(true);
    try {
      await plotLineLinkApi.unlinkPlotCards(lineId, plotCardIds);
      toast.success('取消关联成功');
      await loadPlotCards();
      onSuccess?.();
    } catch (error) {
      toast.error('取消关联失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [lineId, loadPlotCards, onError, onSuccess]);

  return {
    chapterOutlines,
    plotCards,
    loading,
    loadChapterOutlines,
    loadPlotCards,
    linkChapterOutlines,
    unlinkChapterOutlines,
    linkPlotCards,
    unlinkPlotCards,
  };
}

/**
 * 章纲关联管理 Hook
 */
export function useChapterOutlineLinks(outlineId: string, options?: UseLinkManagementOptions) {
  const [plotLines, setPlotLines] = useState<PlotLineWithLinks[]>([]);
  const [plotCards, setPlotCards] = useState<PlotCardWithLinks[]>([]);
  const [loading, setLoading] = useState(false);
  const onSuccess = options?.onSuccess;
  const onError = options?.onError;

  // 加载关联的剧情线
  const loadPlotLines = useCallback(async () => {
    if (!outlineId) return;
    setLoading(true);
    try {
      const data = await chapterOutlineLinkApi.getPlotLines(outlineId);
      setPlotLines(data);
    } catch (error) {
      toast.error('加载关联剧情线失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [outlineId, onError]);

  // 加载关联的剧情卡片
  const loadPlotCards = useCallback(async () => {
    if (!outlineId) return;
    setLoading(true);
    try {
      const data = await chapterOutlineLinkApi.getPlotCards(outlineId);
      setPlotCards(data);
    } catch (error) {
      toast.error('加载关联剧情卡片失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [outlineId, onError]);

  // 自动加载关联数据
  useEffect(() => {
    if (outlineId) {
      loadPlotLines();
      loadPlotCards();
    }
  }, [outlineId, loadPlotCards, loadPlotLines]);

  // 关联剧情线
  const linkPlotLines = useCallback(async (
    plotLineIds: string[],
    role: string = 'main'
  ) => {
    if (!plotLineIds.length) return;
    setLoading(true);
    try {
      await chapterOutlineLinkApi.linkPlotLines(outlineId, {
        plot_line_ids: plotLineIds,
        role,
      });
      toast.success('关联剧情线成功');
      await loadPlotLines();
      
      onSuccess?.();
    } catch (error) {
      toast.error('关联剧情线失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [outlineId, loadPlotLines, onError, onSuccess]);

  // 取消剧情线关联
  const unlinkPlotLines = useCallback(async (plotLineIds: string[]) => {
    setLoading(true);
    try {
      await chapterOutlineLinkApi.unlinkPlotLines(outlineId, plotLineIds);
      toast.success('取消关联成功');
      await loadPlotLines();
      onSuccess?.();
    } catch (error) {
      toast.error('取消关联失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [outlineId, loadPlotLines, onError, onSuccess]);

  // 关联剧情卡片
  const linkPlotCards = useCallback(async (
    plotCardIds: string[],
    usageType: string = 'reference'
  ) => {
    setLoading(true);
    try {
      await chapterOutlineLinkApi.linkPlotCards(outlineId, { plot_card_ids: plotCardIds, usage_type: usageType });
      toast.success('关联剧情卡片成功');
      await loadPlotCards();
      onSuccess?.();
    } catch (error) {
      toast.error('关联剧情卡片失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [outlineId, loadPlotCards, onError, onSuccess]);

  // 取消剧情卡片关联
  const unlinkPlotCards = useCallback(async (plotCardIds: string[]) => {
    setLoading(true);
    try {
      await chapterOutlineLinkApi.unlinkPlotCards(outlineId, plotCardIds);
      toast.success('取消关联成功');
      await loadPlotCards();
      onSuccess?.();
    } catch (error) {
      toast.error('取消关联失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [outlineId, loadPlotCards, onError, onSuccess]);

  // 更新剧情卡片使用状态
  const updatePlotCardUsage = useCallback(async (
    cardId: string,
    usageType: string,
    usageNotes?: string
  ) => {
    setLoading(true);
    try {
      await chapterOutlineLinkApi.updatePlotCardUsage(outlineId, cardId, { usage_type: usageType, usage_notes: usageNotes });
      toast.success('更新使用状态成功');
      await loadPlotCards();
      onSuccess?.();
    } catch (error) {
      toast.error('更新使用状态失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [outlineId, loadPlotCards, onError, onSuccess]);

  return {
    plotLines,
    plotCards,
    loading,
    loadPlotLines,
    loadPlotCards,
    linkPlotLines,
    unlinkPlotLines,
    linkPlotCards,
    unlinkPlotCards,
    updatePlotCardUsage,
  };
}

/**
 * 剧情卡片关联管理 Hook
 */
export function usePlotCardLinks(cardId: string, options?: UseLinkManagementOptions) {
  const [plotLines, setPlotLines] = useState<PlotLineWithLinks[]>([]);
  const [chapterOutlines, setChapterOutlines] = useState<ChapterOutlineWithLinks[]>([]);
  const [loading, setLoading] = useState(false);
  const onSuccess = options?.onSuccess;
  const onError = options?.onError;

  // 加载关联的剧情线
  const loadPlotLines = useCallback(async () => {
    if (!cardId) return;
    setLoading(true);
    try {
      const data = await plotCardLinkApi.getPlotLines(cardId);
      setPlotLines(data);
    } catch (error) {
      toast.error('加载关联剧情线失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [cardId, onError]);

  // 加载关联的章纲
  const loadChapterOutlines = useCallback(async () => {
    if (!cardId) return;
    setLoading(true);
    try {
      const data = await plotCardLinkApi.getChapterOutlines(cardId);
      setChapterOutlines(data);
    } catch (error) {
      toast.error('加载关联章纲失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [cardId, onError]);

  // 自动加载关联数据
  useEffect(() => {
    if (cardId) {
      loadPlotLines();
      loadChapterOutlines();
    }
  }, [cardId, loadChapterOutlines, loadPlotLines]);

  // 关联剧情线
  const linkPlotLines = useCallback(async (plotLineIds: string[]) => {
    setLoading(true);
    try {
      await plotCardLinkApi.linkPlotLines(cardId, plotLineIds);
      toast.success('关联剧情线成功');
      await loadPlotLines();
      onSuccess?.();
    } catch (error) {
      toast.error('关联剧情线失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [cardId, loadPlotLines, onError, onSuccess]);

  // 取消剧情线关联
  const unlinkPlotLines = useCallback(async (plotLineIds: string[]) => {
    setLoading(true);
    try {
      await plotCardLinkApi.unlinkPlotLines(cardId, plotLineIds);
      toast.success('取消关联成功');
      await loadPlotLines();
      onSuccess?.();
    } catch (error) {
      toast.error('取消关联失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [cardId, loadPlotLines, onError, onSuccess]);

  // 关联章纲
  const linkChapterOutlines = useCallback(async (
    links: Array<{ chapter_outline_id: string; usage_type: string; usage_notes?: string }>
  ) => {
    setLoading(true);
    try {
      await plotCardLinkApi.linkChapterOutlines(cardId, links);
      toast.success('关联章纲成功');
      await loadChapterOutlines();
      onSuccess?.();
    } catch (error) {
      toast.error('关联章纲失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [cardId, loadChapterOutlines, onError, onSuccess]);

  // 取消章纲关联
  const unlinkChapterOutlines = useCallback(async (chapterOutlineIds: string[]) => {
    setLoading(true);
    try {
      await plotCardLinkApi.unlinkChapterOutlines(cardId, chapterOutlineIds);
      toast.success('取消关联成功');
      await loadChapterOutlines();
      onSuccess?.();
    } catch (error) {
      toast.error('取消关联失败');
      onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [cardId, loadChapterOutlines, onError, onSuccess]);

  return {
    plotLines,
    chapterOutlines,
    loading,
    loadPlotLines,
    loadChapterOutlines,
    linkPlotLines,
    unlinkPlotLines,
    linkChapterOutlines,
    unlinkChapterOutlines,
  };
}
