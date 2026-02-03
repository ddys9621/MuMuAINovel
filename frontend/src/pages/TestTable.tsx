import React from 'react';
import { Table, Tooltip, Card } from 'antd';

const TestTable: React.FC = () => {
  const data = [
    {
      id: '1',
      title: '测试标题',
      description: '这是一段很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长的描述文字，应该会被截断并显示省略号',
    },
  ];

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      width: 150,
      fixed: 'left' as const,
    },
    {
      title: '描述（有width + ellipsis）',
      dataIndex: 'description',
      key: 'description',
      width: 300,
      ellipsis: {
        showTitle: false,
      },
      render: (text: string) => (
        <Tooltip placement="topLeft" title={text}>
          <span>{text || '-'}</span>
        </Tooltip>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card title="Ellipsis 测试">
        <p>如果配置正确，描述列应该显示省略号（...），鼠标悬停显示完整内容</p>
        <Table
          columns={columns}
          dataSource={data}
          rowKey="id"
          scroll={{ x: 800 }}
          pagination={false}
        />
      </Card>
    </div>
  );
};

export default TestTable;
