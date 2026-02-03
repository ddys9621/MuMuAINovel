import { Modal, Button, Space } from 'antd';
import { useEffect, useState } from 'react';

interface AnnouncementModalProps {
  visible: boolean;
  onClose: () => void;
  onDoNotShowToday: () => void;
}

export default function AnnouncementModal({ visible, onClose, onDoNotShowToday }: AnnouncementModalProps) {
  const [imageError, setImageError] = useState(false);

  useEffect(() => {
    if (visible) {
      setImageError(false);
    }
  }, [visible]);

  const handleDoNotShowToday = () => {
    onDoNotShowToday();
    onClose();
  };

  return (
    <Modal
      title="🎉 欢迎使用 AI小说创作助手"
      open={visible}
      onCancel={onClose}
      footer={
        <Space style={{ width: '100%', justifyContent: 'center' }}>
          <Button onClick={onClose} size="large">
            知道了
          </Button>
          <Button type="primary" onClick={handleDoNotShowToday} size="large">
            今天内不再提示
          </Button>
        </Space>
      }
      width={600}
      centered
      styles={{
        body: {
          padding: '24px',
        },
      }}
    >
      <div style={{ textAlign: 'center' }}>
        <div style={{
          marginBottom: '16px',
          fontSize: '16px',
          color: '#666',
          lineHeight: '1.6',
        }}>
          <p>👋 欢迎加入我们的交流群！</p>
          <p>在这里你可以：</p>
          <ul style={{
            textAlign: 'left',
            marginLeft: '40px',
            marginTop: '12px',
            marginBottom: '20px',
          }}>
            <li>💬 与其他创作者交流心得</li>
            <li>💡 获取最新功能更新和使用技巧</li>
            <li>🐛 反馈问题和建议</li>
            <li>📚 分享创作经验和灵感</li>
          </ul>
          <p style={{ fontWeight: 600, color: '#333', marginBottom: '16px' }}>
            扫描下方二维码加入QQ交流群：
          </p>
        </div>
        
        <div style={{
          marginBottom: '16px',
          padding: '12px',
          background: '#e6f7ff',
          borderRadius: '8px',
          border: '1px solid #91d5ff',
          fontSize: '15px',
          color: '#096dd9',
        }}>
          📧 二开作者QQ：<strong>973606500</strong>
        </div>

        {!imageError ? (
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            padding: '20px',
            background: '#f5f5f5',
            borderRadius: '8px',
          }}>
            <img
              src="/qq.jpg"
              alt="QQ交流群二维码"
              style={{
                maxWidth: '100%',
                maxHeight: '360px',
                borderRadius: '8px',
                boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)',
              }}
              onError={() => setImageError(true)}
            />
          </div>
        ) : (
          <div style={{
            padding: '40px',
            background: '#f5f5f5',
            borderRadius: '8px',
            color: '#999',
          }}>
            <p>二维码加载失败</p>
            <p style={{ fontSize: '12px', marginTop: '8px' }}>
              作者QQ：973606500
            </p>
          </div>
        )}
        
        <div style={{
          marginTop: '20px',
          padding: '12px',
          background: '#fff7e6',
          borderRadius: '8px',
          border: '1px solid #ffd591',
          fontSize: '14px',
          color: '#ad6800',
        }}>
          💡 提示：点击"今天内不再提示"可在今天内不再显示此公告
        </div>
      </div>
    </Modal>
  );
}