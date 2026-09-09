/**
 * V4.1 K2 桥段四章结构 - 前端类型定义
 *
 * 对应后端 PlotBridge model（详见 backend/app/models/plot_bridge.py）
 */

export type BridgePosition = 'intro' | 'build' | 'payoff' | 'aftermath';

export const BRIDGE_POSITION_LABEL: Record<BridgePosition, string> = {
  intro: 'C1 代入+信息差',
  build: 'C2 拉扯+开装',
  payoff: 'C3 兑现爽点',
  aftermath: 'C4 善后+下一目标',
};

export const BRIDGE_POSITION_RATIO: Record<BridgePosition, string> = {
  intro: '5:5',
  build: '9:1',
  payoff: '10:0',
  aftermath: '6:4',
};

export type BridgeStatus = 'draft' | 'ready' | 'generating' | 'completed';

export const BRIDGE_STATUS_LABEL: Record<BridgeStatus, string> = {
  draft: '草稿',
  ready: '就绪',
  generating: '生成中',
  completed: '已展开',
};

export const BRIDGE_STATUS_COLOR: Record<BridgeStatus, string> = {
  draft: 'default',
  ready: 'processing',
  generating: 'warning',
  completed: 'success',
};

/** 副线任务：支线/角色线节点按进度比例挂到主线桥段（由后端 bridge_slot_planner 计算） */
export interface SecondaryBeatTask {
  plot_line_id: string;
  line_title: string;
  line_type: string;
  beat_index: number;
  beat_title: string;
  beat_description: string;
  coverage_start: number;
  coverage_end: number;
}

export interface PlotBridge {
  id: string;
  project_id: string;
  bridge_number: number;
  title: string;
  goal: string;
  showoff_point: string;
  golden_finger_usage: string | null;
  c1_intro: string | null;
  c2_build: string | null;
  c3_payoff: string | null;
  c4_aftermath: string | null;
  next_bridge_hook: string | null;
  status: BridgeStatus;
  order_index: number | null;
  // 桥段 ↔ 主线节点绑定字段（代码写入，非 LLM）
  plot_line_id: string | null;
  beat_index: number | null;
  beat_coverage_start: number | null;
  beat_coverage_end: number | null;
  /** 副线任务列表 */
  secondary_beats: SecondaryBeatTask[];
  /** 确定性章号范围：第 4(n-1)+1 … 4n 章 */
  chapter_start: number;
  chapter_end: number;
}

/** GET /projects/{id}/bridges/plan-preview 返回的槽位表（纯计算，不写库） */
export interface BridgeSlotPreview {
  main_line_id: string;
  total_bridges: number;
  total_chapters: number;
  /** beat_index(字符串) → 该节点桥段数 */
  beat_quotas: Record<string, number>;
  slots: Array<{
    bridge_number: number;
    plot_line_id: string;
    beat_index: number;
    beat_title: string;
    beat_description: string;
    beat_weight: number;
    coverage_start: number;
    coverage_end: number;
    chapter_start: number;
    chapter_end: number;
    secondary: SecondaryBeatTask[];
  }>;
}

/** POST /projects/{id}/bridges/fill-stream 请求体 */
export interface FillBridgesRequest {
  model?: string;
  /** 只填充该主线节点的 draft 桥段 */
  beat_index?: number;
}

/** fill-stream 的 result 事件 */
export interface FillBridgesResult {
  type: 'done';
  filled: number;
  remaining_drafts: number;
}

export interface ExpandBridgeRequest {
  model?: string;
}

export interface ExpandBridgeResponse {
  success: boolean;
  bridge_id: string;
  chapter_count: number;
  chapter_ids: string[];
}

export interface UpdateBridgeRequest {
  title?: string;
  goal?: string;
  showoff_point?: string;
  golden_finger_usage?: string;
  c1_intro?: string;
  c2_build?: string;
  c3_payoff?: string;
  c4_aftermath?: string;
  next_bridge_hook?: string;
  status?: BridgeStatus;
}

/** 批量展开请求（按 bridge_number 顺序，首个失败即停止）。 */
export interface ExpandAllBridgesRequest {
  model?: string;
}

/** 批量展开响应。 */
export interface ExpandAllBridgesResponse {
  success: boolean;
  total: number;
  succeeded: string[];
  failed: Array<{ bridge_id: string; error: string }>;
  created_chapter_count: number;
}
