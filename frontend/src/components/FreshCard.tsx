import React from 'react';
import { Dropdown, Menu, Progress } from 'antd';
import type { MenuProps } from 'antd';
import {
  EditOutlined,
  DeleteOutlined,
  ExportOutlined,
  MoreOutlined,
  BookOutlined,
  UserOutlined,
  EnvironmentOutlined,
} from '@ant-design/icons';
import { freshTheme, getStatusColor } from '../styles/theme';

interface FreshCardProps {
  id: string;
  title: string;
  description?: string;
  genre?: string;
  status?: string;
  wordCount?: number;
  targetWordCount?: number;
  chapters?: number;
  characters?: number;
  updatedAt?: string;
  coverColor?: string;
  onClick?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  onExport?: () => void;
}

const FreshCard: React.FC<FreshCardProps> = ({
  id,
  title,
  description = '暂无简介',
  genre = '未分类',
  status = 'planning',
  wordCount = 0,
  targetWordCount = 50000,
  chapters = 0,
  characters = 0,
  updatedAt = '刚刚',
  coverColor,
  onClick,
  onEdit,
  onDelete,
  onExport,
}) => {
  const progress = Math.min(100, Math.round((wordCount / targetWordCount) * 100));
  const statusColor = getStatusColor(status);
  const stripeColor = coverColor || statusColor;

  const cardStyles: React.CSSProperties = {
    background: freshTheme.colors.background.card,
    borderRadius: freshTheme.radius.lg,
    boxShadow: freshTheme.shadow.medium,
    border: `1px solid ${freshTheme.colors.background.border}`,
    overflow: 'hidden',
    cursor: 'pointer',
    transition: 'all 0.3s ease',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
  };

  const stripeStyles: React.CSSProperties = {
    height: '6px',
    background: `linear-gradient(90deg, ${stripeColor}, ${adjustColorBrightness(stripeColor, 15)})`,
  };

  const contentStyles: React.CSSProperties = {
    padding: '20px',
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  };

  const headerStyles: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: '12px',
  };

  const titleStyles: React.CSSProperties = {
    fontSize: '18px',
    fontWeight: 600,
    color: freshTheme.colors.text.primary,
    margin: 0,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    flex: 1,
  };

  const genreStyles: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    padding: '4px 10px',
    borderRadius: '12px',
    background: `${stripeColor}20`,
    color: adjustColorBrightness(stripeColor, -30),
    fontSize: '12px',
    fontWeight: 500,
  };

  const descriptionStyles: React.CSSProperties = {
    fontSize: '14px',
    color: freshTheme.colors.text.secondary,
    lineHeight: 1.6,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    display: '-webkit-box',
    WebkitLineClamp: 2,
    WebkitBoxOrient: 'vertical' as const,
    flex: 1,
  };

  const progressContainerStyles: React.CSSProperties = {
    marginTop: 'auto',
  };

  const metaStyles: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: '12px',
    color: freshTheme.colors.text.light,
    marginTop: '8px',
  };

  const statusTagStyles: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '4px',
    padding: '2px 8px',
    borderRadius: '10px',
    background: `${statusColor}30`,
    color: adjustColorBrightness(statusColor, -20),
    fontSize: '11px',
    fontWeight: 500,
  };

  const menuItems: MenuProps['items'] = [
    {
      key: 'edit',
      icon: <EditOutlined />,
      label: '编辑',
      onClick: (e) => {
        e?.domEvent?.stopPropagation();
        onEdit?.();
      },
    },
    {
      key: 'export',
      icon: <ExportOutlined />,
      label: '导出',
      onClick: (e) => {
        e?.domEvent?.stopPropagation();
        onExport?.();
      },
    },
    { type: 'divider' },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      label: '删除',
      danger: true,
      onClick: (e) => {
        e?.domEvent?.stopPropagation();
        onDelete?.();
      },
    },
  ];

  return (
    <div
      className="fresh-card"
      style={cardStyles}
      onClick={onClick}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-4px)';
        e.currentTarget.style.boxShadow = freshTheme.shadow.hover;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = freshTheme.shadow.medium;
      }}
    >
      <div style={stripeStyles} />
      
      <div style={contentStyles}>
        <div style={headerStyles}>
          <h3 style={titleStyles}>{title}</h3>
          <Dropdown
            menu={{ items: menuItems }}
            trigger={['click']}
            placement="bottomRight"
          >
            <MoreOutlined
              style={{ color: freshTheme.colors.text.light, cursor: 'pointer' }}
              onClick={(e) => e.stopPropagation()}
            />
          </Dropdown>
        </div>
        
        <span style={genreStyles}>
          <BookOutlined style={{ fontSize: '12px' }} />
          {genre}
        </span>
        
        <p style={descriptionStyles}>{description}</p>
        
        <div style={progressContainerStyles}>
          <Progress
            percent={progress}
            showInfo={false}
            strokeColor={
              {
                '0%': freshTheme.colors.primary.mint,
                '100%': freshTheme.colors.primary.sky,
              }
            }
            trailColor={freshTheme.colors.background.border}
            size="small"
          />
        </div>
        
        <div style={metaStyles}>
          <div style={{ display: 'flex', gap: '12px' }}>
            <span style={statusTagStyles}>
              {status === 'planning' && '📋 规划中'}
              {status === 'writing' && '✍️ 创作中'}
              {status === 'revising' && '📝 修改中'}
              {status === 'completed' && '✅ 已完成'}
            </span>
            <span>
              {(wordCount / 1000).toFixed(1)}K / {(targetWordCount / 1000).toFixed(0)}K 字
            </span>
          </div>
          <span>{updatedAt}</span>
        </div>
      </div>
    </div>
  );
};

// 调整颜色亮度
const adjustColorBrightness = (hex: string, percent: number): string => {
  const num = parseInt(hex.replace('#', ''), 16);
  const amt = Math.round(2.55 * percent);
  const R = Math.min(255, Math.max(0, (num >> 16) + amt));
  const G = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) + amt));
  const B = Math.min(255, Math.max(0, (num & 0x0000FF) + amt));
  return `#${(0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1)}`;
};

export default FreshCard;

