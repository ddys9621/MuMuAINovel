/**
 * 文艺清新风格设计令牌
 * Fresh & Artsy Design Tokens
 */

export const freshTheme = {
  // 色彩系统
  colors: {
    // 主色调 - 柔和色系
    primary: {
      sakura: '#FFD6E0',      // 樱花粉 - 温暖、浪漫
      mint: '#B8E6D4',        // 薄荷绿 - 清新、舒适
      sky: '#A8D8EA',         // 天空蓝 - 纯净、开阔
      lavender: '#D4B8E6',    // 薰衣草紫 - 优雅、文艺
      cream: '#FFF8F0',       // 奶油白 - 温暖、柔和
    },
    
    // 文字颜色
    text: {
      primary: '#5D5A6D',     // 深灰紫 - 主文字
      secondary: '#8A8699',   // 浅灰紫 - 辅助文字
      light: '#B8B4C4',       // 更浅灰紫 - 提示文字
      white: '#FFFFFF',
    },
    
    // 背景颜色
    background: {
      card: '#FEFEFE',        // 卡片背景
      border: '#E8E4ED',      // 边框色
      hover: '#F8F6FA',       // 悬停背景
      disabled: '#F0EEF2',    // 禁用背景
    },
    
    // 状态颜色 - 对应项目状态
    status: {
      planning: '#A8D8EA',    // 规划中 - 天空蓝
      writing: '#B8E6D4',     // 创作中 - 薄荷绿
      revising: '#FFD6E0',    // 修改中 - 樱花粉
      completed: '#D4B8E6',   // 已完成 - 薰衣草紫
    },
    
    // 渐变色
    gradients: {
      sakuraMint: 'linear-gradient(135deg, #FFD6E0 0%, #B8E6D4 100%)',
      skyLavender: 'linear-gradient(135deg, #A8D8EA 0%, #D4B8E6 100%)',
      creamToWhite: 'linear-gradient(135deg, #FFF8F0 0%, #FFFFFF 100%)',
      page: 'linear-gradient(135deg, #FFF8F0 0%, #F8F6FA 50%, #E8F4F0 100%)',
      header: 'linear-gradient(135deg, rgba(255, 214, 224, 0.3) 0%, rgba(184, 230, 212, 0.3) 100%)',
    },
  },
  
  // 间距系统
  spacing: {
    xs: '4px',
    sm: '8px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    xxl: '48px',
  },
  
  // 圆角系统
  radius: {
    sm: '8px',
    md: '12px',
    lg: '16px',
    xl: '20px',
    xxl: '24px',
  },
  
  // 阴影系统
  shadow: {
    soft: '0 2px 12px rgba(93, 90, 109, 0.08)',
    medium: '0 4px 20px rgba(93, 90, 109, 0.1)',
    hover: '0 8px 32px rgba(93, 90, 109, 0.15)',
    card: '0 4px 16px rgba(93, 90, 109, 0.08)',
  },
  
  // 字体系统
  fontSize: {
    xs: '12px',
    sm: '14px',
    md: '16px',
    lg: '18px',
    xl: '20px',
    xxl: '24px',
    xxxl: '32px',
  },
  
  // 动画时长
  transition: {
    fast: '0.15s ease',
    normal: '0.3s ease',
    slow: '0.5s ease',
  },
} as const;

// 导出类型
export type FreshTheme = typeof freshTheme;

// 获取状态对应颜色
export const getStatusColor = (status: string): string => {
  const statusMap: Record<string, string> = {
    planning: freshTheme.colors.status.planning,
    writing: freshTheme.colors.status.writing,
    revising: freshTheme.colors.status.revising,
    completed: freshTheme.colors.status.completed,
    // 中文映射
    '规划中': freshTheme.colors.status.planning,
    '创作中': freshTheme.colors.status.writing,
    '修改中': freshTheme.colors.status.revising,
    '已完成': freshTheme.colors.status.completed,
  };
  return statusMap[status] || freshTheme.colors.status.planning;
};

// 获取状态对应渐变
export const getStatusGradient = (status: string): string => {
  const color = getStatusColor(status);
  return `linear-gradient(135deg, ${color} 0%, ${adjustColorBrightness(color, 20)} 100%)`;
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

export default freshTheme;
