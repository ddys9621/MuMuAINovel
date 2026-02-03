/**
 * 关联管理自定义 Hook
 * 提供统一的关联操作接口和状态管理
 */
import { useState, useCallback, useEffect } from 'react';
import { message } from 'antd';
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

  // 加载关联的章纲
  const loadChapterOutlines = useCallback(async () => {
    if (!lineId) return;
    setLoading(true);
    try {
      const data = await plotLineLinkApi.getChapterOutlines(lineId);
      setChapterOutlines(data);
    } catch (error) {
      message.error('加载关联章纲失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [lineId, options]);

  // 加载关联的剧情卡片
  const loadPlotCards = useCallback(async () => {
    if (!lineId) return;
    setLoading(true);
    try {
      const data = await plotLineLinkApi.getPlotCards(lineId);
      setPlotCards(data);
    } catch (error) {
      message.error('加载关联剧情卡片失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [lineId, options]);

  // 自动加载关联数据
  useEffect(() => {
    if (lineId) {
      loadChapterOutlines();
      loadPlotCards();
    }
  }, [lineId]); // 只依赖lineId，避免无限循环

  // 关联章纲
  const linkChapterOutlines = useCallback(async (
    chapterOutlineIds: string[],
    role: string = 'main'
  ) => {
    setLoading(true);
    try {
      await plotLineLinkApi.linkChapterOutlines(lineId, { chapter_outline_ids: chapterOutlineIds, role });
      message.success('关联章纲成功');
      await loadChapterOutlines();
      options?.onSuccess?.();
    } catch (error) {
      message.error('关联章纲失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [lineId, loadChapterOutlines, options]);

  // 取消章纲关联
  const unlinkChapterOutlines = useCallback(async (chapterOutlineIds: string[]) => {
    setLoading(true);
    try {
      await plotLineLinkApi.unlinkChapterOutlines(lineId, chapterOutlineIds);
      message.success('取消关联成功');
      await loadChapterOutlines();
      options?.onSuccess?.();
    } catch (error) {
      message.error('取消关联失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [lineId, loadChapterOutlines, options]);

  // 关联剧情卡片
  const linkPlotCards = useCallback(async (plotCardIds: string[]) => {
    setLoading(true);
    try {
      await plotLineLinkApi.linkPlotCards(lineId, plotCardIds);
      message.success('关联剧情卡片成功');
      await loadPlotCards();
      options?.onSuccess?.();
    } catch (error) {
      message.error('关联剧情卡片失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [lineId, loadPlotCards, options]);

  // 取消剧情卡片关联
  const unlinkPlotCards = useCallback(async (plotCardIds: string[]) => {
    setLoading(true);
    try {
      await plotLineLinkApi.unlinkPlotCards(lineId, plotCardIds);
      message.success('取消关联成功');
      await loadPlotCards();
      options?.onSuccess?.();
    } catch (error) {
      message.error('取消关联失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [lineId, loadPlotCards, options]);

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

  // 加载关联的剧情线
  const loadPlotLines = useCallback(async () => {
    if (!outlineId) return;
    setLoading(true);
    try {
      const data = await chapterOutlineLinkApi.getPlotLines(outlineId);
      setPlotLines(data);
    } catch (error) {
      message.error('加载关联剧情线失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [outlineId, options]);

  // 加载关联的剧情卡片
  const loadPlotCards = useCallback(async () => {
    if (!outlineId) return;
    setLoading(true);
    try {
      const data = await chapterOutlineLinkApi.getPlotCards(outlineId);
      setPlotCards(data);
    } catch (error) {
      message.error('加载关联剧情卡片失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [outlineId, options]);

  // 自动加载关联数据
  useEffect(() => {
    if (outlineId) {
      loadPlotLines();
      loadPlotCards();
    }
  }, [outlineId]); // 只依赖outlineId，避免无限循环

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
      message.success('关联剧情线成功');
      await loadPlotLines();
      
      // 触发全局数据刷新事件
      const { globalRefreshEvents } = await import('./useGlobalRefresh');
      globalRefreshEvents.emit();
      
      options?.onSuccess?.();
    } catch (error) {
      message.error('关联剧情线失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [outlineId, loadPlotLines, options]);

  // 取消剧情线关联
  const unlinkPlotLines = useCallback(async (plotLineIds: string[]) => {
    setLoading(true);
    try {
      await chapterOutlineLinkApi.unlinkPlotLines(outlineId, plotLineIds);
      message.success('取消关联成功');
      await loadPlotLines();
      options?.onSuccess?.();
    } catch (error) {
      message.error('取消关联失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [outlineId, loadPlotLines, options]);

  // 关联剧情卡片
  const linkPlotCards = useCallback(async (
    plotCardIds: string[],
    usageType: string = 'reference'
  ) => {
    setLoading(true);
    try {
      await chapterOutlineLinkApi.linkPlotCards(outlineId, { plot_card_ids: plotCardIds, usage_type: usageType });
      message.success('关联剧情卡片成功');
      await loadPlotCards();
      options?.onSuccess?.();
    } catch (error) {
      message.error('关联剧情卡片失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [outlineId, loadPlotCards, options]);

  // 取消剧情卡片关联
  const unlinkPlotCards = useCallback(async (plotCardIds: string[]) => {
    setLoading(true);
    try {
      await chapterOutlineLinkApi.unlinkPlotCards(outlineId, plotCardIds);
      message.success('取消关联成功');
      await loadPlotCards();
      options?.onSuccess?.();
    } catch (error) {
      message.error('取消关联失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [outlineId, loadPlotCards, options]);

  // 更新剧情卡片使用状态
  const updatePlotCardUsage = useCallback(async (
    cardId: string,
    usageType: string,
    usageNotes?: string
  ) => {
    setLoading(true);
    try {
      await chapterOutlineLinkApi.updatePlotCardUsage(outlineId, cardId, { usage_type: usageType, usage_notes: usageNotes });
      message.success('更新使用状态成功');
      await loadPlotCards();
      options?.onSuccess?.();
    } catch (error) {
      message.error('更新使用状态失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [outlineId, loadPlotCards, options]);

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

  // 加载关联的剧情线
  const loadPlotLines = useCallback(async () => {
    if (!cardId) return;
    setLoading(true);
    try {
      const data = await plotCardLinkApi.getPlotLines(cardId);
      setPlotLines(data);
    } catch (error) {
      message.error('加载关联剧情线失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [cardId, options]);

  // 加载关联的章纲
  const loadChapterOutlines = useCallback(async () => {
    if (!cardId) return;
    setLoading(true);
    try {
      const data = await plotCardLinkApi.getChapterOutlines(cardId);
      setChapterOutlines(data);
    } catch (error) {
      message.error('加载关联章纲失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [cardId, options]);

  // 自动加载关联数据
  useEffect(() => {
    if (cardId) {
      loadPlotLines();
      loadChapterOutlines();
    }
  }, [cardId]); // 只依赖cardId，避免无限循环

  // 关联剧情线
  const linkPlotLines = useCallback(async (plotLineIds: string[]) => {
    setLoading(true);
    try {
      await plotCardLinkApi.linkPlotLines(cardId, plotLineIds);
      message.success('关联剧情线成功');
      await loadPlotLines();
      options?.onSuccess?.();
    } catch (error) {
      message.error('关联剧情线失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [cardId, loadPlotLines, options]);

  // 取消剧情线关联
  const unlinkPlotLines = useCallback(async (plotLineIds: string[]) => {
    setLoading(true);
    try {
      await plotCardLinkApi.unlinkPlotLines(cardId, plotLineIds);
      message.success('取消关联成功');
      await loadPlotLines();
      options?.onSuccess?.();
    } catch (error) {
      message.error('取消关联失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [cardId, loadPlotLines, options]);

  // 关联章纲
  const linkChapterOutlines = useCallback(async (
    links: Array<{ chapter_outline_id: string; usage_type: string; usage_notes?: string }>
  ) => {
    setLoading(true);
    try {
      await plotCardLinkApi.linkChapterOutlines(cardId, links);
      message.success('关联章纲成功');
      await loadChapterOutlines();
      options?.onSuccess?.();
    } catch (error) {
      message.error('关联章纲失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [cardId, loadChapterOutlines, options]);

  // 取消章纲关联
  const unlinkChapterOutlines = useCallback(async (chapterOutlineIds: string[]) => {
    setLoading(true);
    try {
      await plotCardLinkApi.unlinkChapterOutlines(cardId, chapterOutlineIds);
      message.success('取消关联成功');
      await loadChapterOutlines();
      options?.onSuccess?.();
    } catch (error) {
      message.error('取消关联失败');
      options?.onError?.(error as Error);
    } finally {
      setLoading(false);
    }
  }, [cardId, loadChapterOutlines, options]);

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
