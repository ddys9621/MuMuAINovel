import { useState, useEffect } from 'react';
import {
  Button,
  Modal,
  Form,
  Input,
  message,
  Card,
  Space,
  Tag,
  Popconfirm,
  Empty,
  Typography,
  Row,
  Col,
  Tooltip
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  StarOutlined,
  StarFilled
} from '@ant-design/icons';
import { useStore } from '../store';
import { writingStyleApi } from '../services/api';
import type { WritingStyle, WritingStyleCreate, WritingStyleUpdate } from '../types';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

export default function WritingStyles() {
  const { currentProject } = useStore();
  const [styles, setStyles] = useState<WritingStyle[]>([]);
  const [loading, setLoading] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingStyle, setEditingStyle] = useState<WritingStyle | null>(null);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const isMobile = window.innerWidth <= 768;
  
  // 卡片网格配置
  const gridConfig = {
    gutter: isMobile ? 8 : 16, // 卡片之间的间距
    xs: 24,
    sm: 24,
    md: 12,
    lg: 8,
    xl: 6,
  };

  // 加载项目风格
  useEffect(() => {
    if (currentProject?.id) {
      loadProjectStyles();
    }
  }, [currentProject?.id]);

  const loadProjectStyles = async () => {
    if (!currentProject?.id) return;
    
    try {
      setLoading(true);
      const response = await writingStyleApi.getProjectStyles(currentProject.id);
      // 对风格列表进行排序：默认风格优先，然后按原有顺序
      const sortedStyles = (response.styles || []).sort((a, b) => {
        // 默认风格排在前面
        if (a.is_default && !b.is_default) return -1;
        if (!a.is_default && b.is_default) return 1;
        return 0;
      });
      setStyles(sortedStyles);
    } catch {
      message.error('加载风格列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (values: { name: string; description?: string; prompt_content: string }) => {
    if (!currentProject?.id) return;

    try {
      const createData: WritingStyleCreate = {
        project_id: currentProject.id,
        name: values.name,
        style_type: 'custom',
        description: values.description,
        prompt_content: values.prompt_content,
      };

      await writingStyleApi.createStyle(createData);
      message.success('创建成功');
      setIsCreateModalOpen(false);
      createForm.resetFields();
      await loadProjectStyles();
    } catch {
      message.error('创建失败');
    }
  };

  const handleEdit = (style: WritingStyle) => {
    setEditingStyle(style);
    editForm.setFieldsValue({
      name: style.name,
      description: style.description,
      prompt_content: style.prompt_content,
    });
    setIsEditModalOpen(true);
  };

  const handleUpdate = async (values: WritingStyleUpdate) => {
    if (!editingStyle) return;

    try {
      await writingStyleApi.updateStyle(editingStyle.id, values);
      message.success('更新成功');
      setIsEditModalOpen(false);
      editForm.resetFields();
      setEditingStyle(null);
      await loadProjectStyles();
    } catch {
      message.error('更新失败');
    }
  };

  const handleDelete = async (styleId: number) => {
    try {
      await writingStyleApi.deleteStyle(styleId);
      message.success('删除成功');
      await loadProjectStyles();
    } catch {
      message.error('删除失败');
    }
  };

  const handleSetDefault = async (styleId: number) => {
    if (!currentProject?.id) return;
    
    try {
      await writingStyleApi.setDefaultStyle(styleId, currentProject.id);
      message.success('设置默认风格成功');
      await loadProjectStyles();
    } catch {
      message.error('设置失败');
    }
  };

  const showCreateModal = () => {
    createForm.resetFields();
    setIsCreateModalOpen(true);
  };

  if (!currentProject) return null;

  const getStyleTypeColor = (styleType: string) => {
    return styleType === 'preset' ? 'blue' : 'purple';
  };

  const getStyleTypeLabel = (styleType: string) => {
    return styleType === 'preset' ? '预设' : '自定义';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{
        position: 'sticky',
        top: 0,
        zIndex: 10,
        backgroundColor: '#fff',
        padding: isMobile ? '12px 0' : '16px 0',
        marginBottom: isMobile ? 12 : 16,
        borderBottom: '1px solid #f0f0f0',
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        gap: isMobile ? 12 : 0,
        justifyContent: 'space-between',
        alignItems: isMobile ? 'stretch' : 'center'
      }}>
        <h2 style={{ margin: 0, fontSize: isMobile ? 18 : 24 }}>写作风格管理</h2>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={showCreateModal}
          block={isMobile}
        >
          创建自定义风格
        </Button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {styles.length === 0 ? (
          <Empty description="暂无风格数据" />
        ) : (
          <Row
            gutter={[0, gridConfig.gutter]}
            style={{ marginLeft: 0, marginRight: 0 }}
          >
            {styles.map((style) => (
              <Col
                xs={gridConfig.xs}
                sm={gridConfig.sm}
                md={gridConfig.md}
                lg={gridConfig.lg}
                xl={gridConfig.xl}
                key={style.id}
                style={{
                  paddingLeft: 0,
                  paddingRight: gridConfig.gutter / 2,
                  marginBottom: gridConfig.gutter
                }}
              >
                <Card
                  hoverable
                  style={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    borderRadius: 12,
                    border: style.is_default ? '2px solid #1890ff' : '1px solid #f0f0f0',
                  }}
                  styles={{
                    body: {
                      flex: 1,
                      display: 'flex',
                      flexDirection: 'column',
                      padding: '16px',
                    }
                  }}
                  actions={[
                    <Tooltip key="default" title={style.is_default ? '当前默认' : '设为默认'}>
                      <span
                        onClick={() => !style.is_default && handleSetDefault(style.id)}
                        style={{ cursor: style.is_default ? 'default' : 'pointer' }}
                      >
                        {style.is_default ? (
                          <StarFilled style={{ color: '#faad14', fontSize: 18 }} />
                        ) : (
                          <StarOutlined style={{ fontSize: 18 }} />
                        )}
                      </span>
                    </Tooltip>,
                    <Tooltip key="edit" title={style.project_id === null ? '预设风格不可编辑' : '编辑'}>
                      <EditOutlined
                        onClick={() => style.project_id !== null && handleEdit(style)}
                        style={{
                          fontSize: 18,
                          cursor: style.project_id === null ? 'not-allowed' : 'pointer',
                          color: style.project_id === null ? '#ccc' : undefined
                        }}
                      />
                    </Tooltip>,
                    <Popconfirm
                      key="delete"
                      title="确定删除这个风格吗？"
                      description={style.is_default ? '这是默认风格，删除后需要设置新的默认风格' : undefined}
                      onConfirm={() => handleDelete(style.id)}
                      okText="确定"
                      cancelText="取消"
                      disabled={style.project_id === null || styles.length === 1}
                    >
                      <Tooltip title={
                        style.project_id === null
                          ? '预设风格不可删除'
                          : styles.length === 1
                            ? '至少保留一个风格'
                            : '删除'
                      }>
                        <DeleteOutlined
                          style={{
                            fontSize: 18,
                            color: (style.project_id === null || styles.length === 1) ? '#ccc' : undefined,
                            cursor: (style.project_id === null || styles.length === 1) ? 'not-allowed' : 'pointer'
                          }}
                        />
                      </Tooltip>
                    </Popconfirm>,
                  ]}
                >
                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                    <Space style={{ marginBottom: 12 }} wrap>
                      <Text strong style={{ fontSize: 16 }}>{style.name}</Text>
                      <Tag color={getStyleTypeColor(style.style_type)}>
                        {getStyleTypeLabel(style.style_type)}
                      </Tag>
                      {style.is_default && <Tag color="gold">默认</Tag>}
                    </Space>
                    
                    {style.description && (
                      <Paragraph
                        type="secondary"
                        style={{ fontSize: 13, marginBottom: 12 }}
                        ellipsis={{ rows: 2, tooltip: style.description }}
                      >
                        {style.description}
                      </Paragraph>
                    )}
                    
                    <Paragraph
                      type="secondary"
                      style={{
                        fontSize: 12,
                        marginBottom: 0,
                        backgroundColor: '#fafafa',
                        padding: 8,
                        borderRadius: 4,
                        flex: 1,
                        minHeight: 60,
                      }}
                      ellipsis={{ rows: 3, tooltip: style.prompt_content }}
                    >
                      {style.prompt_content}
                    </Paragraph>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </div>

      {/* 创建自定义风格 Modal */}
      <Modal
        title="创建自定义风格"
        open={isCreateModalOpen}
        onCancel={() => {
          setIsCreateModalOpen(false);
          createForm.resetFields();
        }}
        footer={null}
        centered
        width={isMobile ? 'calc(100vw - 32px)' : 600}
        style={isMobile ? { maxWidth: 'calc(100vw - 32px)', margin: '0 16px' } : undefined}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreate}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            label="风格名称"
            name="name"
            rules={[{ required: true, message: '请输入风格名称' }]}
          >
            <Input placeholder="如：武侠风、科幻风" />
          </Form.Item>
          
          <Form.Item label="风格描述" name="description">
            <TextArea rows={2} placeholder="简要描述这个风格的特点..." />
          </Form.Item>
          
          <Form.Item
            label="提示词内容"
            name="prompt_content"
            rules={[{ required: true, message: '请输入提示词内容' }]}
          >
            <TextArea
              rows={6}
              placeholder="输入风格的提示词，用于引导AI生成符合该风格的内容..."
            />
          </Form.Item>
          
          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => {
                setIsCreateModalOpen(false);
                createForm.resetFields();
              }}>
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={loading}>
                创建
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑风格 Modal */}
      <Modal
        title="编辑写作风格"
        open={isEditModalOpen}
        onCancel={() => {
          setIsEditModalOpen(false);
          editForm.resetFields();
          setEditingStyle(null);
        }}
        footer={null}
        centered
        width={isMobile ? 'calc(100vw - 32px)' : 600}
        style={isMobile ? { maxWidth: 'calc(100vw - 32px)', margin: '0 16px' } : undefined}
      >
        <Form form={editForm} layout="vertical" onFinish={handleUpdate} style={{ marginTop: 16 }}>
          <Form.Item
            label="风格名称"
            name="name"
            rules={[{ required: true, message: '请输入风格名称' }]}
          >
            <Input placeholder="输入风格名称" />
          </Form.Item>
          
          <Form.Item label="风格描述" name="description">
            <TextArea rows={2} placeholder="简要描述这个风格的特点..." />
          </Form.Item>
          
          <Form.Item
            label="提示词内容"
            name="prompt_content"
            rules={[{ required: true, message: '请输入提示词内容' }]}
          >
            <TextArea 
              rows={6} 
              placeholder="输入风格的提示词..."
            />
          </Form.Item>
          
          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => {
                setIsEditModalOpen(false);
                editForm.resetFields();
                setEditingStyle(null);
              }}>
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={loading}>
                保存
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}