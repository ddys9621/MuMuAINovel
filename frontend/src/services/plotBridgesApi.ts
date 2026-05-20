/**
 * V4.1 K2 桥段四章 - 前端 API 客户端
 *
 * 对应后端 backend/app/api/plot_bridges.py 的 6 个端点
 */
import api from '@/services/api';
import type {
  ExpandBridgeRequest,
  ExpandBridgeResponse,
  PlanBridgesRequest,
  PlotBridge,
  UpdateBridgeRequest,
} from '@/types/plot_bridge';

export const plotBridgesApi = {
  /**
   * 规划 N 个桥段（调 AI 注入 bridges + synopsis + methodology 维度）
   * POST /api/projects/{projectId}/bridges/plan
   */
  plan: (projectId: string, payload: PlanBridgesRequest = {}) =>
    api.post<unknown, PlotBridge[]>(
      `/projects/${projectId}/bridges/plan`,
      payload,
    ),

  /**
   * 列出项目下所有桥段
   * GET /api/projects/{projectId}/bridges
   */
  list: (projectId: string) =>
    api.get<unknown, PlotBridge[]>(`/projects/${projectId}/bridges`),

  /**
   * 获取单个桥段详情
   * GET /api/bridges/{bridgeId}
   */
  get: (bridgeId: string) =>
    api.get<unknown, PlotBridge>(`/bridges/${bridgeId}`),

  /**
   * 更新桥段（手工编辑 4 章卡片内容）
   * PATCH /api/bridges/{bridgeId}
   */
  update: (bridgeId: string, payload: UpdateBridgeRequest) =>
    api.patch<unknown, PlotBridge>(`/bridges/${bridgeId}`, payload),

  /**
   * 删除桥段
   * DELETE /api/bridges/{bridgeId}
   */
  delete: (bridgeId: string) =>
    api.delete<unknown, { success: boolean }>(`/bridges/${bridgeId}`),

  /**
   * 把单个桥段展开为 4 个 ChapterOutline
   * POST /api/bridges/{bridgeId}/expand
   */
  expand: (bridgeId: string, payload: ExpandBridgeRequest) =>
    api.post<unknown, ExpandBridgeResponse>(
      `/bridges/${bridgeId}/expand`,
      payload,
    ),
};
