import { useState, useEffect } from 'react';
import { Button, Modal, Form, Input, Select, message, Row, Col, Empty, Tabs, Divider, Typography, Space, InputNumber } from 'antd';
import { ThunderboltOutlined, UserOutlined, TeamOutlined, PlusOutlined } from '@ant-design/icons';
import { useStore } from '../store';
import { useCharacterSync } from '../store/hooks';
import { characterGridConfig } from '../components/CardStyles';
import { CharacterCard } from '../components/CharacterCard';
import { SSELoadingOverlay } from '../components/SSELoadingOverlay';
import MCPSelector, { type MCPSelectorValue } from '../components/MCPSelector';
import type { Character, CharacterUpdate } from '../types';
import { characterApi } from '../services/api';
import { SSEPostClient } from '../utils/sseClient';

const { Title } = Typography;

const { TextArea } = Input;

export default function Characters() {
  const { currentProject, characters } = useStore();
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [activeTab, setActiveTab] = useState<'all' | 'character' | 'organization'>('all');
  const [generateForm] = Form.useForm();
  const [generateOrgForm] = Form.useForm();
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createType, setCreateType] = useState<'character' | 'organization'>('character');
  const [editingCharacter, setEditingCharacter] = useState<Character | null>(null);
  const [mcpSettings, setMcpSettings] = useState<MCPSelectorValue>({
    enable: false,
    selected: []
  });
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false);
  const [isGenerateOrgModalOpen, setIsGenerateOrgModalOpen] = useState(false);

  const {
    refreshCharacters,
    deleteCharacter
  } = useCharacterSync();

  useEffect(() => {
    if (currentProject?.id) {
      refreshCharacters();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject?.id]);

  if (!currentProject) return null;

  const handleDeleteCharacter = async (id: string) => {
    try {
      await deleteCharacter(id);
      message.success('删除成功');
    } catch {
      message.error('删除失败');
    }
  };

  const handleGenerate = async (values: { name?: string; role_type: string; background?: string }) => {
    try {
      setIsGenerating(true);
      setProgress(0);
      setProgressMessage('准备生成角色...');

      const client = new SSEPostClient(
        '/api/characters/generate-stream',
        {
          project_id: currentProject.id,
          name: values.name,
          role_type: values.role_type,
          background: values.background,
          enable_mcp: mcpSettings.enable && mcpSettings.selected.length > 0,
          selected_plugins: mcpSettings.enable ? mcpSettings.selected : [],
        },
        {
          onProgress: (msg, prog) => {
            setProgress(prog);
            setProgressMessage(msg);
          },
          onResult: (data) => {
            console.log('角色生成完成:', data);
          },
          onError: (error) => {
            message.error(`生成失败: ${error}`);
          },
          onComplete: () => {
            setProgress(100);
            setProgressMessage('生成完成！');
          }
        }
      );

      await client.connect();
      message.success('AI生成角色成功');
      setIsGenerateModalOpen(false);
      generateForm.resetFields();
      setMcpSettings({ enable: false, selected: [] });
      await refreshCharacters();
    } catch (error: any) {
      message.error(error.message || 'AI生成失败');
    } finally {
      setTimeout(() => {
        setIsGenerating(false);
        setProgress(0);
        setProgressMessage('');
      }, 500);
    }
  };

  const handleGenerateOrganization = async (values: {
    name?: string;
    organization_type?: string;
    background?: string;
    requirements?: string;
  }) => {
    try {
      setIsGenerating(true);
      setProgress(0);
      setProgressMessage('准备生成组织...');

      const client = new SSEPostClient(
        '/api/organizations/generate-stream',
        {
          project_id: currentProject.id,
          name: values.name,
          organization_type: values.organization_type,
          background: values.background,
          requirements: values.requirements,
          enable_mcp: mcpSettings.enable && mcpSettings.selected.length > 0,
          selected_plugins: mcpSettings.enable ? mcpSettings.selected : [],
        },
        {
          onProgress: (msg, prog) => {
            setProgress(prog);
            setProgressMessage(msg);
          },
          onResult: (data) => {
            console.log('组织生成完成:', data);
          },
          onError: (error) => {
            message.error(`生成失败: ${error}`);
          },
          onComplete: () => {
            setProgress(100);
            setProgressMessage('生成完成！');
          }
        }
      );

      await client.connect();
      message.success('AI生成组织成功');
      setIsGenerateOrgModalOpen(false);
      generateOrgForm.resetFields();
      setMcpSettings({ enable: false, selected: [] });
      await refreshCharacters();
    } catch (error: any) {
      message.error(error.message || 'AI生成失败');
    } finally {
      setTimeout(() => {
        setIsGenerating(false);
        setProgress(0);
        setProgressMessage('');
      }, 500);
    }
  };

  const handleCreateCharacter = async (values: any) => {
    try {
      const createData: any = {
        project_id: currentProject.id,
        name: values.name,
        is_organization: createType === 'organization',
      };

      if (createType === 'character') {
        // 角色字段
        createData.age = values.age;
        createData.gender = values.gender;
        createData.role_type = values.role_type || 'supporting';
        createData.personality = values.personality;
        createData.appearance = values.appearance;
        createData.relationships = values.relationships;
        createData.background = values.background;
      } else {
        // 组织字段
        createData.organization_type = values.organization_type;
        createData.organization_purpose = values.organization_purpose;
        createData.organization_members = values.organization_members;
        createData.background = values.background;
        createData.power_level = values.power_level;
        createData.location = values.location;
        createData.motto = values.motto;
        createData.color = values.color;
        createData.role_type = 'supporting'; // 组织默认为配角
      }

      await characterApi.createCharacter(createData);
      message.success(`${createType === 'character' ? '角色' : '组织'}创建成功`);
      setIsCreateModalOpen(false);
      createForm.resetFields();
      await refreshCharacters();
    } catch {
      message.error('创建失败');
    }
  };

  const handleEditCharacter = (character: Character) => {
    setEditingCharacter(character);
    editForm.setFieldsValue(character);
    setIsEditModalOpen(true);
  };

  const handleUpdateCharacter = async (values: CharacterUpdate) => {
    if (!editingCharacter) return;
    
    try {
      await characterApi.updateCharacter(editingCharacter.id, values);
      message.success('更新成功');
      setIsEditModalOpen(false);
      editForm.resetFields();
      setEditingCharacter(null);
      await refreshCharacters();
    } catch {
      message.error('更新失败');
    }
  };

  const handleDeleteCharacterWrapper = (id: string) => {
    handleDeleteCharacter(id);
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

  const showGenerateOrgModal = () => {
    setIsGenerateOrgModalOpen(true);
  };

  const handleGenerateOrgModalOk = async () => {
    try {
      const values = await generateOrgForm.validateFields();
      await handleGenerateOrganization(values);
    } catch (error) {
      // 表单验证失败，不关闭Modal
    }
  };

  const handleGenerateOrgModalCancel = () => {
    setIsGenerateOrgModalOpen(false);
    generateOrgForm.resetFields();
    setMcpSettings({ enable: false, selected: [] });
  };

  const characterList = characters.filter(c => !c.is_organization);
  const organizationList = characters.filter(c => c.is_organization);

  const getDisplayList = () => {
    if (activeTab === 'character') return characterList;
    if (activeTab === 'organization') return organizationList;
    return characters;
  };

  const displayList = getDisplayList();

  const isMobile = window.innerWidth <= 768;

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
        <h2 style={{ margin: 0, fontSize: isMobile ? 18 : 24 }}>角色与组织管理</h2>
        <Space wrap>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setCreateType('character');
              setIsCreateModalOpen(true);
            }}
            size={isMobile ? 'small' : 'middle'}
          >
            创建角色
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setCreateType('organization');
              setIsCreateModalOpen(true);
            }}
            size={isMobile ? 'small' : 'middle'}
          >
            创建组织
          </Button>
          <Button
            type="dashed"
            icon={<ThunderboltOutlined />}
            onClick={showGenerateModal}
            loading={isGenerating}
            size={isMobile ? 'small' : 'middle'}
          >
            AI生成角色
          </Button>
          <Button
            type="dashed"
            icon={<ThunderboltOutlined />}
            onClick={showGenerateOrgModal}
            loading={isGenerating}
            size={isMobile ? 'small' : 'middle'}
          >
            AI生成组织
          </Button>
        </Space>
      </div>

      {characters.length > 0 && (
        <div style={{
          position: 'sticky',
          top: isMobile ? 60 : 72,
          zIndex: 9,
          backgroundColor: '#fff',
          paddingBottom: 8,
          borderBottom: '1px solid #f0f0f0',
        }}>
          <Tabs
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key as 'all' | 'character' | 'organization')}
            items={[
                {
                  key: 'all',
                  label: `全部 (${characters.length})`,
                },
                {
                  key: 'character',
                  label: (
                    <span>
                      <UserOutlined /> 角色 ({characterList.length})
                    </span>
                  ),
                },
                {
                  key: 'organization',
                  label: (
                    <span>
                      <TeamOutlined /> 组织 ({organizationList.length})
                    </span>
                  ),
                },
              ]}
            />
          </div>
        )}
  
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {characters.length === 0 ? (
            <Empty description="还没有角色或组织，开始创建吧！" />
          ) : (
            <>
              <Row gutter={isMobile ? [8, 8] : characterGridConfig.gutter}>
              {activeTab === 'all' && (
                <>
                  {characterList.length > 0 && (
                    <>
                      <Col span={24}>
                        <Divider orientation="left">
                          <Title level={5} style={{ margin: 0 }}>
                            <UserOutlined style={{ marginRight: 8 }} />
                            角色 ({characterList.length})
                          </Title>
                        </Divider>
                      </Col>
                      {characterList.map((character) => (
                        <Col
                          xs={24}
                          sm={characterGridConfig.sm}
                          md={characterGridConfig.md}
                          lg={characterGridConfig.lg}
                          xl={characterGridConfig.xl}
                          key={character.id}
                          style={{ padding: isMobile ? '4px' : '8px' }}
                        >
                          <CharacterCard
                            character={character}
                            onEdit={handleEditCharacter}
                            onDelete={handleDeleteCharacterWrapper}
                          />
                        </Col>
                      ))}
                    </>
                  )}
                  
                  {organizationList.length > 0 && (
                    <>
                      <Col span={24}>
                        <Divider orientation="left">
                          <Title level={5} style={{ margin: 0 }}>
                            <TeamOutlined style={{ marginRight: 8 }} />
                            组织 ({organizationList.length})
                          </Title>
                        </Divider>
                      </Col>
                      {organizationList.map((org) => (
                        <Col
                          xs={24}
                          sm={characterGridConfig.sm}
                          md={characterGridConfig.md}
                          lg={characterGridConfig.lg}
                          xl={characterGridConfig.xl}
                          key={org.id}
                          style={{ padding: isMobile ? '4px' : '8px' }}
                        >
                          <CharacterCard
                            character={org}
                            onEdit={handleEditCharacter}
                            onDelete={handleDeleteCharacterWrapper}
                          />
                        </Col>
                      ))}
                    </>
                  )}
                </>
              )}
              
              {activeTab === 'character' && characterList.map((character) => (
                <Col
                  xs={24}
                  sm={characterGridConfig.sm}
                  md={characterGridConfig.md}
                  lg={characterGridConfig.lg}
                  xl={characterGridConfig.xl}
                  key={character.id}
                  style={{ padding: isMobile ? '4px' : '8px' }}
                >
                  <CharacterCard
                    character={character}
                    onEdit={handleEditCharacter}
                    onDelete={handleDeleteCharacterWrapper}
                  />
                </Col>
              ))}
              
              {activeTab === 'organization' && organizationList.map((org) => (
                <Col
                  xs={24}
                  sm={characterGridConfig.sm}
                  md={characterGridConfig.md}
                  lg={characterGridConfig.lg}
                  xl={characterGridConfig.xl}
                  key={org.id}
                  style={{ padding: isMobile ? '4px' : '8px' }}
                >
                  <CharacterCard
                    character={org}
                    onEdit={handleEditCharacter}
                    onDelete={handleDeleteCharacterWrapper}
                  />
                </Col>
              ))}
            </Row>

            {displayList.length === 0 && (
              <Empty 
                description={
                  activeTab === 'character' 
                    ? '暂无角色' 
                    : activeTab === 'organization' 
                    ? '暂无组织' 
                    : '暂无数据'
                } 
              />
            )}
          </>
        )}
      </div>

      <Modal
        title={editingCharacter?.is_organization ? '编辑组织' : '编辑角色'}
        open={isEditModalOpen}
        onCancel={() => {
          setIsEditModalOpen(false);
          editForm.resetFields();
          setEditingCharacter(null);
        }}
        footer={null}
        centered={!isMobile}
        width={isMobile ? '100%' : 600}
        style={isMobile ? { top: 0, paddingBottom: 0, maxWidth: '100vw' } : undefined}
        styles={isMobile ? { body: { maxHeight: 'calc(100vh - 110px)', overflowY: 'auto' } } : undefined}
      >
        <Form form={editForm} layout="vertical" onFinish={handleUpdateCharacter}>
          <Row gutter={16}>
            <Col span={editingCharacter?.is_organization ? 24 : 12}>
              <Form.Item
                label={editingCharacter?.is_organization ? '组织名称' : '角色名称'}
                name="name"
                rules={[{ required: true, message: `请输入${editingCharacter?.is_organization ? '组织' : '角色'}名称` }]}
              >
                <Input placeholder={`输入${editingCharacter?.is_organization ? '组织' : '角色'}名称`} />
              </Form.Item>
            </Col>
            
            {!editingCharacter?.is_organization && (
              <Col span={12}>
                <Form.Item label="角色定位" name="role_type">
                  <Select>
                    <Select.Option value="protagonist">主角</Select.Option>
                    <Select.Option value="supporting">配角</Select.Option>
                    <Select.Option value="antagonist">反派</Select.Option>
                  </Select>
                </Form.Item>
              </Col>
            )}
          </Row>

          {!editingCharacter?.is_organization && (
            <>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="年龄" name="age">
                    <Input placeholder="如：25、30岁" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="性别" name="gender">
                    <Select placeholder="选择性别">
                      <Select.Option value="男">男</Select.Option>
                      <Select.Option value="女">女</Select.Option>
                      <Select.Option value="其他">其他</Select.Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item label="性格特点" name="personality">
                <TextArea rows={2} placeholder="描述角色的性格特点..." />
              </Form.Item>

              <Form.Item label="外貌描写" name="appearance">
                <TextArea rows={2} placeholder="描述角色的外貌特征..." />
              </Form.Item>

              <Form.Item label="人际关系" name="relationships">
                <TextArea rows={2} placeholder="描述角色与其他角色的关系..." />
              </Form.Item>
            </>
          )}

          {editingCharacter?.is_organization && (
            <>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="组织类型"
                    name="organization_type"
                    rules={[{ required: true, message: '请输入组织类型' }]}
                  >
                    <Input placeholder="如：帮派、公司、门派、学院" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="主要成员" name="organization_members">
                    <Input placeholder="如：张三、李四、王五" />
                  </Form.Item>
                </Col>
              </Row>
              
              <Form.Item
                label="组织目的"
                name="organization_purpose"
                rules={[{ required: true, message: '请输入组织目的' }]}
              >
                <TextArea rows={2} placeholder="描述组织的宗旨和目标..." />
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="所在地" name="location">
                    <Input placeholder="组织的主要活动区域或总部位置" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="代表颜色" name="color">
                    <Input placeholder="如：深红色、金色、黑色等" />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item label="格言/口号" name="motto">
                <Input placeholder="组织的宗旨、格言或口号" />
              </Form.Item>
            </>
          )}

          <Form.Item label={editingCharacter?.is_organization ? '组织背景' : '角色背景'} name="background">
            <TextArea rows={3} placeholder={`描述${editingCharacter?.is_organization ? '组织' : '角色'}的背景故事...`} />
          </Form.Item>

          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => {
                setIsEditModalOpen(false);
                editForm.resetFields();
                setEditingCharacter(null);
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

      {/* 手动创建角色/组织模态框 */}
      <Modal
        title={createType === 'character' ? '创建角色' : '创建组织'}
        open={isCreateModalOpen}
        onCancel={() => {
          setIsCreateModalOpen(false);
          createForm.resetFields();
        }}
        footer={null}
        centered={!isMobile}
        width={isMobile ? '100%' : 600}
        style={isMobile ? { top: 0, paddingBottom: 0, maxWidth: '100vw' } : undefined}
        styles={isMobile ? { body: { maxHeight: 'calc(100vh - 110px)', overflowY: 'auto' } } : undefined}
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreateCharacter}>
          <Row gutter={16}>
            <Col span={createType === 'organization' ? 24 : 12}>
              <Form.Item
                label={createType === 'character' ? '角色名称' : '组织名称'}
                name="name"
                rules={[{ required: true, message: `请输入${createType === 'character' ? '角色' : '组织'}名称` }]}
              >
                <Input placeholder={`输入${createType === 'character' ? '角色' : '组织'}名称`} />
              </Form.Item>
            </Col>
            
            {createType === 'character' && (
              <Col span={12}>
                <Form.Item label="角色定位" name="role_type" initialValue="supporting">
                  <Select>
                    <Select.Option value="protagonist">主角</Select.Option>
                    <Select.Option value="supporting">配角</Select.Option>
                    <Select.Option value="antagonist">反派</Select.Option>
                  </Select>
                </Form.Item>
              </Col>
            )}
          </Row>

          {createType === 'character' ? (
            <>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="年龄" name="age">
                    <Input placeholder="如：25、30岁" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="性别" name="gender">
                    <Select placeholder="选择性别">
                      <Select.Option value="男">男</Select.Option>
                      <Select.Option value="女">女</Select.Option>
                      <Select.Option value="其他">其他</Select.Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item label="性格特点" name="personality">
                <TextArea rows={2} placeholder="描述角色的性格特点..." />
              </Form.Item>

              <Form.Item label="外貌描写" name="appearance">
                <TextArea rows={2} placeholder="描述角色的外貌特征..." />
              </Form.Item>

              <Form.Item label="人际关系" name="relationships">
                <TextArea rows={2} placeholder="描述角色与其他角色的关系..." />
              </Form.Item>

              <Form.Item label="角色背景" name="background">
                <TextArea rows={3} placeholder="描述角色的背景故事..." />
              </Form.Item>
            </>
          ) : (
            <>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="组织类型"
                    name="organization_type"
                    rules={[{ required: true, message: '请输入组织类型' }]}
                  >
                    <Input placeholder="如：帮派、公司、门派、学院" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    label="势力等级"
                    name="power_level"
                    initialValue={50}
                    tooltip="0-100的数值，表示组织的影响力"
                  >
                    <InputNumber min={0} max={100} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              
              <Form.Item
                label="组织目的"
                name="organization_purpose"
                rules={[{ required: true, message: '请输入组织目的' }]}
              >
                <TextArea rows={2} placeholder="描述组织的宗旨和目标..." />
              </Form.Item>

              <Form.Item label="主要成员" name="organization_members">
                <Input placeholder="如：张三、李四、王五" />
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="所在地" name="location">
                    <Input placeholder="组织的主要活动区域或总部位置" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="代表颜色" name="color">
                    <Input placeholder="如：深红色、金色、黑色等" />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item label="格言/口号" name="motto">
                <Input placeholder="组织的宗旨、格言或口号" />
              </Form.Item>

              <Form.Item label="组织背景" name="background">
                <TextArea rows={3} placeholder="描述组织的背景故事..." />
              </Form.Item>
            </>
          )}

          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => {
                setIsCreateModalOpen(false);
                createForm.resetFields();
              }}>
                取消
              </Button>
              <Button type="primary" htmlType="submit">
                创建
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* AI生成角色Modal */}
      <Modal
        title="AI生成角色"
        open={isGenerateModalOpen}
        onOk={handleGenerateModalOk}
        onCancel={handleGenerateModalCancel}
        width={600}
        centered
        okText="生成"
        cancelText="取消"
      >
        <Form form={generateForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="角色名称"
            name="name"
          >
            <Input placeholder="如：张三、李四（可选，AI会自动生成）" />
          </Form.Item>
          <Form.Item
            label="角色定位"
            name="role_type"
            rules={[{ required: true, message: '请选择角色定位' }]}
          >
            <Select placeholder="选择角色定位">
              <Select.Option value="protagonist">主角</Select.Option>
              <Select.Option value="supporting">配角</Select.Option>
              <Select.Option value="antagonist">反派</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item label="背景设定" name="background">
            <TextArea rows={3} placeholder="简要描述角色背景和故事环境..." />
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

      {/* AI生成组织Modal */}
      <Modal
        title="AI生成组织"
        open={isGenerateOrgModalOpen}
        onOk={handleGenerateOrgModalOk}
        onCancel={handleGenerateOrgModalCancel}
        width={600}
        centered
        okText="生成"
        cancelText="取消"
      >
        <Form form={generateOrgForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="组织名称"
            name="name"
          >
            <Input placeholder="如：天剑门、黑龙会（可选，AI会自动生成）" />
          </Form.Item>
          <Form.Item
            label="组织类型"
            name="organization_type"
          >
            <Input placeholder="如：门派、帮派、公司、学院（可选，AI会根据世界观生成）" />
          </Form.Item>
          <Form.Item label="背景设定" name="background">
            <TextArea rows={3} placeholder="简要描述组织的背景和环境..." />
          </Form.Item>
          <Form.Item label="其他要求" name="requirements">
            <TextArea rows={2} placeholder="其他特殊要求..." />
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

      {/* SSE进度显示 */}
      <SSELoadingOverlay
        loading={isGenerating}
        progress={progress}
        message={progressMessage}
      />
    </div>
  );
}