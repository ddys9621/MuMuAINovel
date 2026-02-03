import React, { useState, useEffect } from 'react';
import {
  Card,
  Button,
  Space,
  Table,
  Modal,
  Form,
  Input,
  Select,
  InputNumber,
  Popconfirm,
  Tooltip,
  Row,
  Col,
  Statistic,
  Progress,
  Drawer,
  Tabs,
  Badge,
  Descriptions,
  Alert,
  // message,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  RobotOutlined,
  ReloadOutlined,
  BarChartOutlined,
  LinkOutlined,
  EyeOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useChapterOutlineSync, usePlotLineSync } from '../store/plotHooks';
import { useChapterOutlineLinks } from '../hooks/useLinkManagement';
import { LinkSelector } from '../components/LinkSelector';
import { SimpleLinkStatistics } from '../components/LinkStatistics';
import BeatsCoverageEditor from '../components/BeatsCoverageEditor';
import MCPSelector, { type MCPSelectorValue } from '../components/MCPSelector';
import SceneGenerator from '../components/SceneGenerator';
import { plotCardApi, chapterOutlineLinkApi } from '../services/api';
import type { ChapterOutline, ChapterOutlineCreate, ChapterOutlineUpdate, ChapterOutlineGenerateRequest, PlotCard, TimelineCoverageUpdate } from '../types';

const { TextArea } = Input;
const { Option } = Select;

interface ChapterOutlinesEnhancedProps {
  projectId?: string;
}

