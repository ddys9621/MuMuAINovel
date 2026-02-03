/**
 * 事件总线 - 用于跨组件/页面的数据同步通信
 * 
 * 使用方式：
 * - eventBus.on('eventName', callback) - 监听事件
 * - eventBus.off('eventName', callback) - 取消监听
 * - eventBus.emit('eventName', data) - 触发事件
 * - eventBus.once('eventName', callback) - 一次性监听
 */

type EventCallback = (data?: unknown) => void;

class EventBus {
  private events: Map<string, EventCallback[]> = new Map();

  /**
   * 监听事件
   */
  on(event: string, callback: EventCallback): void {
    if (!this.events.has(event)) {
      this.events.set(event, []);
    }
    this.events.get(event)!.push(callback);
  }

  /**
   * 取消监听事件
   */
  off(event: string, callback: EventCallback): void {
    const callbacks = this.events.get(event);
    if (callbacks) {
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  /**
   * 触发事件
   */
  emit(event: string, data?: unknown): void {
    const callbacks = this.events.get(event);
    if (callbacks) {
      callbacks.forEach(cb => {
        try {
          cb(data);
        } catch (error) {
          console.error(`事件处理器执行失败 [${event}]:`, error);
        }
      });
    }
  }

  /**
   * 一次性监听事件
   */
  once(event: string, callback: EventCallback): void {
    const onceCallback: EventCallback = (data) => {
      callback(data);
      this.off(event, onceCallback);
    };
    this.on(event, onceCallback);
  }

  /**
   * 移除某个事件的所有监听器
   */
  removeAllListeners(event?: string): void {
    if (event) {
      this.events.delete(event);
    } else {
      this.events.clear();
    }
  }

  /**
   * 获取事件的监听器数量
   */
  listenerCount(event: string): number {
    return this.events.get(event)?.length || 0;
  }
}

// 导出单例
export const eventBus = new EventBus();

// 导出事件名称常量，避免字符串拼写错误
export const EventNames = {
  // 项目相关事件
  PROJECT_CREATED: 'project:created',
  PROJECT_UPDATED: 'project:updated',
  PROJECT_DELETED: 'project:deleted',
  PROJECT_NEEDS_REFRESH: 'project:needsRefresh',

  // 角色相关事件
  CHARACTER_CREATED: 'character:created',
  CHARACTER_UPDATED: 'character:updated',
  CHARACTER_DELETED: 'character:deleted',
  CHARACTER_NEEDS_REFRESH: 'character:needsRefresh',

  // 大纲相关事件
  OUTLINE_CREATED: 'outline:created',
  OUTLINE_UPDATED: 'outline:updated',
  OUTLINE_DELETED: 'outline:deleted',
  OUTLINE_REORDERED: 'outline:reordered',
  OUTLINE_GENERATED: 'outline:generated',
  OUTLINE_NEEDS_REFRESH: 'outline:needsRefresh',

  // 章节相关事件
  CHAPTER_CREATED: 'chapter:created',
  CHAPTER_UPDATED: 'chapter:updated',
  CHAPTER_DELETED: 'chapter:deleted',
  CHAPTER_NEEDS_REFRESH: 'chapter:needsRefresh',
} as const;