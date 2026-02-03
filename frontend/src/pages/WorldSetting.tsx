import { Card, Descriptions, Empty, Typography, Button, Modal, Form, Input, message } from 'antd';
import { GlobalOutlined, EditOutlined } from '@ant-design/icons';
import { useState } from 'react';
import { useStore } from '../store';
import { cardStyles } from '../components/CardStyles';
import { projectApi } from '../services/api';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

export default function WorldSetting() {
  const { currentProject, setCurrentProject } = useStore();
  const [isEditModalVisible, setIsEditModalVisible] = useState(false);
  const [editForm] = Form.useForm();
  const [isSaving, setIsSaving] = useState(false);

  if (!currentProject) return null;

  // 检查是否有世界设定信息
  const hasWorldSetting = currentProject.world_time_period ||
    currentProject.world_location ||
    currentProject.world_atmosphere ||
    currentProject.world_rules;

  if (!hasWorldSetting) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* 固定头部 */}
        <div style={{
          position: 'sticky',
          top: 0,
          zIndex: 10,
          backgroundColor: '#fff',
          padding: '16px 0',
          marginBottom: 16,
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <GlobalOutlined style={{ fontSize: 24, marginRight: 12, color: '#1890ff' }} />
            <h2 style={{ margin: 0 }}>世界设定</h2>
          </div>
          <Button
            type="primary"
            icon={<EditOutlined />}
            onClick={() => {
              editForm.setFieldsValue({
                world_time_period: '',
                world_location: '',
                world_atmosphere: '',
                world_rules: '',
              });
              setIsEditModalVisible(true);
            }}
          >
            添加世界观
          </Button>
        </div>

        {/* 可滚动内容区域 */}
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {/* 基础信息卡片 */}
          <Card
            style={{
              ...cardStyles.base,
              marginBottom: 16
            }}
            title={
              <span style={{ fontSize: 18, fontWeight: 500 }}>
                基础信息
              </span>
            }
          >
            <Descriptions bordered column={1} styles={{ label: { width: 120, fontWeight: 500 } }}>
              <Descriptions.Item label="小说名称">{currentProject.title}</Descriptions.Item>
              {currentProject.description && (
                <Descriptions.Item label="小说简介">{currentProject.description}</Descriptions.Item>
              )}
              <Descriptions.Item label="小说主题">{currentProject.theme || '未设定'}</Descriptions.Item>
              <Descriptions.Item label="小说类型">{currentProject.genre || '未设定'}</Descriptions.Item>
              <Descriptions.Item label="叙事视角">{currentProject.narrative_perspective || '未设定'}</Descriptions.Item>
              <Descriptions.Item label="目标字数">
                {currentProject.target_words ? `${currentProject.target_words.toLocaleString()} 字` : '未设定'}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {/* 世界观空态提示 */}
          <Card
            style={{
              ...cardStyles.base,
              marginBottom: 16
            }}
            title={
              <span style={{ fontSize: 18, fontWeight: 500 }}>
                <GlobalOutlined style={{ marginRight: 8 }} />
                小说世界观
              </span>
            }
          >
            <Empty
              description="暂无世界观信息"
              style={{ padding: '40px 0' }}
            >
              <Paragraph type="secondary" style={{ marginBottom: 16 }}>
                点击右上角「添加世界观」按钮，手动填写时间设定、地点设定、氛围基调和世界规则。
              </Paragraph>
            </Empty>
          </Card>
        </div>

        {/* 编辑世界观模态框 - 复用下方的 Modal */}
        <Modal
          title="添加世界观"
          open={isEditModalVisible}
          centered
          onCancel={() => {
            setIsEditModalVisible(false);
            editForm.resetFields();
          }}
          onOk={async () => {
            try {
              const values = await editForm.validateFields();
              setIsSaving(true);
              const updatedProject = await projectApi.updateProject(currentProject.id, {
                world_time_period: values.world_time_period,
                world_location: values.world_location,
                world_atmosphere: values.world_atmosphere,
                world_rules: values.world_rules,
              });
              setCurrentProject(updatedProject);
              message.success('世界观添加成功');
              setIsEditModalVisible(false);
              editForm.resetFields();
            } catch (error) {
              message.error('保存失败，请重试');
            } finally {
              setIsSaving(false);
            }
          }}
          okText="保存"
          cancelText="取消"
          confirmLoading={isSaving}
          width={700}
        >
          <Form form={editForm} layout="vertical">
            <Form.Item label="时间设定" name="world_time_period">
              <TextArea rows={3} placeholder="描述故事发生的时代背景..." />
            </Form.Item>
            <Form.Item label="地点设定" name="world_location">
              <TextArea rows={3} placeholder="描述故事发生的地理位置..." />
            </Form.Item>
            <Form.Item label="氛围基调" name="world_atmosphere">
              <TextArea rows={3} placeholder="描述整体的氛围和基调..." />
            </Form.Item>
            <Form.Item label="世界规则" name="world_rules">
              <TextArea rows={4} placeholder="描述这个世界的特殊规则..." />
            </Form.Item>
          </Form>
        </Modal>
      </div>
    );
  }

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
          <GlobalOutlined style={{ fontSize: 24, marginRight: 12, color: '#1890ff' }} />
          <h2 style={{ margin: 0 }}>世界设定</h2>
        </div>
        <Button
          type="primary"
          icon={<EditOutlined />}
          onClick={() => {
            editForm.setFieldsValue({
              world_time_period: currentProject.world_time_period || '',
              world_location: currentProject.world_location || '',
              world_atmosphere: currentProject.world_atmosphere || '',
              world_rules: currentProject.world_rules || '',
            });
            setIsEditModalVisible(true);
          }}
        >
          编辑世界观
        </Button>
      </div>

      {/* 可滚动内容区域 */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        <Card
        style={{
          ...cardStyles.base,
          marginBottom: 16
        }}
        title={
          <span style={{ fontSize: 18, fontWeight: 500 }}>
            基础信息
          </span>
        }
      >
        <Descriptions bordered column={1} styles={{ label: { width: 120, fontWeight: 500 } }}>
          <Descriptions.Item label="小说名称">{currentProject.title}</Descriptions.Item>
          {currentProject.description && (
            <Descriptions.Item label="小说简介">{currentProject.description}</Descriptions.Item>
          )}
          <Descriptions.Item label="小说主题">{currentProject.theme || '未设定'}</Descriptions.Item>
          <Descriptions.Item label="小说类型">{currentProject.genre || '未设定'}</Descriptions.Item>
          <Descriptions.Item label="叙事视角">{currentProject.narrative_perspective || '未设定'}</Descriptions.Item>
          <Descriptions.Item label="目标字数">
            {currentProject.target_words ? `${currentProject.target_words.toLocaleString()} 字` : '未设定'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card
        style={{
          ...cardStyles.base,
          marginBottom: 16
        }}
        title={
          <span style={{ fontSize: 18, fontWeight: 500 }}>
            <GlobalOutlined style={{ marginRight: 8 }} />
            小说世界观
          </span>
        }
      >
        <div style={{ padding: '16px 0' }}>
          {currentProject.world_time_period && (
            <div style={{ marginBottom: 24 }}>
              <Title level={5} style={{ color: '#1890ff', marginBottom: 12 }}>
                时间设定
              </Title>
              <Paragraph style={{ 
                fontSize: 15, 
                lineHeight: 1.8,
                padding: 16,
                background: '#f5f5f5',
                borderRadius: 8,
                borderLeft: '4px solid #1890ff'
              }}>
                {currentProject.world_time_period}
              </Paragraph>
            </div>
          )}

          {currentProject.world_location && (
            <div style={{ marginBottom: 24 }}>
              <Title level={5} style={{ color: '#52c41a', marginBottom: 12 }}>
                地点设定
              </Title>
              <Paragraph style={{
                fontSize: 15,
                lineHeight: 1.8,
                padding: 16,
                background: '#f5f5f5',
                borderRadius: 8,
                borderLeft: '4px solid #52c41a'
              }}>
                {currentProject.world_location}
              </Paragraph>
            </div>
          )}

          {currentProject.world_atmosphere && (
            <div style={{ marginBottom: 24 }}>
              <Title level={5} style={{ color: '#faad14', marginBottom: 12 }}>
                氛围设定
              </Title>
              <Paragraph style={{
                fontSize: 15,
                lineHeight: 1.8,
                padding: 16,
                background: '#f5f5f5',
                borderRadius: 8,
                borderLeft: '4px solid #faad14'
              }}>
                {currentProject.world_atmosphere}
              </Paragraph>
            </div>
          )}

          {currentProject.world_rules && (
            <div style={{ marginBottom: 0 }}>
              <Title level={5} style={{ color: '#f5222d', marginBottom: 12 }}>
                规则设定
              </Title>
              <Paragraph style={{
                fontSize: 15,
                lineHeight: 1.8,
                padding: 16,
                background: '#f5f5f5',
                borderRadius: 8,
                borderLeft: '4px solid #f5222d'
              }}>
                {currentProject.world_rules}
              </Paragraph>
            </div>
          )}
        </div>
      </Card>
      </div>

      {/* 编辑世界观模态框 */}
      <Modal
        title="编辑世界观"
        open={isEditModalVisible}
        centered
        onCancel={() => {
          setIsEditModalVisible(false);
          editForm.resetFields();
        }}
        onOk={async () => {
          try {
            const values = await editForm.validateFields();
            setIsSaving(true);

            const updatedProject = await projectApi.updateProject(currentProject.id, {
              world_time_period: values.world_time_period,
              world_location: values.world_location,
              world_atmosphere: values.world_atmosphere,
              world_rules: values.world_rules,
            });

            setCurrentProject(updatedProject);
            message.success('世界观更新成功');
            setIsEditModalVisible(false);
            editForm.resetFields();
          } catch (error) {
            console.error('更新世界观失败:', error);
            message.error('更新失败，请重试');
          } finally {
            setIsSaving(false);
          }
        }}
        confirmLoading={isSaving}
        width={800}
        okText="保存"
        cancelText="取消"
      >
        <Form
          form={editForm}
          layout="vertical"
          style={{ marginTop: 16 }}
        >
          <Form.Item
            label="时间设定"
            name="world_time_period"
            rules={[{ required: true, message: '请输入时间设定' }]}
          >
            <TextArea
              rows={4}
              placeholder="描述故事发生的时代背景..."
              showCount
              maxLength={1000}
            />
          </Form.Item>

          <Form.Item
            label="地点设定"
            name="world_location"
            rules={[{ required: true, message: '请输入地点设定' }]}
          >
            <TextArea
              rows={4}
              placeholder="描述故事发生的地理位置和环境..."
              showCount
              maxLength={1000}
            />
          </Form.Item>

          <Form.Item
            label="氛围设定"
            name="world_atmosphere"
            rules={[{ required: true, message: '请输入氛围设定' }]}
          >
            <TextArea
              rows={4}
              placeholder="描述故事的整体氛围和基调..."
              showCount
              maxLength={1000}
            />
          </Form.Item>

          <Form.Item
            label="规则设定"
            name="world_rules"
            rules={[{ required: true, message: '请输入规则设定' }]}
          >
            <TextArea
              rows={4}
              placeholder="描述这个世界的特殊规则和设定..."
              showCount
              maxLength={1000}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}