const ChapterOutlinesEnhanced: React.FC<ChapterOutlinesEnhancedProps> = ({ projectId }) => {
  const [form] = Form.useForm();
  const [generateForm] = Form.useForm();
  
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isGenerateModalVisible, setIsGenerateModalVisible] = useState(false);
  const [isStatsModalVisible, setIsStatsModalVisible] = useState(false);
  const [isLinkDrawerVisible, setIsLinkDrawerVisible] = useState(false);
  const [isDetailModalVisible, setIsDetailModalVisible] = useState(false);
  const [editingOutline, setEditingOutline] = useState<ChapterOutline | null>(null);
  const [selectedOutline, setSelectedOutline] = useState<ChapterOutline | null>(null);
  const [viewingOutline, setViewingOutline] = useState<ChapterOutline | null>(null);
  const [selectedPlotLineId, setSelectedPlotLineId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [statistics, setStatistics] = useState<any>(null);
  const [mcpSettings, setMcpSettings] = useState<MCPSelectorValue>({
    enable: false,
    selected: []
  });

  // 场景生成相关状态
  const [isSceneGeneratorVisible, setIsSceneGeneratorVisible] = useState(false);
  const [sceneGeneratorOutline, setSceneGeneratorOutline] = useState<ChapterOutline | null>(null);

  const {
    chapterOutlines,
    refreshChapterOutlines,
    createChapterOutline,
    updateChapterOutline,
    deleteChapterOutline,
    generateChapterOutlines,
    getChapterOutlineStatistics,
  } = useChapterOutlineSync();

  const { plotLines, refreshPlotLines } = usePlotLineSync();

  // 使用关联管理 Hook
  const {
    plotLines: linkedPlotLines,
    plotCards: linkedPlotCards,
    loading: linkLoading,
    linkPlotLines,
    unlinkPlotLines,
    linkPlotCards,
    unlinkPlotCards,
  } = useChapterOutlineLinks(selectedOutline?.id || '');

  const [availablePlotCards, setAvailablePlotCards] = useState<PlotCard[]>([]);

  useEffect(() => {
    if (projectId) {
      refreshChapterOutlines(projectId, { plot_line_id: selectedPlotLineId || undefined });
      refreshPlotLines(projectId);
    }
  }, [projectId, selectedPlotLineId, refreshChapterOutlines, refreshPlotLines]);

  const loadAvailablePlotCards = async () => {
    if (!projectId) return;
    try {
      const response = await plotCardApi.getPlotCards(projectId);
      const items = Array.isArray(response) ? response : (response.items || []);
      setAvailablePlotCards(items);
    } catch (error) {
      console.error('加载剧情卡片失败:', error);
    }
  };

  const handleCreate = () => {
    setEditingOutline(null);
    form.resetFields();
    // 自动设置下一个章节号
    const maxChapter = Math.max(0, ...chapterOutlines.map(o => o.chapter_number));
    form.setFieldsValue({ chapter_number: maxChapter + 1 });
    setIsModalVisible(true);
  };

  const handleEdit = (outline: ChapterOutline) => {
    setEditingOutline(outline);
    form.setFieldsValue({
      chapter_number: outline.chapter_number,
      title: outline.title,
      summary: outline.summary,
      plot_points: outline.plot_points,
      target_word_count: outline.target_word_count,
      key_events: outline.key_events,
      characters_involved: outline.characters_involved,
    });
    setIsModalVisible(true);
  };

  const handleView = (outline: ChapterOutline) => {
    setViewingOutline(outline);
    setIsDetailModalVisible(true);
  };

  const handleDelete = async (outlineId: string) => {
    try {
      await deleteChapterOutline(outlineId);
      if (projectId) {
        refreshChapterOutlines(projectId, { plot_line_id: selectedPlotLineId || undefined });
      }
    } catch (error) {
      console.error('删除失败:', error);
    }
  };

  const handleSubmit = async (values: any) => {
    if (!projectId) return;

    try {
      setLoading(true);
      const outlineData = {
        ...values,
        project_id: projectId,
        plot_line_id: selectedPlotLineId || undefined,
        key_events: values.key_events || [],
        characters_involved: values.characters_involved || [],
      };

      if (editingOutline) {
        await updateChapterOutline(editingOutline.id, outlineData as ChapterOutlineUpdate);
      } else {
        await createChapterOutline(outlineData as ChapterOutlineCreate);
      }

      setIsModalVisible(false);
      refreshChapterOutlines(projectId, { plot_line_id: selectedPlotLineId || undefined });
    } catch (error) {
      console.error('保存失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async (values: any) => {
    if (!projectId) return;

    try {
      setLoading(true);
      const generateData: ChapterOutlineGenerateRequest = {
        project_id: projectId,
        plot_line_id: values.plot_line_id,
        prompt: values.prompt,
        start_chapter: values.start_chapter || 1,
        chapter_count: values.chapter_count || 5,
        target_word_count: values.target_word_count || 3000,
        based_on_outline: values.based_on_outline !== false,
        enable_mcp: mcpSettings.enable && mcpSettings.selected.length > 0,
        selected_plugins: mcpSettings.enable ? mcpSettings.selected : [],
      };

      await generateChapterOutlines(generateData);
      setIsGenerateModalVisible(false);
      generateForm.resetFields();
      setMcpSettings({ enable: false, selected: [] });
      refreshChapterOutlines(projectId, { plot_line_id: selectedPlotLineId || undefined });
    } catch (error) {
      console.error('生成失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleShowStatistics = async () => {
    if (!projectId) return;
    
    try {
      const stats = await getChapterOutlineStatistics(projectId);
      setStatistics(stats);
      setIsStatsModalVisible(true);
    } catch (error) {
      console.error('获取统计信息失败:', error);
    }
  };

  const handleManageLinks = (outline: ChapterOutline) => {
    setSelectedOutline(outline);
    setIsLinkDrawerVisible(true);
    loadAvailablePlotCards();
  };

  // 保存节点覆盖度
  const handleSaveCoverage = async (linkId: string, data: TimelineCoverageUpdate) => {
    if (!selectedOutline) return;

    try {
      await chapterOutlineLinkApi.updateTimelineCoverage(
        selectedOutline.id,
        linkId,
        data
      );
      // 可以选择刷新数据或显示成功消息
    } catch (error) {
      console.error('保存覆盖度失败:', error);
      throw error;
    }
  };

  // 获取可用的剧情线（排除已关联的）
  const availablePlotLines = plotLines.filter(
    line => !linkedPlotLines.some(linked => linked.id === line.id)
  );

  const columns = [
    {
      title: '章节',
      dataIndex: 'chapter_number',
      key: 'chapter_number',
      width: 80,
      sorter: (a: ChapterOutline, b: ChapterOutline) => a.chapter_number - b.chapter_number,
      render: (num: number) => `第${num}章`,
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      width: 180,
      render: (text: string) => (
        <div style={{ fontWeight: 'bold' }}>{text}</div>
      ),
    },
    {
      title: '场景',
      dataIndex: 'scene',
      key: 'scene',
      width: 150,
      ellipsis: true,
      render: (text: string) => (
        <div style={{ color: '#666' }}>
          {text || '-'}
        </div>
      ),
    },
    {
      title: '视角',
      dataIndex: 'pov',
      key: 'pov',
      width: 80,
      render: (text: string) => (
        <div style={{ color: '#1890ff' }}>
          {text || '-'}
        </div>
      ),
    },
    {
      title: '目标字数',
      dataIndex: 'target_word_count',
      key: 'target_word_count',
      width: 100,
      render: (count: number) => `${count?.toLocaleString() || 0}字`,
    },
    {
      title: '关联',
      key: 'links',
      width: 150,
      render: (_: any, record: ChapterOutline) => {
        // 优先使用后端提供的统计字段，回退到数组长度
        const lineCount = record.plot_line_count ?? record.plot_lines?.length ?? 0;
        const cardCount = record.plot_card_count ?? record.plot_cards?.length ?? 0;
        
        return (
          <SimpleLinkStatistics
            plotLineCount={lineCount}
            plotCardCount={cardCount}
          />
        );
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 220,
      render: (_: any, record: ChapterOutline) => (
        <Space size="small">
          <Tooltip title="场景生成">
            <Button
              type="text"
              icon={<ThunderboltOutlined style={{ color: '#722ed1' }} />}
              onClick={() => {
                setSceneGeneratorOutline(record);
                setIsSceneGeneratorVisible(true);
              }}
            />
          </Tooltip>
          <Tooltip title="管理关联">
            <Button
              type="text"
              icon={<LinkOutlined />}
              onClick={() => handleManageLinks(record)}
            />
          </Tooltip>
          <Tooltip title="查看详情">
            <Button
              type="text"
              icon={<EyeOutlined />}
              onClick={() => handleView(record)}
            />
          </Tooltip>
          <Tooltip title="编辑">
            <Button
              type="text"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
          <Popconfirm
            title="确定删除这个章纲吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Tooltip title="删除">
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const totalWords = chapterOutlines.reduce((sum, outline) => sum + (outline.target_word_count || 0), 0);

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
          <Col>
            <h2 style={{ margin: 0 }}>章纲管理（增强版）</h2>
            <p style={{ margin: '4px 0 0 0', color: '#666' }}>
              管理项目的章节大纲，支持关联剧情线和剧情卡片
            </p>
          </Col>
          <Col>
            <Space>
              <Select
                placeholder="筛选剧情线"
                style={{ width: 150 }}
                allowClear
                value={selectedPlotLineId || undefined}
                onChange={setSelectedPlotLineId}
              >
                {plotLines.map((line: any) => (
                  <Option key={line.id} value={line.id}>
                    {line.title}
                  </Option>
                ))}
              </Select>
              <Button
                icon={<BarChartOutlined />}
                onClick={handleShowStatistics}
              >
                统计
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => projectId && refreshChapterOutlines(projectId, { plot_line_id: selectedPlotLineId || undefined })}
              >
                刷新
              </Button>
              <Button
                type="primary"
                icon={<RobotOutlined />}
                onClick={() => setIsGenerateModalVisible(true)}
              >
                AI生成
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleCreate}
              >
                新建章纲
              </Button>
            </Space>
          </Col>
        </Row>

        {/* 统计信息 */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Statistic title="总章节数" value={chapterOutlines.length} />
          </Col>
          <Col span={6}>
            <Statistic title="总目标字数" value={totalWords} suffix="字" />
          </Col>
          <Col span={6}>
            <Statistic title="平均字数" value={Math.round(totalWords / (chapterOutlines.length || 1))} suffix="字/章" />
          </Col>
          <Col span={6}>
            <Statistic title="完成进度" value={chapterOutlines.length} suffix={`/ ${chapterOutlines.length}`} />
          </Col>
        </Row>

        <Table
          columns={columns}
          dataSource={chapterOutlines}
          rowKey="id"
          pagination={{
            pageSize: 15,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 个章纲`,
          }}
        />
      </Card>

      {/* 创建/编辑章纲弹窗 */}
      <Modal
        title={editingOutline ? '编辑章纲' : '新建章纲'}
        open={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        footer={null}
        width={700}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="chapter_number"
                label="章节号"
                rules={[{ required: true, message: '请输入章节号' }]}
              >
                <InputNumber min={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="target_word_count"
                label="目标字数"
                initialValue={3000}
              >
                <InputNumber min={500} max={10000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="title"
            label="章节标题"
            rules={[{ required: true, message: '请输入章节标题' }]}
          >
            <Input placeholder="请输入章节标题（5-15字）" />
          </Form.Item>

          {/* 场景信息（新增） */}
          <Row gutter={16}>
            <Col span={16}>
              <Form.Item
                name="scene"
                label="📍 场景地点"
              >
                <Input placeholder="如：拳击场→后台走廊" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="pov"
                label="👁️ 视角角色"
              >
                <Input placeholder="如：阿泰" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="plot_points"
            label="📖 剧情要点"
            tooltip="描述本章核心剧情发展，包含角色行动、冲突展开、转折点，末尾描述情感变化"
          >
            <TextArea
              rows={5}
              placeholder="描述本章核心剧情发展（300-400字），包含角色行动、冲突展开、转折点。末尾用一句话描述情感变化（如：情感从麻木转向震惊与希望）"
            />
          </Form.Item>

          <Form.Item
            name="key_events"
            label="📌 关键事件"
            tooltip="3-5个关键事件，最后一条应为【钩子】开头的章末悬念"
          >
            <Select
              mode="tags"
              placeholder="请输入关键事件，按回车添加（最后一条建议以【钩子】开头）"
              style={{ width: '100%' }}
            />
          </Form.Item>

          <Form.Item
            name="characters_involved"
            label="👥 涉及角色"
          >
            <Select
              mode="tags"
              placeholder="请输入涉及的角色名字，按回车添加"
              style={{ width: '100%' }}
            />
          </Form.Item>

          <Alert
            type="info"
            message="专业网文章纲提示"
            description={
              <ul style={{ margin: 0, paddingLeft: 16 }}>
                <li>场景地点：用箭头表示场景切换，如"宗门广场→藏经阁"</li>
                <li>剧情要点：包含情感变化描述</li>
                <li>关键事件：最后一条以【钩子】开头，作为章末悬念</li>
              </ul>
            }
            showIcon
            style={{ marginBottom: 16 }}
          />

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setIsModalVisible(false)}>
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={loading}>
                {editingOutline ? '更新' : '创建'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* AI生成章纲弹窗 */}
      <Modal
        title="AI生成章纲"
        open={isGenerateModalVisible}
        onCancel={() => setIsGenerateModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form
          form={generateForm}
          layout="vertical"
          onFinish={handleGenerate}
        >
          <Form.Item
            name="plot_line_id"
            label="基于剧情线"
          >
            <Select placeholder="选择要基于的剧情线（可选）" allowClear>
              {plotLines.map((line: any) => (
                <Option key={line.id} value={line.id}>
                  {line.title}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="start_chapter"
                label="起始章节"
                initialValue={1}
              >
                <InputNumber min={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="chapter_count"
                label="生成数量"
                initialValue={5}
              >
                <InputNumber min={1} max={20} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="target_word_count"
            label="每章目标字数"
            initialValue={3000}
          >
            <InputNumber min={500} max={10000} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="prompt"
            label="生成提示"
          >
            <TextArea
              rows={4}
              placeholder="请输入生成提示词，描述您希望生成什么样的章纲"
            />
          </Form.Item>

          {/* MCP 插件选择器 */}
          <div style={{ marginTop: 16 }}>
            <div style={{ marginBottom: 8, fontSize: '14px', fontWeight: 500 }}>
              AI 增强插件
            </div>
            <MCPSelector
              value={mcpSettings}
              onChange={setMcpSettings}
              size="middle"
            />
          </div>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => {
                setIsGenerateModalVisible(false);
                generateForm.resetFields();
                setMcpSettings({ enable: false, selected: [] });
              }}>
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={loading}>
                生成章纲
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 统计信息弹窗 */}
      <Modal
        title="章纲统计信息"
        open={isStatsModalVisible}
        onCancel={() => setIsStatsModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setIsStatsModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={600}
      >
        {statistics && (
          <div>
            <Row gutter={16} style={{ marginBottom: 24 }}>
              <Col span={8}>
                <Statistic title="总章纲数" value={statistics.total_count} />
              </Col>
              <Col span={8}>
                <Statistic title="总目标字数" value={statistics.total_target_words} suffix="字" />
              </Col>
              <Col span={8}>
                <Statistic 
                  title="平均字数" 
                  value={Math.round(statistics.total_target_words / (statistics.total_count || 1))} 
                  suffix="字/章" 
                />
              </Col>
            </Row>

            {statistics.line_statistics && statistics.line_statistics.length > 0 && (
              <div>
                <h4>按剧情线统计</h4>
                {statistics.line_statistics.map((stat: any, index: number) => (
                  <div key={index} style={{ marginBottom: 16 }}>
                    <Row justify="space-between" align="middle">
                      <Col>
                        <strong>{stat.plot_line_id ? `剧情线 ${index + 1}` : '未分配剧情线'}</strong>
                      </Col>
                      <Col>
                        {stat.chapter_count} 章 / {stat.total_target_words?.toLocaleString() || 0} 字
                      </Col>
                    </Row>
                    <Progress 
                      percent={Math.round((stat.total_target_words / statistics.total_target_words) * 100)} 
                      size="small"
                      style={{ marginTop: 4 }}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* 章纲详情弹窗 */}
      <Modal
        title="章纲详情"
        open={isDetailModalVisible}
        onCancel={() => setIsDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setIsDetailModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        {viewingOutline && (
          <div>
            <Descriptions column={2} bordered>
              <Descriptions.Item label="章节序号">
                第{viewingOutline.chapter_number}章
              </Descriptions.Item>
              <Descriptions.Item label="目标字数">
                {viewingOutline.target_word_count || 3000} 字
              </Descriptions.Item>
              <Descriptions.Item label="标题" span={2}>
                <span style={{ fontWeight: 'bold', fontSize: '16px' }}>{viewingOutline.title}</span>
              </Descriptions.Item>
              {/* 场景信息（新增）- 仅当有数据时显示 */}
              {(viewingOutline.scene || viewingOutline.pov) && (
                <>
                  <Descriptions.Item label="📍 场景地点">
                    {viewingOutline.scene || <span style={{ color: '#999' }}>未设置</span>}
                  </Descriptions.Item>
                  <Descriptions.Item label="👁️ 视角角色">
                    <span style={{ color: viewingOutline.pov ? '#1890ff' : '#999' }}>
                      {viewingOutline.pov || '未设置'}
                    </span>
                  </Descriptions.Item>
                </>
              )}
              {/* 剧情信息 */}
              <Descriptions.Item label="📖 剧情要点" span={2}>
                <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.8 }}>
                  {viewingOutline.plot_points || '暂无剧情要点'}
                </div>
              </Descriptions.Item>
              <Descriptions.Item label="📌 关键事件" span={2}>
                <div>
                  {Array.isArray(viewingOutline.key_events) && viewingOutline.key_events.length > 0 ? (
                    <ol style={{ margin: 0, paddingLeft: 20 }}>
                      {viewingOutline.key_events.map((event, index) => (
                        <li key={index} style={{
                          marginBottom: 8,
                          color: event.startsWith('【钩子】') ? '#f5222d' : 'inherit',
                          fontWeight: event.startsWith('【钩子】') ? 'bold' : 'normal'
                        }}>
                          {event}
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <span style={{ color: '#999' }}>暂无关键事件</span>
                  )}
                </div>
              </Descriptions.Item>
              <Descriptions.Item label="👥 涉及角色" span={2}>
                <div>
                  {Array.isArray(viewingOutline.characters_involved) && viewingOutline.characters_involved.length > 0 ? (
                    viewingOutline.characters_involved.map((char, index) => (
                      <span key={index} style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        margin: '2px 4px 2px 0',
                        background: '#f0f0f0',
                        borderRadius: 4
                      }}>
                        {char}
                      </span>
                    ))
                  ) : (
                    <span style={{ color: '#999' }}>暂无角色信息</span>
                  )}
                </div>
              </Descriptions.Item>
              {/* 旧字段（兼容显示） */}
              {viewingOutline.summary && (
                <Descriptions.Item label="📝 章节摘要（旧）" span={2}>
                  <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: '#666' }}>
                    {viewingOutline.summary}
                  </div>
                </Descriptions.Item>
              )}
            </Descriptions>
            {/* 时间信息 - 单独一行确保布局稳定 */}
            <div style={{ marginTop: 16, display: 'flex', justifyContent: 'space-between', color: '#999', fontSize: 12 }}>
              <span>创建时间：{new Date(viewingOutline.created_at).toLocaleString()}</span>
              <span>更新时间：{new Date(viewingOutline.updated_at).toLocaleString()}</span>
            </div>
          </div>
        )}
      </Modal>

      {/* 关联管理抽屉 */}
      <Drawer
        title={
          <Space>
            <LinkOutlined />
            <span>管理关联 - {selectedOutline?.title}</span>
          </Space>
        }
        placement="right"
        width={600}
        open={isLinkDrawerVisible}
        onClose={() => setIsLinkDrawerVisible(false)}
        styles={{
          body: { 
            padding: '16px',
            height: 'calc(100vh - 108px)',
            overflow: 'auto'
          }
        }}
      >
        {selectedOutline && (() => {
          const plotLineOptions = [
            ...linkedPlotLines.map(line => ({
              id: line.id,
              title: line.title,
              subtitle: line.description,
            })),
            ...availablePlotLines.map(line => ({
              id: line.id,
              title: line.title,
              subtitle: line.description,
            }))
          ];

          const availableCards = availablePlotCards.filter(
            card => !linkedPlotCards.some(linked => linked.id === card.id)
          );

          const plotCardOptions = [
            ...linkedPlotCards.map(card => ({
              id: card.id,
              title: card.title,
              subtitle: card.content,
            })),
            ...availableCards.map(card => ({
              id: card.id,
              title: card.title,
              subtitle: card.content,
            }))
          ];

          const tabs = [
            {
              key: 'plotLines',
              label: (
                <Badge count={linkedPlotLines.length} offset={[10, 0]}>
                  <span>剧情线</span>
                </Badge>
              ),
              children: (
                <LinkSelector
                  options={plotLineOptions}
                  selectedIds={linkedPlotLines.map(l => l.id)}
                  onLink={async (ids) => {
                    await linkPlotLines(ids, 'main');
                  }}
                  onUnlink={unlinkPlotLines}
                  loading={linkLoading}
                  placeholder="选择要关联的剧情线"
                />
              )
            },
            {
              key: 'plotCards',
              label: (
                <Badge count={linkedPlotCards.length} offset={[10, 0]}>
                  <span>剧情卡片</span>
                </Badge>
              ),
              children: (
                <LinkSelector
                  options={plotCardOptions}
                  selectedIds={linkedPlotCards.map(card => card.id)}
                  onLink={linkPlotCards}
                  onUnlink={unlinkPlotCards}
                  loading={linkLoading}
                  placeholder="选择要关联的剧情卡片"
                />
              )
            },
            {
              key: 'coverage',
              label: '节点覆盖度',
              children: (
                <BeatsCoverageEditor
                  plotLines={linkedPlotLines}
                  chapterId={selectedOutline.id}
                  onSave={handleSaveCoverage}
                />
              )
            }
          ];

          return (
            <Tabs defaultActiveKey="plotLines" items={tabs} />
          );
        })()}
      </Drawer>

      {/* 场景生成器弹窗 */}
      <Modal
        title={null}
        open={isSceneGeneratorVisible}
        onCancel={() => {
          setIsSceneGeneratorVisible(false);
          setSceneGeneratorOutline(null);
        }}
        footer={null}
        width={900}
        destroyOnClose
      >
        {sceneGeneratorOutline && (
          <SceneGenerator
            chapterOutlineId={sceneGeneratorOutline.id}
            chapterTitle={`第${sceneGeneratorOutline.chapter_number}章 ${sceneGeneratorOutline.title}`}
            targetWordCount={sceneGeneratorOutline.target_word_count}
            onComplete={(content, wordCount) => {
              console.log('章节生成完成:', { content: content.slice(0, 100), wordCount });
              setIsSceneGeneratorVisible(false);
              setSceneGeneratorOutline(null);
              // 可以在这里处理生成完成后的逻辑，比如创建章节
            }}
            onCancel={() => {
              setIsSceneGeneratorVisible(false);
              setSceneGeneratorOutline(null);
            }}
          />
        )}
      </Modal>
    </div>
  );
};

export default ChapterOutlinesEnhanced;
