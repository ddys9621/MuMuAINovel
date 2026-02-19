import { useState, useEffect } from 'react';
import {
  Modal, Form, Input, InputNumber, Select, Button, message,
  Row, Col, Typography, Space
} from 'antd';
import { RocketOutlined } from '@ant-design/icons';
import { wizardStreamApi, projectApi } from '../services/api';
import type { WizardBasicInfo, ApiError } from '../types';
import MCPSelector, { type MCPSelectorValue } from './MCPSelector';
import { GenerationProgress, CompletionResult } from './GenerationProgress';
import { freshTheme } from '../styles/theme';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface ProjectWizardModalProps {
  visible: boolean;
  onClose: () => void;
  onSuccess: (projectId: string) => void;
}

export default function ProjectWizardModal({ visible, onClose, onSuccess }: ProjectWizardModalProps) {
  const [form] = Form.useForm();
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  
  // 状态管理
  const [loading, setLoading] = useState(false);
  const [currentStep, setCurrentStep] = useState<'form' | 'generating' | 'complete'>('form');
  const [projectId, setProjectId] = useState<string>('');
  const [projectTitle, setProjectTitle] = useState<string>('');
  
  // MCP 选择器状态
  const [mcpSettings, setMcpSettings] = useState<MCPSelectorValue>({
    enable: false,
    selected: []
  });
  
  // SSE流式进度状态
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [generationSteps, setGenerationSteps] = useState<{
    worldBuilding: 'pending' | 'processing' | 'completed' | 'error';
    characters: 'pending' | 'processing' | 'completed' | 'error';
    outline: 'pending' | 'processing' | 'completed' | 'error';
  }>({
    worldBuilding: 'pending',
    characters: 'pending',
    outline: 'pending'
  });

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // 重置状态
  const resetState = () => {
    setCurrentStep('form');
    setLoading(false);
    setProjectId('');
    setProjectTitle('');
    setProgress(0);
    setProgressMessage('');
    setGenerationSteps({
      worldBuilding: 'pending',
      characters: 'pending',
      outline: 'pending'
    });
    setMcpSettings({ enable: false, selected: [] });
    form.resetFields();
  };

  // 关闭 Modal
  const handleClose = () => {
    if (currentStep !== 'generating') {
      resetState();
      onClose();
    }
  };

  // 仅创建项目（跳过 AI 生成）
  const handleCreateOnly = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);

      const payload = {
        title: values.title,
        description: values.description,
        theme: values.theme,
        genre: Array.isArray(values.genre) ? values.genre.join('、') : values.genre,
        target_words: values.target_words,
        narrative_perspective: values.narrative_perspective,
      };

      const project = await projectApi.createProject(payload);
      message.success('项目创建成功（未生成世界观/角色/大纲）');
      
      resetState();
      onSuccess(project.id);

    } catch (error) {
      if (error && typeof error === 'object' && 'errorFields' in error) {
        return;
      }
      const apiError = error as ApiError;
      message.error('创建项目失败：' + (apiError.response?.data?.detail || apiError.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  };

  // 自动化生成流程
  const handleAutoGenerate = async (values: WizardBasicInfo) => {
    try {
      setLoading(true);
      setCurrentStep('generating');
      setProjectTitle(values.title);
      setProgress(0);
      setProgressMessage('开始创建项目...');

      // 步骤1: 生成世界观并创建项目
      setGenerationSteps(prev => ({ ...prev, worldBuilding: 'processing' }));
      setProgressMessage('正在生成世界观...');
      
      const worldResult = await wizardStreamApi.generateWorldBuildingStream(
        {
          title: values.title,
          description: values.description,
          theme: values.theme,
          genre: Array.isArray(values.genre) ? values.genre.join('、') : values.genre,
          narrative_perspective: values.narrative_perspective,
          target_words: values.target_words,
          chapter_count: values.chapter_count || 30,
          character_count: values.character_count || 5,
          enable_mcp: mcpSettings.enable && mcpSettings.selected.length > 0,
          selected_plugins: mcpSettings.enable ? mcpSettings.selected : [],
        },
        {
          onProgress: (msg, prog) => {
            setProgress(Math.floor(prog / 3));
            setProgressMessage(msg);
          },
          onResult: (data) => {
            setProjectId(data.project_id);
            setGenerationSteps(prev => ({ ...prev, worldBuilding: 'completed' }));
          },
          onError: (error) => {
            setGenerationSteps(prev => ({ ...prev, worldBuilding: 'error' }));
            throw new Error(error);
          },
          onComplete: () => {
            console.log('世界观生成完成');
          }
        }
      );

      if (!worldResult?.project_id) {
        throw new Error('项目创建失败');
      }

      const createdProjectId = worldResult.project_id;
      setProjectId(createdProjectId);

      // 步骤2: 生成角色
      setGenerationSteps(prev => ({ ...prev, characters: 'processing' }));
      setProgressMessage('正在生成角色...');

      await wizardStreamApi.generateCharactersStream(
        {
          project_id: createdProjectId,
          count: values.character_count || 5,
          world_context: {
            time_period: worldResult.time_period || '',
            location: worldResult.location || '',
            atmosphere: worldResult.atmosphere || '',
            rules: worldResult.rules || '',
          },
          theme: values.theme,
          genre: Array.isArray(values.genre) ? values.genre.join('、') : values.genre,
          enable_mcp: mcpSettings.enable && mcpSettings.selected.length > 0,
          selected_plugins: mcpSettings.enable ? mcpSettings.selected : [],
        },
        {
          onProgress: (msg, prog) => {
            setProgress(33 + Math.floor(prog / 3));
            setProgressMessage(msg);
          },
          onResult: (data) => {
            console.log(`成功生成${data.characters?.length || 0}个角色`);
            setGenerationSteps(prev => ({ ...prev, characters: 'completed' }));
          },
          onError: (error) => {
            setGenerationSteps(prev => ({ ...prev, characters: 'error' }));
            throw new Error(error);
          },
          onComplete: () => {
            console.log('角色生成完成');
          }
        }
      );

      // 步骤3: 生成高层故事大纲
      setGenerationSteps(prev => ({ ...prev, outline: 'processing' }));
      setProgressMessage('正在生成高层故事大纲...');

      await wizardStreamApi.generateCompleteOutlineStream(
        {
          project_id: createdProjectId,
          chapter_count: values.chapter_count || 30,
          narrative_perspective: values.narrative_perspective,
          target_words: values.target_words,
          enable_mcp: mcpSettings.enable && mcpSettings.selected.length > 0,
          selected_plugins: mcpSettings.enable ? mcpSettings.selected : [],
        },
        {
          onProgress: (msg, prog) => {
            setProgress(66 + Math.floor(prog / 3));
            setProgressMessage(msg);
          },
          onResult: () => {
            console.log('大纲生成完成');
            setGenerationSteps(prev => ({ ...prev, outline: 'completed' }));
          },
          onError: (error) => {
            setGenerationSteps(prev => ({ ...prev, outline: 'error' }));
            throw new Error(error);
          },
          onComplete: () => {
            console.log('大纲生成完成');
          }
        }
      );

      // 全部完成
      setProgress(100);
      setProgressMessage('项目创建完成！');
      setCurrentStep('complete');
      message.success('项目创建成功！');

    } catch (error) {
      const apiError = error as ApiError;
      message.error('创建项目失败：' + (apiError.response?.data?.detail || apiError.message || '未知错误'));
      setCurrentStep('form');
      setGenerationSteps({
        worldBuilding: 'pending',
        characters: 'pending',
        outline: 'pending'
      });
    } finally {
      setLoading(false);
    }
  };

  // 渲染表单内容
  const renderFormContent = () => (
    <>
      <Paragraph type="secondary" style={{ marginBottom: 16, fontSize: 13 }}>
        填写基本信息后，选择创建方式：
      </Paragraph>
      <Paragraph type="secondary" style={{ marginBottom: 24, fontSize: 12 }}>
        • <Text strong>AI 自动生成</Text>：自动生成世界观、角色和高层故事大纲<br />
        • <Text strong>仅创建项目</Text>：只创建空项目，后续在项目中手动填写或按需使用 AI
      </Paragraph>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleAutoGenerate}
        initialValues={{
          genre: ['玄幻'],
          chapter_count: 30,
          narrative_perspective: '第三人称',
          character_count: 5,
          target_words: 100000,
        }}
      >
        <Form.Item
          label="书名"
          name="title"
          rules={[{ required: true, message: '请输入书名' }]}
        >
          <Input
            placeholder="输入你的小说标题"
            size="large"
            style={{ borderRadius: freshTheme.radius.md }}
          />
        </Form.Item>

        <Form.Item
          label="小说简介"
          name="description"
          rules={[{ required: true, message: '请输入小说简介' }]}
        >
          <TextArea
            rows={3}
            placeholder="用一段话介绍你的小说..."
            showCount
            maxLength={300}
            style={{ borderRadius: freshTheme.radius.md }}
          />
        </Form.Item>

        <Form.Item
          label="主题"
          name="theme"
          rules={[{ required: true, message: '请输入主题' }]}
        >
          <TextArea
            rows={4}
            placeholder="描述你的小说主题..."
            showCount
            maxLength={500}
            style={{ borderRadius: freshTheme.radius.md }}
          />
        </Form.Item>

        <Form.Item
          label="类型"
          name="genre"
          rules={[{ required: true, message: '请选择小说类型' }]}
        >
          <Select
            mode="tags"
            placeholder="选择或输入类型标签（如：玄幻、都市、修仙）"
            size="large"
            tokenSeparators={[',']}
            maxTagCount={5}
            style={{ borderRadius: freshTheme.radius.md }}
          >
            <Select.Option value="玄幻">玄幻</Select.Option>
            <Select.Option value="都市">都市</Select.Option>
            <Select.Option value="历史">历史</Select.Option>
            <Select.Option value="科幻">科幻</Select.Option>
            <Select.Option value="武侠">武侠</Select.Option>
            <Select.Option value="仙侠">仙侠</Select.Option>
            <Select.Option value="奇幻">奇幻</Select.Option>
            <Select.Option value="悬疑">悬疑</Select.Option>
            <Select.Option value="言情">言情</Select.Option>
            <Select.Option value="修仙">修仙</Select.Option>
          </Select>
        </Form.Item>

        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <Form.Item
              label="叙事视角"
              name="narrative_perspective"
              rules={[{ required: true, message: '请选择叙事视角' }]}
            >
              <Select size="large" placeholder="选择小说的叙事视角">
                <Select.Option value="第一人称">第一人称</Select.Option>
                <Select.Option value="第三人称">第三人称</Select.Option>
                <Select.Option value="全知视角">全知视角</Select.Option>
              </Select>
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item
              label="角色数量"
              name="character_count"
              rules={[{ required: true, message: '请输入角色数量' }]}
            >
              <InputNumber
                min={3}
                max={20}
                style={{ width: '100%' }}
                size="large"
                addonAfter="个"
                placeholder="AI生成的角色数量"
              />
            </Form.Item>
          </Col>
        </Row>

        <Form.Item
          label="目标字数"
          name="target_words"
          rules={[{ required: true, message: '请输入目标字数' }]}
        >
          <InputNumber
            min={10000}
            style={{ width: '100%' }}
            size="large"
            addonAfter="字"
            placeholder="整部小说的目标字数"
          />
        </Form.Item>

        {/* MCP 插件选择器 */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ marginBottom: 8 }}>
            <Text strong>AI 增强插件</Text>
            <Text type="secondary" style={{ marginLeft: 8, fontSize: '12px' }}>
              可选择启用 MCP 插件来增强 AI 生成效果
            </Text>
          </div>
          <MCPSelector
            value={mcpSettings}
            onChange={setMcpSettings}
            size="large"
          />
        </div>

        <Form.Item style={{ marginBottom: 0 }}>
          <Space direction="vertical" style={{ width: '100%' }} size={12}>
            <Button
              type="primary"
              htmlType="submit"
              size="large"
              block
              loading={loading}
              icon={<RocketOutlined />}
              style={{
                background: freshTheme.colors.gradients.sakuraMint,
                border: 'none',
                borderRadius: freshTheme.radius.md,
                height: 44,
                fontWeight: 600,
                color: freshTheme.colors.text.primary,
              }}
            >
              开始创建项目（AI 自动生成）
            </Button>
            <Button
              size="large"
              block
              loading={loading}
              onClick={handleCreateOnly}
              style={{
                borderColor: freshTheme.colors.status.writing,
                color: freshTheme.colors.status.writing,
                borderRadius: freshTheme.radius.md,
                height: 44,
              }}
            >
              仅创建项目（跳过 AI 生成）
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </>
  );

  return (
    <Modal
      title={currentStep === 'form' ? '🚀 创建新项目' : null}
      open={visible}
      onCancel={handleClose}
      footer={null}
      width={isMobile ? '95vw' : 720}
      centered
      closable={currentStep !== 'generating'}
      maskClosable={currentStep !== 'generating'}
      destroyOnClose
      styles={{
        body: {
          maxHeight: isMobile ? '70vh' : '65vh',
          overflowY: 'auto',
          padding: isMobile ? '16px' : '24px',
        }
      }}
    >
      {currentStep === 'form' && renderFormContent()}

      {currentStep === 'generating' && (
        <GenerationProgress
          projectTitle={projectTitle}
          progress={progress}
          progressMessage={progressMessage}
          generationSteps={generationSteps}
          isMobile={isMobile}
        />
      )}

      {currentStep === 'complete' && (
        <CompletionResult
          projectTitle={projectTitle}
          onBackHome={() => {
            resetState();
            onClose();
          }}
          onEnterProject={() => {
            const pid = projectId;
            resetState();
            onSuccess(pid);
          }}
          isMobile={isMobile}
        />
      )}
    </Modal>
  );
}

