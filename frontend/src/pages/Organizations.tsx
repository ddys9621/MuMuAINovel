import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Table, Tag, Button, Space, message, Modal, Form, Select, InputNumber, Input, Descriptions } from 'antd';
import { PlusOutlined, TeamOutlined, UserOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { useStore } from '../store';
import axios from 'axios';

interface Organization {
  id: string;
  character_id: string;
  name: string;
  type: string;
  purpose: string;
  member_count: number;
  power_level: number;
  location?: string;
  motto?: string;
  color?: string;
}

interface OrganizationMember {
  id: string;
  character_id: string;
  character_name: string;
  position: string;
  rank: number;
  loyalty: number;
  contribution: number;
  status: string;
  joined_at?: string;
  left_at?: string;
  notes?: string;
}

interface Character {
  id: string;
  name: string;
  is_organization: boolean;
}

export default function Organizations() {
  const { projectId } = useParams<{ projectId: string }>();
  const { currentProject } = useStore();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<OrganizationMember[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [loading, setLoading] = useState(false);
  const [isAddMemberModalOpen, setIsAddMemberModalOpen] = useState(false);
  const [isEditMemberModalOpen, setIsEditMemberModalOpen] = useState(false);
  const [isEditOrgModalOpen, setIsEditOrgModalOpen] = useState(false);
  const [editingMember, setEditingMember] = useState<OrganizationMember | null>(null);
  const [form] = Form.useForm();
  const [editMemberForm] = Form.useForm();
  const [editOrgForm] = Form.useForm();
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const loadOrganizations = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`/api/organizations/project/${projectId}`);
      setOrganizations(res.data);
      if (res.data.length > 0 && !selectedOrg) {
        setSelectedOrg(res.data[0]);
        loadMembers(res.data[0].id);
      }
    } catch (error) {
      message.error('加载组织列表失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [projectId, selectedOrg]);

  const loadCharacters = useCallback(async () => {
    try {
      const res = await axios.get(`/api/characters?project_id=${projectId}`);
      setCharacters(res.data.items || []);
    } catch (error) {
      console.error('加载角色列表失败', error);
    }
  }, [projectId]);

  useEffect(() => {
    if (projectId) {
      loadOrganizations();
      loadCharacters();
    }
  }, [projectId, loadOrganizations, loadCharacters]);

  const loadMembers = async (orgId: string) => {
    try {
      const res = await axios.get(`/api/organizations/${orgId}/members`);
      setMembers(res.data);
    } catch (error) {
      message.error('加载成员列表失败');
      console.error(error);
    }
  };

  const handleSelectOrganization = (org: Organization) => {
    setSelectedOrg(org);
    loadMembers(org.id);
  };

  const handleAddMember = async (values: Record<string, unknown>) => {
    if (!selectedOrg) return;

    try {
      await axios.post(`/api/organizations/${selectedOrg.id}/members`, values);
      message.success('成员添加成功');
      setIsAddMemberModalOpen(false);
      form.resetFields();
      loadMembers(selectedOrg.id);
      loadOrganizations(); // 刷新成员计数
    } catch (error) {
      message.error('添加成员失败');
      console.error(error);
    }
  };

  const handleRemoveMember = async (memberId: string) => {
    Modal.confirm({
      title: '确认移除',
      content: '确定要移除该成员吗？',
      centered: true,
      okText: '移除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await axios.delete(`/api/organizations/members/${memberId}`);
          message.success('成员移除成功');
          if (selectedOrg) {
            loadMembers(selectedOrg.id);
            loadOrganizations(); // 刷新成员计数
          }
        } catch (error) {
          message.error('移除失败');
          console.error(error);
        }
      }
    });
  };

  const handleEditMember = (member: OrganizationMember) => {
    setEditingMember(member);
    editMemberForm.setFieldsValue({
      position: member.position,
      rank: member.rank,
      loyalty: member.loyalty,
      contribution: member.contribution,
      status: member.status,
      notes: member.notes,
      joined_at: member.joined_at
    });
    setIsEditMemberModalOpen(true);
  };

  const handleUpdateMember = async (values: Record<string, unknown>) => {
    if (!editingMember) return;

    try {
      await axios.put(`/api/organizations/members/${editingMember.id}`, values);
      message.success('成员信息更新成功');
      setIsEditMemberModalOpen(false);
      editMemberForm.resetFields();
      setEditingMember(null);
      if (selectedOrg) {
        loadMembers(selectedOrg.id);
      }
    } catch (error) {
      message.error('更新失败');
      console.error(error);
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      active: 'green',
      retired: 'default',
      expelled: 'red',
      deceased: 'black'
    };
    return colors[status] || 'default';
  };

  const getStatusText = (status: string) => {
    const texts: Record<string, string> = {
      active: '在职',
      retired: '退休',
      expelled: '除名',
      deceased: '已故'
    };
    return texts[status] || status;
  };

  const memberColumns = [
    {
      title: '姓名',
      dataIndex: 'character_name',
      key: 'name',
      render: (name: string) => (
        <Space>
          <UserOutlined />
          <span>{name}</span>
        </Space>
      ),
      width: isMobile ? 80 : undefined,
    },
    {
      title: '职位',
      dataIndex: 'position',
      key: 'position',
      render: (position: string, record: OrganizationMember) => (
        <Tag color="blue">{position} {!isMobile && `(级别 ${record.rank})`}</Tag>
      ),
      width: isMobile ? 80 : undefined,
    },
    ...(!isMobile ? [
      {
        title: '忠诚度',
        dataIndex: 'loyalty',
        key: 'loyalty',
        render: (loyalty: number) => (
          <span style={{ color: loyalty >= 70 ? 'green' : loyalty >= 40 ? 'orange' : 'red' }}>
            {loyalty}%
          </span>
        ),
      },
      {
        title: '贡献度',
        dataIndex: 'contribution',
        key: 'contribution',
        render: (contribution: number) => `${contribution}%`,
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        render: (status: string) => (
          <Tag color={getStatusColor(status)}>{getStatusText(status)}</Tag>
        ),
      },
      {
        title: '加入时间',
        dataIndex: 'joined_at',
        key: 'joined_at',
        render: (time: string) => time || '-',
      }
    ] : []),
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: OrganizationMember) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEditMember(record)}
          >
            {isMobile ? '' : '编辑'}
          </Button>
          <Button
            type="link"
            danger
            size="small"
            icon={<DeleteOutlined />}
            onClick={() => handleRemoveMember(record.id)}
          >
            {isMobile ? '删除' : '移除'}
          </Button>
        </Space>
      ),
      width: isMobile ? 60 : undefined,
      fixed: isMobile ? 'right' as const : undefined,
    },
  ];

  // 过滤掉已是成员的角色
  const availableCharacters = characters.filter(
    c => !c.is_organization && !members.some(m => m.character_id === c.id)
  );

  return (
    <div>
      <Card
        title={
          <Space wrap>
            <TeamOutlined />
            <span style={{ fontSize: isMobile ? 14 : 16 }}>组织管理</span>
            {!isMobile && <Tag color="blue">{currentProject?.title}</Tag>}
          </Space>
        }
      >
        <div style={{
          display: isMobile ? 'flex' : 'grid',
          flexDirection: isMobile ? 'column' : undefined,
          gridTemplateColumns: isMobile ? undefined : '300px 1fr',
          gap: isMobile ? '16px' : '24px',
          maxHeight: isMobile ? 'calc(100vh - 200px)' : undefined,
          overflowY: isMobile ? 'auto' : undefined
        }}>
          {/* 左侧：组织列表 */}
          <div>
            <Card
              size="small"
              title={`组织列表 (${organizations.length})`}
              loading={loading}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                {organizations.map(org => (
                  <Card
                    key={org.id}
                    size="small"
                    hoverable
                    style={{
                      cursor: 'pointer',
                      border: selectedOrg?.id === org.id ? '2px solid #1890ff' : '1px solid #d9d9d9'
                    }}
                    onClick={() => handleSelectOrganization(org)}
                  >
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <strong>{org.name}</strong>
                      <Tag>{org.type}</Tag>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        成员: {org.member_count} | 势力: {org.power_level}
                      </div>
                    </Space>
                  </Card>
                ))}
              </Space>
            </Card>
          </div>

          {/* 右侧：组织详情和成员 */}
          <div style={{ minHeight: isMobile ? 'auto' : undefined }}>
            {selectedOrg ? (
              <Space direction="vertical" style={{ width: '100%' }} size="large">
                <Card
                  title="组织详情"
                  size="small"
                  extra={
                    <Button
                      type="link"
                      size="small"
                      icon={<EditOutlined />}
                      onClick={() => {
                        editOrgForm.setFieldsValue({
                          power_level: selectedOrg.power_level,
                          location: selectedOrg.location,
                          motto: selectedOrg.motto,
                          color: selectedOrg.color
                        });
                        setIsEditOrgModalOpen(true);
                      }}
                    >
                      编辑
                    </Button>
                  }
                >
                  <Descriptions column={isMobile ? 1 : 2} size="small">
                    <Descriptions.Item label="组织名称">{selectedOrg.name}</Descriptions.Item>
                    <Descriptions.Item label="类型">{selectedOrg.type}</Descriptions.Item>
                    <Descriptions.Item label="成员数量">{selectedOrg.member_count}</Descriptions.Item>
                    <Descriptions.Item label="势力等级">
                      <Tag color={selectedOrg.power_level >= 70 ? 'red' : selectedOrg.power_level >= 50 ? 'orange' : 'default'}>
                        {selectedOrg.power_level}
                      </Tag>
                    </Descriptions.Item>
                    {selectedOrg.location && (
                      <Descriptions.Item label="所在地" span={isMobile ? 1 : 2}>
                        {selectedOrg.location}
                      </Descriptions.Item>
                    )}
                    {selectedOrg.color && (
                      <Descriptions.Item label="代表颜色">
                        {selectedOrg.color}
                      </Descriptions.Item>
                    )}
                    {selectedOrg.motto && (
                      <Descriptions.Item label="格言/口号" span={2}>
                        {selectedOrg.motto}
                      </Descriptions.Item>
                    )}
                    <Descriptions.Item label="组织目的" span={2}>
                      {selectedOrg.purpose}
                    </Descriptions.Item>
                  </Descriptions>
                </Card>

                <Card
                  title={`组织成员 (${members.length})`}
                  extra={
                    <Button
                      type="primary"
                      size="small"
                      icon={<PlusOutlined />}
                      onClick={() => setIsAddMemberModalOpen(true)}
                      disabled={availableCharacters.length === 0}
                    >
                      添加成员
                    </Button>
                  }
                >
                  <Table
                    columns={memberColumns}
                    dataSource={members}
                    rowKey="id"
                    pagination={isMobile ? { simple: true, pageSize: 10 } : false}
                    size="small"
                    scroll={isMobile ? { x: 'max-content', y: 400 } : undefined}
                  />
                </Card>
              </Space>
            ) : (
              <Card>
                <div style={{ textAlign: 'center', padding: '40px', color: '#999' }}>
                  请从左侧选择一个组织查看详情
                </div>
              </Card>
            )}
          </div>
        </div>
      </Card>

      {/* 添加成员模态框 */}
      <Modal
        title="添加组织成员"
        open={isAddMemberModalOpen}
        onCancel={() => {
          setIsAddMemberModalOpen(false);
          form.resetFields();
        }}
        footer={null}
        centered={!isMobile}
        width={isMobile ? '100%' : 500}
        style={isMobile ? { top: 0, paddingBottom: 0, maxWidth: '100vw' } : undefined}
        styles={isMobile ? { body: { maxHeight: 'calc(100vh - 110px)', overflowY: 'auto' } } : undefined}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleAddMember}
        >
          <Form.Item
            name="character_id"
            label="选择角色"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select
              placeholder="选择要加入的角色"
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              options={availableCharacters.map(c => ({
                label: c.name,
                value: c.id
              }))}
            />
          </Form.Item>

          <Form.Item
            name="position"
            label="职位"
            rules={[{ required: true, message: '请输入职位' }]}
          >
            <Input placeholder="如：掌门、长老、弟子" />
          </Form.Item>

          <Form.Item
            name="rank"
            label="职位等级"
            initialValue={5}
            tooltip="数字越大等级越高"
          >
            <InputNumber min={0} max={10} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="loyalty"
            label="初始忠诚度"
            initialValue={50}
          >
            <InputNumber min={0} max={100} style={{ width: '100%' }} addonAfter="%" />
          </Form.Item>

          <Form.Item
            name="status"
            label="状态"
            initialValue="active"
          >
            <Select>
              <Select.Option value="active">在职</Select.Option>
              <Select.Option value="retired">退休</Select.Option>
              <Select.Option value="expelled">除名</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="joined_at"
            label="加入时间"
          >
            <Input placeholder="如：开山大典时、三年前、建立之初等" />
          </Form.Item>

          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setIsAddMemberModalOpen(false)}>取消</Button>
              <Button type="primary" htmlType="submit">
                添加
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑成员模态框 */}
      <Modal
        title="编辑成员信息"
        open={isEditMemberModalOpen}
        onCancel={() => {
          setIsEditMemberModalOpen(false);
          editMemberForm.resetFields();
          setEditingMember(null);
        }}
        footer={null}
        centered={true}
        width={isMobile ? '90%' : 500}
        style={isMobile ? {
          maxWidth: '90vw',
          margin: '0 auto'
        } : undefined}
        styles={isMobile ? {
          body: {
            maxHeight: 'calc(80vh - 110px)',
            overflowY: 'auto',
            padding: '20px 16px'
          }
        } : undefined}
      >
        <Form
          form={editMemberForm}
          layout="vertical"
          onFinish={handleUpdateMember}
        >
          <Form.Item
            name="position"
            label="职位"
            rules={[{ required: true, message: '请输入职位' }]}
          >
            <Input placeholder="如：掌门、长老、弟子" />
          </Form.Item>

          <Form.Item
            name="rank"
            label="职位等级"
            tooltip="数字越大等级越高"
          >
            <InputNumber min={0} max={10} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="loyalty"
            label="忠诚度"
          >
            <InputNumber min={0} max={100} style={{ width: '100%' }} addonAfter="%" />
          </Form.Item>

          <Form.Item
            name="contribution"
            label="贡献度"
          >
            <InputNumber min={0} max={100} style={{ width: '100%' }} addonAfter="%" />
          </Form.Item>

          <Form.Item
            name="status"
            label="状态"
          >
            <Select>
              <Select.Option value="active">在职</Select.Option>
              <Select.Option value="retired">退休</Select.Option>
              <Select.Option value="expelled">除名</Select.Option>
              <Select.Option value="deceased">已故</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="joined_at"
            label="加入时间"
          >
            <Input placeholder="如：开山大典时、三年前、建立之初等" />
          </Form.Item>

          <Form.Item
            name="notes"
            label="备注"
          >
            <Input.TextArea rows={3} placeholder="成员相关的备注信息" />
          </Form.Item>

          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => {
                setIsEditMemberModalOpen(false);
                editMemberForm.resetFields();
                setEditingMember(null);
              }}>
                取消
              </Button>
              <Button type="primary" htmlType="submit">
                保存
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑组织模态框 */}
      <Modal
        title="编辑组织信息"
        open={isEditOrgModalOpen}
        onCancel={() => {
          setIsEditOrgModalOpen(false);
          editOrgForm.resetFields();
        }}
        footer={null}
        centered={!isMobile}
        width={isMobile ? '100%' : 500}
        style={isMobile ? { top: 0, paddingBottom: 0, maxWidth: '100vw' } : undefined}
        styles={isMobile ? { body: { maxHeight: 'calc(100vh - 110px)', overflowY: 'auto' } } : undefined}
      >
        <Form
          form={editOrgForm}
          layout="vertical"
          onFinish={async (values) => {
            if (!selectedOrg) return;
            try {
              await axios.put(`/api/organizations/${selectedOrg.id}`, values);
              message.success('组织信息更新成功');
              setIsEditOrgModalOpen(false);
              loadOrganizations();
            } catch (error) {
              message.error('更新失败');
              console.error(error);
            }
          }}
        >
          <Form.Item
            name="power_level"
            label="势力等级"
            rules={[{ required: true, message: '请输入势力等级' }]}
            tooltip="0-100的数值，表示组织的影响力"
          >
            <InputNumber min={0} max={100} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="location"
            label="所在地"
          >
            <Input placeholder="组织的主要活动区域或总部位置" />
          </Form.Item>

          <Form.Item
            name="motto"
            label="格言/口号"
          >
            <Input placeholder="组织的宗旨、格言或口号" />
          </Form.Item>

          <Form.Item
            name="color"
            label="代表颜色"
          >
            <Input placeholder="如：深红色、金色、黑色等" />
          </Form.Item>

          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setIsEditOrgModalOpen(false)}>取消</Button>
              <Button type="primary" htmlType="submit">
                保存
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}