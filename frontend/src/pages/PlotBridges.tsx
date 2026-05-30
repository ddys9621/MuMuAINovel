/**
 * V4.1 K2 桥段规划页
 *
 * 路由：/project/:projectId/plot-bridges
 *
 * 功能：
 * - 列出项目下所有桥段（按 bridge_number 排序）
 * - "AI 规划桥段"按钮：调 plotBridgesApi.plan() 让 AI 一次性生成 N 个桥段
 * - 编辑单个桥段（弹窗）：修改标题/目标/装逼点/4 章卡片
 * - "展开为 4 章"按钮：调 plotBridgesApi.expand() 把桥段展开为 4 个 ChapterOutline
 * - 删除桥段（确认弹窗）
 *
 * K2 设计：桥段四章结构（C1 代入+信息差 / C2 拉扯+开装 / C3 兑现爽点 / C4 善后+下一目标）
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Button,
  Card,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Radio,
  Select,
  Spin,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import {
  EditOutlined,
  DeleteOutlined,
  ThunderboltOutlined,
  ExpandAltOutlined,
  ReloadOutlined,
  PlusOutlined,
  RocketOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { toast } from 'sonner';

import { plotBridgesApi } from '@/services/plotBridgesApi';
import { settingsApi } from '@/services/api';
import {
  BRIDGE_STATUS_COLOR,
  BRIDGE_STATUS_LABEL,
  type PlotBridge,
  type UpdateBridgeRequest,
} from '@/types/plot_bridge';

const { Text, Paragraph } = Typography;

type ModelOption = { value: string; label: string };

// 兜底候选：用户未配置 API、加载失败、或使用 Anthropic（无公开 /models 接口）时显示
const FALLBACK_MODEL_OPTIONS: ModelOption[] = [
  { value: 'deepseek-v3', label: 'DeepSeek V3（推荐，64K 大窗口）' },
  { value: 'claude-sonnet-4-5', label: 'Claude Sonnet 4.5（旗舰，200K）' },
  { value: 'qwen-max', label: '通义千问 Max（32K）' },
  { value: 'doubao-pro-32k', label: '豆包 Pro 32K' },
  { value: 'gpt-4o', label: 'GPT-4o（128K）' },
  { value: 'glm-4', label: 'GLM-4（64K）' },
];

/**
 * 拉取用户在「设置」中配置的 API 的真实可用模型列表。
 * - 默认模型 = Settings 里的 llm_model（如有）
 * - Anthropic 没公开 /models 接口 → 走 fallback + 补上用户的默认模型
 * - 拉取失败 → 静默降级到 fallback，不阻塞 UI
 */
