/**
 * 关联选择器组件
 * 用于选择和管理实体之间的关联关系
 */
import React, { useState, useEffect } from 'react';
import { Select, Tag, Space, Button, Tooltip } from 'antd';
import { PlusOutlined, LinkOutlined } from '@ant-design/icons';
import type { SelectProps } from 'antd';

interface LinkItem {
  id: string;
  title: string;
  subtitle?: string;
  extra?: React.ReactNode;
}

interface LinkSelectorProps {
  // 可选项列表
  options: LinkItem[];
  // 已选中的项
  selectedIds: string[];
  // 选择变化回调
  onChange?: (selectedIds: string[]) => void;
  // 添加关联回调
  onLink?: (ids: string[]) => Promise<void>;
  // 删除关联回调
  onUnlink?: (ids: string[]) => Promise<void>;
  // 是否显示操作按钮
  showActions?: boolean;
  // 是否多选
  multiple?: boolean;
  // 占位符
  placeholder?: string;
  // 是否加载中
  loading?: boolean;
  // 是否禁用
  disabled?: boolean;
  // 自定义渲染选项
  renderOption?: (item: LinkItem) => React.ReactNode;
  // 自定义渲染标签
  renderTag?: (item: LinkItem, onClose: () => void) => React.ReactNode;
}

export const LinkSelector: React.FC<LinkSelectorProps> = ({
  options,
  selectedIds,
  onChange,
  onLink,
  onUnlink,
  showActions = true,
  multiple = true,
  placeholder = '选择关联项',
  loading = false,
  disabled = false,
  // renderOption,
  renderTag,
}) => {
  const [tempSelectedIds, setTempSelectedIds] = useState<string[]>([]);
  const [linking, setLinking] = useState(false);

  useEffect(() => {
    // 过滤掉在 options 中找不到的 ID
    const validIds = selectedIds.filter(id => options.some(opt => opt.id === id));
    setTempSelectedIds(validIds);
  }, [selectedIds, options]);

  // 处理选择变化
  const handleSelectChange = (value: string | string[]) => {
    const ids = Array.isArray(value) ? value : [value];
    setTempSelectedIds(ids);
    onChange?.(ids);
  };

  // 处理添加关联
  const handleLink = async () => {
    const newIds = tempSelectedIds.filter(id => !selectedIds.includes(id));
    if (newIds.length === 0) return;

    setLinking(true);
    try {
      await onLink?.(newIds);
    } finally {
      setLinking(false);
    }
  };

  // 处理删除关联
  const handleUnlink = async (id: string) => {
    setLinking(true);
    try {
      await onUnlink?.([id]);
    } finally {
      setLinking(false);
    }
  };

  // 获取选项数据
  const getOptionData = (id: string): LinkItem | undefined => {
    return options.find(opt => opt.id === id);
  };

  // 默认选项渲染
  // const defaultRenderOption = (item: LinkItem) => (
  //   <div style={{
  //     display: 'flex',
  //     justifyContent: 'space-between',
  //     alignItems: 'center',
  //     maxWidth: '100%',
  //     overflow: 'hidden'
  //   }}>
  //     <div style={{ flex: 1, minWidth: 0 }}>
  //       <div style={{
  //         overflow: 'hidden',
  //         textOverflow: 'ellipsis',
  //         whiteSpace: 'nowrap'
  //       }}>
  //         {item.title}
  //       </div>
  //       {item.subtitle && (
  //         <div style={{
  //           fontSize: '12px',
  //           color: '#999',
  //           overflow: 'hidden',
  //           textOverflow: 'ellipsis',
  //           whiteSpace: 'nowrap'
  //         }}>
  //           {item.subtitle}
  //         </div>
  //       )}
  //     </div>
  //     {item.extra && (
  //       <div style={{ marginLeft: '8px', flexShrink: 0 }}>
  //         {item.extra}
  //       </div>
  //     )}
  //   </div>
  // );

  // 默认标签渲染
  const defaultRenderTag = (item: LinkItem, onClose: () => void) => {
    const isClosable = !disabled && !!onUnlink;
    
    return (
      <Tag
        closable={isClosable}
        onClose={(e) => {
          e.preventDefault();
          e.stopPropagation();
          onClose();
        }}
        style={{ 
          marginRight: 3,
          maxWidth: '200px',
          display: 'inline-flex',
          alignItems: 'center'
        }}
        title={item.title}
      >
        <span style={{
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          display: 'inline-block',
          maxWidth: isClosable ? '170px' : '200px'
        }}>
          {item.title}
        </span>
      </Tag>
    );
  };

  // Select 选项 - 修复显示问题
  const selectOptions: SelectProps['options'] = options.map(item => ({
    label: item.title, // 直接使用title作为label
    value: item.id,
    // 保留原始数据用于渲染
    ...item
  }));

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      {/* 选择器 */}
      <Space.Compact style={{ width: '100%' }}>
        <Select
          mode={multiple ? 'multiple' : undefined}
          style={{ 
            flex: 1,
            minWidth: '300px',
            maxWidth: '500px'
          }}
          placeholder={placeholder}
          value={tempSelectedIds}
          onChange={handleSelectChange}
          options={selectOptions}
          loading={loading}
          disabled={disabled || linking}
          showSearch
          optionLabelProp="label"
          styles={{
            popup: {
              root: {
                minWidth: '400px',
                maxWidth: '600px'
              }
            }
          }}
          tagRender={(props) => {
            const { value, closable, onClose } = props;
            const item = options.find(opt => opt.id === value);
            if (!item) {
              return (
                <Tag closable={closable} onClose={onClose}>
                  {value}
                </Tag>
              );
            }
            
            return (
              <Tag
                closable={!disabled && closable}
                onClose={onClose}
                style={{ 
                  marginRight: 3,
                  maxWidth: '200px',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  display: 'inline-block'
                }}
                title={item.title}
              >
                {item.title}
              </Tag>
            );
          }}
          filterOption={(input, option) => {
            const item = options.find(opt => opt.id === option?.value);
            if (!item) return false;
            return (
              item.title.toLowerCase().includes(input.toLowerCase()) ||
              item.subtitle?.toLowerCase().includes(input.toLowerCase()) ||
              false
            );
          }}
        />
        {showActions && onLink && (
          <Tooltip title="添加关联">
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleLink}
              loading={linking}
              disabled={disabled || tempSelectedIds.length === 0}
            />
          </Tooltip>
        )}
      </Space.Compact>

      {/* 已关联项列表 */}
      {selectedIds.length > 0 && (
        <div style={{ 
          marginTop: 8,
          maxHeight: '200px',
          overflow: 'auto',
          border: '1px solid #f0f0f0',
          borderRadius: '6px',
          padding: '8px',
          backgroundColor: '#fafafa'
        }}>
          <div style={{ marginBottom: '4px', fontSize: '12px', color: '#666' }}>
            已关联项 ({selectedIds.length})
          </div>
          <Space size={[0, 8]} wrap>
            {selectedIds.map(id => {
              const item = getOptionData(id);
              if (!item) return null;

              if (renderTag) {
                return (
                  <React.Fragment key={id}>
                    {renderTag(item, () => handleUnlink(id))}
                  </React.Fragment>
                );
              }

              return (
                <React.Fragment key={id}>
                  {defaultRenderTag(item, () => handleUnlink(id))}
                </React.Fragment>
              );
            })}
          </Space>
        </div>
      )}
    </Space>
  );
};

