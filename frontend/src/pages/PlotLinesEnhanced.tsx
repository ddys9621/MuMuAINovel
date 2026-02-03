/**
 * 增强版剧情线页面
 * 集成关联管理功能
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Button,
  Space,
  Table,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  Tag,
  Popconfirm,
  Tooltip,
  Row,
  Col,
  Drawer,
  Tabs,
  Descriptions,
  Progress,
  Alert,
  Spin,
  List,
  Divider,
  message,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  RobotOutlined,
  ReloadOutlined,
  LinkOutlined,
  EyeOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { usePlotLineSync } from '../store/plotHooks';
import { useStore } from '../store';
import { usePlotLineLinks } from '../hooks/useLinkManagement';
import { SimpleLinkStatistics } from '../components/LinkStatistics';
import { LinkSelector } from '../components/LinkSelector';
import MCPSelector, { type MCPSelectorValue } from '../components/MCPSelector';
import TimelineEditorModal from '../components/TimelineEditorModal';
import { chapterOutlineApi, plotCardApi, plotLineApi } from '../services/api';
import type { PlotLine, PlotLineCreate, PlotLineUpdate, PlotLineGenerateRequest, ChapterOutline, PlotCard, PlotLineProgress, TimelineData } from '../types';

const { TextArea } = Input;
const { Option } = Select;

interface PlotLinesEnhancedProps {
  projectId?: string;
}

const PlotLinesEnhanced: React.FC<PlotLinesEnhancedProps> = ({ projectId }) => {
  const [form] = Form.useForm();
  const [generateForm] = Form.useForm();
  
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isGenerateModalVisible, setIsGenerateModalVisible] = useState(false);
  const [isLinkDrawerVisible, setIsLinkDrawerVisible] = useState(false);
  const [isDetailModalVisible, setIsDetailModalVisible] = useState(false);
  const [isTimelineModalVisible, setIsTimelineModalVisible] = useState(false);
  const [editingLine, setEditingLine] = useState<PlotLine | null>(null);
  const [selectedLine, setSelectedLine] = useState<PlotLine | null>(null);
  const [viewingLine, setViewingLine] = useState<PlotLine | null>(null);
  const [timelineLine, setTimelineLine] = useState<PlotLine | null>(null);
  const [selectedLineType, setSelectedLineType] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [tempTimelineData, setTempTimelineData] = useState<TimelineData | null>(null);
  const [mcpSettings, setMcpSettings] = useState<MCPSelectorValue>({
    enable: false,
    selected: []
  });

  // 关联管理相关状态
  const [availableChapterOutlines, setAvailableChapterOutlines] = useState<ChapterOutline[]>([]);
  const [availablePlotCards, setAvailablePlotCards] = useState<PlotCard[]>([]);

  // 进度相关状态
  const [currentLineProgress, setCurrentLineProgress] = useState<PlotLineProgress | null>(null);
  const [progressLoading, setProgressLoading] = useState(false);
  const [progressError, setProgressError] = useState<string>('');

  const {
    plotLines,
    refreshPlotLines,
    createPlotLine,
    updatePlotLine,
    deletePlotLine,
    generatePlotLines,
  } = usePlotLineSync();

  // const { generateChapterOutlines } = useChapterOutlineSync();

  const { outlines } = useStore();

  // 使用关联管理 Hook
  const {
    chapterOutlines: linkedChapterOutlines,
    plotCards: linkedPlotCards,
    loading: linkLoading,
    loadChapterOutlines,
    loadPlotCards,
    linkChapterOutlines,
    unlinkChapterOutlines,
    linkPlotCards,
    unlinkPlotCards,
  } = usePlotLineLinks(selectedLine?.id || '', {
    onSuccess: () => {
      // 刷新关联数据
      if (selectedLine) {
        loadChapterOutlines();
        loadPlotCards();
      }
    },
  });

  // 剧情线类型选项
  const lineTypeOptions = [
    { value: 'main', label: '主线剧情', color: 'red' },
    { value: 'sub', label: '支线剧情', color: 'blue' },
    { value: 'character', label: '角色线', color: 'green' },
  ];

  useEffect(() => {
    if (projectId) {
      refreshPlotLines(projectId, { line_type: selectedLineType || undefined });
    }
  }, [projectId, selectedLineType, refreshPlotLines]);

  // 加载可用的章纲和剧情卡片
  const loadAvailableData = useCallback(async () => {
    if (!projectId) return;
    
    try {
      const [chaptersRes, cardsRes] = await Promise.all([
        chapterOutlineApi.getChapterOutlines(projectId),
        plotCardApi.getPlotCards(projectId),
      ]);
      
      setAvailableChapterOutlines(chaptersRes.items || []);
      setAvailablePlotCards(cardsRes.items || []);
    } catch (error) {
      console.error('加载数据失败:', error);
    }
  }, [projectId]);

  // 打开关联管理抽屉
  const handleOpenLinkDrawer = async (line: PlotLine) => {
    console.log('打开关联管理抽屉，剧情线:', line.title);
    setSelectedLine(line);
    setIsLinkDrawerVisible(true);
    
    // 加载关联数据
    await loadAvailableData();
    
    // 使用 Hook 加载已关联的数据
    // 注意：这里需要等待 selectedLine 更新后再调用
    setTimeout(() => {
      loadChapterOutlines();
      loadPlotCards();
    }, 100);
  };

  const handleCreate = () => {
    setEditingLine(null);
    setTempTimelineData(null);
    form.resetFields();
    setIsModalVisible(true);
  };

  const handleEdit = (line: PlotLine) => {
    setEditingLine(line);
    setTempTimelineData(line.timeline_data as TimelineData || null);
    form.setFieldsValue({
      title: line.title,
      description: line.description,
      line_type: line.line_type,
    });
    setIsModalVisible(true);
  };

  const handleView = async (line: PlotLine) => {
    setViewingLine(line);
    setIsDetailModalVisible(true);

    // 加载剧情线进度
    setProgressLoading(true);
    setProgressError('');
    setCurrentLineProgress(null);

    try {
      const progressData = await plotLineApi.getPlotLineProgress(line.id);
      setCurrentLineProgress(progressData);
    } catch (error: any) {
      console.error('加载进度失败:', error);
      const errorMsg = error?.response?.data?.detail || error?.message || '加载进度失败';
      setProgressError(errorMsg);
    } finally {
      setProgressLoading(false);
    }
  };

  const handleCloseDetailModal = () => {
    setIsDetailModalVisible(false);
    setViewingLine(null);
    setCurrentLineProgress(null);
    setProgressError('');
    setProgressLoading(false);
  };

  const handleDelete = async (lineId: string) => {
    try {
      await deletePlotLine(lineId);
      if (projectId) {
        refreshPlotLines(projectId, { line_type: selectedLineType || undefined });
      }
    } catch (error) {
      console.error('删除失败:', error);
    }
  };

  // 打开时间线编辑器(从列表)
  const handleEditTimeline = (line: PlotLine) => {
    setTimelineLine(line);
    setIsTimelineModalVisible(true);
  };

  // 打开时间线编辑器(从创建/编辑Modal)
  const handleEditTimelineInModal = () => {
    // 创建一个临时的PlotLine对象用于编辑
    const tempLine: PlotLine = {
      id: editingLine?.id || 'temp',
      project_id: projectId || '',
      title: form.getFieldValue('title') || '新剧情线',
      description: form.getFieldValue('description'),
      line_type: form.getFieldValue('line_type') || 'main',
      timeline_data: tempTimelineData || undefined,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    setTimelineLine(tempLine);
    setIsTimelineModalVisible(true);
  };

  // 保存时间线
  const handleSaveTimeline = async (data: TimelineData) => {
    if (!timelineLine) return;

    try {
      // 如果是从列表编辑,直接保存到后端
      if (timelineLine.id !== 'temp') {
        await plotLineApi.updateTimeline(timelineLine.id, data);
        message.success('时间线保存成功');

        // 刷新剧情线列表
        if (projectId) {
          refreshPlotLines(projectId, { line_type: selectedLineType || undefined });
        }
      } else {
        // 如果是从创建/编辑Modal编辑,保存到临时状态
        setTempTimelineData(data);
        message.success('时间线已配置,请继续完成剧情线创建');
      }
    } catch (error) {
      console.error('时间线保存失败:', error);
      message.error('时间线保存失败');
      throw error;
    }
  };

  const handleSubmit = async (values: any) => {
    if (!projectId) return;

    try {
      setLoading(true);
      const lineData = {
        ...values,
        project_id: projectId,
        timeline_data: tempTimelineData || undefined,
      };

      if (editingLine) {
        await updatePlotLine(editingLine.id, lineData as PlotLineUpdate);
      } else {
        await createPlotLine(lineData as PlotLineCreate);
      }

      setIsModalVisible(false);
      setTempTimelineData(null);
      refreshPlotLines(projectId, { line_type: selectedLineType || undefined });
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
      const generateData: PlotLineGenerateRequest = {
        project_id: projectId,
        story_outline_id: values.story_outline_id,
        prompt: values.prompt,
        line_type: values.line_type || 'main',
        based_on_cards: values.based_on_cards,
        based_on_lines: values.based_on_lines,
        extend_existing: values.extend_existing || false,
        count: values.count || 3,
        enable_mcp: mcpSettings.enable && mcpSettings.selected.length > 0,
        selected_plugins: mcpSettings.enable ? mcpSettings.selected : [],
      };

      await generatePlotLines(generateData);
      setIsGenerateModalVisible(false);
      generateForm.resetFields();
      setMcpSettings({ enable: false, selected: [] });
      refreshPlotLines(projectId, { line_type: selectedLineType || undefined });
    } catch (error) {
      console.error('生成失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const getLineTypeColor = (type: string) => {
    const option = lineTypeOptions.find(opt => opt.value === type);
    return option?.color || 'default';
  };

  const getLineTypeLabel = (type: string) => {
    const option = lineTypeOptions.find(opt => opt.value === type);
    return option?.label || type;
  };

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      width: 220,
      fixed: 'left' as const,
      render: (text: string, record: PlotLine) => (
        <div>
          <Tooltip title={text}>
            <div style={{ fontWeight: 'bold', marginBottom: 4 }}>{text}</div>
          </Tooltip>
          <Tag color={getLineTypeColor(record.line_type)}>
            {getLineTypeLabel(record.line_type)}
          </Tag>
        </div>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      render: (text: string) => (
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {text || '-'}
        </div>
      ),
    },
    {
      title: '预计章节',
      dataIndex: 'estimated_chapters',
      key: 'estimated_chapters',
      width: 100,
      render: (value: number | undefined) => (
        <Tooltip title="完成该剧情线预计需要的章节数量">
          <Tag color="blue">{value ? `${value} 章` : '未设置'}</Tag>
        </Tooltip>
      ),
    },
    {
      title: '关联统计',
      key: 'links',
      width: 200,
      render: (_: any, record: PlotLine) => {
        // 优先使用后端提供的统计字段，回退到数组长度
        const chapterCount = record.chapter_outline_count ?? record.chapter_outlines?.length ?? 0;
        const cardCount = record.plot_card_count ?? record.plot_cards?.length ?? 0;


        return (
          <SimpleLinkStatistics
            chapterOutlineCount={chapterCount}
            plotCardCount={cardCount}
          />
        );
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 120,
      render: (text: string) => new Date(text).toLocaleDateString(),
    },
    {
      title: '操作',
      key: 'actions',
      width: 240,
      fixed: 'right' as const,
      render: (_: any, record: PlotLine) => (
        <Space size="small">
          <Tooltip title="管理关联">
            <Button
              type="text"
              icon={<LinkOutlined />}
              onClick={() => handleOpenLinkDrawer(record)}
            />
          </Tooltip>
          <Tooltip title="编辑时间线">
            <Button
              type="text"
              icon={<ClockCircleOutlined />}
              onClick={() => handleEditTimeline(record)}
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
            title="确定删除这条剧情线吗？"
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

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
          <Col>
            <h2 style={{ margin: 0 }}>剧情线管理</h2>
            <p style={{ margin: '4px 0 0 0', color: '#666' }}>
              管理项目的剧情线，关联章纲和剧情卡片形成完整的故事线
            </p>
          </Col>
          <Col>
            <Space>
              <Select
                placeholder="筛选类型"
                style={{ width: 120 }}
                allowClear
                value={selectedLineType || undefined}
                onChange={setSelectedLineType}
              >
                {lineTypeOptions.map(option => (
                  <Option key={option.value} value={option.value}>
                    <Tag color={option.color} style={{ margin: 0 }}>
                      {option.label}
                    </Tag>
                  </Option>
                ))}
              </Select>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => projectId && refreshPlotLines(projectId, { line_type: selectedLineType || undefined })}
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
                新建剧情线
              </Button>
            </Space>
          </Col>
        </Row>

        <Table
          columns={columns}
          dataSource={plotLines}
          rowKey="id"
          scroll={{ x: 1200 }}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条剧情线`,
            pageSizeOptions: ['10', '20', '50'],
          }}
        />
      </Card>

      {/* 创建/编辑剧情线弹窗 */}
      <Modal
        title={editingLine ? '编辑剧情线' : '新建剧情线'}
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
          <Form.Item
            name="title"
            label="剧情线标题"
            rules={[{ required: true, message: '请输入剧情线标题' }]}
          >
            <Input placeholder="请输入剧情线标题" />
          </Form.Item>

          <Form.Item
            name="line_type"
            label="剧情线类型"
            rules={[{ required: true, message: '请选择剧情线类型' }]}
          >
            <Select placeholder="请选择剧情线类型">
              {lineTypeOptions.map(option => (
                <Option key={option.value} value={option.value}>
                  <Tag color={option.color} style={{ margin: 0 }}>
                    {option.label}
                  </Tag>
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="description"
            label="剧情线描述"
          >
            <TextArea
              rows={4}
              placeholder="请输入剧情线描述"
            />
          </Form.Item>

          <Form.Item
            name="estimated_chapters"
            label="预计章节数"
            tooltip="完成该剧情线预计需要的章节数量。AI 会根据剧情线复杂度自动估算，也可手动调整"
          >
            <InputNumber
              min={1}
              max={999}
              placeholder="如: 25"
              style={{ width: '100%' }}
            />
          </Form.Item>

          <Form.Item label="时间线配置">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Button
                icon={<ClockCircleOutlined />}
                onClick={handleEditTimelineInModal}
                block
              >
                {tempTimelineData ? '编辑时间线 (已配置)' : '配置时间线 (可选)'}
              </Button>
              {tempTimelineData && (
                <Alert
                  type="success"
                  message={`已配置 ${tempTimelineData.beats?.length || 0} 个节点`}
                  showIcon
                />
              )}
            </Space>
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setIsModalVisible(false)}>
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={loading}>
                {editingLine ? '更新' : '创建'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* AI生成剧情线弹窗 */}
      <Modal
        title="AI生成剧情线"
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
            name="story_outline_id"
            label="基于大纲"
          >
            <Select placeholder="选择要基于的大纲（可选）" allowClear>
              {outlines.map((outline: any) => (
                <Option key={outline.id} value={outline.id}>
                  {outline.title}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="line_type"
            label="剧情线类型"
            initialValue="main"
          >
            <Select>
              {lineTypeOptions.map(option => (
                <Option key={option.value} value={option.value}>
                  <Tag color={option.color} style={{ margin: 0 }}>
                    {option.label}
                  </Tag>
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="based_on_lines"
            label="参考剧情线"
            tooltip="选择要延续的历史剧情线，新生成的剧情线将基于这些内容保持连贯性"
          >
            <Select
              mode="multiple"
              placeholder="选择要参考的剧情线（可选）"
              allowClear
              showSearch
              filterOption={(input, option) =>
                option?.label?.toString().toLowerCase().includes(input.toLowerCase()) || false
              }
            >
              {plotLines
                .sort((a, b) => (b.order_index || 0) - (a.order_index || 0))
                .map((line: PlotLine) => (
                  <Option key={line.id} value={line.id}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Tag color={lineTypeOptions.find(opt => opt.value === line.line_type)?.color || 'default'}>
                        {lineTypeOptions.find(opt => opt.value === line.line_type)?.label || line.line_type}
                      </Tag>
                      <span>{line.title}</span>
                    </div>
                  </Option>
                ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="count"
            label="生成数量"
            initialValue={3}
            rules={[{ required: true, message: '请选择生成数量' }]}
          >
            <Select placeholder="选择要生成的剧情线数量">
              {[1, 2, 3, 4, 5].map(num => (
                <Option key={num} value={num}>{num}条</Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="prompt"
            label="生成提示"
          >
            <TextArea
              rows={4}
              placeholder="请输入生成提示词，描述您希望生成什么样的剧情线"
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
                生成剧情线
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 剧情线详情弹窗 */}
      <Modal
        title="剧情线详情"
        open={isDetailModalVisible}
        onCancel={handleCloseDetailModal}
        footer={[
          <Button key="close" onClick={handleCloseDetailModal}>
            关闭
          </Button>
        ]}
        width={800}
      >
        {viewingLine && (
          <div>
            <Descriptions column={2} bordered>
              <Descriptions.Item label="标题" span={2}>
                {viewingLine.title}
              </Descriptions.Item>
              <Descriptions.Item label="类型">
                <Tag color={getLineTypeColor(viewingLine.line_type)}>
                  {getLineTypeLabel(viewingLine.line_type)}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="预计章节数">
                {viewingLine.estimated_chapters ? (
                  <Tag color="blue">{viewingLine.estimated_chapters} 章</Tag>
                ) : (
                  <span style={{ color: '#999' }}>未设置</span>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="关联章纲数">
                {viewingLine.chapter_outline_count || 0} 个
              </Descriptions.Item>
              <Descriptions.Item label="关联卡片数">
                {viewingLine.plot_card_count || 0} 个
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {new Date(viewingLine.created_at).toLocaleString()}
              </Descriptions.Item>
              <Descriptions.Item label="描述" span={2}>
                <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {viewingLine.description || '暂无描述'}
                </div>
              </Descriptions.Item>
            </Descriptions>

            {/* 写作进度区块 */}
            <Divider orientation="left">写作进度（基于剧情线节点）</Divider>

            {progressLoading && (
              <div style={{ textAlign: 'center', padding: '20px 0' }}>
                <Spin tip="加载进度数据中..." />
              </div>
            )}

            {!progressLoading && progressError && (
              <Alert
                message="进度加载失败"
                description={progressError}
                type="error"
                showIcon
                style={{ marginBottom: 16 }}
              />
            )}

            {!progressLoading && !progressError && currentLineProgress && (
              <div>
                {/* 无节点配置提示 */}
                {!currentLineProgress.has_beats && (
                  <Alert
                    message="该剧情线尚未配置节点结构（beats）"
                    description={currentLineProgress.message || '无法计算进度，请先为该剧情线配置节点结构。'}
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                )}

                {/* 有节点配置时展示进度 */}
                {currentLineProgress.has_beats && (
                  <>
                    {/* 整体进度条 */}
                    <div style={{ marginBottom: 24 }}>
                      <div style={{ marginBottom: 8, fontWeight: 500 }}>
                        整体进度：{currentLineProgress.total_progress !== null
                          ? `${(currentLineProgress.total_progress * 100).toFixed(1)}%`
                          : '无法计算'}
                      </div>
                      <Progress
                        percent={currentLineProgress.total_progress !== null
                          ? Math.round(currentLineProgress.total_progress * 100)
                          : 0}
                        status={
                          currentLineProgress.total_progress === 1
                            ? 'success'
                            : currentLineProgress.total_progress && currentLineProgress.total_progress > 0
                              ? 'active'
                              : 'normal'
                        }
                        strokeColor={{
                          '0%': '#108ee9',
                          '100%': '#87d068',
                        }}
                      />
                      <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
                        已关联章纲：{currentLineProgress.linked_chapters_count} 个
                      </div>
                    </div>

                    {/* 节点列表 */}
                    {currentLineProgress.beats && currentLineProgress.beats.length > 0 && (
                      <div>
                        <div style={{ marginBottom: 12, fontWeight: 500 }}>节点详情：</div>
                        <List
                          grid={{ gutter: 12, xs: 1, sm: 1, md: 2, lg: 2, xl: 2, xxl: 2 }}
                          dataSource={currentLineProgress.beats}
                          renderItem={(beat) => {
                            // 节点类型中文映射
                            const beatTypeMap: Record<string, string> = {
                              opening: '开端',
                              inciting_incident: '触发事件',
                              first_turning_point: '第一转折点',
                              rising_action: '上升行动',
                              midpoint: '中点',
                              second_turning_point: '第二转折点',
                              climax: '高潮',
                              falling_action: '下降行动',
                              resolution: '结局',
                            };

                            // 状态配置
                            const statusConfig = {
                              completed: {
                                borderColor: '#52c41a',
                                bgColor: '#f6ffed',
                                text: '已完成',
                                tagColor: 'success',
                                icon: '✓'
                              },
                              in_progress: {
                                borderColor: '#1890ff',
                                bgColor: '#e6f7ff',
                                text: '进行中',
                                tagColor: 'processing',
                                icon: '▶'
                              },
                              not_started: {
                                borderColor: '#d9d9d9',
                                bgColor: '#fafafa',
                                text: '未开始',
                                tagColor: 'default',
                                icon: '○'
                              },
                            };
                            const config = statusConfig[beat.status] || statusConfig.not_started;
                            const beatTypeCN = beatTypeMap[beat.key as keyof typeof beatTypeMap] || beat.key;

                            return (
                              <List.Item style={{ marginBottom: 0 }}>
                                <Card
                                  size="small"
                                  style={{
                                    borderLeft: `3px solid ${config.borderColor}`,
                                    backgroundColor: config.bgColor,
                                    transition: 'all 0.3s',
                                    height: '100%',
                                  }}
                                  bodyStyle={{ padding: '10px 12px' }}
                                  hoverable
                                >
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                                        <span style={{ fontSize: 14 }}>{config.icon}</span>
                                        <span style={{ fontWeight: 600, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                          节点 {beat.index}: {beat.title}
                                        </span>
                                      </div>
                                      <div style={{ fontSize: 11, color: '#8c8c8c', marginLeft: 20 }}>
                                        {beatTypeCN}
                                      </div>
                                    </div>
                                    <Tag color={config.tagColor} style={{ margin: 0, fontSize: 11, padding: '0 6px', lineHeight: '20px' }}>
                                      {config.text}
                                    </Tag>
                                  </div>

                                  {beat.description && (
                                    <div style={{
                                      marginTop: 8,
                                      marginBottom: 8,
                                      padding: '8px 10px',
                                      backgroundColor: 'rgba(0, 0, 0, 0.02)',
                                      borderRadius: 4,
                                      fontSize: 12,
                                      color: '#595959',
                                      lineHeight: '1.6',
                                      whiteSpace: 'pre-wrap',
                                      wordBreak: 'break-word'
                                    }}>
                                      {beat.description}
                                    </div>
                                  )}

                                  <div style={{ marginTop: 8, marginBottom: 6 }}>
                                    <Progress
                                      percent={Math.round(beat.coverage * 100)}
                                      size="small"
                                      strokeColor={config.borderColor}
                                      trailColor="#f0f0f0"
                                      format={(percent) => `${percent}%`}
                                      strokeWidth={6}
                                    />
                                  </div>

                                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#595959' }}>
                                    <span>权重: {(beat.weight * 100).toFixed(0)}%</span>
                                    <span>覆盖度: {(beat.coverage * 100).toFixed(0)}%</span>
                                  </div>
                                </Card>
                              </List.Item>
                            );
                          }}
                        />
                      </div>
                    )}

                  </>
                )}
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* 关联管理抽屉 */}
      <Drawer
        title={`管理关联 - ${selectedLine?.title}`}
        placement="right"
        width={720}
        onClose={() => setIsLinkDrawerVisible(false)}
        open={isLinkDrawerVisible}
        styles={{
          body: { 
            padding: '16px',
            height: 'calc(100vh - 108px)',
            overflow: 'auto'
          }
        }}
      >
        {selectedLine && (() => {
          const chapterTab = {
            key: 'chapter',
            label: '关联章纲',
            children: (
              <LinkSelector
                options={[
                  // 合并已关联的和可选的，确保已关联的项也在选项中
                  ...linkedChapterOutlines.map(outline => ({
                    id: outline.id,
                    title: `第${outline.chapter_number}章：${outline.title}`,
                    subtitle: outline.summary,
                  })),
                  ...availableChapterOutlines
                    .filter(outline => !linkedChapterOutlines.some(linked => linked.id === outline.id))
                    .map(outline => ({
                      id: outline.id,
                      title: `第${outline.chapter_number}章：${outline.title}`,
                      subtitle: outline.summary,
                    }))
                ]}
                selectedIds={linkedChapterOutlines.map(o => typeof o === 'string' ? o : o.id)}
                onLink={async (ids) => {
                  await linkChapterOutlines(ids, 'main');
                }}
                onUnlink={async (ids) => {
                  await unlinkChapterOutlines(ids);
                }}
                loading={linkLoading}
                placeholder="选择要关联的章纲"
              />
            )
          };

          const plotCardTab = {
            key: 'plotCards',
            label: '关联剧情卡片',
            children: (() => {
              const allOptions = [
                ...linkedPlotCards.map(card => ({
                  id: card.id,
                  title: card.title,
                  subtitle: card.content,
                  extra: <Tag color="blue">{card.card_type}</Tag>,
                })),
                ...availablePlotCards
                  .filter(card => !linkedPlotCards.some(linked => linked.id === card.id))
                  .map(card => ({
                    id: card.id,
                    title: card.title,
                    subtitle: card.content,
                    extra: <Tag color="blue">{card.card_type}</Tag>,
                  }))
              ];
              const selectedIds = linkedPlotCards.map(c => typeof c === 'string' ? c : c.id);

              return (
                <LinkSelector
                  options={allOptions}
                  selectedIds={selectedIds}
                  onLink={async (ids) => {
                    await linkPlotCards(ids);
                  }}
                  onUnlink={async (ids) => {
                    await unlinkPlotCards(ids);
                  }}
                  loading={linkLoading}
                  placeholder="选择要关联的剧情卡片"
                />
              );
            })()
          };

          return (
            <Tabs defaultActiveKey="chapter" items={[chapterTab, plotCardTab]} />
          );
        })()}
      </Drawer>

      {/* 时间线编辑器 */}
      <TimelineEditorModal
        visible={isTimelineModalVisible}
        plotLine={timelineLine}
        onClose={() => {
          setIsTimelineModalVisible(false);
          setTimelineLine(null);
        }}
        onSave={handleSaveTimeline}
      />
    </div>
  );
};

export default PlotLinesEnhanced;
