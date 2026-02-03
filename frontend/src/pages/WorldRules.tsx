import { useState, useEffect } from 'react';
import { Card, Tabs, Table, Button, Modal, Form, Input, InputNumber, message, Popconfirm, Space } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, BookOutlined } from '@ant-design/icons';
import { useStore } from '../store';
import { worldRulesApi } from '../services/api';
import type { WorldRule, WorldRuleCreate, WorldRuleUpdate } from '../types';

const { TextArea } = Input;

export default function WorldRules() {
  const { currentProject } = useStore();
  const [activeTab, setActiveTab] = useState<'cultivation_realm' | 'equipment_template' | 'map_location'>('cultivation_realm');
  const [rules, setRules] = useState<WorldRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingRule, setEditingRule] = useState<WorldRule | null>(null);
  const [form] = Form.useForm();

  // 加载规则列表
  const loadRules = async (category: 'cultivation_realm' | 'equipment_template' | 'map_location') => {
    if (!currentProject) return;

    setLoading(true);
    try {
      const response = await worldRulesApi.list(currentProject.id, category);
      setRules(response.items);
    } catch (error) {
      message.error('加载规则失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  // 切换 Tab 时重新加载
  useEffect(() => {
    loadRules(activeTab);
  }, [activeTab, currentProject]);

  // 打开新增/编辑弹窗
  const handleOpenModal = (rule?: WorldRule) => {
    if (rule) {
      setEditingRule(rule);
      form.setFieldsValue({
        key: rule.key,
        name: rule.name,
        order_index: rule.order_index,
        summary: rule.summary,
        details: rule.details,
      });
    } else {
      setEditingRule(null);
      form.resetFields();
      // 设置默认 order_index 为当前列表最大值 + 1
      const maxOrder = rules.length > 0 ? Math.max(...rules.map(r => r.order_index)) : 0;
      form.setFieldsValue({ order_index: maxOrder + 1 });
    }
    setIsModalVisible(true);
  };

  // 保存规则
  const handleSave = async () => {
    if (!currentProject) return;

    try {
      const values = await form.validateFields();
      
      if (editingRule) {
        // 更新
        const updateData: WorldRuleUpdate = {
          key: values.key,
          name: values.name,
          order_index: values.order_index,
          summary: values.summary,
          details: values.details,
        };
        await worldRulesApi.update(editingRule.id, updateData);
        message.success('更新成功');
      } else {
        // 新增
        const createData: WorldRuleCreate = {
          category: activeTab,
          key: values.key,
          name: values.name,
          order_index: values.order_index,
          summary: values.summary,
          details: values.details,
        };
        await worldRulesApi.create(currentProject.id, createData);
        message.success('创建成功');
      }

      setIsModalVisible(false);
      loadRules(activeTab);
    } catch (error: any) {
      if (error.errorFields) {
        // 表单验证错误
        return;
      }
      message.error(error.message || '保存失败');
      console.error(error);
    }
  };

  // 删除规则
  const handleDelete = async (ruleId: string) => {
    try {
      await worldRulesApi.delete(ruleId);
      message.success('删除成功');
      loadRules(activeTab);
    } catch (error) {
      message.error('删除失败');
      console.error(error);
    }
  };

  if (!currentProject) return null;

  // 表格列定义
  const columns = [
    {
      title: '序号',
      dataIndex: 'order_index',
      key: 'order_index',
      width: 80,
      sorter: (a: WorldRule, b: WorldRule) => a.order_index - b.order_index,
    },
    {
      title: '标识',
      dataIndex: 'key',
      key: 'key',
      width: 180,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 150,
    },
    {
      title: '简要描述',
      dataIndex: 'summary',
      key: 'summary',
      ellipsis: true,
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      render: (_: any, record: WorldRule) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleOpenModal(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此规则吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* 固定头部 */}
      <div style={{
        position: 'sticky',
        top: 0,
        zIndex: 10,
        backgroundColor: '#fff',
        padding: '16px 0',
        marginBottom: 24,
        borderBottom: '1px solid #f0f0f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <BookOutlined style={{ fontSize: 24, marginRight: 12, color: '#1890ff' }} />
          <h2 style={{ margin: 0 }}>世界规则系统</h2>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => handleOpenModal()}
        >
          新增规则
        </Button>
      </div>

      {/* 可滚动内容区域 */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        <Card>
          <Tabs
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key as 'cultivation_realm' | 'equipment_template' | 'map_location')}
            items={[
              {
                key: 'cultivation_realm',
                label: '能力/地位体系',
                children: (
                  <Table
                    columns={columns}
                    dataSource={rules}
                    rowKey="id"
                    loading={loading}
                    pagination={{ pageSize: 20 }}
                  />
                ),
              },
              {
                key: 'equipment_template',
                label: '资源/载体系统',
                children: (
                  <Table
                    columns={columns}
                    dataSource={rules}
                    rowKey="id"
                    loading={loading}
                    pagination={{ pageSize: 20 }}
                  />
                ),
              },
              {
                key: 'map_location',
                label: '地图/地点系统',
                children: (
                  <Table
                    columns={columns}
                    dataSource={rules}
                    rowKey="id"
                    loading={loading}
                    pagination={{ pageSize: 20 }}
                  />
                ),
              },
            ]}
          />
        </Card>
      </div>

      {/* 新增/编辑弹窗 */}
      <Modal
        title={editingRule ? '编辑规则' : '新增规则'}
        open={isModalVisible}
        onOk={handleSave}
        onCancel={() => setIsModalVisible(false)}
        width={600}
        okText="保存"
        cancelText="取消"
      >
        <Form
          form={form}
          layout="vertical"
        >
          <Form.Item
            name="key"
            label="规则标识"
            rules={[
              { required: true, message: '请输入规则标识' },
              { pattern: /^[a-z_]+$/, message: '只能使用小写字母和下划线' }
            ]}
            extra="唯一标识，如：foundation_establishment"
          >
            <Input placeholder="foundation_establishment" />
          </Form.Item>

          <Form.Item
            name="name"
            label="规则名称"
            rules={[{ required: true, message: '请输入规则名称' }]}
          >
            <Input placeholder="筑基期" />
          </Form.Item>

          <Form.Item
            name="order_index"
            label="排序序号"
            rules={[{ required: true, message: '请输入排序序号' }]}
            extra="用于境界层级等有顺序的规则"
          >
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="summary"
            label="简要描述"
          >
            <TextArea
              rows={3}
              placeholder="简要描述此规则的核心内容"
            />
          </Form.Item>

          <Form.Item
            name="details"
            label="详细设定"
            extra="可以使用 JSON 格式或长文本，存储突破条件、战力范围、叙事建议等"
          >
            <TextArea
              rows={6}
              placeholder='例如：{"breakthrough": "需要凝聚金丹", "lifespan": "500年", "power": "可御剑飞行"}'
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

