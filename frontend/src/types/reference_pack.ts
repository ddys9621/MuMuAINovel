/**
 * 拆书 V3 仿写：参考包类型定义
 *
 * 参见：@/agent-docs/features/book_dissect_v3_imitation_design.md
 * 后端 schema：@/backend/app/schemas/reference_pack.py
 */

export type ReferencePackStatus = 'generating' | 'ready' | 'partial' | 'failed';

export type ReferenceDimension =
  | 'methodology'
  | 'style'
  | 'structure'
  | 'archetypes'
  | 'worldbuilding'
  | 'synopsis' // V3.2：故事类型骨架（Story Bible 层）
  | 'entities' // V3.2-P2：实体类型分布/命名风格信号
  | 'relations' // V3.2-P2：关系类型频谱
  | 'events' // V3.2-P2：事件节奏与类型分布
  | 'corpus'; // tab 6：灵感语料（来自 V2 表）

export type ReferenceStrength = 'light' | 'medium' | 'deep';

/**
 * 参考包列表项（不含 5 tab 详细内容）
 */
export interface ReferencePackSummary {
  id: string;
  user_id: string;
  task_id: string;
  source_book_title: string;
  status: ReferencePackStatus;
  generated_dimensions: string[];
  error_message: string | null;
  attached_project_count: number;
  created_at: string;
  updated_at: string | null;
}

/**
 * 参考包详情（含 5 核心 tab + V3.2 synopsis）
 *
 * 所有 tab 内部为灵活的 dict，前端按需展示 prompt 字段。
 * 任一字段为 null 表示该维度未生成（partial 状态下常见）。
 * V3.2：synopsis 是「故事类型骨架」，充当 Story Bible 全局引导。
 */
export interface ReferencePackDetail extends ReferencePackSummary {
  methodology: Record<string, unknown> | null;
  style: Record<string, unknown> | null;
  structure: Record<string, unknown> | null;
  archetypes: Record<string, unknown> | null;
  worldbuilding: Record<string, unknown> | null;
  synopsis?: Record<string, unknown> | null; // V3.2 可选增强
  // V3.2-P2 模式三维度（纯聚合，不含具体名字）
  entities?: Record<string, unknown> | null;
  relations?: Record<string, unknown> | null;
  events?: Record<string, unknown> | null;
}

/**
 * 项目已挂载参考包列表项
 */
export interface ProjectReferencePackItem {
  id: string; // 关联表主键
  project_id: string;
  pack_id: string;
  pack_summary: ReferencePackSummary;
  default_dimensions: ReferenceDimension[];
  default_strength: ReferenceStrength;
  attached_at: string;
}

/**
 * 挂载参考包请求 body
 */
export interface AttachReferencePackRequest {
  pack_id: string;
  default_dimensions?: ReferenceDimension[];
  default_strength?: ReferenceStrength;
}

export interface UpdateAttachmentRequest {
  default_dimensions?: ReferenceDimension[];
  default_strength?: ReferenceStrength;
}

export interface AttachReferencePackResponse {
  attachment_id: string;
  project_id: string;
  pack_id: string;
  default_dimensions: ReferenceDimension[];
  default_strength: ReferenceStrength;
}

// ============================================================
// 5 个 tab 内容的"软约束"类型（实际仍为 Record<string, unknown>，
// 此处仅作 IDE 自动补全提示，方便组件渲染时识别字段名）
// ============================================================

export interface MethodologyData {
  golden_finger_pattern?: {
    type?: string;
    balance_mechanism?: string;
    evolution_pattern?: string;
    writing_tips?: string;
    [k: string]: unknown;
  } | null;
  opening_hook_pattern?: {
    hook_type?: string;
    first_chapter_strategy?: string;
    writing_tips?: string;
    [k: string]: unknown;
  } | null;
  facepunch_rhythm?: {
    small_facepunch_freq?: string;
    big_facepunch_freq?: string;
    three_elements_pattern?: string;
    writing_tips?: string;
    [k: string]: unknown;
  } | null;
  power_progression?: {
    system_type?: string;
    level_count?: number;
    pace?: string;
    writing_tips?: string;
    [k: string]: unknown;
  } | null;
  highlight_density?: {
    small_per_n_chapters?: number;
    medium_per_n_chapters?: number;
    big_per_n_chapters?: number;
    writing_tips?: string;
    [k: string]: unknown;
  } | null;
}

export interface StyleData {
  name?: string;
  description?: string;
  prompt_content?: string;
  traits?: string[];
}

export interface StructureData {
  opening_pattern?: Record<string, unknown> | null;
  midpoint_conflict_escalation?: Record<string, unknown> | null;
  ending_hook_pattern?: Record<string, unknown> | null;
}

export interface ArchetypeData {
  protagonist_archetype?: Record<string, unknown> | null;
  supporting_archetype?: Record<string, unknown> | null;
  antagonist_archetype?: Record<string, unknown> | null;
}

export interface WorldbuildingData {
  era_design?: Record<string, unknown> | null;
  location_hierarchy_design?: Record<string, unknown> | null;
  rule_balance_design?: Record<string, unknown> | null;
}

// ============================================================
// 一键仿写（V3 R5）
// 后端 schema：@/backend/app/schemas/imitation.py
// ============================================================

/**
 * 一键仿写请求体
 *
 * pack_ids / dimensions / strength 全部可省略：
 * - 省略 pack_ids → 使用项目所有已挂载且 ready 的参考包
 * - 省略 dimensions → 取所选 pack 挂载关联的 default_dimensions 并集
 * - 省略 strength → 取所选 pack 中"最深"者
 */
export interface ImitateChapterRequest {
  user_intent: string;
  target_chapter_id?: string;
  pack_ids?: string[];
  dimensions?: ReferenceDimension[];
  strength?: ReferenceStrength;
  target_word_count?: number;
  style_id?: number;
}

export interface ImitationPackUsage {
  pack_id: string;
  source_book_title: string;
  dimensions: string[];
}

export interface ImitatePromptPreview {
  system_prompt: string;
  user_prompt: string;
  used_packs: ImitationPackUsage[];
  used_dimensions: string[];
  strength: ReferenceStrength;
  target_word_count: number;
  project_context_chars: number;
  reference_chars: number;
  extras?: Record<string, unknown>;
}

/** SSE 流式事件载荷（meta 事件） */
export interface ImitationStreamMeta {
  type: 'meta';
  used_packs: ImitationPackUsage[];
  used_dimensions: string[];
  strength: ReferenceStrength;
  project_context_chars: number;
  reference_chars: number;
}
