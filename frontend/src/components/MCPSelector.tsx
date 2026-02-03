import React, { useState, useEffect } from 'react';
import { Switch, Select, Card, Space, Typography, message, Spin } from 'antd';
import { ThunderboltOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { mcpPluginApi } from '../services/api';
import type { MCPPlugin } from '../types';

const { Text } = Typography;

export interface MCPSelectorValue {
  enable: boolean;
  selected: string[];
}

export interface MCPSelectorProps {
  value?: MCPSelectorValue;
  onChange?: (value: MCPSelectorValue) => void;
  disabled?: boolean;
  size?: 'small' | 'middle' | 'large';
  style?: React.CSSProperties;
}

export const MCPSelector: React.FC<MCPSelectorProps> = ({
  value = { enable: false, selected: [] },
  onChange,
  disabled = false,
  size = 'middle',
  style
}) => {
  const [plugins, setPlugins] = useState<MCPPlugin[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string>('');

  // 加载已启用的插件列表
  const loadPlugins = async () => {
    setLoading(true);
    setLoadError('');
    try {
      const data = await mcpPluginApi.getPlugins({ enabled_only: true });
      setPlugins(data);
    } catch (error: any) {
      const errorMsg = error?.response?.data?.detail || '加载插件列表失败';
      setLoadError(errorMsg);
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPlugins();
  }, []);

  const handleEnableChange = (enable: boolean) => {
    const newValue: MCPSelectorValue = {
      enable,
      selected: enable ? value.selected : []
    };
    onChange?.(newValue);
  };

  const handlePluginChange = (selected: string[]) => {
    const newValue: MCPSelectorValue = {
      enable: value.enable,
      selected
    };
    onChange?.(newValue);
  };

  // 插件选项
  const pluginOptions = plugins.map(plugin => ({
    label: (
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        <Text strong>{plugin.display_name || plugin.plugin_name}</Text>
        {plugin.description && (
          <Text type="secondary" style={{ fontSize: '12px' }}>
            {plugin.description.length > 50 
              ? `${plugin.description.substring(0, 50)}...` 
              : plugin.description
            }
          </Text>
        )}
      </div>
    ),
    value: plugin.plugin_name
  }));

  return (
    <Card 
      size="small" 
      style={{ 
        backgroundColor: '#f8f9ff', 
        border: '1px solid #d6e4ff',
        ...style 
      }}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        {/* 主开关 */}
        <Space align="center">
          <ThunderboltOutlined style={{ color: '#1890ff' }} />
          <Switch
            checked={value.enable}
            onChange={handleEnableChange}
            disabled={disabled}
            style={{ margin: '4px 8px' }}
          />
          <Text strong>启用 MCP 插件增强</Text>
          {loadError && (
            <InfoCircleOutlined 
              style={{ color: '#ff4d4f', cursor: 'pointer' }} 
              title={`加载失败: ${loadError}`}
              onClick={loadPlugins}
            />
          )}
        </Space>

        {/* 插件多选 */}
        {value.enable && (
          <div>
            <Text type="secondary" style={{ fontSize: '12px', marginBottom: 8, display: 'block' }}>
              选择本次生成要使用的插件（至少选择一个）：
            </Text>
            <Spin spinning={loading}>
              <Select
                mode="multiple"
                placeholder={plugins.length === 0 ? "暂无可用插件" : "请选择插件"}
                value={value.selected}
                onChange={handlePluginChange}
                disabled={disabled || plugins.length === 0}
                style={{ width: '100%' }}
                size={size}
                options={pluginOptions}
                maxTagCount={3}
                maxTagPlaceholder={(omittedValues) => `+${omittedValues.length} 个插件`}
                notFoundContent={loading ? "加载中..." : "暂无可用插件"}
                optionLabelProp="label"
              />
            </Spin>
            
            {plugins.length === 0 && !loading && !loadError && (
              <Text type="secondary" style={{ fontSize: '12px', marginTop: 4, display: 'block' }}>
                请先在 MCP 插件管理页面启用插件
              </Text>
            )}
            
            {value.enable && value.selected.length === 0 && plugins.length > 0 && (
              <Text type="warning" style={{ fontSize: '12px', marginTop: 4, display: 'block' }}>
                ⚠️ 未选择任何插件，将不会启用 MCP 功能
              </Text>
            )}
          </div>
        )}
      </Space>
    </Card>
  );
};

export default MCPSelector;
