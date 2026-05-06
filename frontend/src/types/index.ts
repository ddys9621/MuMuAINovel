// 用户类型定义
export interface User {
  user_id: string;
  username: string;
  display_name: string;
  avatar_url?: string;
  trust_level: number;
  is_admin: boolean;
  is_active?: boolean;
  linuxdo_id: string;
  created_at: string;
  last_login: string;
}

// 设置类型定义
export interface Settings {
  id: string;
  user_id: string;
  api_provider: string;
  api_key: string;
  api_base_url: string;
  llm_model: string;
  temperature: number;
  max_tokens: number;
  preferences?: string;
  created_at: string;
  updated_at: string;
}

export interface SettingsUpdate {
  api_provider?: string;
  api_key?: string;
  api_base_url?: string;
  llm_model?: string;
  temperature?: number;
  max_tokens?: number;
  preferences?: string;
}

// 项目类型定义
export interface Project {
  id: string;  // UUID字符串
  title: string;
  description?: string;
  theme?: string;
  genre?: string;
  target_words?: number;
  current_words: number;
  status: 'planning' | 'writing' | 'revising' | 'completed';
  wizard_status?: 'incomplete' | 'completed';
  wizard_step?: number;
  world_time_period?: string;
  world_location?: string;
  world_atmosphere?: string;
  world_rules?: string;
  chapter_count?: number;
  narrative_perspective?: string;
  character_count?: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  title: string;
  description?: string;
  theme?: string;
  genre?: string;
  target_words?: number;
  narrative_perspective?: string;
  chapter_count?: number;
  character_count?: number;
  wizard_status?: 'incomplete' | 'completed';
  wizard_step?: number;
  world_time_period?: string;
  world_location?: string;
  world_atmosphere?: string;
  world_rules?: string;
}

export interface ProjectUpdate {
  title?: string;
  description?: string;
  theme?: string;
  genre?: string;
  target_words?: number;
  status?: 'planning' | 'writing' | 'revising' | 'completed';
  world_time_period?: string;
  world_location?: string;
  world_atmosphere?: string;
  world_rules?: string;
  chapter_count?: number;
  narrative_perspective?: string;
  character_count?: number;
  // current_words 由章节内容自动计算，不在此接口中
}

// 向导专用的项目更新接口，包含向导流程控制字段
export interface ProjectWizardUpdate extends ProjectUpdate {
  wizard_status?: 'incomplete' | 'completed';
  wizard_step?: number;
}

// 项目创建向导
export interface ProjectWizardRequest {
  title: string;
  theme: string;
  genre?: string;
  chapter_count: number;
  narrative_perspective: string;
  character_count?: number;
  target_words?: number;
  world_building?: {
    time_period: string;
    location: string;
    atmosphere: string;
    rules: string;
  };
}

export interface WorldBuildingResponse {
  project_id: string;
  time_period: string;
  location: string;
  atmosphere: string;
  rules: string;
}

