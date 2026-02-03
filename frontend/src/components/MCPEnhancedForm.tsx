/**
 * MCP 增强表单组件
 * 用于在生成功能中启用 MCP 工具
 */
import React, { useState } from 'react';
import { Form, Switch, Select, Tooltip, Space, Tag } from 'antd';
import { InfoCircleOutlined, ThunderboltOutlined } from '@ant-design/icons';

interface MCPEnhancedFormProps {
  value?: {
    enable_mcp: boolean;
    selected_plugins: string[];
  };
  onChange?: (value: { enable_mcp: boolean; selected_plugins: string[] }) => void;
}

/**
 * MCP 增强表单组件
 * 
 * 使用示例:
 * ```tsx
 * <Form.Item name="mcp_config" label="AI 增强">
 *   <MCPEnhancedForm />
 * </Form.Item>
 * ```
 */
export const MCPEnhancedForm: React.FC<MCPEnhancedFormProps> = ({ value, onChange }) => {
  const [enableMcp, setEnableMcp] = useState(value?.enable_mcp || false);
  const [selectedPlugins, setSelectedPlugins] = useState<string[]>(value?.selected_plugins || []);

  const handleEnableChange = (checked: boolean) => {
    setEnableMcp(checked);
    onChange?.({
      enable_mcp: checked,
      selected_plugins: checked ? selectedPlugins : []
    });
  };

  const handlePluginsChange = (plugins: string[]) => {
    setSelectedPlugins(plugins);
    onChange?.({
      enable_mcp: enableMcp,
      selected_plugins: plugins
    });
  };

  // 可用的 MCP 插件列表
  const availablePlugins = [
    {
      value: 'exa',
      label: 'Exa 搜索',
      description: '使用 Exa 搜索引擎查询相关资料'
    },
    {
      value: 'filesystem',
      label: '文件系统',
      description: '读取本地文件和文档'
    },
    {
      value: 'brave-search',
      label: 'Brave 搜索',
      description: '使用 Brave 搜索引擎'
    },
    {
      value: 'fetch',
      label: '网页抓取',
      description: '抓取网页内容'
    }
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space>
        <Switch
          checked={enableMcp}
          onChange={handleEnableChange}
          checkedChildren={<ThunderboltOutlined />}
          unCheckedChildren="关闭"
        />
        <span>启用 MCP 工具增强</span>
        <Tooltip title="MCP (Model Context Protocol) 允许 AI 调用外部工具获取实时信息，提升生成质量">
          <InfoCircleOutlined style={{ color: '#1890ff' }} />
        </Tooltip>
      </Space>

      {enableMcp && (
        <Form.Item
          label="选择工具"
          style={{ marginBottom: 0 }}
          help="选择 AI 可以使用的工具，留空则使用所有已启用的工具"
        >
          <Select
            mode="multiple"
            placeholder="选择要使用的工具（可选）"
            value={selectedPlugins}
            onChange={handlePluginsChange}
            style={{ width: '100%' }}
            options={availablePlugins.map(plugin => ({
              label: (
                <Space>
                  <span>{plugin.label}</span>
                  <Tag color="blue" style={{ fontSize: '12px' }}>
                    {plugin.value}
                  </Tag>
                </Space>
              ),
              value: plugin.value,
              title: plugin.description
            }))}
          />
        </Form.Item>
      )}

      {enableMcp && selectedPlugins.length > 0 && (
        <div style={{ fontSize: '12px', color: '#666' }}>
          已选择 {selectedPlugins.length} 个工具：
          {selectedPlugins.map(plugin => (
            <Tag key={plugin} color="processing" style={{ marginLeft: 4 }}>
              {plugin}
            </Tag>
          ))}
        </div>
      )}
    </Space>
  );
};

/**
 * 使用示例组件
 */
export const MCPEnhancedFormExample: React.FC = () => {
  const [form] = Form.useForm();

  const handleSubmit = (values: any) => {
    console.log('表单值:', values);
    
    // 提取 MCP 配置
    const { mcp_config, ...otherValues } = values;
    
    // 构建请求数据
    const requestData = {
      ...otherValues,
      enable_mcp: mcp_config?.enable_mcp || false,
      selected_plugins: mcp_config?.selected_plugins || []
    };
    
    console.log('请求数据:', requestData);
    
    // 调用 API
    // await generatePlotCards(requestData);
  };

  return (
    <Form form={form} onFinish={handleSubmit} layout="vertical">
      <Form.Item name="project_id" label="项目 ID" required>
        <input type="text" />
      </Form.Item>

      <Form.Item name="outline_id" label="大纲 ID" required>
        <input type="text" />
      </Form.Item>

      <Form.Item name="count" label="生成数量" initialValue={3}>
        <input type="number" min={1} max={10} />
      </Form.Item>

      <Form.Item name="mcp_config" label="AI 增强">
        <MCPEnhancedForm />
      </Form.Item>

      <Form.Item>
        <button type="submit">生成剧情卡片</button>
      </Form.Item>
    </Form>
  );
};

export default MCPEnhancedForm;
