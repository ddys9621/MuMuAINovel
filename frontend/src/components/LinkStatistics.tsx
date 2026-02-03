/**
 * 关联统计组件
 * 显示实体的关联统计信息
 */
import React from 'react';
import { Card, Statistic, Row, Col, Progress, Space, Tag, Tooltip } from 'antd';
import {
  LinkOutlined,
  FileTextOutlined,
  BranchesOutlined,
  TagsOutlined,
} from '@ant-design/icons';

interface LinkStatisticsProps {
  // 统计数据
  statistics: {
    totalPlotLines?: number;
    totalChapterOutlines?: number;
    totalPlotCards?: number;
    mainPlotLines?: number;
    subPlotLines?: number;
    characterPlotLines?: number;
    usedCards?: number;
    plannedCards?: number;
    referenceCards?: number;
  };
  // 是否显示详细信息
  showDetails?: boolean;
  // 自定义样式
  style?: React.CSSProperties;
}

export const LinkStatistics: React.FC<LinkStatisticsProps> = ({
  statistics,
  showDetails = true,
  style,
}) => {
  const {
    totalPlotLines = 0,
    totalChapterOutlines = 0,
    totalPlotCards = 0,
    mainPlotLines = 0,
    subPlotLines = 0,
    characterPlotLines = 0,
  } = statistics;


  return (
    <Card
      title={
        <Space>
          <LinkOutlined />
          关联统计
        </Space>
      }
      style={style}
    >
      <Row gutter={[16, 16]}>
        {/* 基础统计 */}
        <Col xs={24} sm={8}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic
              title="剧情线"
              value={totalPlotLines}
              prefix={<BranchesOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
            {showDetails && totalPlotLines > 0 && (
              <Space size="small" style={{ marginTop: 8 }}>
                <Tag color="blue">主线 {mainPlotLines}</Tag>
                <Tag color="green">支线 {subPlotLines}</Tag>
                <Tag color="orange">角色 {characterPlotLines}</Tag>
              </Space>
            )}
          </Card>
        </Col>

        <Col xs={24} sm={8}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic
              title="章纲"
              value={totalChapterOutlines}
              prefix={<FileTextOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>

        <Col xs={24} sm={8}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Statistic
              title="剧情卡片"
              value={totalPlotCards}
              prefix={<TagsOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 详细统计 */}
      {showDetails && (
        <>
          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col span={24}>
              <Card size="small" title="剧情线分布">
                <Space direction="vertical" style={{ width: '100%' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>主线</span>
                    <span>{mainPlotLines}</span>
                  </div>
                  <Progress
                    percent={totalPlotLines > 0 ? Math.round((mainPlotLines / totalPlotLines) * 100) : 0}
                    strokeColor="#1890ff"
                    showInfo={false}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>支线</span>
                    <span>{subPlotLines}</span>
                  </div>
                  <Progress
                    percent={totalPlotLines > 0 ? Math.round((subPlotLines / totalPlotLines) * 100) : 0}
                    strokeColor="#52c41a"
                    showInfo={false}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>角色线</span>
                    <span>{characterPlotLines}</span>
                  </div>
                  <Progress
                    percent={totalPlotLines > 0 ? Math.round((characterPlotLines / totalPlotLines) * 100) : 0}
                    strokeColor="#faad14"
                    showInfo={false}
                  />
                </Space>
              </Card>
            </Col>
          </Row>
        </>
      )}
    </Card>
  );
};

/**
 * 简化版统计组件 - 仅显示数字
 */
interface SimpleLinkStatisticsProps {
  plotLineCount?: number;
  chapterOutlineCount?: number;
  plotCardCount?: number;
  style?: React.CSSProperties;
}

export const SimpleLinkStatistics: React.FC<SimpleLinkStatisticsProps> = ({
  plotLineCount = 0,
  chapterOutlineCount = 0,
  plotCardCount = 0,
  style,
}) => {
  return (
    <Space size="large" style={style}>
      <Tooltip title="关联的剧情线数量">
        <Space>
          <BranchesOutlined style={{ color: '#52c41a' }} />
          <span>{plotLineCount}</span>
        </Space>
      </Tooltip>
      <Tooltip title="关联的章纲数量">
        <Space>
          <FileTextOutlined style={{ color: '#1890ff' }} />
          <span>{chapterOutlineCount}</span>
        </Space>
      </Tooltip>
      <Tooltip title="关联的剧情卡片数量">
        <Space>
          <TagsOutlined style={{ color: '#cf1322' }} />
          <span>{plotCardCount}</span>
        </Space>
      </Tooltip>
    </Space>
  );
};

export default LinkStatistics;