function useAvailableModels() {
  const [options, setOptions] = useState<ModelOption[]>(FALLBACK_MODEL_OPTIONS);
  const [defaultModel, setDefaultModel] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const loadModels = useCallback(async (showToast: boolean) => {
    try {
      setLoading(true);
      const settings = await settingsApi.getSettings();
      const userDefault = settings?.llm_model || '';
      if (userDefault) setDefaultModel(userDefault);

      const provider = settings?.api_provider || 'openai';

      // Anthropic 没公开 /models 接口
      if (provider === 'anthropic') {
        if (userDefault && !FALLBACK_MODEL_OPTIONS.some((o) => o.value === userDefault)) {
          setOptions([{ value: userDefault, label: `${userDefault}（设置中默认）` }, ...FALLBACK_MODEL_OPTIONS]);
        }
        return;
      }

      if (!settings?.api_key || !settings?.api_base_url) {
        // 未配置 API → 保留 fallback
        return;
      }

      const res = await settingsApi.getAvailableModels({
        api_key: settings.api_key,
        api_base_url: settings.api_base_url,
        provider,
      });
      const fetched = (res.models || []).map((m) => ({ value: m.value, label: m.label }));
      if (fetched.length) {
        // 若用户默认模型不在返回列表里，补到最前（避免下拉框看不到当前默认）
        const finalList =
          userDefault && !fetched.some((o) => o.value === userDefault)
            ? [{ value: userDefault, label: `${userDefault}（设置中默认）` }, ...fetched]
            : fetched;
        setOptions(finalList);
        if (showToast) toast.success(`已加载 ${fetched.length} 个可用模型`);
      } else if (showToast) {
        toast.warning('API 未返回模型列表，使用内置候选');
      }
    } catch (err) {
      console.warn('[PlotBridges] 加载用户模型失败，使用内置候选:', err);
      if (showToast) toast.warning('加载模型列表失败，使用内置候选');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadModels(false);
  }, [loadModels]);

  return { options, defaultModel, loading, refresh: () => void loadModels(true) };
}

export default function PlotBridgesPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [bridges, setBridges] = useState<PlotBridge[]>([]);
  const [loading, setLoading] = useState(true);
  const [planning, setPlanning] = useState(false);
  const [planModalOpen, setPlanModalOpen] = useState(false);
  const [expandingAll, setExpandingAll] = useState(false);
  const [editingBridge, setEditingBridge] = useState<PlotBridge | null>(null);
  const [expandingBridge, setExpandingBridge] = useState<PlotBridge | null>(null);

  // 从用户配置的 API 拉取真实可用模型列表（plan/expand 弹窗共用）
  const {
    options: modelOptions,
    defaultModel,
    loading: loadingModels,
    refresh: refreshModels,
  } = useAvailableModels();

  const fetchBridges = useCallback(async () => {
    if (!projectId) return;
    try {
      setLoading(true);
      const data = await plotBridgesApi.list(projectId);
      setBridges(Array.isArray(data) ? data : []);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '加载桥段列表失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchBridges();
  }, [fetchBridges]);

  const handlePlan = useCallback(
    async (values: {
      bridge_count: number;
      model: string;
      mode: 'by_plot_line' | 'free';
    }) => {
      if (!projectId) return;
      setPlanning(true);
      try {
        const newBridges = await plotBridgesApi.plan(projectId, values);
        const modeLabel = values.mode === 'by_plot_line' ? '按主线节点' : '自由';
        toast.success(`AI 已${modeLabel}生成 ${newBridges.length} 个桥段`);
        setPlanModalOpen(false);
        await fetchBridges();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : '规划桥段失败');
      } finally {
        setPlanning(false);
      }
    },
    [projectId, fetchBridges],
  );

  const handleDelete = useCallback(
    async (bridgeId: string) => {
      try {
        await plotBridgesApi.delete(bridgeId);
        toast.success('已删除');
        setBridges((prev) => prev.filter((b) => b.id !== bridgeId));
      } catch (err) {
        toast.error(err instanceof Error ? err.message : '删除失败');
      }
    },
    [],
  );

  // T2.1：桥段状态统计 + 批量展开
  const stats = useMemo(() => {
    const ready = bridges.filter((b) => b.status === 'ready').length;
    const completed = bridges.filter((b) => b.status === 'completed').length;
    return {
      total: bridges.length,
      ready,
      completed,
      allCompleted: bridges.length > 0 && ready === 0 && completed === bridges.length,
    };
  }, [bridges]);

  const handleExpandAll = useCallback(async () => {
    if (!projectId || stats.ready === 0) return;
    if (
      !window.confirm(
        `将展开 ${stats.ready} 个 ready 状态的桥段为 ${stats.ready * 4} 个章纲。\n` +
          `单个桥段失败不影响其他桥段。是否继续？`,
      )
    ) {
      return;
    }
    setExpandingAll(true);
    try {
      const res = await plotBridgesApi.expandAll(projectId, {
        model: defaultModel || undefined,
      });
      if (res.failed.length === 0) {
        toast.success(
          `成功展开 ${res.succeeded.length} 个桥段，共创建 ${res.created_chapter_count} 个章纲`,
        );
      } else {
        toast.warning(
          `部分完成：${res.succeeded.length}/${res.total} 成功，${res.failed.length} 失败`,
        );
      }
      await fetchBridges();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '批量展开失败');
    } finally {
      setExpandingAll(false);
    }
  }, [projectId, stats.ready, defaultModel, fetchBridges]);

  const handleGoToChapterOutlines = useCallback(() => {
    if (!projectId) return;
    navigate(`/project/${projectId}/outline`);
  }, [navigate, projectId]);

  if (!projectId) return null;

  return (
    <div className="space-y-4 p-6">
      {/* Header */}
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <RocketOutlined className="text-blue-500" />
            桥段规划（K2 桥段四章）
          </h1>
          <Paragraph type="secondary" className="!mb-0 mt-1 text-sm">
            一本网文 ≈ 200-300 桥段，每桥段 4 章。
            <strong className="text-blue-600">
              C1 代入 → C2 拉扯 → C3 兑现 → C4 善后
            </strong>
            。AI 规划后可手工微调，再展开为完整章纲。
          </Paragraph>
        </div>
        <div className="flex gap-2">
          <Button icon={<ReloadOutlined />} onClick={fetchBridges}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={() => setPlanModalOpen(true)}
            disabled={planning}
          >
            AI 规划桥段
          </Button>
          {stats.ready > 0 && (
            <Button
              type="primary"
              icon={<ExpandAltOutlined />}
              onClick={handleExpandAll}
              loading={expandingAll}
              danger={false}
              style={{ background: '#16a34a', borderColor: '#16a34a' }}
            >
              {expandingAll
                ? '正在展开...'
                : `一键展开全部（${stats.ready}）`}
            </Button>
          )}
        </div>
      </header>

      {/* T2.1：状态总览 + 完成跳转提示 */}
      {stats.total > 0 && (
        <Alert
          type={stats.allCompleted ? 'success' : 'info'}
          showIcon
          icon={stats.allCompleted ? <CheckCircleOutlined /> : undefined}
          message={
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <span>
                共 {stats.total} 个桥段：
                <Tag color="processing" className="ml-1">就绪 {stats.ready}</Tag>
                <Tag color="success">已展开 {stats.completed}</Tag>
                {stats.allCompleted && (
                  <span className="ml-2 text-green-700">
                    全部桥段已展开为章纲，可前往章纲页继续创作。
                  </span>
                )}
              </span>
              {stats.allCompleted && (
                <Button
                  type="primary"
                  onClick={handleGoToChapterOutlines}
                >
                  进入章纲页 →
                </Button>
              )}
            </div>
          }
        />
      )}

      {/* List */}
      {loading ? (
        <div className="flex justify-center py-20">
          <Spin size="large" tip="加载中..." />
        </div>
      ) : bridges.length === 0 ? (
        <Empty
          description={
            <span className="text-sm">
              暂无桥段。点击"AI 规划桥段"让系统根据故事大纲 + 拆书参考一次性生成。
            </span>
          }
        >
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setPlanModalOpen(true)}
          >
            生成第一批桥段
          </Button>
        </Empty>
      ) : (
        <BridgeListByBeat
          bridges={bridges}
          onEdit={(b) => setEditingBridge(b)}
          onExpand={(b) => setExpandingBridge(b)}
          onDelete={(id) => handleDelete(id)}
        />
      )}

      {/* AI 规划桥段弹窗 */}
      <Modal
        title="AI 规划桥段"
        open={planModalOpen}
        onCancel={() => setPlanModalOpen(false)}
        footer={null}
        destroyOnClose
        width={480}
      >
        <Form
          // 用 defaultModel 作为 key：异步加载完成后强制重渲染，让 initialValues 生效
          key={`plan-form-${defaultModel || 'pending'}`}
          layout="vertical"
          initialValues={{
            bridge_count: 25,
            model: defaultModel || modelOptions[0]?.value || 'deepseek-v3',
            mode: 'by_plot_line',
          }}
          onFinish={handlePlan}
        >
          <Form.Item
            label="规划模式"
            name="mode"
            extra="按主线节点：桥段绑定剧情线节点，按权重自动分配配额（推荐）；自由：忽略主线节点独立规划"
            rules={[{ required: true }]}
          >
            <Radio.Group>
              <Radio.Button value="by_plot_line">按主线节点（方案 C）</Radio.Button>
              <Radio.Button value="free">自由规划</Radio.Button>
            </Radio.Group>
          </Form.Item>
          <Form.Item
            label="桥段数量"
            name="bridge_count"
            extra="1 桥段 ≈ 4 章，25 个桥段 ≈ 100 章"
            rules={[{ required: true, type: 'number', min: 1, max: 300 }]}
          >
            <InputNumber min={1} max={300} step={5} className="w-full" />
          </Form.Item>
          <Form.Item
            label={
              <div className="flex items-center gap-2">
                <span>使用模型</span>
                <Tooltip title="重新从「设置」中配置的 API 拉取模型列表">
                  <Button
                    type="text"
                    size="small"
                    icon={<ReloadOutlined spin={loadingModels} />}
                    onClick={refreshModels}
                  />
                </Tooltip>
              </div>
            }
            name="model"
            rules={[{ required: true }]}
            extra="列表来自「设置」中配置的 API；下拉所选模型会同时用于推理 + 决定 prompt 档位（XL/L/M/S）"
          >
            <Select
              options={modelOptions}
              loading={loadingModels}
              showSearch
              optionFilterProp="label"
              placeholder={loadingModels ? '加载模型中...' : '选择模型'}
            />
          </Form.Item>
          <Form.Item className="!mb-0 text-right">
            <Button onClick={() => setPlanModalOpen(false)} className="mr-2">
              取消
            </Button>
            <Button
              type="primary"
              htmlType="submit"
              loading={planning}
              icon={<ThunderboltOutlined />}
            >
              {planning ? '正在规划...' : '开始规划'}
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑桥段弹窗 */}
      <EditBridgeModal
        bridge={editingBridge}
        onClose={() => setEditingBridge(null)}
        onSaved={(updated) => {
          setBridges((prev) =>
            prev.map((b) => (b.id === updated.id ? updated : b)),
          );
          setEditingBridge(null);
        }}
      />

      {/* 展开为 4 章弹窗 */}
      <ExpandBridgeModal
        bridge={expandingBridge}
        modelOptions={modelOptions}
        defaultModel={defaultModel}
        loadingModels={loadingModels}
        refreshModels={refreshModels}
        onClose={() => setExpandingBridge(null)}
        onExpanded={() => {
          setExpandingBridge(null);
          fetchBridges();
        }}
      />
    </div>
  );
}

