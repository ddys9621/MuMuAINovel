import { useState } from 'react';
import { Card, Input, Button, message, Space } from 'antd';
import { ThunderboltOutlined } from '@ant-design/icons';
import { polishApi } from '../services/api';

const { TextArea } = Input;

export default function Polish() {
  const [originalText, setOriginalText] = useState('');
  const [polishedText, setPolishedText] = useState('');
  const [loading, setLoading] = useState(false);

  const handlePolish = async () => {
    if (!originalText.trim()) {
      message.warning('请输入要去味的文本');
      return;
    }

    try {
      setLoading(true);
      const result = await polishApi.polishText({ text: originalText });
      setPolishedText(result.polished_text);
      message.success('AI去味完成');
    } catch {
      message.error('AI去味失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(polishedText);
    message.success('已复制到剪贴板');
  };

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>AI去味工具</h2>
      <p style={{ color: 'rgba(0,0,0,0.45)', marginBottom: 24 }}>
        将AI生成的文本变得更自然、更像人类作家的手笔
      </p>

      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <Card title="原始文本" extra={
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={handlePolish}
            loading={loading}
          >
            开始去味
          </Button>
        }>
          <TextArea
            rows={10}
            placeholder="粘贴或输入需要去味的文本..."
            value={originalText}
            onChange={(e) => setOriginalText(e.target.value)}
          />
        </Card>

        {polishedText && (
          <Card title="去味后文本" extra={
            <Button onClick={handleCopy}>复制文本</Button>
          }>
            <TextArea
              rows={10}
              value={polishedText}
              readOnly
            />
          </Card>
        )}
      </Space>
    </div>
  );
}