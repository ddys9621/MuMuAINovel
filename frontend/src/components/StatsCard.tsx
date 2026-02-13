import React from 'react';
import { freshTheme } from '../styles/theme';

interface StatsCardProps {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  color?: 'sakura' | 'mint' | 'sky' | 'lavender';
  suffix?: string;
}

const StatsCard: React.FC<StatsCardProps> = ({
  icon,
  label,
  value,
  color = 'mint',
  suffix = '',
}) => {
  const colorMap = {
    sakura: {
      bg: 'rgba(255, 214, 224, 0.2)',
      iconBg: freshTheme.colors.primary.sakura,
    },
    mint: {
      bg: 'rgba(184, 230, 212, 0.2)',
      iconBg: freshTheme.colors.primary.mint,
    },
    sky: {
      bg: 'rgba(168, 216, 234, 0.2)',
      iconBg: freshTheme.colors.primary.sky,
    },
    lavender: {
      bg: 'rgba(212, 184, 230, 0.2)',
      iconBg: freshTheme.colors.primary.lavender,
    },
  };

  const styles: React.CSSProperties = {
    background: freshTheme.colors.background.card,
    borderRadius: freshTheme.radius.lg,
    padding: '20px',
    boxShadow: freshTheme.shadow.soft,
    border: `1px solid ${freshTheme.colors.background.border}`,
    transition: 'all 0.3s ease',
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  };

  const iconContainerStyles: React.CSSProperties = {
    width: '48px',
    height: '48px',
    borderRadius: freshTheme.radius.md,
    background: colorMap[color].bg,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '24px',
    flexShrink: 0,
  };

  const contentStyles: React.CSSProperties = {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  };

  const valueStyles: React.CSSProperties = {
    fontSize: '28px',
    fontWeight: 600,
    color: freshTheme.colors.text.primary,
    lineHeight: 1.2,
  };

  const labelStyles: React.CSSProperties = {
    fontSize: freshTheme.fontSize.sm,
    color: freshTheme.colors.text.secondary,
  };

  return (
    <div
      className="fresh-stats-card"
      style={styles}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.boxShadow = freshTheme.shadow.medium;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = freshTheme.shadow.soft;
      }}
    >
      <div style={iconContainerStyles}>{icon}</div>
      <div style={contentStyles}>
        <div style={valueStyles}>
          {value}
          {suffix}
        </div>
        <div style={labelStyles}>{label}</div>
      </div>
    </div>
  );
};

export default StatsCard;

