import axios from 'axios';

interface MCPPluginSimpleCreate {
  config_json: string;
  enabled: boolean;
}
import { toast } from 'sonner';
import { ssePost } from '../utils/sseClient';
import type { SSEClientOptions } from '../utils/sseClient';
import type {
  User,
  Project,
  ProjectCreate,
  ProjectUpdate,
  WorldBuildingResponse,
  Outline,
  OutlineCreate,
  OutlineUpdate,
  Character,
  CharacterUpdate,
  Chapter,
  ChapterCreate,
  ChapterGenerateRequest,
  ChapterUpdate,
  GenerateCharacterRequest,
  GenerateCharactersResponse,
  GenerateOutlineResponse,
  Settings,
  SettingsUpdate,
  WritingStyle,
  WritingStyleCreate,
  WritingStyleUpdate,
  PresetStyle,
  WritingStyleListResponse,
  MCPPlugin,
  MCPPluginCreate,
  MCPPluginUpdate,
  MCPTestResult,
  MCPTool,
  MCPToolCallRequest,
  MCPToolCallResponse,
  PlotCard,
  PlotCardCreate,
  PlotCardUpdate,
  PlotCardGenerateRequest,
  PlotCardReorderRequest,
  PlotCardListResponse,
  PlotLine,
  PlotLineCreate,
  PlotLineUpdate,
  PlotLineGenerateRequest,
  PlotLineReorderRequest,
  PlotLineListResponse,
  PlotLineProgress,
  TimelineData,
  TimelineCoverageUpdate,
  ChapterOutline,
  ChapterOutlineCreate,
  ChapterOutlineUpdate,
  ChapterOutlineGenerateRequest,
  ChapterOutlineReorderRequest,
  ChapterOutlineListResponse,
  ChapterOutlineBatchCreateRequest,
  PlotLineWithLinks,
  ChapterOutlineWithLinks,
  PlotCardWithLinks,
  WorldRule,
  WorldRuleCreate,
  WorldRuleUpdate,
  WorldRuleListResponse,
  PaginationResponse,
  ChapterAnalysisResponse,
} from '../types';

type ChapterListApiResponse = Chapter[] | { items?: Chapter[] };

const api = axios.create({
  baseURL: '/api',
  timeout: 180000, // 3分钟超时
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

api.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    let errorMessage = '请求失败';
    
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data;
      
      switch (status) {
        case 400:
          errorMessage = data?.detail || '请求参数错误';
          break;
        case 401:
          errorMessage = '未授权，请先登录';
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }
          break;
        case 403:
          errorMessage = '没有权限访问';
          break;
        case 404:
          errorMessage = data?.detail || '请求的资源不存在';
          break;
        case 422:
          errorMessage = data?.detail || '请求参数验证失败';
          if (data?.errors) {
            console.error('验证错误详情:', data.errors);
          }
          break;
        case 500:
          errorMessage = data?.detail || '服务器内部错误';
          break;
        case 503:
          errorMessage = '服务暂时不可用，请稍后重试';
          break;
        default:
          errorMessage = data?.detail || data?.message || `请求失败 (${status})`;
      }
    } else if (error.request) {
      errorMessage = '网络错误，请检查网络连接';
    } else {
      errorMessage = error.message || '请求失败';
    }
    
    toast.error(errorMessage);
    console.error('API Error:', errorMessage, error);
    
    return Promise.reject(error);
  }
);

export const authApi = {
  getAuthConfig: () => api.get<unknown, { local_auth_enabled: boolean }>('/auth/config'),
  
  localLogin: (username: string, password: string) =>
    api.post<unknown, { success: boolean; message: string; user: User }>('/auth/local/login', { username, password }),
  
  getCurrentUser: () => api.get<unknown, User>('/auth/user'),
  
  getPasswordStatus: () => api.get<unknown, {
    has_password: boolean;
    has_custom_password: boolean;
    username: string | null;
    default_password: string | null;
  }>('/auth/password/status'),
  
  setPassword: (password: string) =>
    api.post<unknown, { success: boolean; message: string }>('/auth/password/set', { password }),
  
  refreshSession: () => api.post<unknown, { message: string; expire_at: number; remaining_minutes: number }>('/auth/refresh'),
  
  logout: () => api.post('/auth/logout'),
};

export const userApi = {
  getCurrentUser: () => api.get<unknown, User>('/users/current'),
  
  listUsers: () => api.get<unknown, User[]>('/users'),
  
  setAdmin: (userId: string, isAdmin: boolean) =>
    api.post('/users/set-admin', { user_id: userId, is_admin: isAdmin }),
  
  deleteUser: (userId: string) => api.delete(`/users/${userId}`),
  
  getUser: (userId: string) => api.get<unknown, User>(`/users/${userId}`),
  
  resetPassword: (userId: string, newPassword?: string) =>
    api.post<unknown, {
      message: string;
      user_id: string;
      username: string;
      default_password?: string;
    }>('/users/reset-password', { user_id: userId, new_password: newPassword }),
};

export const settingsApi = {
  getSettings: () => api.get<unknown, Settings>('/settings'),
  
  saveSettings: (data: SettingsUpdate) =>
    api.post<unknown, Settings>('/settings', data),
  
  updateSettings: (data: SettingsUpdate) =>
    api.put<unknown, Settings>('/settings', data),
  
  deleteSettings: () => api.delete<unknown, { message: string; user_id: string }>('/settings'),
  
  getAvailableModels: (params: { api_key: string; api_base_url: string; provider: string }) =>
    api.get<unknown, { provider: string; models: Array<{ value: string; label: string; description: string }>; count?: number }>('/settings/models', { params }),
  
  testApiConnection: (params: { api_key: string; api_base_url: string; provider: string; llm_model: string }) =>
    api.post<unknown, {
      success: boolean;
      message: string;
      response_time_ms?: number;
      provider?: string;
      model?: string;
      response_preview?: string;
      details?: Record<string, boolean>;
      error?: string;
      error_type?: string;
      suggestions?: string[];
    }>('/settings/test', params),
};

