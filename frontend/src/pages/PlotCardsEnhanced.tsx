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
  Tag,
  Popconfirm,
  Tooltip,
  Row,
  Col,
  Drawer,
  Tabs,
  Badge,
  Statistic,
  Descriptions,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  RobotOutlined,
  ReloadOutlined,
  LinkOutlined,
  FilterOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { usePlotCardSync } from '../store/plotHooks';
import { useStore } from '../store';
import { usePlotCardLinks } from '../hooks/useLinkManagement';
import { LinkSelector } from '../components/LinkSelector';
import MCPSelector, { type MCPSelectorValue } from '../components/MCPSelector';
import { SimpleLinkStatistics } from '../components/LinkStatistics';
import { plotLineApi, chapterOutlineApi } from '../services/api';
import type { PlotCard, PlotCardCreate, PlotCardUpdate, PlotCardGenerateRequest, PlotLine, ChapterOutline } from '../types';

const { TextArea } = Input;
const { Option } = Select;

interface PlotCardsEnhancedProps {
  projectId?: string;
}

const PlotCardsEnhanced: React.FC<PlotCardsEnhancedProps> = ({ projectId }) => {
  const [form] = Form.useForm();
  const [generateForm] = Form.useForm();
  
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isGenerateModalVisible, setIsGenerateModalVisible] = useState(false);
  const [isLinkDrawerVisible, setIsLinkDrawerVisible] = useState(false);
  const [isDetailModalVisible, setIsDetailModalVisible] = useState(false);
  const [editingCard, setEditingCard] = useState<PlotCard | null>(null);
  const [selectedCard, setSelectedCard] = useState<PlotCard | null>(null);
  const [viewingCard, setViewingCard] = useState<PlotCard | null>(null);
  const [selectedCardType, setSelectedCardType] = useState<string>('');
  const [selectedChapterOutlineId, setSelectedChapterOutlineId] = useState<string>('');
  const [selectedPlotLineId, setSelectedPlotLineId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [availablePlotLines, setAvailablePlotLines] = useState<PlotLine[]>([]);
  const [availableChapterOutlines, setAvailableChapterOutlines] = useState<ChapterOutline[]>([]);
  const [mcpSettings, setMcpSettings] = useState<MCPSelectorValue>({
    enable: false,
    selected: []
  });

  const {
    plotCards,
    refreshPlotCards,
    createPlotCard,
    updatePlotCard,
    deletePlotCard,
    generatePlotCards,
  } = usePlotCardSync();

  const { outlines, chapterOutlines, plotLines } = useStore();

  // 使用关联管理 Hook
  const {
    plotLines: linkedPlotLines,
    chapterOutlines: linkedChapterOutlines,
    loading: linkLoading,
    linkPlotLines,
    unlinkPlotLines,
    linkChapterOutlines,
    unlinkChapterOutlines,
  } = usePlotCardLinks(selectedCard?.id || '');

  // 卡片类型选项
  const cardTypeOptions = [
    { value: 'plot', label: '剧情事件', color: 'blue' },
    { value: 'character', label: '角色行为', color: 'green' },
    { value: 'scene', label: '场景描述', color: 'orange' },
    { value: 'conflict', label: '冲突矛盾', color: 'red' },
  ];

  useEffect(() => {
    if (projectId) {
      refreshPlotCards(projectId, { 
        card_type: selectedCardType || undefined,
        chapter_outline_id: selectedChapterOutlineId || undefined,
      });
    }
  }, [projectId, selectedCardType, selectedChapterOutlineId, refreshPlotCards]);

  const handleCreate = () => {
    setEditingCard(null);
    form.resetFields();
    setIsModalVisible(true);
  };

  const handleEdit = (card: PlotCard) => {
    setEditingCard(card);
    form.setFieldsValue({
      title: card.title,
      content: card.content,
      card_type: card.card_type,
      tags: card.tags,
    });
    setIsModalVisible(true);
  };

  const handleView = (card: PlotCard) => {
    setViewingCard(card);
    setIsDetailModalVisible(true);
  };

  const handleDelete = async (cardId: string) => {
    try {
      await deletePlotCard(cardId);
      if (projectId) {
        refreshPlotCards(projectId, { 
          card_type: selectedCardType || undefined,
          chapter_outline_id: selectedChapterOutlineId || undefined,
        });
      }
    } catch (error) {
      console.error('删除失败:', error);
    }
  };

  const handleSubmit = async (values: any) => {
    if (!projectId) return;

    try {
      setLoading(true);
      const cardData = {
        ...values,
        project_id: projectId,
        tags: values.tags || [],
      };

      if (editingCard) {
        await updatePlotCard(editingCard.id, cardData as PlotCardUpdate);
      } else {
        await createPlotCard(cardData as PlotCardCreate);
      }

      setIsModalVisible(false);
      refreshPlotCards(projectId, { 
        card_type: selectedCardType || undefined,
        chapter_outline_id: selectedChapterOutlineId || undefined,
      });
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
      const generateData: PlotCardGenerateRequest = {
        project_id: projectId,
        outline_id: values.outline_id,
        chapter_outline_id: values.chapter_outline_id,
        prompt: values.prompt,
        card_type: values.card_type || 'plot',
        count: values.count || 3,
        extend_from_card_id: values.extend_from_card_id,
        enable_mcp: mcpSettings.enable && mcpSettings.selected.length > 0,
        selected_plugins: mcpSettings.enable ? mcpSettings.selected : [],
      };

      await generatePlotCards(generateData);
      setIsGenerateModalVisible(false);
      generateForm.resetFields();
      setMcpSettings({ enable: false, selected: [] });
      refreshPlotCards(projectId, { 
        card_type: selectedCardType || undefined,
        chapter_outline_id: selectedChapterOutlineId || undefined,
      });
    } catch (error) {
      console.error('生成失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleManageLinks = async (card: PlotCard) => {
    setSelectedCard(card);
    await loadAvailableLinkData();
    setIsLinkDrawerVisible(true);
  };

  const getCardTypeColor = (type: string) => {
    const option = cardTypeOptions.find(opt => opt.value === type);
    return option?.color || 'default';
  };

  const getCardTypeLabel = (type: string) => {
    const option = cardTypeOptions.find(opt => opt.value === type);
    return option?.label || type;
  };

  const loadAvailableLinkData = async () => {
    if (!projectId) return;
    try {
      const [linesRes, outlinesRes] = await Promise.all([
        plotLineApi.getPlotLines(projectId),
        chapterOutlineApi.getChapterOutlines(projectId)
      ]);
      const lines = Array.isArray(linesRes) ? linesRes : (linesRes.items || []);
      const outlines = Array.isArray(outlinesRes) ? outlinesRes : (outlinesRes.items || []);
      setAvailablePlotLines(lines as PlotLine[]);
      setAvailableChapterOutlines(outlines as ChapterOutline[]);
    } catch (error) {
      console.error('加载关联数据失败:', error);
    }
  };

  const getPlotLineOptions = () => {
    const usedIds = new Set(linkedPlotLines.map(line => line.id));
    const availableLines = availablePlotLines.filter(line => !usedIds.has(line.id));
    return [
      ...linkedPlotLines,
      ...availableLines,
    ].map(line => ({
      id: line.id,
      title: line.title,
      subtitle: line.description,
    }));
  };

  const getChapterOutlineOptions = () => {
    const usedIds = new Set(linkedChapterOutlines.map(outline => outline.id));
    const availableOutlines = availableChapterOutlines.filter(outline => !usedIds.has(outline.id));
    return [
      ...linkedChapterOutlines,
      ...availableOutlines,
    ].map(outline => ({
      id: outline.id,
      title: `第${outline.chapter_number}章：${outline.title}`,
      subtitle: outline.summary,
    }));
  };

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      width: 220,
      fixed: 'left' as const,
      render: (text: string, record: PlotCard) => (
        <div>
          <Tooltip title={text}>
            <div style={{ fontWeight: 'bold', marginBottom: 4 }}>{text}</div>
          </Tooltip>
          <Tag color={getCardTypeColor(record.card_type)}>
            {getCardTypeLabel(record.card_type)}
          </Tag>
        </div>
      ),
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      render: (text: string) => (
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {text || '-'}
        </div>
      ),
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 150,
      render: (tags: string[]) => (
        <div>
          {tags?.slice(0, 2).map((tag, index) => (
            <Tag key={index}>{tag}</Tag>
          ))}
          {tags?.length > 2 && <Tag>+{tags.length - 2}</Tag>}
        </div>
      ),
    },
    {
      title: '关联',
      key: 'links',
      width: 150,
      render: (_: any, record: PlotCard) => {
        // 优先使用后端提供的统计字段，回退到数组长度
        const lineCount = record.plot_line_count ?? record.plot_lines?.length ?? 0;
        const outlineCount = record.chapter_outline_count ?? record.chapter_outlines?.length ?? 0;
        
        return (
          <SimpleLinkStatistics
            plotLineCount={lineCount}
            chapterOutlineCount={outlineCount}
          />
        );
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 200,
      fixed: 'right' as const,
      render: (_: any, record: PlotCard) => (
        <Space size="small">
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
            title="确定删除这个剧情卡片吗？"
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

  // 统计信息
  const cardTypeStats = cardTypeOptions.map(option => ({
    ...option,
    count: plotCards.filter(card => card.card_type === option.value).length,
  }));

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
          <Col>
            <h2 style={{ margin: 0 }}>剧情卡片（增强版）</h2>
            <p style={{ margin: '4px 0 0 0', color: '#666' }}>
              管理项目的剧情卡片，支持关联剧情线和章纲
            </p>
          </Col>
          <Col>
            <Space>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => projectId && refreshPlotCards(projectId, { 
                  card_type: selectedCardType || undefined,
                  chapter_outline_id: selectedChapterOutlineId || undefined,
                })}
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
                新建卡片
              </Button>
            </Space>
          </Col>
        </Row>

        {/* 筛选器 */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Select
              placeholder="筛选卡片类型"
              style={{ width: '100%' }}
              allowClear
              value={selectedCardType || undefined}
              onChange={setSelectedCardType}
              suffixIcon={<FilterOutlined />}
            >
              {cardTypeOptions.map(option => (
                <Option key={option.value} value={option.value}>
                  <Tag color={option.color} style={{ margin: 0 }}>
                    {option.label}
                  </Tag>
                </Option>
              ))}
            </Select>
          </Col>
          <Col span={9}>
            <Select
              placeholder="按剧情线筛选"
              style={{ width: '100%' }}
              allowClear
              value={selectedPlotLineId || undefined}
              onChange={setSelectedPlotLineId}
            >
              {plotLines.map(line => (
                <Option key={line.id} value={line.id}>
                  {line.title}
                </Option>
              ))}
            </Select>
          </Col>
          <Col span={9}>
            <Select
              placeholder="按章纲筛选"
              style={{ width: '100%' }}
              allowClear
              value={selectedChapterOutlineId || undefined}
              onChange={setSelectedChapterOutlineId}
            >
              {chapterOutlines.map(co => (
                <Option key={co.id} value={co.id}>
                  第{co.chapter_number}章：{co.title}
                </Option>
              ))}
            </Select>
          </Col>
        </Row>

        {/* 统计信息 */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Statistic title="总卡片数" value={plotCards.length} />
          </Col>
          {cardTypeStats.map(stat => (
            <Col span={4.5} key={stat.value}>
              <Statistic 
                title={stat.label} 
                value={stat.count}
                valueStyle={{ color: `var(--ant-${stat.color}-6)` }}
              />
            </Col>
          ))}
        </Row>

        <Table
          columns={columns}
          dataSource={plotCards}
          rowKey="id"
          scroll={{ x: 1300 }}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 个卡片`,
            pageSizeOptions: ['10', '20', '50'],
          }}
        />
      </Card>

      {/* 创建/编辑卡片弹窗 */}
      <Modal
        title={editingCard ? '编辑剧情卡片' : '新建剧情卡片'}
        open={isModalVisible}
        onCancel={() => setIsModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Form.Item
            name="title"
            label="卡片标题"
            rules={[{ required: true, message: '请输入卡片标题' }]}
          >
            <Input placeholder="请输入卡片标题" />
          </Form.Item>

          <Form.Item
            name="card_type"
            label="卡片类型"
            rules={[{ required: true, message: '请选择卡片类型' }]}
          >
            <Select placeholder="请选择卡片类型">
              {cardTypeOptions.map(option => (
                <Option key={option.value} value={option.value}>
                  <Tag color={option.color} style={{ margin: 0 }}>
                    {option.label}
                  </Tag>
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="content"
            label="卡片内容"
          >
            <TextArea
              rows={6}
              placeholder="请输入卡片内容描述"
            />
          </Form.Item>

          <Form.Item
            name="tags"
            label="标签"
          >
            <Select
              mode="tags"
              placeholder="请输入标签，按回车添加"
              style={{ width: '100%' }}
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setIsModalVisible(false)}>
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={loading}>
                {editingCard ? '更新' : '创建'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* AI生成卡片弹窗 */}
      <Modal
        title="AI生成剧情卡片"
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
            name="outline_id"
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
            name="chapter_outline_id"
            label="基于章纲"
          >
            <Select placeholder="选择要基于的章纲（可选）" allowClear>
              {chapterOutlines.map((chapterOutline: any) => (
                <Option key={chapterOutline.id} value={chapterOutline.id}>
                  第{chapterOutline.chapter_number}章：{chapterOutline.title}
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="card_type"
            label="卡片类型"
            initialValue="plot"
          >
            <Select>
              {cardTypeOptions.map(option => (
                <Option key={option.value} value={option.value}>
                  <Tag color={option.color} style={{ margin: 0 }}>
                    {option.label}
                  </Tag>
                </Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="count"
            label="生成数量"
            initialValue={3}
          >
            <Select>
              <Option value={1}>1个</Option>
              <Option value={3}>3个</Option>
              <Option value={5}>5个</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="prompt"
            label="生成提示"
          >
            <TextArea
              rows={4}
              placeholder="请输入生成提示词，描述您希望生成什么样的剧情卡片"
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
                生成卡片
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 剧情卡片详情弹窗 */}
      <Modal
        title="剧情卡片详情"
        open={isDetailModalVisible}
        onCancel={() => setIsDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setIsDetailModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        {viewingCard && (
          <div>
            <Descriptions column={2} bordered>
              <Descriptions.Item label="标题" span={2}>
                {viewingCard.title}
              </Descriptions.Item>
              <Descriptions.Item label="类型">
                <Tag color={getCardTypeColor(viewingCard.card_type)}>
                  {getCardTypeLabel(viewingCard.card_type)}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="标签">
                {viewingCard.tags?.length ? viewingCard.tags.join('，') : '无'}
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {new Date(viewingCard.created_at).toLocaleString()}
              </Descriptions.Item>
              <Descriptions.Item label="更新时间">
                {new Date(viewingCard.updated_at).toLocaleString()}
              </Descriptions.Item>
              <Descriptions.Item label="内容" span={2}>
                <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                  {viewingCard.content || '暂无内容'}
                </div>
              </Descriptions.Item>
            </Descriptions>
          </div>
        )}
      </Modal>

      {/* 关联管理抽屉 */}
      <Drawer
        title={
          <Space>
            <LinkOutlined />
            <span>管理关联 - {selectedCard?.title}</span>
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
        {selectedCard && (() => {
          const plotLineOptions = getPlotLineOptions();
          const chapterOutlineOptions = getChapterOutlineOptions();

          const tabItems = [
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
                  onLink={linkPlotLines}
                  onUnlink={unlinkPlotLines}
                  loading={linkLoading}
                  placeholder="选择要关联的剧情线"
                />
              )
            },
            {
              key: 'chapterOutlines',
              label: (
                <Badge count={linkedChapterOutlines.length} offset={[10, 0]}>
                  <span>章纲</span>
                </Badge>
              ),
              children: (
                <LinkSelector
                  options={chapterOutlineOptions}
                  selectedIds={linkedChapterOutlines.map(o => o.id)}
                  onLink={async (ids) => {
                    await linkChapterOutlines(ids.map(id => ({ chapter_outline_id: id, usage_type: 'reference', usage_notes: '' })));
                  }}
                  onUnlink={unlinkChapterOutlines}
                  loading={linkLoading}
                  placeholder="选择要关联的章纲"
                />
              )
            }
          ];

          return (
            <Tabs defaultActiveKey="plotLines" items={tabItems} />
          );
        })()}
      </Drawer>
    </div>
  );
};

export default PlotCardsEnhanced;
