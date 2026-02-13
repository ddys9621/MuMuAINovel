import React from 'react';
import { Button, Space } from 'antd';
import {
  PlusOutlined,
  BulbOutlined,
  RocketOutlined,
} from '@ant-design/icons';
import { freshTheme } from '../styles/theme';

interface WelcomeHeaderProps {
  username?: string;
  onCreateProject?: () => void;
  onInspirationMode?: () => void;
}

const WelcomeHeader: React.FC<WelcomeHeaderProps> = ({
  username = '创作者',
  onCreateProject,
  onInspirationMode,
}) => {
  // 根据当前时间获取问候语
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 6) return '夜深了';
    if (hour < 12) return '早上好';
    if (hour < 14) return '中午好';
    if (hour < 18) return '下午好';
    return '晚上好';
  };

  const containerStyles: React.CSSProperties = {
    background: freshTheme.colors.gradients.header,
    borderRadius: freshTheme.radius.xl,
    padding: '32px',
    marginBottom: '24px',
    position: 'relative',
    overflow: 'hidden',
  };

  const contentStyles: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '16px',
  };

  const titleStyles: React.CSSProperties = {
    fontSize: '28px',
    fontWeight: 600,
    color: freshTheme.colors.text.primary,
    marginBottom: '8px',
  };

  const subtitleStyles: React.CSSProperties = {
    fontSize: freshTheme.fontSize.md,
    color: freshTheme.colors.text.secondary,
  };

  const buttonStyles: React.CSSProperties = {
    borderRadius: freshTheme.radius.md,
    height: '40px',
    fontWeight: 500,
    border: 'none',
    boxShadow: freshTheme.shadow.soft,
  };

  const primaryButtonStyles: React.CSSProperties = {
    ...buttonStyles,
    background: freshTheme.colors.gradients.sakuraMint,
    color: freshTheme.colors.text.primary,
  };

  const secondaryButtonStyles: React.CSSProperties = {
    ...buttonStyles,
    background: freshTheme.colors.background.card,
    color: freshTheme.colors.text.secondary,
    border: `1px solid ${freshTheme.colors.background.border}`,
  };

  // 装饰性元素
  const decorationStyles: React.CSSProperties = {
    position: 'absolute',
    right: '-50px',
    top: '-50px',
    width: '200px',
    height: '200px',
    borderRadius: '50%',
    background: 'rgba(255, 214, 224, 0.2)',
    pointerEvents: 'none',
  };

  const decoration2Styles: React.CSSProperties = {
    position: 'absolute',
    right: '60px',
    bottom: '-30px',
    width: '120px',
    height: '120px',
    borderRadius: '50%',
    background: 'rgba(184, 230, 212, 0.2)',
    pointerEvents: 'none',
  };

  return (
    <div className="fresh-welcome-header" style={containerStyles}>
      <div style={decorationStyles} />
      <div style={decoration2Styles} />
      
      <div style={contentStyles}>
        <div>
          <h1 style={titleStyles}>
            {getGreeting()}，{username} 👋
          </h1>
          <p style={subtitleStyles}>
            今天想创作一个怎样的故事呢？让灵感自由流动吧~
          </p>
        </div>
        
        <Space size="middle">
          <Button
            type="primary"
            icon={<BulbOutlined />}
            onClick={onInspirationMode}
            style={primaryButtonStyles}
          >
            💡 灵感模式
          </Button>
          <Button
            icon={<PlusOutlined />}
            onClick={onCreateProject}
            style={secondaryButtonStyles}
          >
            创建项目
          </Button>
        </Space>
      </div>
    </div>
  );
};

export default WelcomeHeader;

