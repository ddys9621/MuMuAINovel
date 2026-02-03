import React from 'react';

interface SSEProgressBarProps {
  loading: boolean;
  progress: number;
  message: string;
}

export const SSEProgressBar: React.FC<SSEProgressBarProps> = ({
  loading,
  progress,
  message
}) => {
  if (!loading) return null;

  return (
    <div style={{ marginTop: 16 }}>
      {/* 进度条 */}
      <div style={{
        height: 8,
        background: '#f0f0f0',
        borderRadius: 4,
        overflow: 'hidden',
        marginBottom: 8
      }}>
        <div style={{
          height: '100%',
          background: progress === 100 ? '#52c41a' : '#1890ff',
          width: `${progress}%`,
          transition: 'all 0.3s ease',
          borderRadius: 4
        }} />
      </div>
      
      {/* 进度信息 */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: 14
      }}>
        <span style={{ color: '#666' }}>
          {message || '准备生成...'}
        </span>
        <span style={{ 
          fontWeight: 'bold',
          color: progress === 100 ? '#52c41a' : '#1890ff'
        }}>
          {progress}%
        </span>
      </div>
    </div>
  );
};