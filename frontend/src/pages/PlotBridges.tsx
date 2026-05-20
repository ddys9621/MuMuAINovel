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
import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  Button,
  Card,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
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
} from '@ant-design/icons';
import { toast } from 'sonner';

import { plotBridgesApi } from '@/services/plotBridgesApi';
import {
  BRIDGE_STATUS_COLOR,
  BRIDGE_STATUS_LABEL,
  type PlotBridge,
  type UpdateBridgeRequest,
} from '@/types/plot_bridge';

const { Text, Paragraph } = Typography;

// 模型选项（与 backend MODEL_TIERS 对齐的主流模型）
const MODEL_OPTIONS = [
  { value: 'deepseek-v3', label: 'DeepSeek V3（推荐，64K 大窗口）' },
  { value: 'claude-sonnet-4-5', label: 'Claude Sonnet 4.5（旗舰，200K）' },
  { value: 'qwen-max', label: '通义千问 Max（32K）' },
  { value: 'doubao-pro-32k', label: '豆包 Pro 32K' },
  { value: 'gpt-4o', label: 'GPT-4o（128K）' },
  { value: 'glm-4', label: 'GLM-4（64K）' },
];

export default function PlotBridgesPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [bridges, setBridges] = useState<PlotBridge[]>([]);
  const [loading, setLoading] = useState(true);
  const [planning, setPlanning] = useState(false);
  const [planModalOpen, setPlanModalOpen] = useState(false);
  const [editingBridge, setEditingBridge] = useState<PlotBridge | null>(null);
  const [expandingBridge, setExpandingBridge] = useState<PlotBridge | null>(null);

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
    async (values: { bridge_count: number; model: string }) => {
      if (!projectId) return;
      setPlanning(true);
      try {
        const newBridges = await plotBridgesApi.plan(projectId, values);
        toast.success(`AI 已生成 ${newBridges.length} 个桥段`);
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
        </div>
      </header>

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
        <div className="space-y-3">
          {bridges.map((bridge) => (
            <BridgeCard
              key={bridge.id}
              bridge={bridge}
              onEdit={() => setEditingBridge(bridge)}
              onExpand={() => setExpandingBridge(bridge)}
              onDelete={() => handleDelete(bridge.id)}
            />
          ))}
        </div>
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
          layout="vertical"
          initialValues={{ bridge_count: 25, model: 'deepseek-v3' }}
          onFinish={handlePlan}
        >
          <Form.Item
            label="桥段数量"
            name="bridge_count"
            extra="1 桥段 ≈ 4 章，25 个桥段 ≈ 100 章"
            rules={[{ required: true, type: 'number', min: 1, max: 300 }]}
          >
            <InputNumber min={1} max={300} step={5} className="w-full" />
          </Form.Item>
          <Form.Item
            label="使用模型"
            name="model"
            rules={[{ required: true }]}
            extra="档位越高（XL > L > M > S），AI 能参考的拆书内容越深"
          >
            <Select options={MODEL_OPTIONS} />
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
  return (
    <Card
      size="small"
      className="hover:shadow-md transition-shadow"
      title={
        <div className="flex items-center gap-2">
          <span className="rounded bg-blue-50 px-2 py-0.5 text-sm font-medium text-blue-600">
            #{bridge.bridge_number}
          </span>
          <span className="font-semibold">{bridge.title}</span>
          <Tag color={BRIDGE_STATUS_COLOR[bridge.status]}>
            {BRIDGE_STATUS_LABEL[bridge.status]}
          </Tag>
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
}: {
  bridge: PlotBridge | null;
  onClose: () => void;
  onExpanded: () => void;
}) {
  const [form] = Form.useForm<{ start_chapter_number: number; model: string }>();
  const [expanding, setExpanding] = useState(false);

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
        initialValues={{ start_chapter_number: 1, model: 'deepseek-v3' }}
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
        <Form.Item label="使用模型" name="model" rules={[{ required: true }]}>
          <Select options={MODEL_OPTIONS} />
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
