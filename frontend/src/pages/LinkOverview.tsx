import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Row,
  Col,
  Statistic,
  Table,
  Tabs,
  Tag,
  Button,
  Spin,
  Tooltip,
} from 'antd';
import {
  LineChartOutlined,
  FileTextOutlined,
  BookOutlined,
  TagsOutlined,
  ReloadOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { usePlotLineSync, useChapterOutlineSync, usePlotCardSync } from '../store/plotHooks';
import { useLinkGraph } from '../hooks/useLinkGraph';
import LinkStatistics from '../components/LinkStatistics';
import { LinkVisualization } from '../components/LinkVisualization';
import type {
  PlotLine,
  ChapterOutline,
  PlotCard,
  LinkGraphEntityType,
} from '../types';

interface LinkOverviewProps {
  projectId?: string;
}

const LinkOverview: React.FC<LinkOverviewProps> = ({ projectId }) => {
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const navigate = useNavigate();

  const { plotLines, refreshPlotLines } = usePlotLineSync();
  const { chapterOutlines, refreshChapterOutlines } = useChapterOutlineSync();
  const { plotCards, refreshPlotCards } = usePlotCardSync();
  const {
    filteredGraph,
    highlightedIds,
    loading: graphLoading,
    nodeLoading,
    filters,
    searchKeyword,
    initializeGraph,
    expandNode,
    setFilters,
    setSearchKeyword,
    resetGraph,
  } = useLinkGraph({ initialLimit: 50 });

  const handleRefresh = useCallback(async () => {
    if (!projectId) return;
    
    setLoading(true);
    try {
      await Promise.all([
        refreshPlotLines(projectId),
        refreshChapterOutlines(projectId),
        refreshPlotCards(projectId),
      ]);
      await initializeGraph(projectId);
    } catch (error) {
      console.error('刷新数据失败:', error);
    } finally {
      setLoading(false);
    }
  }, [projectId, refreshPlotLines, refreshChapterOutlines, refreshPlotCards, initializeGraph]);

  useEffect(() => {
    if (projectId) {
      handleRefresh();
    }
    
    // 订阅全局刷新事件
    import('../hooks/useGlobalRefresh').then(({ globalRefreshEvents }) => {
      const unsubscribe = globalRefreshEvents.subscribe(handleRefresh);
      
      // 清理函数会在组件卸载时调用
      return unsubscribe;
    });
  }, [projectId, handleRefresh]); // 只依赖projectId，避免无限循环

  useEffect(() => {
    if (!projectId) return;
    initializeGraph(projectId);
    return () => {
      resetGraph();
    };
  }, [projectId, initializeGraph, resetGraph]);

  // 计算统计信息
  const totalPlotLines = plotLines.length;
  const totalChapterOutlines = chapterOutlines.length;
  const totalPlotCards = plotCards.length;

  // 优化的关联统计计算 - 使用后端提供的统计字段
  const plotLineLinks = plotLines.reduce((sum, line) => {
    // 优先使用后端提供的计数字段，回退到数组长度
    const chapterCount = line.chapter_outline_count ?? line.chapter_outlines?.length ?? 0;
    const cardCount = line.plot_card_count ?? line.plot_cards?.length ?? 0;
    return sum + chapterCount + cardCount;
  }, 0);
  
  const chapterOutlineLinks = chapterOutlines.reduce((sum, outline) => {
    // 优先使用后端提供的计数字段，回退到数组长度
    const lineCount = outline.plot_line_count ?? outline.plot_lines?.length ?? 0;
    const cardCount = outline.plot_card_count ?? outline.plot_cards?.length ?? 0;
    return sum + lineCount + cardCount;
  }, 0);
  
  const plotCardLinks = plotCards.reduce((sum, card) => {
    // 优先使用后端提供的计数字段，回退到数组长度
    const lineCount = card.plot_line_count ?? card.plot_lines?.length ?? 0;
    const outlineCount = card.chapter_outline_count ?? card.chapter_outlines?.length ?? 0;
    return sum + lineCount + outlineCount;
  }, 0);
  
  const totalLinks = (plotLineLinks + chapterOutlineLinks + plotCardLinks) / 2; // 除以2因为双向计数

  const lineTypeCounts = plotLines.reduce(
    (acc, line) => {
      const type = line.line_type as 'main' | 'sub' | 'character';
      if (type && acc[type] !== undefined) {
        acc[type] += 1;
      } else {
        acc.sub += 1;
      }
      return acc;
    },
    { main: 0, sub: 0, character: 0 }
  );

  const cardUsageCounts = chapterOutlines.reduce(
    (acc, outline) => {
      outline.plot_cards?.forEach((card: any) => {
        const usageType = card?.usage_type ?? 'reference';
        if (usageType === 'used') acc.used += 1;
        else if (usageType === 'planned') acc.planned += 1;
        else acc.reference += 1;
      });
      return acc;
    },
    { used: 0, planned: 0, reference: 0 }
  );

  const statisticsData = {
    totalPlotLines,
    totalChapterOutlines,
    totalPlotCards,
    mainPlotLines: lineTypeCounts.main,
    subPlotLines: lineTypeCounts.sub,
    characterPlotLines: lineTypeCounts.character,
    usedCards: cardUsageCounts.used,
    plannedCards: cardUsageCounts.planned,
    referenceCards: Math.max(cardUsageCounts.reference, totalPlotCards - (cardUsageCounts.used + cardUsageCounts.planned)),
  };

  const buildEntityPath = useCallback(
    (type: LinkGraphEntityType, id: string) => {
      if (!projectId || !id) return null;
      if (type === 'plot_line') {
        return `/project/${projectId}/outline/plot-lines-enhanced?focus=${id}`;
      }
      if (type === 'chapter_outline') {
        return `/project/${projectId}/outline/chapter-outlines-enhanced?focus=${id}`;
      }
      if (type === 'plot_card') {
        return `/project/${projectId}/outline/plot-cards-enhanced?focus=${id}`;
      }
      return null;
    },
    [projectId]
  );

  const handleNodeClick = useCallback(
    (type: LinkGraphEntityType, id: string) => {
      const path = buildEntityPath(type, id);
      if (path) {
        navigate(path);
      }
    },
    [buildEntityPath, navigate]
  );

  // 剧情线详细表格
  const plotLineColumns = [
    {
      title: '剧情线',
      dataIndex: 'title',
      key: 'title',
      width: 200,
      fixed: 'left' as const,
      render: (text: string) => (
        <Tooltip title={text}>
          <strong>{text}</strong>
        </Tooltip>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      render: (text: string) => (
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {text || '-'}
        </div>
      ),
    },
    {
      title: '关联章纲',
      key: 'chapter_outlines',
      width: 120,
      render: (_: any, record: PlotLine) => (
        <Tag color="blue">{record.chapter_outlines?.length || 0} 个</Tag>
      ),
    },
    {
      title: '关联卡片',
      key: 'plot_cards',
      width: 120,
      render: (_: any, record: PlotLine) => (
        <Tag color="green">{record.plot_cards?.length || 0} 个</Tag>
      ),
    },
    {
      title: '总关联',
      key: 'total',
      width: 100,
      render: (_: any, record: PlotLine) => {
        const total = (record.chapter_outlines?.length || 0) + (record.plot_cards?.length || 0);
        return <Tag color={total > 0 ? 'purple' : 'default'}>{total} 个</Tag>;
      },
    },
  ];

  // 章纲详细表格
  const chapterOutlineColumns = [
    {
      title: '章节',
      dataIndex: 'chapter_number',
      key: 'chapter_number',
      width: 80,
      fixed: 'left' as const,
      render: (num: number) => `第${num}章`,
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      width: 200,
      render: (text: string) => (
        <Tooltip title={text}>
          <strong>{text}</strong>
        </Tooltip>
      ),
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      render: (text: string) => (
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {text || '-'}
        </div>
      ),
    },
    {
      title: '关联剧情线',
      key: 'plot_lines',
      width: 120,
      render: (_: any, record: ChapterOutline) => (
        <Tag color="blue">{record.plot_lines?.length || 0} 个</Tag>
      ),
    },
    {
      title: '关联卡片',
      key: 'plot_cards',
      width: 120,
      render: (_: any, record: ChapterOutline) => (
        <Tag color="green">{record.plot_cards?.length || 0} 个</Tag>
      ),
    },
    {
      title: '总关联',
      key: 'total',
      width: 100,
      render: (_: any, record: ChapterOutline) => {
        const total = (record.plot_lines?.length || 0) + (record.plot_cards?.length || 0);
        return <Tag color={total > 0 ? 'purple' : 'default'}>{total} 个</Tag>;
      },
    },
  ];

  // 剧情卡片详细表格
  const plotCardColumns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      width: 200,
      fixed: 'left' as const,
      render: (text: string, record: PlotCard) => (
        <div>
          <Tooltip title={text}>
            <strong>{text}</strong>
          </Tooltip>
          <div style={{ marginTop: 4 }}>
            <Tag color="orange">{record.card_type}</Tag>
          </div>
        </div>
      ),
    },
    {
      title: '内容',
      dataIndex: 'content',
      key: 'content',
      render: (text: string) => (
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {text || '-'}
        </div>
      ),
    },
    {
      title: '关联剧情线',
      key: 'plot_lines',
      width: 120,
      render: (_: any, record: PlotCard) => (
        <Tag color="blue">{record.plot_lines?.length || 0} 个</Tag>
      ),
    },
    {
      title: '关联章纲',
      key: 'chapter_outlines',
      width: 120,
      render: (_: any, record: PlotCard) => (
        <Tag color="green">{record.chapter_outlines?.length || 0} 个</Tag>
      ),
    },
    {
      title: '总关联',
      key: 'total',
      width: 100,
      render: (_: any, record: PlotCard) => {
        const total = (record.plot_lines?.length || 0) + (record.chapter_outlines?.length || 0);
        return <Tag color={total > 0 ? 'purple' : 'default'}>{total} 个</Tag>;
      },
    },
  ];

  // 找出未关联的项目
  const unlinkedPlotLines = plotLines.filter(line => 
    (!line.chapter_outlines || line.chapter_outlines.length === 0) &&
    (!line.plot_cards || line.plot_cards.length === 0)
  );
  const unlinkedChapterOutlines = chapterOutlines.filter(outline => 
    (!outline.plot_lines || outline.plot_lines.length === 0) &&
    (!outline.plot_cards || outline.plot_cards.length === 0)
  );
  const unlinkedPlotCards = plotCards.filter(card => 
    (!card.plot_lines || card.plot_lines.length === 0) &&
    (!card.chapter_outlines || card.chapter_outlines.length === 0)
  );

  const tabItems = [
    {
      key: 'overview',
      label: (
        <span>
          <FileTextOutlined />
          总览
        </span>
      ),
      children: (
        <div>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col xs={24} xl={10}>
              <LinkStatistics statistics={statisticsData} />
            </Col>
            <Col xs={24} xl={14}>
              <LinkVisualization
                projectId={projectId}
                filteredGraph={filteredGraph}
                highlightedIds={highlightedIds}
                loading={graphLoading}
                nodeLoading={nodeLoading}
                filters={filters}
                searchKeyword={searchKeyword}
                onSearchChange={setSearchKeyword}
                onFiltersChange={setFilters}
                onExpandNode={expandNode}
                onRefresh={projectId ? () => initializeGraph(projectId) : undefined}
                onNodeNavigate={handleNodeClick}
              />
            </Col>
          </Row>
          {(unlinkedPlotLines.length > 0 || unlinkedChapterOutlines.length > 0 || unlinkedPlotCards.length > 0) && (
            <Card
              title={
                <span>
                  ⚠️ 未关联项目
                  <span style={{ marginLeft: 8, fontSize: 12, color: '#999', fontWeight: 'normal' }}>
                    以下项目尚未建立关联关系
                  </span>
                </span>
              }
              style={{ marginBottom: 16 }}
              size="small"
            >
              <Row gutter={16}>
                {unlinkedPlotLines.length > 0 && (
                  <Col span={8}>
                    <div style={{ marginBottom: 6, fontSize: 13 }}>
                      <strong>剧情线 ({unlinkedPlotLines.length})</strong>
                    </div>
                    <div style={{ maxHeight: 120, overflowY: 'auto' }}>
                      {unlinkedPlotLines.slice(0, 5).map((line) => (
                        <div key={line.id} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <Tag>{line.title}</Tag>
                          <Button
                            type="link"
                            size="small"
                            onClick={() => {
                              const path = buildEntityPath('plot_line', line.id);
                              if (path) navigate(path);
                            }}
                          >
                            前往
                          </Button>
                        </div>
                      ))}
                      {unlinkedPlotLines.length > 5 && (
                        <div style={{ color: '#666', fontSize: 12, marginTop: 4 }}>
                          还有 {unlinkedPlotLines.length - 5} 个...
                        </div>
                      )}
                    </div>
                  </Col>
                )}
                {unlinkedChapterOutlines.length > 0 && (
                  <Col span={8}>
                    <div style={{ marginBottom: 6, fontSize: 13 }}>
                      <strong>章纲 ({unlinkedChapterOutlines.length})</strong>
                    </div>
                    <div style={{ maxHeight: 120, overflowY: 'auto' }}>
                      {unlinkedChapterOutlines.slice(0, 5).map((outline) => (
                        <div key={outline.id} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <Tag>第{outline.chapter_number}章：{outline.title}</Tag>
                          <Button
                            type="link"
                            size="small"
                            onClick={() => {
                              const path = buildEntityPath('chapter_outline', outline.id);
                              if (path) navigate(path);
                            }}
                          >
                            前往
                          </Button>
                        </div>
                      ))}
                      {unlinkedChapterOutlines.length > 5 && (
                        <div style={{ color: '#666', fontSize: 12, marginTop: 4 }}>
                          还有 {unlinkedChapterOutlines.length - 5} 个...
                        </div>
                      )}
                    </div>
                  </Col>
                )}
                {unlinkedPlotCards.length > 0 && (
                  <Col span={8}>
                    <div style={{ marginBottom: 6, fontSize: 13 }}>
                      <strong>剧情卡片 ({unlinkedPlotCards.length})</strong>
                    </div>
                    <div style={{ maxHeight: 120, overflowY: 'auto' }}>
                      {unlinkedPlotCards.slice(0, 5).map((card) => (
                        <div key={card.id} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <Tag>{card.title}</Tag>
                          <Button
                            type="link"
                            size="small"
                            onClick={() => {
                              const path = buildEntityPath('plot_card', card.id);
                              if (path) navigate(path);
                            }}
                          >
                            前往
                          </Button>
                        </div>
                      ))}
                      {unlinkedPlotCards.length > 5 && (
                        <div style={{ color: '#666', fontSize: 12, marginTop: 4 }}>
                          还有 {unlinkedPlotCards.length - 5} 个...
                        </div>
                      )}
                    </div>
                  </Col>
                )}
              </Row>
            </Card>
          )}
        </div>
      ),
    },
    {
      key: 'plotLines',
      label: (
        <span>
          <LineChartOutlined />
          剧情线 ({totalPlotLines})
        </span>
      ),
      children: (
        <Table
          columns={plotLineColumns}
          dataSource={plotLines}
          rowKey="id"
          scroll={{ x: 1000 }}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 个剧情线`,
            pageSizeOptions: ['10', '20', '50'],
          }}
        />
      ),
    },
    {
      key: 'chapterOutlines',
      label: (
        <span>
          <BookOutlined />
          章纲 ({totalChapterOutlines})
        </span>
      ),
      children: (
        <Table
          columns={chapterOutlineColumns}
          dataSource={chapterOutlines}
          rowKey="id"
          scroll={{ x: 1000 }}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 个章纲`,
            pageSizeOptions: ['10', '20', '50'],
          }}
        />
      ),
    },
    {
      key: 'plotCards',
      label: (
        <span>
          <TagsOutlined />
          剧情卡片 ({totalPlotCards})
        </span>
      ),
      children: (
        <Table
          columns={plotCardColumns}
          dataSource={plotCards}
          rowKey="id"
          scroll={{ x: 1000 }}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 个剧情卡片`,
            pageSizeOptions: ['10', '20', '50'],
          }}
        />
      ),
    },
  ];

  return (
    <div style={{ padding: '24px', minHeight: '100vh', overflowY: 'auto' }}>
      <Card>
        <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
          <Col>
            <h2 style={{ margin: 0 }}>
              <LinkOutlined style={{ marginRight: 8 }} />
              关联总览
            </h2>
            <p style={{ margin: '4px 0 0 0', color: '#666' }}>
              查看项目中所有元素的关联关系和统计信息
            </p>
          </Col>
          <Col>
            <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={loading}>
              刷新数据
            </Button>
          </Col>
        </Row>

        <Spin spinning={loading}>
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={6}>
              <Card>
                <Statistic
                  title="剧情线"
                  value={totalPlotLines}
                  prefix={<LineChartOutlined />}
                  valueStyle={{ color: '#1890ff' }}
                />
                <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>未关联: {unlinkedPlotLines.length}</div>
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="章纲"
                  value={totalChapterOutlines}
                  prefix={<BookOutlined />}
                  valueStyle={{ color: '#52c41a' }}
                />
                <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>未关联: {unlinkedChapterOutlines.length}</div>
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="剧情卡片"
                  value={totalPlotCards}
                  prefix={<TagsOutlined />}
                  valueStyle={{ color: '#faad14' }}
                />
                <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>未关联: {unlinkedPlotCards.length}</div>
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="总关联数"
                  value={totalLinks}
                  prefix={<LinkOutlined />}
                  valueStyle={{ color: '#722ed1' }}
                />
                <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
                  平均关联度: {(totalLinks / (totalPlotLines + totalChapterOutlines + totalPlotCards) || 0).toFixed(1)}
                </div>
              </Card>
            </Col>
          </Row>

          <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
        </Spin>
      </Card>
    </div>
  );
}

export default LinkOverview;
