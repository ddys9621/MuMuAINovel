import { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Button, Modal, Form, Input, Card, Select, Tabs, Row, Col, Tag, Progress, Typography, message, Empty, Drawer, Space } from 'antd';
import { ThunderboltOutlined, FileTextOutlined, CreditCardOutlined, NodeIndexOutlined, OrderedListOutlined, LinkOutlined, StarOutlined, EditOutlined } from '@ant-design/icons';
import { useStore } from '../store';
import { useOutlineSync } from '../store/hooks';
import { wizardStreamApi } from '../services/api';
import MCPSelector, { type MCPSelectorValue } from '../components/MCPSelector';
import PlotCardsEnhanced from './PlotCardsEnhanced';
import PlotLinesEnhanced from './PlotLinesEnhanced';
import ChapterOutlinesEnhanced from './ChapterOutlinesEnhanced';
import LinkOverview from './LinkOverview';

const { TextArea } = Input;
const { Paragraph } = Typography;

export default function Outline() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { currentProject, outlines } = useStore();
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateForm] = Form.useForm();
  // SSE进度状态
  const [sseProgress, setSSEProgress] = useState(0);
  const [sseMessage, setSSEMessage] = useState('');
  const [sseModalVisible, setSSEModalVisible] = useState(false);

  const { refreshOutlines, updateOutline } = useOutlineSync();

  // 组件挂载时刷新大纲数据，确保数据是最新的
  useEffect(() => {
    if (currentProject?.id) {
      refreshOutlines(currentProject.id);
    }
  }, [currentProject?.id, refreshOutlines]);
  
  // 编辑相关状态
  const [isEditDrawerVisible, setIsEditDrawerVisible] = useState(false);
  const [editForm] = Form.useForm();
  const [isEditing, setIsEditing] = useState(false);
  
  // MCP 选择器状态
  const [mcpSettings, setMcpSettings] = useState<MCPSelectorValue>({
    enable: false,
    selected: []
  });
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false);

  // 根据当前路由计算 activeKey
  const getActiveKey = () => {
    const path = location.pathname;
    if (path.endsWith('/plot-cards-enhanced')) return 'plot-cards-enhanced';
    if (path.endsWith('/plot-lines-enhanced')) return 'plot-lines-enhanced';
    if (path.endsWith('/chapter-outlines-enhanced')) return 'chapter-outlines-enhanced';
    if (path.endsWith('/link-overview')) return 'link-overview';
    return 'high-level-outline';
  };

  // Tab 切换处理
  const handleTabChange = (key: string) => {
    if (!projectId) return;
    
    if (key === 'high-level-outline') {
      navigate(`/project/${projectId}/outline`);
    } else {
      navigate(`/project/${projectId}/outline/${key}`);
    }
  };

  // 根据当前路由渲染对应视图
  const renderCurrentView = () => {
    const activeKey = getActiveKey();
    switch (activeKey) {
      case 'plot-cards-enhanced':
        return <PlotCardsEnhanced projectId={projectId} />;
      case 'plot-lines-enhanced':
        return <PlotLinesEnhanced projectId={projectId} />;
      case 'chapter-outlines-enhanced':
        return <ChapterOutlinesEnhanced projectId={projectId} />;
      case 'link-overview':
        return <LinkOverview projectId={projectId} />;
      default:
        return renderStoryPremise();
    }
  };

  if (!currentProject) return null;

  // 获取故事前提大纲（第一条记录）
  const storyOutline = outlines[0];

  const handleGenerate = async (values: any) => {
    try {
      setIsGenerating(true);
      
      // 关闭生成表单Modal
      setIsGenerateModalOpen(false);
      generateForm.resetFields();
      setMcpSettings({ enable: false, selected: [] });
      
      // 显示进度Modal
      setSSEProgress(0);
      setSSEMessage('正在连接AI服务...');
      setSSEModalVisible(true);
      
      // 准备请求数据（使用正确的流式大纲生成接口）
      const requestData = {
        project_id: currentProject.id,
        narrative_perspective: values.narrative_perspective || currentProject.narrative_perspective || '第三人称',
        target_words: currentProject.target_words || 100000,
        requirements: values.requirements,
        provider: values.provider,
        model: values.model,
        enable_mcp: mcpSettings.enable && mcpSettings.selected.length > 0,
        selected_plugins: mcpSettings.enable ? mcpSettings.selected : []
      };
      
      // 使用正确的流式API
      await wizardStreamApi.generateCompleteOutlineStream(requestData, {
        onProgress: (msg: string, progress: number) => {
          setSSEMessage(msg);
          setSSEProgress(progress);
        },
        onResult: (data: any) => {
          console.log('生成完成，结果:', data);
        },
        onError: (error: string) => {
          message.error(`生成失败: ${error}`);
          setSSEModalVisible(false);
          setIsGenerating(false);
        },
        onComplete: () => {
          message.success('高层大纲生成完成！');
          setSSEModalVisible(false);
          setIsGenerating(false);
          // 刷新大纲列表
          refreshOutlines();
        }
      });
      
    } catch (error) {
      console.error('AI生成失败:', error);
      message.error('AI生成失败');
      setSSEModalVisible(false);
      setIsGenerating(false);
    }
  };

  const showGenerateModal = () => {
    setIsGenerateModalOpen(true);
  };

  const handleGenerateModalOk = async () => {
    try {
      const values = await generateForm.validateFields();
      await handleGenerate(values);
    } catch (error) {
      // 表单验证失败，不关闭Modal
    }
  };

  const handleGenerateModalCancel = () => {
    setIsGenerateModalOpen(false);
    generateForm.resetFields();
    setMcpSettings({ enable: false, selected: [] });
  };

  // 显示编辑大纲抽屉
  const showEditDrawer = () => {
    if (!storyOutline) return;

    // 初始化表单数据
    editForm.setFieldsValue({
      title: storyOutline.title,
      content: storyOutline.content,
      status: storyOutline.status || 'published'
    });

    setIsEditDrawerVisible(true);
  };

  // 处理编辑提交
  const handleEditSubmit = async (values: any) => {
    if (!storyOutline) return;

    try {
      setIsEditing(true);

      // 更新大纲
      await updateOutline(storyOutline.id, {
        title: values.title,
        content: values.content,
        status: values.status,
        version: storyOutline.version || 1
      });

      setIsEditDrawerVisible(false);
      message.success('故事前提更新成功');
      // 刷新大纲数据
      refreshOutlines();

    } catch (error) {
      console.error('更新大纲失败:', error);
      message.error('更新失败，请重试');
    } finally {
      setIsEditing(false);
    }
  };

  // 解析故事大纲内容（支持JSON格式） - v4 修复版
  const parseOutlineContent = (content: string | undefined): Record<string, any> | null => {
    if (!content) return null;
    
    // 如果已经是对象，直接返回
    if (typeof content === 'object') {
      return content as Record<string, any>;
    }
    
    // 确保是字符串
    const str = String(content).trim();
    if (!str) return null;
    
    // 辅助函数：安全解析 JSON
    const safeParse = (s: string): any => {
      try {
        return JSON.parse(s);
      } catch {
        return null;
      }
    };
    
    // 递归解析，处理多层序列化
    const deepParse = (val: any, depth: number = 0): any => {
      if (depth > 5) return val; // 防止无限递归
      if (typeof val !== 'string') return val;
      
      const parsed = safeParse(val);
      if (parsed === null) return val;
      if (typeof parsed === 'string') {
        return deepParse(parsed, depth + 1);
      }
      return parsed;
    };
    
    // 尝试直接解析
    let result = deepParse(str);
    
    // 如果结果是有效对象，返回
    if (result && typeof result === 'object' && !Array.isArray(result)) {
      return result;
    }
    
    // 尝试提取 JSON 部分（处理前后有其他文本的情况）
    const startIdx = str.indexOf('{');
    const endIdx = str.lastIndexOf('}');
    if (startIdx !== -1 && endIdx > startIdx) {
      const jsonPart = str.substring(startIdx, endIdx + 1);
      result = deepParse(jsonPart);
      if (result && typeof result === 'object' && !Array.isArray(result)) {
        return result;
      }
    }
    
    // 解析失败，返回原始内容作为 premise
    return { premise: str };
  };

  // 渲染故事前提视图
  const renderStoryPremise = () => {
    if (!storyOutline) {
      return (
        <Empty
          description="还没有故事前提，开始创建吧！"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <Button type="primary" icon={<ThunderboltOutlined />} onClick={showGenerateModal}>
            AI生成故事前提
          </Button>
        </Empty>
      );
    }

    // 解析content字段（新版7要素，去除重复字段）
    const outlineData = parseOutlineContent(storyOutline.content);
    const premise = outlineData?.premise || storyOutline.content || '暂无内容';
    const goldenFinger = outlineData?.golden_finger;
    const sellingPoints = outlineData?.selling_points;
    const powerSystem = outlineData?.power_system;
    const mainTropes = outlineData?.main_tropes;
    const ultimateGoal = outlineData?.ultimate_goal;
    const openingHook = outlineData?.opening_hook;

    // 从项目获取关联信息（避免重复存储）
    const projectTitle = currentProject?.title || '未命名项目';
    const projectGenre = currentProject?.genre || '未设定';
    const projectTheme = currentProject?.theme || '未设定';

    return (
      <div style={{ padding: '0 0 24px 0' }}>
        {/* 顶部关联信息区 */}
        <Card size="small" style={{ marginBottom: 16, background: '#fafafa' }}>
          <Row justify="space-between" align="middle">
            <Col>
              <Space size="large">
                <span><strong>📚 书名：</strong>{projectTitle}</span>
                <span><strong>📁 类型：</strong><Tag color="blue">{projectGenre}</Tag></span>
                <span><strong>🎯 主题：</strong><Tag color="purple">{projectTheme}</Tag></span>
              </Space>
            </Col>
            <Col>
              <Space>
                <Button icon={<EditOutlined />} onClick={showEditDrawer}>
                  编辑前提
                </Button>
                <Button type="primary" icon={<ThunderboltOutlined />} onClick={showGenerateModal} loading={isGenerating}>
                  重新生成前提
                </Button>
              </Space>
            </Col>
          </Row>
          <div style={{ marginTop: 8 }}>
            <Tag color={(storyOutline.status || 'published') === 'published' ? 'green' : 'orange'}>
              {(storyOutline.status || 'published') === 'published' ? '已发布' : '草稿'}
            </Tag>
            <Tag>版本 {storyOutline.version || 1}</Tag>
            {storyOutline.updated_at && (
              <span style={{ color: '#666', fontSize: 12, marginLeft: 8 }}>
                更新于 {new Date(storyOutline.updated_at).toLocaleString()}
              </span>
            )}
          </div>
        </Card>

        {/* 故事梗概 */}
        <Card title="📖 故事梗概" size="small" style={{ marginBottom: 16 }}>
          <Paragraph style={{ fontSize: 15, lineHeight: 1.8, whiteSpace: 'pre-wrap', marginBottom: 0 }}>
            {premise}
          </Paragraph>
        </Card>

        <Row gutter={16}>
          {/* 金手指 */}
          {goldenFinger && (
            <Col span={12}>
              <Card title="✨ 金手指" size="small" style={{ marginBottom: 16 }}>
                <Paragraph style={{ marginBottom: 0 }}>{goldenFinger}</Paragraph>
              </Card>
            </Col>
          )}

          {/* 终极目标 */}
          {ultimateGoal && (
            <Col span={12}>
              <Card title="🏆 终极目标" size="small" style={{ marginBottom: 16 }}>
                <Paragraph style={{ marginBottom: 0 }}>{ultimateGoal}</Paragraph>
              </Card>
            </Col>
          )}
        </Row>

        <Row gutter={16}>
          {/* 升级路线 */}
          {powerSystem && (
            <Col span={12}>
              <Card title="📈 升级路线" size="small" style={{ marginBottom: 16 }}>
                <Paragraph style={{ marginBottom: 0, fontFamily: 'monospace' }}>{powerSystem}</Paragraph>
              </Card>
            </Col>
          )}

          {/* 开篇钩子 */}
          {openingHook && (
            <Col span={12}>
              <Card title="🪝 开篇钩子" size="small" style={{ marginBottom: 16 }}>
                <Paragraph style={{ marginBottom: 0 }}>{openingHook}</Paragraph>
              </Card>
            </Col>
          )}
        </Row>

        <Row gutter={16}>
          {/* 核心卖点 */}
          {sellingPoints && Array.isArray(sellingPoints) && sellingPoints.length > 0 && (
            <Col span={12}>
              <Card title="🎯 核心卖点" size="small" style={{ marginBottom: 16 }}>
                <Space wrap>
                  {sellingPoints.map((point: string, index: number) => (
                    <Tag key={index} color="blue">{point}</Tag>
                  ))}
                </Space>
              </Card>
            </Col>
          )}

          {/* 主要套路 */}
          {mainTropes && Array.isArray(mainTropes) && mainTropes.length > 0 && (
            <Col span={12}>
              <Card title="🎭 主要套路" size="small" style={{ marginBottom: 16 }}>
                <Space wrap>
                  {mainTropes.map((trope: string, index: number) => (
                    <Tag key={index} color="orange">{trope}</Tag>
                  ))}
                </Space>
              </Card>
            </Col>
          )}
        </Row>

        <div style={{ marginTop: 16, padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
          <Paragraph type="secondary" style={{ margin: 0, fontSize: 13 }}>
            💡 <strong>提示：</strong>故事前提专注于"这本书爽在哪里"，包含金手指、卖点、套路和升级路线。
            主角信息请在「角色设定」模块查看，世界观请在「世界设定」模块查看。
          </Paragraph>
        </div>
      </div>
    );
  };

  // Tab配置（只包含标签，不包含内容）
  const tabItems = [
    {
      key: 'high-level-outline',
      label: (
        <span>
          <FileTextOutlined />
          故事大纲
        </span>
      ),
    },
    {
      key: 'plot-lines-enhanced',
      label: (
        <span>
          <NodeIndexOutlined />
          <StarOutlined style={{ fontSize: 10, marginLeft: 4, color: '#faad14' }} />
          剧情线
        </span>
      ),
    },
    {
      key: 'chapter-outlines-enhanced',
      label: (
        <span>
          <OrderedListOutlined />
          <StarOutlined style={{ fontSize: 10, marginLeft: 4, color: '#faad14' }} />
          章纲
        </span>
      ),
    },
    {
      key: 'plot-cards-enhanced',
      label: (
        <span>
          <CreditCardOutlined />
          <StarOutlined style={{ fontSize: 10, marginLeft: 4, color: '#faad14' }} />
          剧情卡片
        </span>
      ),
    },
    {
      key: 'link-overview',
      label: (
        <span>
          <LinkOutlined />
          关联总览
        </span>
      ),
    },
  ];

  return (
    <>
      {/* SSE进度Modal */}
      <Modal
        title="生成大纲中"
        open={sseModalVisible}
        footer={null}
        closable={false}
        centered
        width={500}
      >
        <div style={{ padding: '20px 0' }}>
          <Progress
            percent={sseProgress}
            status={sseProgress === 100 ? 'success' : 'active'}
            strokeColor={{
              '0%': '#108ee9',
              '100%': '#87d068',
            }}
          />
          <div style={{
            marginTop: 16,
            color: '#666',
            fontSize: 14,
            minHeight: 40,
            lineHeight: '20px'
          }}>
            {sseMessage}
          </div>
        </div>
      </Modal>

      {/* 编辑故事前提抽屉 */}
      <Drawer
        title="编辑故事前提"
        placement="right"
        width={720}
        open={isEditDrawerVisible}
        onClose={() => setIsEditDrawerVisible(false)}
        footer={
          <div style={{ textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setIsEditDrawerVisible(false)}>
                取消
              </Button>
              <Button type="primary" onClick={() => editForm.submit()} loading={isEditing}>
                保存
              </Button>
            </Space>
          </div>
        }
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleEditSubmit}
        >
          <Form.Item
            name="title"
            label="标题"
            rules={[{ required: true, message: '请输入标题' }]}
          >
            <Input placeholder="请输入故事前提标题" />
          </Form.Item>

          <Form.Item
            name="content"
            label="故事前提"
            rules={[
              { required: true, message: '请输入故事前提' },
              { min: 50, message: '故事前提至少需要50个字符' },
              { max: 5000, message: '故事前提最多5000个字符' }
            ]}
            extra="用3-10句话说明：主角是谁、因为什么事件/动机、决定去做什么、会经历怎样的冲突、最终如何收尾"
          >
            <TextArea
              rows={12}
              placeholder="请输入故事前提，例如：&#10;&#10;主角是一名普通的高中生，名叫李明。某天他意外发现自己拥有了读心术的能力。为了弄清楚这个能力的来源，他决定深入调查。在调查过程中，他发现了一个隐藏在城市背后的超能力组织，该组织试图控制所有超能力者。李明必须在保护自己和朋友的同时，与这个强大的组织对抗。最终，他揭露了组织的阴谋，但也付出了失去部分记忆的代价。"
              showCount
              maxLength={5000}
            />
          </Form.Item>

          <Form.Item
            name="status"
            label="状态"
          >
            <Select>
              <Select.Option value="draft">草稿</Select.Option>
              <Select.Option value="published">已发布</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Drawer>

      {/* AI生成故事前提Modal */}
      <Modal
        title="生成故事前提"
        open={isGenerateModalOpen}
        onOk={handleGenerateModalOk}
        onCancel={handleGenerateModalCancel}
        width={600}
        centered
        okText="开始生成"
        cancelText="取消"
      >
        <Form
          form={generateForm}
          layout="vertical"
          style={{ marginTop: 16 }}
          initialValues={{
            narrative_perspective: currentProject.narrative_perspective || '第三人称',
            theme: currentProject.theme || '',
          }}
        >
          <Form.Item
            label="故事主题"
            name="theme"
            rules={[{ required: true, message: '请输入故事主题' }]}
          >
            <TextArea rows={3} placeholder="描述你的故事主题、核心设定和主要情节..." />
          </Form.Item>

          <Form.Item
            label="叙事视角"
            name="narrative_perspective"
            rules={[{ required: true, message: '请选择叙事视角' }]}
          >
            <Select>
              <Select.Option value="第一人称">第一人称</Select.Option>
              <Select.Option value="第三人称">第三人称</Select.Option>
              <Select.Option value="全知视角">全知视角</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item label="其他要求" name="requirements">
            <TextArea rows={2} placeholder="其他特殊要求（可选）" />
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
        </Form>
      </Modal>

      <div style={{ padding: '24px' }}>
        <Tabs
          activeKey={getActiveKey()}
          onChange={handleTabChange}
          items={tabItems}
          size="large"
        />
        <div style={{ marginTop: 24 }}>
          {renderCurrentView()}
        </div>
      </div>
    </>
  );
}