// 大纲类型定义
export interface Outline {
  id: string;
  project_id: string;
  title: string;
  content: string; // 故事前提（premise）
  version?: number;
  status?: string;
  editor_id?: string;
  is_active?: boolean;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface OutlineCreate {
  project_id: string;
  title: string;
  content: string; // 故事前提（premise）
  order_index: number;
}

export interface OutlineUpdate {
  title?: string;
  content?: string; // 故事前提（premise）
  status?: string;
  version?: number; // 用于乐观锁
}

// 角色类型定义
export interface Character {
  id: string;
  project_id: string;
  name: string;
  age?: string;
  gender?: string;
  is_organization: boolean;
  role_type?: string;
  personality?: string;
  background?: string;
  appearance?: string;
  relationships?: string;
  organization_type?: string;
  organization_purpose?: string;
  organization_members?: string;
  traits?: string;
  avatar_url?: string;
  // 组织扩展字段（从Organization表关联）
  power_level?: number;
  location?: string;
  motto?: string;
  color?: string;
  created_at: string;
  updated_at: string;
}

export interface CharacterUpdate {
  name?: string;
  age?: string;
  gender?: string;
  is_organization?: boolean;
  role_type?: string;
  personality?: string;
  background?: string;
  appearance?: string;
  relationships?: string;
  organization_type?: string;
  organization_purpose?: string;
  organization_members?: string;
  traits?: string;
  // 组织扩展字段
  power_level?: number;
  location?: string;
  motto?: string;
  color?: string;
}

// 章节类型定义
export interface Chapter {
  id: string;
  project_id: string;
  chapter_outline_id?: string;
  title: string;
  content?: string;
  summary?: string;
  chapter_number: number;
  word_count: number;
  status: 'draft' | 'writing' | 'completed';
  created_at: string;
  updated_at: string;
}

export interface ChapterCreate {
  project_id: string;
  chapter_outline_id?: string;
  title: string;
  chapter_number: number;
  content?: string;
  summary?: string;
  status?: 'draft' | 'writing' | 'completed';
}

export interface ChapterUpdate {
  title?: string;
  content?: string;
  // chapter_number 不允许修改，由大纲顺序决定
  summary?: string;
  // word_count 自动计算，不允许手动修改
  status?: 'draft' | 'writing' | 'completed';
}

// 章节生成请求类型
export interface ChapterGenerateRequest {
  style_id?: number;
  target_word_count?: number;
  enable_mcp?: boolean;
  selected_plugins?: string[];
}

// 章节生成检查响应
export interface ChapterCanGenerateResponse {
  can_generate: boolean;
  reason: string;
  previous_chapters: {
    id: string;
    chapter_number: number;
    title: string;
    has_content: boolean;
    word_count: number;
  }[];
  chapter_number: number;
}

// AI生成请求类型
export interface GenerateOutlineRequest {
  project_id: string;
  genre?: string;
  theme: string;
  chapter_count: number;
  narrative_perspective: string;
  world_context?: Record<string, unknown>;
  characters_context?: Character[];
  target_words?: number;
  requirements?: string;
  provider?: string;
  model?: string;
  // 续写功能新增字段
  mode?: 'auto' | 'new' | 'continue';
  story_direction?: string;
  plot_stage?: 'development' | 'climax' | 'ending';
  keep_existing?: boolean;
}

// 大纲重排序请求类型
export interface OutlineReorderItem {
  id: string;
  order_index: number;
}

export interface OutlineReorderRequest {
  orders: OutlineReorderItem[];
}

export interface GenerateCharacterRequest {
  project_id: string;
  name?: string;
  role_type?: string;
  background?: string;
  requirements?: string;
  provider?: string;
  model?: string;
  enable_mcp?: boolean;
  selected_plugins?: string[];
}

// 向导API响应类型
export interface GenerateCharactersResponse {
  message?: string;
  count?: number;
  batches?: number;
  characters: Character[];
}

export interface GenerateOutlineResponse {
  message?: string;
  outline?: Outline;
  outlines?: Outline[];
  total_chapters?: number;
}

// API响应类型
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

// 写作风格类型定义
export interface WritingStyle {
  id: number;
  project_id: string;
  name: string;
  style_type: 'preset' | 'custom';
  preset_id?: string;
  description?: string;
  prompt_content: string;
  is_default: boolean;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface WritingStyleCreate {
  project_id: string;
  name: string;
  style_type: 'preset' | 'custom';
  preset_id?: string;
  description?: string;
  prompt_content: string;
  is_default?: boolean;
}

export interface WritingStyleUpdate {
  name?: string;
  description?: string;
  prompt_content?: string;
  order_index?: number;
}

export interface PresetStyle {
  id: string;
  name: string;
  description: string;
  prompt_content: string;
}

export interface WritingStyleListResponse {
  styles: WritingStyle[];
  total: number;
}

export interface PaginationResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// 向导表单数据类型
export interface WizardBasicInfo {
  title: string;
  description: string;
  theme: string;
  genre: string | string[];
  chapter_count: number;
  narrative_perspective: string;
  character_count?: number;
  target_words?: number;
}

// API 错误响应类型
export interface ApiError {
  response?: {
    data?: {
      detail?: string;
    };
  };
  message?: string;
}

// 章节分析任务相关类型
export interface AnalysisTask {
  has_task: boolean;
  task_id: string | null;
  chapter_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'none';
  progress: number;
  error_message?: string | null;
  auto_recovered?: boolean;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

// 分析结果 - 钩子
export interface AnalysisHook {
  type: string;
  content: string;
  strength: number;
  position: string;
}

// 分析结果 - 伏笔
export interface AnalysisForeshadow {
  content: string;
  type: 'planted' | 'resolved';
  strength: number;
  subtlety: number;
  reference_chapter?: number;
}

// 分析结果 - 冲突
export interface AnalysisConflict {
  types: string[];
  parties: string[];
  level: number;
  description: string;
  resolution_progress: number;
}

// 分析结果 - 情感曲线
export interface AnalysisEmotionalArc {
  primary_emotion: string;
  intensity: number;
  curve: string;
  secondary_emotions: string[];
}

// 分析结果 - 角色状态
export interface AnalysisCharacterState {
  character_name: string;
  state_before: string;
  state_after: string;
  psychological_change: string;
  key_event: string;
  relationship_changes: Record<string, string>;
}

// 分析结果 - 情节点
export interface AnalysisPlotPoint {
  content: string;
  type: 'revelation' | 'conflict' | 'resolution' | 'transition';
  importance: number;
  impact: string;
}

// 分析结果 - 场景
export interface AnalysisScene {
  location: string;
  atmosphere: string;
  duration: string;
}

// 分析结果 - 评分
export interface AnalysisScores {
  pacing: number;
  engagement: number;
  coherence: number;
  overall: number;
}

// 完整分析数据 - 匹配后端PlotAnalysis模型
export interface AnalysisData {
  id: string;
  chapter_id: string;
  plot_stage: string;
  conflict_level: number;
  conflict_types: string[];
  emotional_tone: string;
  emotional_intensity: number;
  hooks: AnalysisHook[];
  hooks_count: number;
  foreshadows: AnalysisForeshadow[];
  foreshadows_planted: number;
  foreshadows_resolved: number;
  plot_points: AnalysisPlotPoint[];
  plot_points_count: number;
  character_states: AnalysisCharacterState[];
  scenes?: AnalysisScene[];
  pacing: string;
  overall_quality_score: number;
  pacing_score: number;
  engagement_score: number;
  coherence_score: number;
  analysis_report: string;
  suggestions: string[];
  dialogue_ratio: number;
  description_ratio: number;
  created_at: string;
}

// 记忆片段
export interface StoryMemory {
  id: string;
  type: 'hook' | 'foreshadow' | 'plot_point' | 'character_event';
  title: string;
  content: string;
  importance: number;
  tags: string[];
  is_foreshadow: 0 | 1 | 2; // 0=普通, 1=已埋下, 2=已回收
}

// 章节分析结果响应 - 匹配后端API返回
export interface ChapterAnalysisResponse {
  chapter_id: string;
  analysis: AnalysisData;  // 注意：后端返回的是analysis而不是analysis_data
  memories: StoryMemory[];
  narrative_state?: ChapterNarrativeState;
  consistency_audit?: ConsistencyAuditView;
  created_at: string;
}

export interface ChapterCausalLinkView {
  cause: string;
  event: string;
  effect: string;
  decision: string;
  importance: number;
  reversible: boolean;
  actor_names: string[];
  target_names: string[];
  evidence?: string | null;
}

export interface NarrativePromiseView {
  id: string;
  promise_type: 'foreshadow' | 'promise' | 'mystery' | 'conflict' | string;
  title: string;
  content: string;
  priority: 'low' | 'medium' | 'high' | 'critical' | string;
  status: 'open' | 'progressing' | 'resolved' | 'broken' | string;
  source_chapter_number?: number | null;
  resolved_chapter_number?: number | null;
  deadline_chapter?: number | null;
  owner_character_name?: string | null;
  target_character_name?: string | null;
  resolution_note?: string | null;
}

export interface TimelineEventView {
  id: string;
  event_type: string;
  title: string;
  description: string;
  location?: string | null;
  time_marker?: string | null;
  actor_names: string[];
  target_names: string[];
  public_visibility?: 'public' | 'private' | 'secret' | string;
}

export interface RelationshipGraphNode {
  id: string;
  label: string;
}

export interface RelationshipGraphEdge {
  source: string;
  target: string;
  delta: number;
  reason?: string | null;
  new_status?: string | null;
  intimacy_level?: number | null;
}

export interface RelationshipGraphView {
  nodes: RelationshipGraphNode[];
  edges: RelationshipGraphEdge[];
}

export interface ConsistencyAuditIssue {
  severity: 'critical' | 'high' | 'medium' | 'low' | string;
  issue_type: string;
  rule_code: string;
  title: string;
  details: string;
  evidence?: string | null;
  character_name?: string | null;
  signal_key?: string | null;
  reference_chapter_number?: number | null;
}

export interface ConsistencyAuditSummary {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface ConsistencyAuditView {
  summary: ConsistencyAuditSummary;
  issues: ConsistencyAuditIssue[];
}

export interface ChapterNarrativeState {
  causal_links: ChapterCausalLinkView[];
  promises: NarrativePromiseView[];
  timeline_events: TimelineEventView[];
  relationship_graph: RelationshipGraphView;
}

// 手动触发分析响应
export interface TriggerAnalysisResponse {
  task_id: string;
  chapter_id: string;
  status: string;
  message: string;
}

// MCP 插件类型定义 - 优化后只包含必要字段
export interface MCPPlugin {
  id: string;
  plugin_name: string;
  display_name: string;
  description?: string;
  plugin_type: 'http' | 'stdio';
  category: string;
  
