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
  // V4.1 方案 C：桥段 ↔ 剧情线节点绑定字段
  plot_line_id?: string | null;
  beat_index?: number | null;
  beat_coverage_start?: number | null;
  beat_coverage_end?: number | null;
}

/** V4.1 方案 C：桥段规划模式 */
export type BridgePlanMode = 'by_plot_line' | 'free';

export interface PlanBridgesRequest {
  bridge_count?: number;
  model?: string;
  /** 'by_plot_line'（默认）按主线节点权重分配桥段；'free' 自由规划不绑节点 */
  mode?: BridgePlanMode;
}

export interface ExpandBridgeRequest {
  start_chapter_number: number;
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

/** T2.1 批量展开请求。 */
export interface ExpandAllBridgesRequest {
  model?: string;
  start_chapter_number?: number;
}

/** T2.1 批量展开响应。 */
export interface ExpandAllBridgesResponse {
  success: boolean;
  total: number;
  succeeded: string[];
  failed: Array<{ bridge_id: string; error: string }>;
  created_chapter_count: number;
}