/**
 * 简化版关联选择器 - 仅用于显示和快速操作
 */
interface SimpleLinkSelectorProps {
  items: LinkItem[];
  onRemove?: (id: string) => void;
  onAdd?: () => void;
  loading?: boolean;
  emptyText?: string;
}

export const SimpleLinkSelector: React.FC<SimpleLinkSelectorProps> = ({
  items,
  onRemove,
  onAdd,
  emptyText = '暂无关联',
}) => {
  if (items.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '20px 0', color: '#999' }}>
        <LinkOutlined style={{ fontSize: 24, marginBottom: 8 }} />
        <div>{emptyText}</div>
        {onAdd && (
          <Button
            type="link"
            icon={<PlusOutlined />}
            onClick={onAdd}
            style={{ marginTop: 8 }}
          >
            添加关联
          </Button>
        )}
      </div>
    );
  }

  return (
    <Space size={[0, 8]} wrap>
      {items.map(item => (
        <Tag
          key={item.id}
          closable={!!onRemove}
          onClose={() => onRemove?.(item.id)}
          style={{ marginRight: 3 }}
        >
          <Space size={4}>
            {item.title}
            {item.extra}
          </Space>
        </Tag>
      ))}
      {onAdd && (
        <Tag
          icon={<PlusOutlined />}
          onClick={onAdd}
          style={{ cursor: 'pointer', borderStyle: 'dashed' }}
        >
          添加
        </Tag>
      )}
    </Space>
  );
};

export default LinkSelector;