// ============================================================
// 按节点分组列表（V4.1 方案 C）
// ============================================================

interface BridgeListByBeatProps {
  bridges: PlotBridge[];
  onEdit: (b: PlotBridge) => void;
  onExpand: (b: PlotBridge) => void;
  onDelete: (id: string) => void;
}

/**
 * 按 (plot_line_id, beat_index) 把桥段分组渲染。
 *
 * 分组规则：
 * - 同 plot_line_id + 同 beat_index → 同一个节点组（按 beat_coverage_start 排序）
 * - plot_line_id / beat_index 缺失 → 落入「未绑节点」分组（free 模式 / 老数据）
 * - 节点组按 (plot_line_id, beat_index) 自然顺序排列，未绑节点组排最后
 *
 * 节点 title / 剧情线 title 用 plot_line_id 短哈希做 fallback —— 完整剧情线数据
 * 可在后续版本通过 plotLinesApi 拉来填充更友好的 label。
 */
function BridgeListByBeat({
  bridges,
  onEdit,
  onExpand,
  onDelete,
}: BridgeListByBeatProps) {
  // 分组
  const groups = useMemo(() => {
    const map = new Map<string, PlotBridge[]>();
    const KEY_UNBOUND = '__unbound__';
    for (const b of bridges) {
      const key =
        b.plot_line_id && b.beat_index != null
          ? `${b.plot_line_id}::${b.beat_index}`
          : KEY_UNBOUND;
      const arr = map.get(key) ?? [];
      arr.push(b);
      map.set(key, arr);
    }
    // 节点组内按 coverage_start asc → bridge_number asc 排序
    for (const arr of map.values()) {
      arr.sort((a, b) => {
        const ca = a.beat_coverage_start ?? 0;
        const cb = b.beat_coverage_start ?? 0;
        if (ca !== cb) return ca - cb;
        return (a.bridge_number ?? 0) - (b.bridge_number ?? 0);
      });
    }
    return map;
  }, [bridges]);

  // 渲染顺序：先所有绑节点的组（按 plot_line_id + beat_index），再未绑组
  const orderedKeys = useMemo(() => {
    const bound: string[] = [];
    let unbound: string | null = null;
    for (const key of groups.keys()) {
      if (key === '__unbound__') unbound = key;
      else bound.push(key);
    }
    bound.sort((a, b) => {
      const [la, ia] = a.split('::');
      const [lb, ib] = b.split('::');
      if (la !== lb) return la.localeCompare(lb);
      return Number(ia) - Number(ib);
    });
    return unbound ? [...bound, unbound] : bound;
  }, [groups]);

  return (
    <div className="space-y-5">
      {orderedKeys.map((key) => {
        const groupBridges = groups.get(key) ?? [];
        const isUnbound = key === '__unbound__';
        const first = groupBridges[0];
        const groupLabel = isUnbound
          ? '未绑节点（free 模式 / 老桥段）'
          : `剧情线 ${first?.plot_line_id?.slice(0, 8) ?? '?'}… · 节点 ${first?.beat_index ?? '?'}（${groupBridges.length} 桥段）`;
        return (
          <div key={key} className="space-y-2">
            <div
              className={`flex items-center gap-2 rounded px-3 py-1.5 text-sm font-medium ${
                isUnbound
                  ? 'bg-gray-50 text-gray-500'
                  : 'bg-geekblue-50 text-geekblue-700'
              }`}
              style={
                isUnbound
                  ? undefined
                  : { background: '#f0f5ff', color: '#1d39c4' }
              }
            >
              {isUnbound ? '🔓' : '🎯'} {groupLabel}
            </div>
            <div className="space-y-3 pl-3">
              {groupBridges.map((bridge) => (
                <BridgeCard
                  key={bridge.id}
                  bridge={bridge}
                  onEdit={() => onEdit(bridge)}
                  onExpand={() => onExpand(bridge)}
                  onDelete={() => onDelete(bridge.id)}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}


// ============================================================
// 桥段卡片组件
// ============================================================

interface BridgeCardProps {
  bridge: PlotBridge;
  onEdit: () => void;
  onExpand: () => void;
  onDelete: () => void;
}

function BridgeCard({ bridge, onEdit, onExpand, onDelete }: BridgeCardProps) {
  const isCompleted = bridge.status === 'completed';
  // V4.1 方案 C：桥段绑定剧情线节点时显示节点信息 Tag
  const hasBeatBinding =
    bridge.beat_index != null &&
    bridge.beat_coverage_start != null &&
    bridge.beat_coverage_end != null;
  const coveragePct = hasBeatBinding
    ? `${Math.round((bridge.beat_coverage_start ?? 0) * 100)}%-${Math.round(
        (bridge.beat_coverage_end ?? 0) * 100,
      )}%`
    : null;
  return (
    <Card
      size="small"
      className="hover:shadow-md transition-shadow"
      title={
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded bg-blue-50 px-2 py-0.5 text-sm font-medium text-blue-600">
            #{bridge.bridge_number}
          </span>
          <span className="font-semibold">{bridge.title}</span>
          <Tag color={BRIDGE_STATUS_COLOR[bridge.status]}>
            {BRIDGE_STATUS_LABEL[bridge.status]}
          </Tag>
          {hasBeatBinding && (
            <Tooltip
              title={
                `本桥段绑定到剧情线节点 ${bridge.beat_index}，覆盖该节点进度 ${coveragePct}。` +
                ' 章节正文生成时会按节点权重推进，避免主线节奏失控。'
              }
            >
              <Tag color="geekblue" className="!ml-0">
                节点 {bridge.beat_index} · {coveragePct}
              </Tag>
            </Tooltip>
          )}
        </div>
      }
      extra={
        <div className="flex gap-1">
          <Tooltip title="编辑桥段">
            <Button size="small" icon={<EditOutlined />} onClick={onEdit} />
          </Tooltip>
          <Tooltip
            title={isCompleted ? '此桥段已展开为 4 章，可重新展开覆盖' : '展开为 4 个 ChapterOutline'}
          >
            <Button
              size="small"
              type={isCompleted ? 'default' : 'primary'}
              icon={<ExpandAltOutlined />}
              onClick={onExpand}
            >
              {isCompleted ? '重新展开' : '展开 4 章'}
            </Button>
          </Tooltip>
          <Popconfirm
            title={`确定删除桥段「${bridge.title}」？`}
            description="不会删除已展开的章纲，但会解除关联"
            onConfirm={onDelete}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Tooltip title="删除桥段">
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </div>
      }
    >
      <div className="space-y-2 text-sm">
        <div>
          <Text strong className="text-blue-600">目标：</Text>
          <Text>{bridge.goal}</Text>
        </div>
        <div>
          <Text strong className="text-orange-600">装逼点：</Text>
          <Text>{bridge.showoff_point}</Text>
        </div>
        {bridge.golden_finger_usage && (
          <div>
            <Text strong className="text-purple-600">金手指用法：</Text>
            <Text type="secondary">{bridge.golden_finger_usage}</Text>
          </div>
        )}

        {/* 4 章卡片预览 */}
        <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-4">
          <ChapterCardPreview label="C1 代入" hint="5:5" content={bridge.c1_intro} color="bg-blue-50" />
          <ChapterCardPreview label="C2 拉扯" hint="9:1 章尾开装" content={bridge.c2_build} color="bg-yellow-50" />
          <ChapterCardPreview label="C3 兑现" hint="无钩子" content={bridge.c3_payoff} color="bg-orange-50" />
          <ChapterCardPreview label="C4 善后" hint="承上启下" content={bridge.c4_aftermath} color="bg-green-50" />
        </div>

        {bridge.next_bridge_hook && (
          <div className="mt-2 rounded bg-gray-50 px-2 py-1.5 text-xs text-gray-600">
            <Text strong>下桥段钩子：</Text> {bridge.next_bridge_hook}
          </div>
        )}
      </div>
    </Card>
  );
}

function ChapterCardPreview({
  label,
  hint,
  content,
  color,
}: {
  label: string;
  hint: string;
  content: string | null;
  color: string;
}) {
  return (
    <div className={`${color} rounded p-2 text-xs`}>
      <div className="mb-1 flex items-center justify-between">
        <Text strong className="text-gray-800">{label}</Text>
        <Text type="secondary" className="text-[10px]">{hint}</Text>
      </div>
      <Paragraph
        ellipsis={{ rows: 3, tooltip: content }}
        className="!mb-0 text-gray-600"
      >
        {content || '（待 AI 规划）'}
      </Paragraph>
    </div>
  );
}

// ============================================================
// 编辑桥段弹窗
// ============================================================

function EditBridgeModal({
  bridge,
  onClose,
  onSaved,
}: {
  bridge: PlotBridge | null;
  onClose: () => void;
  onSaved: (updated: PlotBridge) => void;
}) {
  const [form] = Form.useForm<UpdateBridgeRequest>();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (bridge) {
      form.setFieldsValue({
        title: bridge.title,
        goal: bridge.goal,
        showoff_point: bridge.showoff_point,
        golden_finger_usage: bridge.golden_finger_usage ?? '',
        c1_intro: bridge.c1_intro ?? '',
        c2_build: bridge.c2_build ?? '',
        c3_payoff: bridge.c3_payoff ?? '',
        c4_aftermath: bridge.c4_aftermath ?? '',
        next_bridge_hook: bridge.next_bridge_hook ?? '',
      });
    }
  }, [bridge, form]);

  const handleSave = async (values: UpdateBridgeRequest) => {
    if (!bridge) return;
    setSaving(true);
    try {
      const updated = await plotBridgesApi.update(bridge.id, values);
      toast.success('已保存');
      onSaved(updated);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={bridge ? `编辑桥段 #${bridge.bridge_number}` : '编辑桥段'}
      open={!!bridge}
      onCancel={onClose}
      footer={null}
      width={720}
      destroyOnClose
    >
      <Form layout="vertical" form={form} onFinish={handleSave}>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Form.Item label="桥段标题" name="title" rules={[{ required: true, max: 200 }]}>
            <Input placeholder="8-15 字简洁标题，如『拜师云鹿书院』" />
          </Form.Item>
          <Form.Item label="金手指用法" name="golden_finger_usage">
            <Input placeholder="本桥段如何使用金手指（20-40 字）" />
          </Form.Item>
        </div>
        <Form.Item label="桥段目标" name="goal" rules={[{ required: true }]}>
          <Input.TextArea rows={2} placeholder="本桥段要解决的具体问题（30-60 字）" />
        </Form.Item>
        <Form.Item label="装逼点设计" name="showoff_point" rules={[{ required: true }]}>
          <Input.TextArea rows={2} placeholder="装逼/爽点设计（40-80 字）" />
        </Form.Item>

        <div className="my-3 border-t pt-3">
          <Text strong className="mb-2 block">4 章内容卡（章纲展开时用）</Text>
        </div>
        <Form.Item label="C1 代入+信息差（5:5）" name="c1_intro">
          <Input.TextArea rows={3} placeholder="上半日常代入素材 + 下半信息差（80-120 字）" />
        </Form.Item>
        <Form.Item label="C2 拉扯+开装（9:1，章尾开装）" name="c2_build">
          <Input.TextArea rows={3} placeholder="拉扯素材 + 章尾开装动作（80-120 字）" />
        </Form.Item>
        <Form.Item label="C3 兑现爽点（10:0，无钩子）" name="c3_payoff">
          <Input.TextArea rows={3} placeholder="装逼完整展开 + 配角反应（80-120 字）" />
        </Form.Item>
        <Form.Item label="C4 善后+下一目标（承上启下）" name="c4_aftermath">
          <Input.TextArea rows={3} placeholder="本桥段收尾事件 + 下桥段引子（60-100 字）" />
        </Form.Item>
        <Form.Item label="给下一桥段的钩子" name="next_bridge_hook">
          <Input placeholder="20-40 字" />
        </Form.Item>

        <Form.Item className="!mb-0 text-right">
          <Button onClick={onClose} className="mr-2">取消</Button>
          <Button type="primary" htmlType="submit" loading={saving}>保存</Button>
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ============================================================
// 展开为 4 章弹窗
// ============================================================

function ExpandBridgeModal({
  bridge,
  onClose,
  onExpanded,
  modelOptions,
  defaultModel,
  loadingModels,
  refreshModels,
}: {
  bridge: PlotBridge | null;
  onClose: () => void;
  onExpanded: () => void;
  modelOptions: ModelOption[];
  defaultModel: string;
  loadingModels: boolean;
  refreshModels: () => void;
}) {
  const [form] = Form.useForm<{ start_chapter_number: number; model: string }>();
  const [expanding, setExpanding] = useState(false);

  // 异步加载完成、或弹窗打开时，把表单 model 字段同步到用户默认模型
  useEffect(() => {
    if (!bridge) return;
    const target = defaultModel || modelOptions[0]?.value;
    if (target) form.setFieldValue('model', target);
  }, [bridge, defaultModel, modelOptions, form]);

  const handleExpand = async (values: { start_chapter_number: number; model: string }) => {
    if (!bridge) return;
    setExpanding(true);
    try {
      const res = await plotBridgesApi.expand(bridge.id, values);
      toast.success(
        `已展开 ${res.chapter_count} 个章纲（第 ${values.start_chapter_number}-${values.start_chapter_number + 3} 章）`,
      );
      onExpanded();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '展开失败');
    } finally {
      setExpanding(false);
    }
  };

  return (
    <Modal
      title={bridge ? `展开「${bridge.title}」为 4 章` : '展开桥段'}
      open={!!bridge}
      onCancel={onClose}
      footer={null}
      width={480}
      destroyOnClose
    >
      <Form
        layout="vertical"
        form={form}
        initialValues={{
          start_chapter_number: 1,
          model: defaultModel || modelOptions[0]?.value || 'deepseek-v3',
        }}
        onFinish={handleExpand}
      >
        <Form.Item
          label="起始章号"
          name="start_chapter_number"
          rules={[{ required: true, type: 'number', min: 1 }]}
          extra="将生成连续 4 章：起始章 → 起始章+3"
        >
          <InputNumber min={1} className="w-full" />
        </Form.Item>
        <Form.Item
          label={
            <div className="flex items-center gap-2">
              <span>使用模型</span>
              <Tooltip title="重新从「设置」中配置的 API 拉取模型列表">
                <Button
                  type="text"
                  size="small"
                  icon={<ReloadOutlined spin={loadingModels} />}
                  onClick={refreshModels}
                />
              </Tooltip>
            </div>
          }
          name="model"
          rules={[{ required: true }]}
          extra="列表来自「设置」中配置的 API"
        >
          <Select
            options={modelOptions}
            loading={loadingModels}
            showSearch
            optionFilterProp="label"
            placeholder={loadingModels ? '加载模型中...' : '选择模型'}
          />
        </Form.Item>
        <Form.Item className="!mb-0 text-right">
          <Button onClick={onClose} className="mr-2">取消</Button>
          <Button
            type="primary"
            htmlType="submit"
            loading={expanding}
            icon={<ExpandAltOutlined />}
          >
            {expanding ? '正在展开...' : '展开为 4 章'}
          </Button>
        </Form.Item>
      </Form>
    </Modal>
  );
}