export const projectApi = {
  getProjects: () => api.get<unknown, { total: number; items: Project[] }>('/projects'),
  
  getProject: (id: string) => api.get<unknown, Project>(`/projects/${id}`),
  
  createProject: (data: ProjectCreate) => api.post<unknown, Project>('/projects', data),
  
  updateProject: (id: string, data: ProjectUpdate) =>
    api.put<unknown, Project>(`/projects/${id}`, data),
  
  deleteProject: (id: string) => api.delete(`/projects/${id}`),
  
  exportProject: (id: string) => {
    window.open(`/api/projects/${id}/export`, '_blank');
  },
  
  // 导出项目数据为JSON
  exportProjectData: async (id: string, options: { include_generation_history?: boolean; include_writing_styles?: boolean }) => {
    const response = await axios.post(
      `/api/projects/${id}/export-data`,
      options,
      {
        responseType: 'blob',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
    
    // 从响应头获取文件名
    const contentDisposition = response.headers['content-disposition'];
    let filename = 'project_export.json';
    if (contentDisposition) {
      const matches = /filename\*=UTF-8''(.+)/.exec(contentDisposition);
      if (matches && matches[1]) {
        filename = decodeURIComponent(matches[1]);
      }
    }
    
    // 创建下载链接
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
  
  // 验证导入文件
  validateImportFile: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<unknown, {
      valid: boolean;
      version: string;
      project_name?: string;
      statistics: Record<string, number>;
      errors: string[];
      warnings: string[];
    }>('/projects/validate-import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  // 导入项目
  importProject: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<unknown, {
      success: boolean;
      project_id?: string;
      message: string;
      statistics: Record<string, number>;
      warnings: string[];
    }>('/projects/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  // 数据一致性检查
  checkConsistency: (projectId: string, autoFix = true) =>
    api.post<unknown, Record<string, unknown>>(`/projects/${projectId}/check-consistency`, null, { params: { auto_fix: autoFix } }),

  // 修复组织记录
  fixOrganizations: (projectId: string) =>
    api.post<unknown, { success: boolean; message: string; fixed_count: number; total_count: number }>(`/projects/${projectId}/fix-organizations`),

  // 修复成员计数
  fixMemberCounts: (projectId: string) =>
    api.post<unknown, { success: boolean; message: string; fixed_count: number; total_count: number }>(`/projects/${projectId}/fix-member-counts`),

  // 导出为TXT
  exportTxt: (projectId: string) => {
    window.open(`/api/projects/${projectId}/export`, '_blank');
  },
};

export const outlineApi = {
  getOutlines: (projectId: string) =>
    api.get<unknown, Outline[]>(`/projects/${projectId}/story-outlines`),
  
  getOutline: (id: string) => api.get<unknown, Outline>(`/story-outlines/${id}`),
  
  createOutline: (projectId: string, data: OutlineCreate) => 
    api.post<unknown, Outline>(`/projects/${projectId}/story-outlines`, data),
  
  updateOutline: (id: string, data: OutlineUpdate) =>
    api.put<unknown, Outline>(`/story-outlines/${id}`, data),
  
  deleteOutline: (id: string) => api.delete(`/story-outlines/${id}`),
  
  activateOutline: (id: string) =>
    api.post<unknown, Outline>(`/story-outlines/${id}/activate`),

  // 获取大纲关联的剧情线
  getPlotLines: (outlineId: string) =>
    api.get<unknown, Array<{ id: string; title: string; description?: string; line_type?: string; order_index?: number }>>(`/story-outlines/${outlineId}/plot-lines`),
};

export const characterApi = {
  getCharacters: (projectId: string) =>
    api.get<unknown, Character[] | PaginationResponse<Character>>(`/characters/project/${projectId}`)
      .then(res => Array.isArray(res) ? res : (res.items || [])),
  
  getCharacter: (id: string) => api.get<unknown, Character>(`/characters/${id}`),
  
  createCharacter: (data: {
    project_id: string;
    name: string;
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
    avatar_url?: string;
    power_level?: number;
    location?: string;
    motto?: string;
    color?: string;
  }) =>
    api.post<unknown, Character>('/characters', data),
  
  updateCharacter: (id: string, data: CharacterUpdate) =>
    api.put<unknown, Character>(`/characters/${id}`, data),
  
  deleteCharacter: (id: string) => api.delete(`/characters/${id}`),
  
  generateCharacter: (data: GenerateCharacterRequest) =>
    api.post<unknown, Character>('/characters/generate', data),
};

export const chapterApi = {
  getChapters: (projectId: string) =>
    api.get<unknown, ChapterListApiResponse>(`/chapters/project/${projectId}`)
       .then(res => Array.isArray(res) ? res : (res.items || [])),
  
  getChapter: (id: string) => api.get<unknown, Chapter>(`/chapters/${id}`),
  
  createChapter: (data: ChapterCreate) => api.post<unknown, Chapter>('/chapters', data),
  
  updateChapter: (id: string, data: ChapterUpdate) =>
    api.put<unknown, Chapter>(`/chapters/${id}`, data),
  
  deleteChapter: (id: string) => api.delete(`/chapters/${id}`),
  
  checkCanGenerate: (chapterId: string) =>
    api.get<unknown, import('../types').ChapterCanGenerateResponse>(`/chapters/${chapterId}/can-generate`),
  
  // 根据章纲获取或创建章节
  getOrCreateChapterFromOutline: (outlineId: string) =>
    api.post<unknown, Chapter>(`/chapters/chapter-outlines/${outlineId}/chapter`),

  // 从章纲批量同步章节
  syncFromOutlines: (projectId: string) =>
    api.post<unknown, { created: number; skipped: number; total_outlines: number; message: string }>(
      `/chapters/project/${projectId}/sync-from-outlines`
    ),
  
  // 章节重新生成相关
  getRegenerationTasks: (chapterId: string, limit?: number) =>
    api.get<unknown, {
      chapter_id: string;
      total: number;
      tasks: Array<{
        task_id: string;
        status: string;
        version_number: number | null;
        version_note: string | null;
        original_word_count: number | null;
        regenerated_word_count: number | null;
        created_at: string | null;
        completed_at: string | null;
      }>;
    }>(`/chapters/${chapterId}/regeneration/tasks`, { params: { limit } }),

  // 章节导航
  getNavigation: (chapterId: string) =>
    api.get<unknown, {
      current: Chapter;
      previous: Chapter | null;
      next: Chapter | null;
    }>(`/chapters/${chapterId}/navigation`),

  // 生成章节内容（流式）
  generateChapterStream: (
    chapterId: string,
    data?: ChapterGenerateRequest,
    options?: SSEClientOptions
  ) => ssePost(
    `/api/chapters/${chapterId}/generate-stream`,
    data || {},
    options
  ),

  // 获取章节分析任务状态
  getAnalysisStatus: (chapterId: string) =>
    api.get<unknown, {
      has_task: boolean;
      task_id?: string | null;
      status: string;
      progress?: number;
      error_message?: string | null;
      auto_recovered?: boolean;
    }>(`/chapters/${chapterId}/analysis/status`),

  // 获取章节分析结果
  getAnalysis: (chapterId: string) =>
    api.get<unknown, ChapterAnalysisResponse>(`/chapters/${chapterId}/analysis`),

  // 获取章节标注
  getAnnotations: (chapterId: string) =>
    api.get<unknown, Record<string, unknown>>(`/chapters/${chapterId}/annotations`),

  // 触发章节分析
  analyzeChapter: (chapterId: string) =>
    api.post<unknown, { task_id: string; status: string }>(`/chapters/${chapterId}/analyze`),

  // 批量生成章节
  batchGenerate: (projectId: string, data?: Record<string, unknown>) =>
    api.post<unknown, { batch_id: string; status: string }>(`/chapters/project/${projectId}/batch-generate`, data || {}),

  // 获取批量生成状态
  getBatchGenerateStatus: (batchId: string) =>
    api.get<unknown, { batch_id: string; status: string; progress?: number; results?: Array<Record<string, unknown>> }>(`/chapters/batch-generate/${batchId}/status`),

  // 获取活跃的批量生成任务
  getActiveBatchGenerate: (projectId: string) =>
    api.get<unknown, Array<{ batch_id: string; status: string; progress?: number }>>(`/chapters/project/${projectId}/batch-generate/active`),

  // 取消批量生成
  cancelBatchGenerate: (batchId: string) =>
    api.post<unknown, { message: string }>(`/chapters/batch-generate/${batchId}/cancel`),

  // 重新生成章节（流式）
  regenerateChapterStream: (
    chapterId: string,
    data?: Record<string, unknown>,
    options?: SSEClientOptions
  ) => ssePost(
    `/api/chapters/${chapterId}/regenerate-stream`,
    data || {},
    options
  ),
};

export const writingStyleApi = {
  // 获取预设风格列表
  getPresetStyles: () =>
    api.get<unknown, PresetStyle[]>('/writing-styles/presets/list'),
  
  // 获取项目的所有风格
  getProjectStyles: (projectId: string) =>
    api.get<unknown, WritingStyleListResponse>(`/writing-styles/project/${projectId}`),
  
  // 创建新风格（基于预设或自定义）
  createStyle: (data: WritingStyleCreate) =>
    api.post<unknown, WritingStyle>('/writing-styles', data),
  
  // 更新风格
  updateStyle: (styleId: number, data: WritingStyleUpdate) =>
    api.put<unknown, WritingStyle>(`/writing-styles/${styleId}`, data),
  
  // 删除风格
  deleteStyle: (styleId: number) =>
    api.delete<unknown, { message: string }>(`/writing-styles/${styleId}`),
  
  // 设置默认风格
  setDefaultStyle: (styleId: number, projectId: string) =>
    api.post<unknown, WritingStyle>(`/writing-styles/${styleId}/set-default`, { project_id: projectId }),
  
  // 为项目初始化默认风格（如果没有任何风格）
  initializeDefaultStyles: (projectId: string) =>
    api.post<unknown, WritingStyleListResponse>(`/writing-styles/project/${projectId}/init-defaults`, {}),
};

export const inspirationApi = {
  // 生成选项建议
  generateOptions: (data: {
    step: 'title' | 'description' | 'theme' | 'genre';
    context: {
      title?: string;
      description?: string;
      theme?: string;
    };
    hint?: string;
  }) =>
    api.post<unknown, {
      prompt?: string;
      options: string[];
      error?: string;
    }>('/inspiration/generate-options', data),
  
  // 智能补全缺失信息
  quickGenerate: (data: {
    title?: string;
    description?: string;
    theme?: string;
    genre?: string | string[];
  }) =>
    api.post<unknown, {
      title: string;
      description: string;
      theme: string;
      genre: string[];
      narrative_perspective: string;
    }>('/inspiration/quick-generate', data),
};

export default api;


export const wizardStreamApi = {
  generateWorldBuildingStream: (
    data: {
      title: string;
      description: string;
      theme: string;
      genre: string | string[];
      narrative_perspective?: string;
      target_words?: number;
      chapter_count?: number;
      character_count?: number;
      provider?: string;
      model?: string;
      enable_mcp?: boolean;
      selected_plugins?: string[];
    },
    options?: SSEClientOptions<WorldBuildingResponse>
  ) => ssePost<WorldBuildingResponse>(
    '/api/wizard-stream/world-building',
    data,
    options
  ),

  generateCharactersStream: (
    data: {
      project_id: string;
      count?: number;
      world_context?: Record<string, string>;
      theme?: string;
      genre?: string;
      requirements?: string;
      provider?: string;
      model?: string;
      enable_mcp?: boolean;
      selected_plugins?: string[];
    },
    options?: SSEClientOptions<GenerateCharactersResponse>
  ) => ssePost<GenerateCharactersResponse>(
    '/api/wizard-stream/characters',
    data,
    options
  ),

  /**
   * 生成高层故事大纲（向导/灵感模式）
   * 
   * 注意：此接口生成的是高层故事大纲（单个大纲对象），不再自动生成章节记录
   * 
   * @param data.project_id - 项目ID
   * @param data.chapter_count - 预估章节数（作为提示，不保证生成对应数量的章节）
   * @param data.narrative_perspective - 叙事视角
   * @param data.target_words - 目标字数
   * @param data.requirements - 其他要求
   * @param data.provider - AI提供商
   * @param data.model - AI模型
   * @param data.enable_mcp - 是否启用MCP工具增强（默认true）
   */
  generateCompleteOutlineStream: (
    data: {
      project_id: string;
      chapter_count?: number;  // 改为可选，作为预估提示
      narrative_perspective: string;
      target_words?: number;
      requirements?: string;
      provider?: string;
      model?: string;
      enable_mcp?: boolean;  // 新增：是否启用MCP
      selected_plugins?: string[];  // 新增：选择的插件列表
    },
    options?: SSEClientOptions<GenerateOutlineResponse>
  ) => ssePost<GenerateOutlineResponse>(
    '/api/wizard-stream/outline',
    data,
    options
  ),

  updateWorldBuildingStream: (
    projectId: string,
    data: {
      time_period?: string;
      location?: string;
      atmosphere?: string;
      rules?: string;
    },
    options?: SSEClientOptions<WorldBuildingResponse>
  ) => ssePost<WorldBuildingResponse>(
    '/api/wizard-stream/world-building',
    { ...data, project_id: projectId, mode: 'update' },
    options
  ),

  regenerateWorldBuildingStream: (
    projectId: string,
    data?: {
      provider?: string;
      model?: string;
      enable_mcp?: boolean;
      selected_plugins?: string[];
    },
    options?: SSEClientOptions<WorldBuildingResponse>
  ) => ssePost<WorldBuildingResponse>(
    '/api/wizard-stream/world-building',
    { ...(data || {}), project_id: projectId, mode: 'regenerate' },
    options
  ),

  cleanupWizardDataStream: (
    projectId: string,
    options?: SSEClientOptions<{ message: string; deleted: { characters: number; outlines: number; chapters: number } }>
  ) => ssePost<{ message: string; deleted: { characters: number; outlines: number; chapters: number } }>(
    `/api/wizard-stream/cleanup/${projectId}`,
    {},
    options
  ),
};

export const mcpPluginApi = {
  // 获取所有插件
  getPlugins: (params?: { enabled_only?: boolean }) =>
    api.get<unknown, MCPPlugin[]>('/mcp/plugins', { params }),
  
  // 获取单个插件
  getPlugin: (id: string) =>
    api.get<unknown, MCPPlugin>(`/mcp/plugins/${id}`),
  
  // 创建插件
  createPlugin: (data: MCPPluginCreate) =>
    api.post<unknown, MCPPlugin>('/mcp/plugins', data),
  
  // 简化创建插件（通过标准MCP配置JSON）
  createPluginSimple: (data: MCPPluginSimpleCreate) =>
    api.post<unknown, MCPPlugin>('/mcp/plugins/simple', data),
  
  // 更新插件
  updatePlugin: (id: string, data: MCPPluginUpdate) =>
    api.put<unknown, MCPPlugin>(`/mcp/plugins/${id}`, data),
  
  // 删除插件
  deletePlugin: (id: string) =>
    api.delete<unknown, { message: string }>(`/mcp/plugins/${id}`),
  
  // 启用/禁用插件
  togglePlugin: (id: string, enabled: boolean) =>
    api.post<unknown, MCPPlugin>(`/mcp/plugins/${id}/toggle`, null, { params: { enabled } }),
  
  // 测试插件连接
  testPlugin: (id: string) =>
    api.post<unknown, MCPTestResult>(`/mcp/plugins/${id}/test`),
  
  // 获取插件工具列表
  getPluginTools: (id: string) =>
    api.get<unknown, { tools: MCPTool[] }>(`/mcp/plugins/${id}/tools`),
  
  // 调用工具
  callTool: (data: MCPToolCallRequest) =>
    api.post<unknown, MCPToolCallResponse>('/mcp/plugins/call', data),

  // 获取工具调用指标
  getMetrics: (toolName?: string) =>
    api.get<unknown, Record<string, unknown>>('/mcp/plugins/metrics', { params: { tool_name: toolName } }),

  // 获取缓存统计
  getCacheStats: () =>
    api.get<unknown, Record<string, unknown>>('/mcp/plugins/cache/stats'),

  // 清理缓存
  clearCache: (userId?: string, pluginName?: string) =>
    api.post<unknown, { success: boolean; message: string }>('/mcp/plugins/cache/clear', null, { params: { user_id: userId, plugin_name: pluginName } }),
};

// 管理员API
export const adminApi = {
  // 获取用户列表
  getUsers: () =>
    api.get<unknown, { total: number; users: User[] }>('/admin/users'),
  
  // 添加用户
  createUser: (data: {
    username: string;
    display_name: string;
    password?: string;
    avatar_url?: string;
    trust_level?: number;
    is_admin?: boolean;
  }) =>
    api.post<unknown, {
      success: boolean;
      message: string;
      user: User;
      default_password?: string;
    }>('/admin/users', data),
  
  // 编辑用户
  updateUser: (userId: string, data: {
    display_name?: string;
    avatar_url?: string;
    trust_level?: number;
  }) =>
    api.put<unknown, {
      success: boolean;
      message: string;
      user: User;
    }>(`/admin/users/${userId}`, data),
  
  // 切换用户状态（启用/禁用）
  toggleUserStatus: (userId: string, isActive: boolean) =>
    api.post<unknown, {
      success: boolean;
      message: string;
      is_active: boolean;
    }>(`/admin/users/${userId}/toggle-status`, { is_active: isActive }),
  
  // 重置密码
  resetPassword: (userId: string, newPassword?: string) =>
    api.post<unknown, {
      success: boolean;
      message: string;
      new_password: string;
    }>(`/admin/users/${userId}/reset-password`, { new_password: newPassword }),
  
  // 删除用户
  deleteUser: (userId: string) =>
    api.delete<unknown, {
      success: boolean;
      message: string;
    }>(`/admin/users/${userId}`),
};

// 剧情卡片 API
export const plotCardApi = {
  // 获取项目的剧情卡片列表
  getPlotCards: (projectId: string, params?: {
    skip?: number;
    limit?: number;
    card_type?: string;
    chapter_outline_id?: string;
  }) =>
    api.get<unknown, PlotCardListResponse>(`/plot-cards/project/${projectId}`, { params }),

  // 获取单个剧情卡片
  getPlotCard: (cardId: string) =>
    api.get<unknown, PlotCard>(`/plot-cards/${cardId}`),

  // 创建剧情卡片
  createPlotCard: (data: PlotCardCreate) =>
    api.post<unknown, PlotCard>('/plot-cards', data),

  // 更新剧情卡片
  updatePlotCard: (cardId: string, data: PlotCardUpdate) =>
    api.put<unknown, PlotCard>(`/plot-cards/${cardId}`, data),

  // 删除剧情卡片
  deletePlotCard: (cardId: string) =>
    api.delete<unknown, { message: string }>(`/plot-cards/${cardId}`),

  // 重排序剧情卡片
  reorderPlotCards: (data: PlotCardReorderRequest) =>
    api.post<unknown, { message: string }>('/plot-cards/reorder', data),

  // AI生成剧情卡片
  generatePlotCards: (data: PlotCardGenerateRequest) =>
    api.post<unknown, PlotCard[]>('/plot-cards/generate', data),

  // 获取项目中使用的卡片类型
  getCardTypes: (projectId: string) =>
    api.get<unknown, { types: Array<{ type: string; count: number }> }>(`/plot-cards/project/${projectId}/types`),
};

// 剧情线 API
export const plotLineApi = {
  // 获取项目的剧情线列表
  getPlotLines: (projectId: string, params?: {
    skip?: number;
    limit?: number;
    line_type?: string;
  }) =>
    api.get<unknown, PlotLineListResponse>(`/plot-lines/project/${projectId}`, { params }),

  // 获取单个剧情线
  getPlotLine: (lineId: string) =>
    api.get<unknown, PlotLine>(`/plot-lines/${lineId}`),

  // 创建剧情线
  createPlotLine: (data: PlotLineCreate) =>
    api.post<unknown, PlotLine>('/plot-lines', data),

  // 更新剧情线
  updatePlotLine: (lineId: string, data: PlotLineUpdate) =>
    api.put<unknown, PlotLine>(`/plot-lines/${lineId}`, data),

  // 删除剧情线
  deletePlotLine: (lineId: string) =>
    api.delete<unknown, { message: string }>(`/plot-lines/${lineId}`),

  // 重排序剧情线
  reorderPlotLines: (data: PlotLineReorderRequest) =>
    api.post<unknown, { message: string }>('/plot-lines/reorder', data),

  // AI生成剧情线
  generatePlotLines: (data: PlotLineGenerateRequest) =>
    api.post<unknown, PlotLine[]>('/plot-lines/generate', data),

  // 获取项目中使用的剧情线类型
  getLineTypes: (projectId: string) =>
    api.get<unknown, { types: Array<{ type: string; count: number }> }>(`/plot-lines/project/${projectId}/types`),

  // 向剧情线添加剧情卡片
  addCardsToLine: (lineId: string, cardIds: string[]) =>
    api.post<unknown, { message: string }>(`/plot-lines/${lineId}/add-cards`, cardIds),

  // 从剧情线移除剧情卡片
  removeCardsFromLine: (lineId: string, cardIds: string[]) =>
    api.delete<unknown, { message: string }>(`/plot-lines/${lineId}/remove-cards`, { data: cardIds }),

  // 获取剧情线写作进度
  getPlotLineProgress: (lineId: string) =>
    api.get<unknown, PlotLineProgress>(`/plot-lines/${lineId}/progress`),

  // 更新时间线数据
  updateTimeline: (lineId: string, data: TimelineData) =>
    api.put<unknown, PlotLine>(`/plot-lines/${lineId}/timeline`, data),
};

// 章纲 API
export const chapterOutlineApi = {
  // 获取项目的章纲列表
  getChapterOutlines: (projectId: string, params?: {
    skip?: number;
    limit?: number;
    plot_line_id?: string;
  }) =>
    api.get<unknown, ChapterOutlineListResponse>(`/chapter-outlines/project/${projectId}`, { params }),

  // 获取单个章纲
  getChapterOutline: (outlineId: string) =>
    api.get<unknown, ChapterOutline>(`/chapter-outlines/${outlineId}`),

  // 创建章纲
  createChapterOutline: (data: ChapterOutlineCreate) =>
    api.post<unknown, ChapterOutline>('/chapter-outlines', data),

  // 更新章纲
  updateChapterOutline: (outlineId: string, data: ChapterOutlineUpdate) =>
    api.put<unknown, ChapterOutline>(`/chapter-outlines/${outlineId}`, data),

  // 删除章纲
  deleteChapterOutline: (outlineId: string) =>
    api.delete<unknown, { message: string }>(`/chapter-outlines/${outlineId}`),

  // 重排序章纲
  reorderChapterOutlines: (data: ChapterOutlineReorderRequest) =>
    api.post<unknown, { message: string }>('/chapter-outlines/reorder', data),

  // 批量创建章纲
  batchCreateChapterOutlines: (data: ChapterOutlineBatchCreateRequest) =>
    api.post<unknown, ChapterOutline[]>('/chapter-outlines/batch', data),

  // AI生成章纲
  generateChapterOutlines: (data: ChapterOutlineGenerateRequest) =>
    api.post<unknown, ChapterOutline[]>('/chapter-outlines/generate', data),

  // 获取项目章纲统计信息
  getChapterOutlineStatistics: (projectId: string) =>
    api.get<unknown, {
      total_count: number;
      total_target_words: number;
      line_statistics: Array<{
        plot_line_id: string | null;
        chapter_count: number;
        total_target_words: number;
      }>;
    }>(`/chapter-outlines/project/${projectId}/statistics`),
};

// ============================================
// 关联管理 API
// ============================================

// 剧情线关联管理 API
export const plotLineLinkApi = {
  // 查询关联
  getChapterOutlines: (lineId: string) =>
    api.get<unknown, ChapterOutlineWithLinks[]>(`/plot-lines/${lineId}/chapter-outlines`),

  getPlotCards: (lineId: string) =>
    api.get<unknown, PlotCardWithLinks[]>(`/plot-lines/${lineId}/plot-cards`),

  // 管理关联
  linkChapterOutlines: (lineId: string, data: { chapter_outline_ids: string[]; role?: string }) =>
    api.post<unknown, { message: string; created_count: number; skipped_count: number }>(
      `/plot-lines/${lineId}/link-chapter-outlines`,
      {
        chapter_outline_ids: data.chapter_outline_ids,
        role: data.role || 'main'
      }
    ),

  unlinkChapterOutlines: (lineId: string, chapterOutlineIds: string[]) =>
    api.delete<unknown, { message: string; removed_count: number }>(
      `/plot-lines/${lineId}/unlink-chapter-outlines`,
      {
        data: { ids: chapterOutlineIds }
      }
    ),

  linkPlotCards: (lineId: string, plotCardIds: string[]) =>
    api.post<unknown, { message: string; created_count: number; skipped_count: number }>(
      `/plot-lines/${lineId}/link-plot-cards`,
      {
        plot_card_ids: plotCardIds
      }
    ),

  unlinkPlotCards: (lineId: string, plotCardIds: string[]) =>
    api.delete<unknown, { message: string; removed_count: number }>(
      `/plot-lines/${lineId}/unlink-plot-cards`,
      {
        data: { ids: plotCardIds }
      }
    ),
};

// 章纲关联管理 API
export const chapterOutlineLinkApi = {
  // 查询关联
  getPlotLines: (outlineId: string) =>
    api.get<unknown, PlotLineWithLinks[]>(`/chapter-outlines/${outlineId}/plot-lines`),

  getPlotCards: (outlineId: string) =>
    api.get<unknown, PlotCardWithLinks[]>(`/chapter-outlines/${outlineId}/plot-cards`),

  // 管理关联
  linkPlotLines: (outlineId: string, data: { plot_line_ids: string[]; role?: string }) =>
    api.post<unknown, { message: string; created_count: number; skipped_count: number }>(
      `/chapter-outlines/${outlineId}/link-plot-lines`,
      {
        plot_line_ids: data.plot_line_ids,
        role: data.role || 'main'
      }
    ),

  unlinkPlotLines: (outlineId: string, plotLineIds: string[]) =>
    api.delete<unknown, { message: string; removed_count: number }>(
      `/chapter-outlines/${outlineId}/unlink-plot-lines`,
      {
        data: { ids: plotLineIds }
      }
    ),

  linkPlotCards: (outlineId: string, data: { plot_card_ids: string[]; usage_type?: string; usage_notes?: string }) =>
    api.post<unknown, { message: string; created_count: number; skipped_count: number }>(
      `/chapter-outlines/${outlineId}/link-plot-cards`,
      {
        plot_card_ids: data.plot_card_ids,
        usage_type: data.usage_type || 'reference',
        usage_notes: data.usage_notes
      }
    ),

  unlinkPlotCards: (outlineId: string, plotCardIds: string[]) =>
    api.delete<unknown, { message: string; removed_count: number }>(
      `/chapter-outlines/${outlineId}/unlink-plot-cards`,
      {
        data: { ids: plotCardIds }
      }
    ),

  updatePlotCardUsage: (outlineId: string, cardId: string, data: {
    usage_type: string;
    usage_notes?: string;
  }) =>
    api.put<unknown, { message: string }>(
      `/chapter-outlines/${outlineId}/plot-cards/${cardId}/usage`,
      data
    ),

  // 更新节点覆盖度
  updateTimelineCoverage: (
    chapterId: string,
    linkId: string,
    data: TimelineCoverageUpdate
  ) =>
    api.put<unknown, { message: string; updated_beats_count: number }>(
      `/chapter-outlines/${chapterId}/plot-line-links/${linkId}/timeline-coverage`,
      data
    ),

  // 获取剧情线节点的贡献度分布
  getBeatContributions: (plotLineId: string) =>
    api.get<unknown, Record<number, { total_coverage: number; chapters: Array<{ chapter_id: string; chapter_number: number; chapter_title: string; coverage: number }> }>>(
      `/chapter-outlines/plot-lines/${plotLineId}/beat-contributions`
    ),
};

// 剧情卡片关联管理 API
export const plotCardLinkApi = {
  // 查询关联
  getPlotLines: (cardId: string) =>
    api.get<unknown, PlotLineWithLinks[]>(`/plot-cards/${cardId}/plot-lines`),

  getChapterOutlines: (cardId: string) =>
    api.get<unknown, ChapterOutlineWithLinks[]>(`/plot-cards/${cardId}/chapter-outlines`),

  // 管理关联
  linkPlotLines: (cardId: string, plotLineIds: string[]) =>
    api.post<unknown, { message: string; created_count: number; skipped_count: number }>(
      `/plot-cards/${cardId}/link-plot-lines`,
      { plot_line_ids: plotLineIds }
    ),

  unlinkPlotLines: (cardId: string, plotLineIds: string[]) =>
    api.delete<unknown, { message: string; removed_count: number }>(
      `/plot-cards/${cardId}/unlink-plot-lines`,
      {
        data: { ids: plotLineIds }
      }
    ),

  linkChapterOutlines: (cardId: string, links: Array<{
    chapter_outline_id: string;
    usage_type: string;
    usage_notes?: string;
  }>) =>
    api.post<unknown, { message: string; created_count: number; skipped_count: number }>(
      `/plot-cards/${cardId}/link-chapter-outlines`,
      { links }
    ),

  unlinkChapterOutlines: (cardId: string, chapterOutlineIds: string[]) =>
    api.delete<unknown, { message: string; removed_count: number }>(
      `/plot-cards/${cardId}/unlink-chapter-outlines`,
      {
        data: { ids: chapterOutlineIds }
      }
    ),
};

// 世界规则系统 API
export const worldRulesApi = {
  // 获取世界规则列表
  list: (projectId: string, category?: 'cultivation_realm' | 'equipment_template' | 'map_location') =>
    api.get<unknown, WorldRuleListResponse>(
      `/projects/${projectId}/world-rules`,
      { params: category ? { category } : {} }
    ),

  // 创建世界规则
  create: (projectId: string, data: WorldRuleCreate) =>
    api.post<unknown, WorldRule>(`/projects/${projectId}/world-rules`, data),

  // 更新世界规则
  update: (ruleId: string, data: WorldRuleUpdate) =>
    api.put<unknown, WorldRule>(`/world-rules/${ruleId}`, data),

  // 删除世界规则
  delete: (ruleId: string) =>
    api.delete<unknown, { message: string }>(`/world-rules/${ruleId}`),
};

// 场景生成 API（简化版 - 按剧情卡片分段生成）
export const sceneGenerationApi = {
  // 获取章纲关联的剧情卡片
  getPlotCards: (chapterOutlineId: string) =>
    api.get<unknown, {
      chapter_outline_id: string;
      plot_cards: Array<{
        id: string;
        title: string;
        content?: string;
        generation_status: string;
        word_count_target: number;
        word_count_actual: number;
        generation_order: number;
      }>;
    }>(`/scene-generation/chapter-outlines/${chapterOutlineId}/plot-cards`),

  // 流式生成场景（使用 ssePost，携带认证拦截）
  generateSceneStream: (
    data: {
      chapter_outline_id: string;
      plot_card_id: string;
      writing_style_id?: string;
      previous_generated_content?: string;
    },
    options?: SSEClientOptions
  ) => ssePost('/api/scene-generation/generate-scene-stream', data, options),

  // 流式生成场景的 URL（兼容现有裸 fetch 用法）
  getGenerateSceneStreamUrl: () => '/api/scene-generation/generate-scene-stream',
};

// ============================================
// 关系 API
// ============================================
export const relationshipApi = {
  // 获取关系类型列表
  getTypes: () =>
    api.get<unknown, Array<{
      id: number;
      name: string;
      category: string;
      reverse_name?: string;
      intimacy_range?: string;
      icon?: string;
      description?: string;
    }>>('/relationships/types'),

  // 获取项目关系列表
  getProjectRelationships: (projectId: string) =>
    api.get<unknown, Array<Record<string, unknown>>>(`/relationships/project/${projectId}`),

  // 获取关系图谱数据
  getGraph: (projectId: string) =>
    api.get<unknown, { nodes: Array<Record<string, unknown>>; edges: Array<Record<string, unknown>> }>(`/relationships/graph/${projectId}`),

  // 创建关系
  createRelationship: (data: {
    project_id: string;
    character_from_id: string;
    character_to_id: string;
    relationship_type_id?: number;
    relationship_name?: string;
    intimacy_level?: number;
    status?: string;
    description?: string;
    started_at?: string;
    ended_at?: string;
  }) =>
    api.post<unknown, Record<string, unknown>>('/relationships/', data),

  // 更新关系
  updateRelationship: (relationshipId: string, data: {
    relationship_type_id?: number;
    relationship_name?: string;
    intimacy_level?: number;
    status?: string;
    description?: string;
  }) =>
    api.put<unknown, Record<string, unknown>>(`/relationships/${relationshipId}`, data),

  // 删除关系
  deleteRelationship: (relationshipId: string) =>
    api.delete<unknown, { message: string }>(`/relationships/${relationshipId}`),
};

// ============================================
// 组织 API
// ============================================
export const organizationApi = {
  // 获取项目组织列表
  getProjectOrganizations: (projectId: string) =>
    api.get<unknown, Array<Record<string, unknown>>>(`/organizations/project/${projectId}`),

  // 获取组织详情
  getOrganization: (orgId: string) =>
    api.get<unknown, Record<string, unknown>>(`/organizations/${orgId}`),

  // 创建组织（需要先通过 characterApi.createCharacter 创建 is_organization=true 的角色）
  createOrganization: (data: {
    character_id: string;
    project_id: string;
    parent_org_id?: string;
    level?: number;
    power_level?: number;
    location?: string;
    motto?: string;
    color?: string;
  }) =>
    api.post<unknown, Record<string, unknown>>('/organizations', data),

  // 更新组织
  updateOrganization: (orgId: string, data: {
    parent_org_id?: string;
    level?: number;
    power_level?: number;
    location?: string;
    motto?: string;
    color?: string;
  }) =>
    api.put<unknown, Record<string, unknown>>(`/organizations/${orgId}`, data),

  // 删除组织
  deleteOrganization: (orgId: string) =>
    api.delete<unknown, { message: string }>(`/organizations/${orgId}`),

  // 获取组织成员
  getMembers: (orgId: string) =>
    api.get<unknown, Array<Record<string, unknown>>>(`/organizations/${orgId}/members`),

  // 添加成员
  addMember: (orgId: string, data: {
    character_id: string;
    position: string;
    rank?: number;
    status?: string;
    joined_at?: string;
    left_at?: string;
    loyalty?: number;
    contribution?: number;
    notes?: string;
  }) =>
    api.post<unknown, Record<string, unknown>>(`/organizations/${orgId}/members`, data),

  // 更新成员
  updateMember: (memberId: string, data: {
    position?: string;
    rank?: number;
    status?: string;
    joined_at?: string;
    left_at?: string;
    loyalty?: number;
    contribution?: number;
    notes?: string;
  }) =>
    api.put<unknown, Record<string, unknown>>(`/organizations/members/${memberId}`, data),

  // 移除成员
  removeMember: (memberId: string) =>
    api.delete<unknown, { message: string }>(`/organizations/members/${memberId}`),

  // AI生成组织
  generateOrganization: (data: {
    project_id: string;
    requirements?: string;
  }) =>
    api.post<unknown, Record<string, unknown>>('/organizations/generate', data),

  // AI流式生成组织
  generateOrganizationStream: (
    data: {
      project_id: string;
      requirements?: string;
    },
    options?: SSEClientOptions
  ) => ssePost(
    '/api/organizations/generate-stream',
    data,
    options
  ),
};

// ============================================
// 记忆系统 API
// ============================================
export const memoryApi = {
  // 分析章节记忆
  analyzeChapterMemory: (projectId: string, chapterId: string) =>
    api.post<unknown, { success: boolean; message: string; analysis: Record<string, unknown>; memories_count: number }>(`/memories/projects/${projectId}/analyze-chapter/${chapterId}`),

  // 获取项目记忆列表
  getProjectMemories: (projectId: string, params?: {
    memory_type?: string;
    chapter_id?: string;
    limit?: number;
  }) =>
    api.get<unknown, { success: boolean; memories: Array<Record<string, unknown>>; total: number }>(`/memories/projects/${projectId}/memories`, { params }),

  // 获取章节分析结果
  getChapterAnalysis: (projectId: string, chapterId: string) =>
    api.get<unknown, { success: boolean; analysis: Record<string, unknown> }>(`/memories/projects/${projectId}/analysis/${chapterId}`),

  // 搜索记忆
  searchMemories: (projectId: string, data: {
    query: string;
    memory_types?: string[];
    limit?: number;
    min_importance?: number;
  }) =>
    api.post<unknown, { success: boolean; query: string; memories: Array<Record<string, unknown>>; total: number }>(
      `/memories/projects/${projectId}/search`,
      null,
      { params: data }
    ),

  // 获取未解决伏笔
  getForeshadows: (projectId: string, currentChapter: number) =>
    api.get<unknown, { success: boolean; foreshadows: Array<Record<string, unknown>>; total: number }>(`/memories/projects/${projectId}/foreshadows`, { params: { current_chapter: currentChapter } }),

  // 获取记忆统计
  getStats: (projectId: string) =>
    api.get<unknown, { success: boolean; stats: Record<string, unknown> }>(`/memories/projects/${projectId}/stats`),

  // 删除章节记忆
  deleteChapterMemories: (projectId: string, chapterId: string) =>
    api.delete<unknown, { success: boolean; message: string }>(`/memories/projects/${projectId}/chapters/${chapterId}/memories`),
};