  // HTTP类型字段
  server_url?: string;
  headers?: Record<string, string>;
  
  // Stdio类型字段
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  
  // 状态字段
  enabled: boolean;
  status: 'active' | 'inactive' | 'error';
  last_error?: string;
  last_test_at?: string;
  
  // 时间戳
  created_at: string;
}

export interface MCPPluginCreate {
  plugin_name: string;
  display_name?: string;
  description?: string;
  plugin_type: 'http' | 'stdio';
  server_url?: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  headers?: Record<string, string>;
  enabled?: boolean;
}

export interface MCPPluginUpdate {
  display_name?: string;
  description?: string;
  server_url?: string;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  headers?: Record<string, string>;
  enabled?: boolean;
}

export interface MCPTool {
  name: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
}

export interface MCPTestResult {
  success: boolean;
  message: string;
  tools?: MCPTool[];
  tools_count?: number;
  response_time_ms?: number;
  error?: string;
  error_type?: string;
  suggestions?: string[];
}

export interface MCPToolCallRequest {
  plugin_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
}

export interface MCPToolCallResponse {
  success: boolean;
  result?: unknown;
  error?: string;
}

// 剧情卡片类型定义
export interface PlotCard {
  id: string;
  project_id: string;
  outline_id?: string;
  chapter_outline_id?: string;
  title: string;
  content?: string;
  card_type: string;
  order_index?: number;
  tags?: string[];
  created_at: string;
  updated_at: string;
  // 关联字段（从API返回时可能包含）
  plot_lines?: PlotLine[];
  chapter_outlines?: ChapterOutline[];
  // 统计字段
  plot_line_count?: number;
  chapter_outline_count?: number;
}

export interface PlotCardCreate {
  project_id: string;
  outline_id?: string;
  chapter_outline_id?: string;
  title: string;
  content?: string;
  card_type: string;
  order_index?: number;
  tags?: string[];
}

export interface PlotCardUpdate {
  title?: string;
  content?: string;
  card_type?: string;
  order_index?: number;
  tags?: string[];
  chapter_outline_id?: string;
}

export interface PlotCardGenerateRequest {
  project_id: string;
  outline_id?: string;
  chapter_outline_id?: string;
  prompt?: string;
  card_type: string;
  count: number;
  extend_from_card_id?: string;
  enable_mcp?: boolean;
  selected_plugins?: string[];
}

export interface PlotCardReorderRequest {
  orders: Array<{
    id: string;
    order_index: number;
  }>;
}

export interface PlotCardListResponse {
  total: number;
  items: PlotCard[];
}

// 剧情线类型定义
export interface PlotLine {
  id: string;
  project_id: string;
  outline_id?: string;
  title: string;
  description?: string;
  line_type: string;
  order_index?: number;
  plot_cards?: string[];
  timeline_data?: TimelineData;
  estimated_chapters?: number;  // 预计章节数
  created_at: string;
  updated_at: string;
  // 关联字段（从API返回时可能包含）
  chapter_outlines?: ChapterOutline[];
  // 统计字段
  chapter_outline_count?: number;
  plot_card_count?: number;
}

export interface PlotLineCreate {
  project_id: string;
  outline_id?: string;
  title: string;
  description?: string;
  line_type: string;
  order_index?: number;
  plot_cards?: string[];
  timeline_data?: TimelineData;
  estimated_chapters?: number;  // 预计章节数
}

export interface PlotLineUpdate {
  title?: string;
  description?: string;
  line_type?: string;
  order_index?: number;
  plot_cards?: string[];
  timeline_data?: TimelineData;
  estimated_chapters?: number;  // 预计章节数
}

export interface PlotLineGenerateRequest {
  project_id: string;
  story_outline_id?: string;
  prompt?: string;
  line_type: string;
  based_on_cards?: string[];
  based_on_lines?: string[];
  extend_existing: boolean;
  count: number;
  enable_mcp?: boolean;
  selected_plugins?: string[];
}

export interface PlotLineReorderRequest {
  orders: Array<{
    id: string;
    order_index: number;
  }>;
}

export interface PlotLineListResponse {
  total: number;
  items: PlotLine[];
}

// 剧情线进度相关类型定义
export interface PlotLineBeatProgress {
  index: number;
  key?: string;
  title: string;
  description?: string;
  weight: number;
  coverage: number;
  status: 'completed' | 'in_progress' | 'not_started';
}

export interface PlotLineProgress {
  plot_line_id: string;
  plot_line_title: string;
  has_beats: boolean;
  total_progress: number | null;
  beats: PlotLineBeatProgress[];
  linked_chapters_count: number;
  message?: string;
}

// 时间线相关类型定义
export interface TimelineBeat {
  index: number;
  key: string;
  title: string;
  description?: string;
  weight: number;
}

export interface TimelineData {
  beats: TimelineBeat[];
}

// 节点覆盖度相关类型定义
export interface BeatCoverage {
  beat_index: number;
  coverage: number;  // 本章对该节点的贡献度(0-1,表示0%-100%)
}

export interface TimelineCoverageUpdate {
  beats_covered: BeatCoverage[];
}

// 节点贡献度分布
export interface BeatContributionChapter {
  chapter_id: string;
  chapter_number: number;
  chapter_title: string;
  coverage: number;
}

export interface BeatContribution {
  total_coverage: number;
  chapters: BeatContributionChapter[];
}

export interface BeatContributionsMap {
  [beat_index: number]: BeatContribution;
}

// 章纲类型定义
// 章纲类型定义 - 专业网文版
export interface ChapterOutline {
  id: string;
  project_id: string;
  plot_line_id?: string;
  chapter_number: number;
  title: string;
  // 场景信息（新增）
  scene?: string;                // 场景地点，如"拳击场→后台"
  pov?: string;                  // 视角角色名
  // 剧情信息
  plot_points?: string;          // 剧情要点（含情感变化）
  key_events?: string[];         // 关键事件，最后一条为章末钩子
  characters_involved?: string[];
  // 旧字段（保留兼容）
  summary?: string;              // 已废弃，保留兼容旧数据
  // 系统字段
  target_word_count: number;
  order_index?: number;
  created_at: string;
  updated_at: string;
  // 关联字段（从API返回时可能包含）
  plot_lines?: PlotLine[];
  plot_cards?: PlotCard[];
  // 统计字段
  plot_line_count?: number;
  plot_card_count?: number;
}

export interface ChapterOutlineCreate {
  project_id: string;
  plot_line_id?: string;
  chapter_number: number;
  title: string;
  // 场景信息（新增）
  scene?: string;
  pov?: string;
  // 剧情信息
  plot_points?: string;
  key_events?: string[];
  characters_involved?: string[];
  // 旧字段（保留兼容）
  summary?: string;
  // 系统字段
  target_word_count: number;
  order_index?: number;
}

export interface ChapterOutlineUpdate {
  chapter_number?: number;
  title?: string;
  // 场景信息（新增）
  scene?: string;
  pov?: string;
  // 剧情信息
  plot_points?: string;
  key_events?: string[];
  characters_involved?: string[];
  // 旧字段（保留兼容）
  summary?: string;
  // 系统字段
  target_word_count?: number;
  order_index?: number;
}

export interface ChapterOutlineGenerateRequest {
  project_id: string;
  plot_line_id?: string;
  prompt?: string;
  start_chapter: number;
  chapter_count: number;
  target_word_count: number;
  based_on_outline: boolean;
  enable_mcp?: boolean;
  selected_plugins?: string[];
  auto_generate_plot_cards?: boolean;
}

export interface ChapterOutlineReorderRequest {
  orders: Array<{
    id: string;
    order_index: number;
    chapter_number: number;
  }>;
}

export interface ChapterOutlineListResponse {
  total: number;
  items: ChapterOutline[];
}

export interface ChapterOutlineBatchCreateRequest {
  project_id: string;
  plot_line_id?: string;
  outlines: ChapterOutlineCreate[];
}

// ============================================
// 关联关系类型定义
// ============================================

// 章纲-剧情线关联
export interface ChapterOutlinePlotLineLink {
  id: string;
  chapter_outline_id: string;
  plot_line_id: string;
  role: 'main' | 'sub' | 'character';
  order_index?: number;
  timeline_coverage?: {
    beats_covered: BeatCoverage[];
  };
  created_at: string;
}

export interface ChapterOutlinePlotLineLinkCreate {
  plot_line_id: string;
  role: 'main' | 'sub' | 'character';
  order_index?: number;
}

export interface ChapterOutlinePlotLineLinkBatch {
  links: ChapterOutlinePlotLineLinkCreate[];
}

// 剧情卡片-剧情线关联
export interface PlotCardPlotLineLink {
  id: string;
  plot_card_id: string;
  plot_line_id: string;
  created_at: string;
}

export interface PlotCardPlotLineLinkBatch {
  plot_line_ids: string[];
}

// 剧情卡片-章纲关联
export interface PlotCardChapterOutlineLink {
  id: string;
  plot_card_id: string;
  chapter_outline_id: string;
  usage_type: 'reference' | 'used' | 'planned';
  usage_notes?: string;
  created_at: string;
  updated_at: string;
}

export interface PlotCardChapterOutlineLinkCreate {
  chapter_outline_id: string;
  usage_type: 'reference' | 'used' | 'planned';
  usage_notes?: string;
}

export interface PlotCardChapterOutlineLinkBatch {
  links: PlotCardChapterOutlineLinkCreate[];
}

export interface PlotCardChapterOutlineLinkUpdate {
  usage_type?: 'reference' | 'used' | 'planned';
  usage_notes?: string;
}

// 扩展响应类型（包含关联信息）
export interface PlotLineWithLinks {
  id: string;
  title: string;
  description?: string;
  line_type: string;
  chapter_count: number;
  card_count: number;
  link_id?: string;  // 章纲-剧情线关联ID（用于更新覆盖度）
  timeline_data?: TimelineData;  // 时间线数据
  timeline_coverage?: {  // 节点覆盖度数据
    beats_covered: BeatCoverage[];
  };
}

export interface ChapterOutlineWithLinks {
  id: string;
  chapter_number: number;
  title: string;
  summary?: string;
  plot_line_count: number;
  card_count: number;
}

export interface PlotCardWithLinks {
  id: string;
  title: string;
  content?: string;
  card_type: string;
  plot_line_count: number;
  chapter_count: number;
}

export interface LinkOverviewTopEntity {
  id: string;
  title: string;
  type: 'plot_line' | 'chapter_outline' | 'plot_card';
  totalLinks: number;
}

export type LinkGraphEntityType = 'project' | 'plot_line' | 'chapter_outline' | 'plot_card';

export interface LinkGraphNode {
  id: string;
  title: string;
  type: LinkGraphEntityType;
  level: number;
  description?: string;
  stats?: {
    chapterCount?: number;
    plotCardCount?: number;
    plotLineCount?: number;
  };
  expandable?: boolean;
  expanded?: boolean;
}

export interface LinkGraphEdge {
  id: string;
  source: string;
  target: string;
  relation: 'line-outline' | 'line-card' | 'outline-card' | 'outline-line' | 'card-line' | 'card-outline' | 'project-line';
  weight?: number;
}

export interface LinkGraphPayload {
  nodes: LinkGraphNode[];
  edges: LinkGraphEdge[];
}

// 关联管理请求类型
export interface LinkChapterOutlinesRequest {
  chapter_outline_ids: string[];
  role?: 'main' | 'sub' | 'character';
}

export interface LinkPlotCardsRequest {
  plot_card_ids: string[];
}

export interface LinkPlotLinesRequest {
  plot_line_ids: string[];
}

export interface UpdatePlotCardUsageRequest {
  usage_type: 'reference' | 'used' | 'planned';
  usage_notes?: string;
}

// 世界规则系统类型定义
export interface WorldRule {
  id: string;
  project_id: string;
  category: 'cultivation_realm' | 'equipment_template' | 'map_location';
  key: string;
  name: string;
  order_index: number;
  summary?: string;
  details?: string;
  created_at: string;
  updated_at: string;
}

export interface WorldRuleCreate {
  category: 'cultivation_realm' | 'equipment_template' | 'map_location';
  key: string;
  name: string;
  order_index: number;
  summary?: string;
  details?: string;
}

export interface WorldRuleUpdate {
  category?: 'cultivation_realm' | 'equipment_template' | 'map_location';
  key?: string;
  name?: string;
  order_index?: number;
  summary?: string;
  details?: string;
}

export interface WorldRuleListResponse {
  total: number;
  items: WorldRule[];
}

// ============================================
// 场景生成相关类型定义（场景级创作循环）
// ============================================

// 创建会话请求
export interface SceneSessionCreateRequest {
  chapter_outline_id: string;
  provider?: string;
  model?: string;
  enable_mcp?: boolean;
  selected_plugins?: string[];
  writing_style_id?: string;
  target_word_count?: number;
}

// 会话响应
export interface SceneSessionResponse {
  session_id: string;
  status: 'active' | 'completed' | 'expired' | 'cancelled';
  chapter_outline_id: string;
  created_at?: string;
  expires_at?: string;
}

// 会话状态响应
export interface SceneSessionStatusResponse {
  session_id: string;
  status: 'active' | 'completed' | 'expired' | 'cancelled';
  is_expired: boolean;
  total_word_count: number;
  scenes_count: number;
  created_at?: string;
  expires_at?: string;
}

// 剧情卡片状态（场景生成用）
export interface PlotCardSceneStatus {
  id: string;
  title: string;
  content?: string;
  generation_status: 'pending' | 'generating' | 'completed' | 'rejected';
  generated_content?: string;
  word_count_target: number;
  word_count_actual: number;
  generation_order: number;
}

// 生成场景请求
export interface GenerateSceneRequest {
  plot_card_id: string;
}

// 反馈请求
export interface SceneFeedbackRequest {
  plot_card_id: string;
  is_satisfied: boolean;
  feedback_text?: string;
}

// 重生成请求
export interface SceneRegenerateRequest {
  plot_card_id: string;
  optimization_hint?: string;
}

// 完成会话响应
export interface CompleteSessionResponse {
  session_id: string;
  status: string;
  content: string;
  total_word_count: number;
  scenes_count: number;
  completed_at: string;
}

// SSE 流式响应数据
export interface SceneStreamData {
  content?: string;
  done?: boolean;
  error?: string;
}
