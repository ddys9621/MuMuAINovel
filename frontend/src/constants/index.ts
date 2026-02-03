/**
 * 前端常量配置
 * 集中管理超时时间、轮询间隔等配置项
 */

// ============================================
// API 请求相关常量
// ============================================

/** API 请求超时时间（毫秒）- 3分钟 */
export const API_TIMEOUT = 180000;

/** API 请求重试次数 */
export const API_RETRY_COUNT = 3;

// ============================================
// 轮询相关常量
// ============================================

/** 轮询间隔时间（毫秒）- 2秒 */
export const POLLING_INTERVAL = 2000;

/** 轮询超时时间（毫秒）- 5分钟 */
export const POLLING_TIMEOUT = 300000;

/** 批量任务轮询间隔（毫秒）- 2秒 */
export const BATCH_POLLING_INTERVAL = 2000;

// ============================================
// SSE 相关常量
// ============================================

/** SSE 连接超时时间（毫秒）- 3分钟 */
export const SSE_TIMEOUT = 180000;

/** SSE 重连延迟（毫秒）- 1秒 */
export const SSE_RECONNECT_DELAY = 1000;

// ============================================
// UI 相关常量
// ============================================

/** 移动设备断点宽度（像素） */
export const MOBILE_BREAKPOINT = 768;

/** 消息提示显示时长（秒） */
export const MESSAGE_DURATION = 3;

/** 模态框关闭延迟（毫秒）- 用于显示最终状态 */
export const MODAL_CLOSE_DELAY = 2000;

// ============================================
// 会话相关常量
// ============================================

/** 会话检查间隔（毫秒）- 1分钟 */
export const SESSION_CHECK_INTERVAL = 60000;

/** 会话刷新阈值（分钟）- 剩余时间少于此值时刷新 */
export const SESSION_REFRESH_THRESHOLD_MINUTES = 30;

// ============================================
// 章节相关常量
// ============================================

/** 默认目标字数 */
export const DEFAULT_TARGET_WORD_COUNT = 3000;

/** 最小章节字数 */
export const MIN_CHAPTER_WORD_COUNT = 100;

/** 最大章节字数 */
export const MAX_CHAPTER_WORD_COUNT = 50000;

