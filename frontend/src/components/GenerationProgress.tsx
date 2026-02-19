import React from 'react';
import { Progress, Typography, Space, Button } from 'antd';
import { CheckCircleOutlined, LoadingOutlined, RocketOutlined } from '@ant-design/icons';
import { freshTheme } from '../styles/theme';

const { Title, Paragraph, Text } = Typography;

interface GenerationStep {
  worldBuilding: 'pending' | 'processing' | 'completed' | 'error';
  characters: 'pending' | 'processing' | 'completed' | 'error';
  outline: 'pending' | 'processing' | 'completed' | 'error';
}

interface GenerationProgressProps {
  projectTitle: string;
  progress: number;
  progressMessage: string;
  generationSteps: GenerationStep;
  isMobile?: boolean;
}

interface CompletionResultProps {
  projectTitle: string;
  onBackHome: () => void;
  onEnterProject: () => void;
  isMobile?: boolean;
}

// 获取步骤状态的图标和颜色
const getStepStatus = (step: 'pending' | 'processing' | 'completed' | 'error') => {
  if (step === 'completed') return { icon: <CheckCircleOutlined />, color: freshTheme.colors.status.completed };
  if (step === 'processing') return { icon: <LoadingOutlined />, color: freshTheme.colors.status.writing };
  if (step === 'error') return { icon: '✗', color: '#ff4d4f' };
  return { icon: '○', color: freshTheme.colors.text.light };
};

// 生成进度组件
export const GenerationProgress: React.FC<GenerationProgressProps> = ({
  projectTitle,
  progress,
  progressMessage,
  generationSteps,
  isMobile = false,
}) => {
  return (
    <div style={{ textAlign: 'center', padding: isMobile ? '24px 16px' : '40px 24px' }}>
      <Title level={isMobile ? 4 : 3} style={{ 
        marginBottom: 24,
        color: freshTheme.colors.text.primary,
      }}>
        正在为《{projectTitle}》生成内容
      </Title>

      <Progress
        percent={progress}
        status={progress === 100 ? 'success' : 'active'}
        strokeColor={{
          '0%': freshTheme.colors.primary.sakura,
          '50%': freshTheme.colors.primary.mint,
          '100%': freshTheme.colors.primary.lavender,
        }}
        style={{ marginBottom: 32 }}
        strokeWidth={12}
      />

      <Paragraph style={{ 
        fontSize: isMobile ? 14 : 16, 
        marginBottom: 40,
        color: freshTheme.colors.text.secondary,
      }}>
        {progressMessage}
      </Paragraph>

      <Space direction="vertical" size={16} style={{ width: '100%', maxWidth: 400, margin: '0 auto' }}>
        {[
          { key: 'worldBuilding', label: '生成世界观', step: generationSteps.worldBuilding },
          { key: 'characters', label: '生成角色', step: generationSteps.characters },
          { key: 'outline', label: '生成大纲', step: generationSteps.outline },
        ].map(({ key, label, step }) => {
          const status = getStepStatus(step);
          return (
            <div
              key={key}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: isMobile ? '10px 16px' : '12px 20px',
                background: step === 'processing' 
                  ? `${freshTheme.colors.primary.mint}20`
                  : freshTheme.colors.background.card,
                borderRadius: freshTheme.radius.md,
                border: `1px solid ${step === 'processing' 
                  ? freshTheme.colors.primary.mint 
                  : freshTheme.colors.background.border}`,
                boxShadow: step === 'processing' ? freshTheme.shadow.soft : 'none',
                transition: freshTheme.transition.normal,
              }}
            >
              <Text style={{ 
                fontSize: isMobile ? 14 : 16, 
                fontWeight: step === 'processing' ? 600 : 400,
                color: freshTheme.colors.text.primary,
              }}>
                {label}
              </Text>
              <span style={{ fontSize: 20, color: status.color }}>
                {status.icon}
              </span>
            </div>
          );
        })}
      </Space>

      <Paragraph type="secondary" style={{ 
        marginTop: 40,
        color: freshTheme.colors.text.secondary,
        fontSize: isMobile ? 12 : 14,
      }}>
        请耐心等待，AI正在为您精心创作...
      </Paragraph>
    </div>
  );
};

// 完成结果组件
export const CompletionResult: React.FC<CompletionResultProps> = ({
  projectTitle,
  onBackHome,
  onEnterProject,
  isMobile = false,
}) => {
  return (
    <div style={{
      textAlign: 'center',
      padding: isMobile ? '32px 16px' : '48px 24px',
    }}>
      <div style={{
        fontSize: isMobile ? 56 : 72,
        color: freshTheme.colors.status.completed,
        marginBottom: isMobile ? 16 : 24,
        fontWeight: 'bold',
      }}>
        ✓
      </div>
      <Title
        level={isMobile ? 3 : 2}
        style={{
          color: freshTheme.colors.status.completed,
          marginBottom: isMobile ? 8 : 16,
          fontWeight: 700,
        }}
      >
        项目创建完成！
      </Title>
      <Paragraph style={{
        fontSize: isMobile ? 14 : 16,
        marginTop: isMobile ? 16 : 24,
        marginBottom: isMobile ? 32 : 48,
        color: freshTheme.colors.text.secondary,
      }}>
        《{projectTitle}》已成功创建，包含完整的世界观、角色和高层故事大纲
      </Paragraph>

      <Space
        size={isMobile ? 12 : 16}
        direction={isMobile ? 'vertical' : 'horizontal'}
        style={{ width: isMobile ? '100%' : 'auto' }}
      >
        <Button
          size="large"
          onClick={onBackHome}
          block={isMobile}
          style={{
            minWidth: 120,
            height: isMobile ? 44 : 40,
            borderRadius: freshTheme.radius.md,
          }}
        >
          返回首页
        </Button>
        <Button
          type="primary"
          size="large"
          icon={<RocketOutlined />}
          onClick={onEnterProject}
          block={isMobile}
          style={{
            minWidth: 120,
            height: isMobile ? 44 : 40,
            background: freshTheme.colors.gradients.sakuraMint,
            border: 'none',
            borderRadius: freshTheme.radius.md,
            color: freshTheme.colors.text.primary,
            fontWeight: 600,
          }}
        >
          进入项目
        </Button>
      </Space>
    </div>
  );
};

