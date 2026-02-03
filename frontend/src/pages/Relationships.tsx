import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Table, Tag, Button, Space, message, Modal, Form, Select, Slider, Input, Tabs, AutoComplete } from 'antd';
import { PlusOutlined, TeamOutlined, UserOutlined } from '@ant-design/icons';
import { useStore } from '../store';
import axios from 'axios';

const { TextArea } = Input;

interface Relationship {
  id: string;
  character_from_id: string;
  character_to_id: string;
  relationship_name: string;
  intimacy_level: number;
  status: string;
  description?: string;
  source: string;
}

interface RelationshipType {
  id: number;
  name: string;
  category: string;
  reverse_name?: string;
  icon?: string;
}

interface Character {
  id: string;
  name: string;
  is_organization: boolean;
}

export default function Relationships() {
  const { projectId } = useParams<{ projectId: string }>();
  const { currentProject } = useStore();
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [relationshipTypes, setRelationshipTypes] = useState<RelationshipType[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form] = Form.useForm();
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const [pageSize, setPageSize] = useState(10);
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    if (projectId) {
      loadData();
    }
  }, [projectId]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [relsRes, typesRes, charsRes] = await Promise.all([
        axios.get(`/api/relationships/project/${projectId}`),
        axios.get('/api/relationships/types'),
        axios.get(`/api/characters?project_id=${projectId}`)
      ]);
      
      setRelationships(relsRes.data);
      setRelationshipTypes(typesRes.data);
      setCharacters(charsRes.data.items || []);
    } catch (error) {
      message.error('加载数据失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRelationship = async (values: {
    character_from_id: string;
    character_to_id: string;
    relationship_name: string;
    intimacy_level: number;
    status: string;
    description?: string;
  }) => {
    try {
      await axios.post('/api/relationships/', {
        project_id: projectId,
        ...values
      });
      message.success('关系创建成功');
      setIsModalOpen(false);
      form.resetFields();
      loadData();
    } catch (error) {
      message.error('创建关系失败');
      console.error(error);
    }
  };

  const handleDeleteRelationship = async (id: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这条关系吗？',
      centered: true,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await axios.delete(`/api/relationships/${id}`);
          message.success('关系删除成功');
          loadData();
        } catch (error) {
          message.error('删除失败');
          console.error(error);
        }
      }
    });
  };

  const getCharacterName = (id: string) => {
    const char = characters.find(c => c.id === id);
    return char?.name || '未知';
  };

  const getIntimacyColor = (level: number) => {
    if (level >= 75) return 'green';
    if (level >= 50) return 'blue';
    if (level >= 25) return 'orange';
    if (level >= 0) return 'volcano';
    return 'red';
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      active: 'green',
      broken: 'red',
      past: 'default',
      complicated: 'orange'
    };
    return colors[status] || 'default';
  };

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      family: 'magenta',
      social: 'blue',
      hostile: 'red',
      professional: 'cyan'
    };
    return colors[category] || 'default';
  };

  const columns = [
    {
      title: '角色A',
      dataIndex: 'character_from_id',
      key: 'from',
      render: (id: string) => (
        <Tag icon={<UserOutlined />} color="blue">
          {getCharacterName(id)}
        </Tag>
      ),
      width: 120,
    },
    {
      title: '关系',
      dataIndex: 'relationship_name',
      key: 'relationship',
      render: (name: string) => <strong>{name}</strong>,
      width: 120,
    },
    {
      title: '角色B',
      dataIndex: 'character_to_id',
      key: 'to',
      render: (id: string) => (
        <Tag icon={<UserOutlined />} color="purple">
          {getCharacterName(id)}
        </Tag>
      ),
      width: 120,
    },
    {
      title: '亲密度',
      dataIndex: 'intimacy_level',
      key: 'intimacy',
      render: (level: number) => (
        <Tag color={getIntimacyColor(level)}>{level}</Tag>
      ),
      width: 80,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>{status}</Tag>
      ),
      width: 80,
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      render: (source: string) => (
        <Tag>{source === 'ai' ? 'AI生成' : '手动创建'}</Tag>
      ),
      width: 100,
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Relationship) => (
        <Button
          type="link"
          danger
          size="small"
          onClick={() => handleDeleteRelationship(record.id)}
        >
          删除
        </Button>
      ),
      width: 80,
      fixed: isMobile ? ('right' as const) : undefined,
    },
  ];

  // 按类别分组关系类型
  const groupedTypes = relationshipTypes.reduce((acc, type) => {
    if (!acc[type.category]) {
      acc[type.category] = [];
    }
    acc[type.category].push(type);
    return acc;
  }, {} as Record<string, RelationshipType[]>);

  const categoryLabels: Record<string, string> = {
    family: '家族关系',
    social: '社交关系',
    professional: '职业关系',
    hostile: '敌对关系'
  };

  return (
    <div>
      <Card
        title={
          <Space wrap>
            <TeamOutlined />
            <span style={{ fontSize: isMobile ? 14 : 16 }}>关系管理</span>
            {!isMobile && <Tag color="blue">{currentProject?.title}</Tag>}
          </Space>
        }
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setIsModalOpen(true)}
            size={isMobile ? 'small' : 'middle'}
          >
            {isMobile ? '添加' : '添加关系'}
          </Button>
        }
      >
        <Tabs
          items={[
            {
              key: 'list',
              label: `关系列表 (${relationships.length})`,
              children: (
                <Table
                  columns={columns}
                  dataSource={relationships}
                  rowKey="id"
                  loading={loading}
                  pagination={{
                    current: currentPage,
                    pageSize: isMobile ? 10 : pageSize,
                    pageSizeOptions: ['10', '20', '50', '100'],
                    position: ['bottomCenter'],
                    showSizeChanger: !isMobile,
                    showQuickJumper: !isMobile,
                    showTotal: (total) => `共 ${total} 条`,
                    simple: isMobile,
                    onChange: (page, size) => {
                      setCurrentPage(page);
                      if (size !== pageSize) {
                        setPageSize(size);
                        setCurrentPage(1); // 切换每页条数时重置到第一页
                      }
                    },
                    onShowSizeChange: (_, size) => {
                      setPageSize(size);
                      setCurrentPage(1);
                    }
                  }}
                  scroll={{
                    x: 700,
                    y: isMobile ? 'calc(100vh - 360px)' : 'calc(100vh - 440px)'
                  }}
                  size={isMobile ? 'small' : 'middle'}
                />
              ),
            },
            {
              key: 'types',
              label: `关系类型 (${relationshipTypes.length})`,
              children: (
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fill, minmax(200px, 1fr))',
                  gap: isMobile ? '12px' : '16px',
                  maxHeight: isMobile ? 'calc(100vh - 400px)' : 'calc(100vh - 350px)',
                  overflow: 'auto'
                }}>
                  {Object.entries(groupedTypes).map(([category, types]) => (
                    <Card
                      key={category}
                      size="small"
                      title={categoryLabels[category] || category}
                      headStyle={{ backgroundColor: '#f5f5f5' }}
                    >
                      <Space direction="vertical" style={{ width: '100%' }}>
                        {types.map(type => (
                          <Tag key={type.id} color={getCategoryColor(category)}>
                            {type.icon} {type.name}
                            {type.reverse_name && ` ↔ ${type.reverse_name}`}
                          </Tag>
                        ))}
                      </Space>
                    </Card>
                  ))}
                </div>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title="添加关系"
        open={isModalOpen}
        onCancel={() => {
          setIsModalOpen(false);
          form.resetFields();
        }}
        footer={null}
        centered={!isMobile}
        width={isMobile ? '100%' : 600}
        style={isMobile ? { top: 0, paddingBottom: 0, maxWidth: '100vw' } : undefined}
        styles={isMobile ? { body: { maxHeight: 'calc(100vh - 110px)', overflowY: 'auto' } } : undefined}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreateRelationship}
        >
          <Form.Item
            name="character_from_id"
            label="角色A"
            rules={[{ required: true, message: '请选择角色A' }]}
          >
            <Select
              placeholder="选择角色"
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              options={characters
                .filter(c => !c.is_organization)
                .map(c => ({ label: c.name, value: c.id }))}
            />
          </Form.Item>

          <Form.Item
            name="relationship_name"
            label="关系类型"
            rules={[{ required: true, message: '请选择或输入关系类型' }]}
          >
            <AutoComplete
              placeholder="选择预定义类型或输入自定义关系"
              options={relationshipTypes.map(t => ({
                label: `${t.icon || ''} ${t.name} (${categoryLabels[t.category]})`,
                value: t.name
              }))}
              filterOption={(inputValue, option) =>
                option!.value.toUpperCase().indexOf(inputValue.toUpperCase()) !== -1
              }
            />
          </Form.Item>

          <Form.Item
            name="character_to_id"
            label="角色B"
            rules={[{ required: true, message: '请选择角色B' }]}
          >
            <Select
              placeholder="选择角色"
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              options={characters
                .filter(c => !c.is_organization)
                .map(c => ({ label: c.name, value: c.id }))}
            />
          </Form.Item>

          <Form.Item
            name="intimacy_level"
            label="亲密度"
            initialValue={50}
          >
            <Slider
              min={-100}
              max={100}
              marks={{
                '-100': '-100',
                '-50': '-50',
                0: '0',
                50: '50',
                100: '100'
              }}
            />
          </Form.Item>

          <Form.Item
            name="status"
            label="状态"
            initialValue="active"
          >
            <Select>
              <Select.Option value="active">活跃</Select.Option>
              <Select.Option value="broken">破裂</Select.Option>
              <Select.Option value="past">过去</Select.Option>
              <Select.Option value="complicated">复杂</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item name="description" label="关系描述">
            <TextArea rows={3} placeholder="描述这段关系的细节..." />
          </Form.Item>

          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setIsModalOpen(false)}>取消</Button>
              <Button type="primary" htmlType="submit">
                创建
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}