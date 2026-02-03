/**
 * 全局数据刷新系统
 * 统一管理所有关联数据的刷新
 */
import { useCallback } from 'react';
import { usePlotLineSync, useChapterOutlineSync, usePlotCardSync } from '../store/plotHooks';

interface UseGlobalRefreshOptions {
  projectId?: string;
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}

export const useGlobalRefresh = (options: UseGlobalRefreshOptions = {}) => {
  const { projectId, onSuccess, onError } = options;
  
  const { refreshPlotLines } = usePlotLineSync();
  const { refreshChapterOutlines } = useChapterOutlineSync();
  const { refreshPlotCards } = usePlotCardSync();

  // 刷新所有数据
  const refreshAll = useCallback(async () => {
    if (!projectId) return;
    
    try {
      await Promise.all([
        refreshPlotLines(projectId),
        refreshChapterOutlines(projectId),
        refreshPlotCards(projectId),
      ]);
      
      onSuccess?.();
    } catch (error) {
      console.error('全局数据刷新失败:', error);
      onError?.(error as Error);
    }
  }, [projectId, refreshPlotLines, refreshChapterOutlines, refreshPlotCards, onSuccess, onError]);

  // 刷新剧情线相关数据
  const refreshPlotLineRelated = useCallback(async () => {
    if (!projectId) return;
    
    try {
      await Promise.all([
        refreshPlotLines(projectId),
        refreshChapterOutlines(projectId), // 章纲统计可能受影响
      ]);
      
      onSuccess?.();
    } catch (error) {
      console.error('剧情线相关数据刷新失败:', error);
      onError?.(error as Error);
    }
  }, [projectId, refreshPlotLines, refreshChapterOutlines, onSuccess, onError]);

  // 刷新章纲相关数据
  const refreshChapterOutlineRelated = useCallback(async () => {
    if (!projectId) return;
    
    try {
      await Promise.all([
        refreshChapterOutlines(projectId),
        refreshPlotLines(projectId), // 剧情线统计可能受影响
      ]);
      
      onSuccess?.();
    } catch (error) {
      console.error('章纲相关数据刷新失败:', error);
      onError?.(error as Error);
    }
  }, [projectId, refreshChapterOutlines, refreshPlotLines, onSuccess, onError]);

  // 刷新剧情卡片相关数据
  const refreshPlotCardRelated = useCallback(async () => {
    if (!projectId) return;
    
    try {
      await Promise.all([
        refreshPlotCards(projectId),
        refreshPlotLines(projectId), // 剧情线统计可能受影响
        refreshChapterOutlines(projectId), // 章纲统计可能受影响
      ]);
      
      onSuccess?.();
    } catch (error) {
      console.error('剧情卡片相关数据刷新失败:', error);
      onError?.(error as Error);
    }
  }, [projectId, refreshPlotCards, refreshPlotLines, refreshChapterOutlines, onSuccess, onError]);

  return {
    refreshAll,
    refreshPlotLineRelated,
    refreshChapterOutlineRelated,
    refreshPlotCardRelated,
  };
};

// 全局刷新事件系统
class GlobalRefreshEventSystem {
  private listeners: Set<() => void> = new Set();

  subscribe(callback: () => void) {
    this.listeners.add(callback);
    
    // 返回取消订阅函数
    return () => {
      this.listeners.delete(callback);
    };
  }

  emit() {
    this.listeners.forEach(callback => {
      try {
        callback();
      } catch (error) {
        console.error('全局刷新事件处理失败:', error);
      }
    });
  }
}

export const globalRefreshEvents = new GlobalRefreshEventSystem();
