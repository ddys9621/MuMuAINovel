/**
 * 关联管理面板组件
 * 用于显示和管理实体之间的关联关系
 */
import React, { useEffect, useMemo, useState } from 'react';
import { Card, Tabs, List, Tag, Button, Space, Empty, Spin, Badge, Tooltip, Modal } from 'antd';
import type { TabsProps } from 'antd';
import { LinkOutlined, PlusOutlined, DeleteOutlined, EditOutlined, InfoCircleOutlined } from '@ant-design/icons';
import type {
  PlotLineWithLinks,
  ChapterOutlineWithLinks,
  PlotCardWithLinks,
} from '../types';

interface LinkManagementPanelProps {
  // 实体类型
  entityType: 'plot_line' | 'chapter_outline' | 'plot_card';
  // 实体ID
  entityId: string;
  // 关联数据
  links: {
    plotLines?: PlotLineWithLinks[];
    chapterOutlines?: ChapterOutlineWithLinks[];
    plotCards?: PlotCardWithLinks[];
  };
  // 加载状态
  loading?: boolean;
  // 操作回调
  onAddLink?: (type: string) => void;
  onRemoveLink?: (type: string, id: string) => void;
  onEditLink?: (type: string, id: string) => void;
  onRefresh?: () => void;
}

export const LinkManagementPanel: React.FC<LinkManagementPanelProps> = ({
  entityType,
  links,
  loading = false,
  onAddLink,
  onRemoveLink,
  onEditLink,
  onRefresh,
}) => {
  const availableTabs = useMemo(() => {
    switch (entityType) {
      case 'plot_line':
        return ['chapterOutlines', 'plotCards'];
      case 'chapter_outline':
        return ['plotLines', 'plotCards'];
      case 'plot_card':
        return ['plotLines', 'chapterOutlines'];
      default:
        return [];
    }
  }, [entityType]);

  const [activeTab, setActiveTab] = useState<string>(availableTabs[0] || '');

  useEffect(() => {
    setActiveTab(availableTabs[0] || '');
  }, [availableTabs]);

  // 渲染剧情线列表
  const renderPlotLines = () => {
    const items = links.plotLines || [];
    
    if (items.length === 0) {
      return (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无关联的剧情线"
        >
          {onAddLink && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => onAddLink('plotLines')}>
              添加剧情线
            </Button>
          )}
        </Empty>
      );
    }

    return (
      <List
        dataSource={items}
        renderItem={(item) => (
          <List.Item
            actions={[
              onEditLink && (
                <Tooltip title="编辑">
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => onEditLink('plotLines', item.id)}
                  />
                </Tooltip>
              ),
              onRemoveLink && (
                <Tooltip title="取消关联">
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => {
                      Modal.confirm({
                        title: '确认取消关联',
                        content: `确定要取消与"${item.title}"的关联吗？`,
                        onOk: () => onRemoveLink('plotLines', item.id),
                      });
                    }}
                  />
                </Tooltip>
              ),
            ].filter(Boolean)}
          >
            <List.Item.Meta
              title={
                <Space>
                  {item.title}
                  <Tag color={item.line_type === 'main' ? 'blue' : item.line_type === 'sub' ? 'green' : 'orange'}>
                    {item.line_type === 'main' ? '主线' : item.line_type === 'sub' ? '支线' : '角色线'}
                  </Tag>
                </Space>
              }
              description={
                <Space size="large">
                  <span>
                    <InfoCircleOutlined /> {item.description || '暂无描述'}
                  </span>
                  <Badge count={item.chapter_count} showZero style={{ backgroundColor: '#52c41a' }}>
                    <span style={{ marginRight: 8 }}>章纲</span>
                  </Badge>
                  <Badge count={item.card_count} showZero style={{ backgroundColor: '#1890ff' }}>
                    <span style={{ marginRight: 8 }}>卡片</span>
                  </Badge>
                </Space>
              }
            />
          </List.Item>
        )}
      />
    );
  };

  // 渲染章纲列表
  const renderChapterOutlines = () => {
    const items = links.chapterOutlines || [];
    
    if (items.length === 0) {
      return (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无关联的章纲"
        >
          {onAddLink && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => onAddLink('chapterOutlines')}>
              添加章纲
            </Button>
          )}
        </Empty>
      );
    }

    return (
      <List
        dataSource={items}
        renderItem={(item) => (
          <List.Item
            actions={[
              onEditLink && (
                <Tooltip title="编辑">
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => onEditLink('chapterOutlines', item.id)}
                  />
                </Tooltip>
              ),
              onRemoveLink && (
                <Tooltip title="取消关联">
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => {
                      Modal.confirm({
                        title: '确认取消关联',
                        content: `确定要取消与"第${item.chapter_number}章：${item.title}"的关联吗？`,
                        onOk: () => onRemoveLink('chapterOutlines', item.id),
                      });
                    }}
                  />
                </Tooltip>
              ),
            ].filter(Boolean)}
          >
            <List.Item.Meta
              title={
                <Space>
                  <Tag color="purple">第{item.chapter_number}章</Tag>
                  {item.title}
                </Space>
              }
              description={
                <Space size="large">
                  <span>
                    <InfoCircleOutlined /> {item.summary || '暂无摘要'}
                  </span>
                  <Badge count={item.plot_line_count} showZero style={{ backgroundColor: '#52c41a' }}>
                    <span style={{ marginRight: 8 }}>剧情线</span>
                  </Badge>
                  <Badge count={item.card_count} showZero style={{ backgroundColor: '#1890ff' }}>
                    <span style={{ marginRight: 8 }}>卡片</span>
                  </Badge>
                </Space>
              }
            />
          </List.Item>
        )}
      />
    );
  };

  // 渲染剧情卡片列表
  const renderPlotCards = () => {
    const items = links.plotCards || [];
    
    if (items.length === 0) {
      return (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="暂无关联的剧情卡片"
        >
          {onAddLink && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => onAddLink('plotCards')}>
              添加剧情卡片
            </Button>
          )}
        </Empty>
      );
    }

    return (
      <List
        dataSource={items}
        renderItem={(item) => (
          <List.Item
            actions={[
              onEditLink && (
                <Tooltip title="编辑">
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => onEditLink('plotCards', item.id)}
                  />
                </Tooltip>
              ),
              onRemoveLink && (
                <Tooltip title="取消关联">
                  <Button
                    type="text"
                    size="small"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => {
                      Modal.confirm({
                        title: '确认取消关联',
                        content: `确定要取消与"${item.title}"的关联吗？`,
                        onOk: () => onRemoveLink('plotCards', item.id),
                      });
                    }}
                  />
                </Tooltip>
              ),
            ].filter(Boolean)}
          >
            <List.Item.Meta
              title={
                <Space>
                  {item.title}
                  <Tag color={
                    item.card_type === 'plot' ? 'blue' :
                    item.card_type === 'character' ? 'green' :
                    item.card_type === 'scene' ? 'orange' : 'red'
                  }>
                    {item.card_type === 'plot' ? '剧情' :
                     item.card_type === 'character' ? '角色' :
                     item.card_type === 'scene' ? '场景' : '冲突'}
                  </Tag>
                </Space>
              }
              description={
                <Space size="large">
                  <span>
                    <InfoCircleOutlined /> {item.content || '暂无内容'}
                  </span>
                  <Badge count={item.plot_line_count} showZero style={{ backgroundColor: '#52c41a' }}>
                    <span style={{ marginRight: 8 }}>剧情线</span>
                  </Badge>
                  <Badge count={item.chapter_count} showZero style={{ backgroundColor: '#1890ff' }}>
                    <span style={{ marginRight: 8 }}>章纲</span>
                  </Badge>
                </Space>
              }
            />
          </List.Item>
        )}
      />
    );
  };

  const tabItems = useMemo<TabsProps['items']>(() => {
    const items: TabsProps['items'] = [];

    if (availableTabs.includes('plotLines')) {
      items.push({
        key: 'plotLines',
        label: (
          <Badge count={links.plotLines?.length || 0} offset={[10, 0]}>
            剧情线
          </Badge>
        ),
        children: renderPlotLines(),
      });
    }

    if (availableTabs.includes('chapterOutlines')) {
      items.push({
        key: 'chapterOutlines',
        label: (
          <Badge count={links.chapterOutlines?.length || 0} offset={[10, 0]}>
            章纲
          </Badge>
        ),
        children: renderChapterOutlines(),
      });
    }

    if (availableTabs.includes('plotCards')) {
      items.push({
        key: 'plotCards',
        label: (
          <Badge count={links.plotCards?.length || 0} offset={[10, 0]}>
            剧情卡片
          </Badge>
        ),
        children: renderPlotCards(),
      });
    }

    return items;
  }, [availableTabs, links.plotLines, links.chapterOutlines, links.plotCards]);

  return (
    <Card
      title={
        <Space>
          <LinkOutlined />
          关联管理
        </Space>
      }
      extra={
        onRefresh && (
          <Button size="small" onClick={onRefresh}>
            刷新
          </Button>
        )
      }
    >
      <Spin spinning={loading}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
        />
      </Spin>
    </Card>
  );
}

export default LinkManagementPanel;
