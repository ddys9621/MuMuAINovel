import React, { useEffect, useMemo, useRef } from 'react';
import { Card, Space, Empty, Spin, Input, Checkbox, Tag, Tooltip, Button } from 'antd';
import {
  ApartmentOutlined,
  FilterOutlined,
  SearchOutlined,
  ReloadOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import * as G6 from '@antv/g6';
import type { LinkGraphEntityType, LinkGraphNode, LinkGraphPayload } from '../types';

type CheckboxValueType = string | number;

const ENTITY_META: Record<LinkGraphEntityType, { label: string; color: string; bg: string }> = {
  project: { label: '项目', color: '#722ed1', bg: '#f4f0ff' },
  plot_line: { label: '剧情线', color: '#52c41a', bg: '#f6ffed' },
  chapter_outline: { label: '章纲', color: '#1890ff', bg: '#e6f4ff' },
  plot_card: { label: '剧情卡片', color: '#cf1322', bg: '#fff1f0' },
};

const LINK_CARD_NODE_TYPE = 'link-card';

interface LinkVisualizationProps {
  projectId?: string;
  filteredGraph: LinkGraphPayload;
  highlightedIds?: string[];
  loading?: boolean;
  nodeLoading?: Record<string, boolean>;
  filters: LinkGraphEntityType[];
  searchKeyword: string;
  onSearchChange: (keyword: string) => void;
  onFiltersChange: (types: LinkGraphEntityType[]) => void;
  onExpandNode: (nodeId: string, type: LinkGraphEntityType) => Promise<void> | void;
  onRefresh?: () => void;
  onNodeNavigate?: (type: LinkGraphEntityType, id: string) => void;
}

const buildStatsText = (node?: LinkGraphNode) => {
  if (!node?.stats) {
    return {} as { total?: string; details?: string };
  }
  const { chapterCount, plotCardCount, plotLineCount } = node.stats;
  const detailParts: string[] = [];
  const totals = [chapterCount, plotCardCount, plotLineCount]
    .filter((val) => typeof val === 'number')
    .map((val) => Number(val));
  if (typeof chapterCount === 'number') {
    detailParts.push(`章纲 ${chapterCount}`);
  }
  if (typeof plotCardCount === 'number') {
    detailParts.push(`剧情卡片 ${plotCardCount}`);
  }
  if (typeof plotLineCount === 'number') {
    detailParts.push(`剧情线 ${plotLineCount}`);
  }
  const totalValue = totals.reduce((acc, cur) => acc + cur, 0);
  return {
    total: totals.length ? `关联 ${totalValue} 个` : undefined,
    details: detailParts.length ? detailParts.join(' · ') : undefined,
  };
};

const buildNodeLines = (node?: LinkGraphNode) => {
  if (!node) return [] as string[];
  const stats = buildStatsText(node);
  const meta = ENTITY_META[node.type];
  const lines: string[] = [];
  if (meta.label && node.type !== 'project') {
    lines.push(`[${meta.label}]`);
  }
  lines.push(node.title);
  if (stats.total) lines.push(stats.total);
  if (stats.details) lines.push(stats.details);
  return lines;
};

let linkCardNodeRegistered = false;

const registerLinkCardNode = () => {
  if (typeof window === 'undefined' || linkCardNodeRegistered) return;
  linkCardNodeRegistered = true;

  G6.registerNode(LINK_CARD_NODE_TYPE, {
    draw(cfg, group) {
      const data = (cfg?.data || {}) as LinkGraphNode;
      const entityType = data?.type ?? 'plot_line';
      const meta = ENTITY_META[entityType] || ENTITY_META.plot_line;
      const width = 220;
      const height = 120;
      const radius = 16;
      const lines = buildNodeLines(data);

      const keyShape = group.addShape('rect', {
        name: 'card-border',
        attrs: {
          x: -width / 2,
          y: -height / 2,
          width,
          height,
          radius,
          fill: '#fff',
          stroke: meta.color,
          lineWidth: 2,
          shadowColor: 'rgba(0,0,0,0.12)',
          shadowBlur: 12,
        },
      });

      group.addShape('rect', {
        name: 'card-inner',
        attrs: {
          x: -width / 2 + 3,
          y: -height / 2 + 3,
          width: width - 6,
          height: height - 6,
          radius: radius - 2,
          fill: meta.bg,
          stroke: 'transparent',
        },
        capture: false,
      });

      const baseX = -width / 2 + 16;
      let currentY = -height / 2 + 16;

      lines.forEach((line, index) => {
        const isTypeLine = index === 0 && data?.type !== 'project';
        group.addShape('text', {
          name: `card-line-${index}`,
          attrs: {
            text: line,
            x: baseX,
            y: currentY,
            fill: isTypeLine ? meta.color : '#1f1f1f',
            fontSize: isTypeLine ? 12 : 14,
            fontWeight: isTypeLine ? 600 : 500,
            textBaseline: 'top',
          },
          capture: false,
        });
        currentY += isTypeLine ? 18 : 20;
      });

      const indicatorLabel = data?.expandable ? (data?.expanded ? '收起' : '展开') : '跳转';
      group.addShape('text', {
        name: 'card-indicator-text',
        attrs: {
          text: indicatorLabel,
          x: width / 2 - 50,
          y: height / 2 - 22,
          fill: data?.expandable ? meta.color : '#8c8c8c',
          fontSize: 12,
          fontWeight: 600,
        },
        capture: false,
      });

      return keyShape;
    },
  });
};

registerLinkCardNode();

export const LinkVisualization: React.FC<LinkVisualizationProps> = ({
  projectId,
  filteredGraph,
  highlightedIds = [],
  loading = false,
  nodeLoading = {},
  filters,
  searchKeyword,
  onSearchChange,
  onFiltersChange,
  onExpandNode,
  onRefresh,
  onNodeNavigate,
}) => {
  const graphContainerRef = useRef<HTMLDivElement | null>(null);
  const graphRef = useRef<G6.Graph | null>(null);
  const nodePositionsRef = useRef<Record<string, { x: number; y: number }>>({});
  const isInitialRenderRef = useRef(true);

  const filterOptions = useMemo(
    () => [
      { label: '剧情线', value: 'plot_line' },
      { label: '章纲', value: 'chapter_outline' },
      { label: '剧情卡片', value: 'plot_card' },
    ],
    []
  );

  const handleFilterChange = (values: CheckboxValueType[]) => {
    onFiltersChange(values as LinkGraphEntityType[]);
  };

  const handleFitView = () => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.fitView(80);
    graph.zoomTo(0.8, {
      x: (graph.get('width') || 0) / 2,
      y: (graph.get('height') || 0) / 2,
    });
  };

  useEffect(() => {
    const container = graphContainerRef.current;
    if (!container || graphRef.current) return;

    const tooltip = new G6.Tooltip({
      offsetX: 12,
      offsetY: 12,
      trigger: 'mouseenter',
      itemTypes: ['node'],
      getContent: (evt) => {
        const model = evt?.item?.getModel();
        const data = model?.data as LinkGraphNode;
        const container = document.createElement('div');
        container.style.padding = '8px 12px';
        container.style.background = '#fff';
        container.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
        container.style.borderRadius = '8px';
        container.style.maxWidth = '260px';
        const title = data?.title ?? '节点';
        const description = data?.description ?? '暂无简介';
        container.innerHTML = `
          <div style="font-weight:600;margin-bottom:4px;">${title}</div>
          <div style="font-size:12px;color:#595959;white-space:pre-wrap;">${description}</div>
        `;
        return container;
      },
    });

    const graph = new G6.Graph({
      container,
      width: container.clientWidth || 800,
      height: container.clientHeight || 520,
      layout: {
        type: 'circular',
        radius: 200,
        preventOverlap: true,
        nodeSpacing: 50,
      },
      modes: {
        default: [
          {
            type: 'drag-canvas',
            shouldBegin: (evt: any) => {
              // 如果点击的是节点，不触发画布拖拽
              const item = evt.item;
              return !item || item.getType() !== 'node';
            },
          },
          {
            type: 'zoom-canvas',
            sensitivity: 2,
          },
          {
            type: 'drag-node',
            enableDelegate: false,
          },
        ],
      },
      defaultNode: {
        type: LINK_CARD_NODE_TYPE,
        size: [220, 120],
        draggable: true,
      },
      defaultEdge: {
        style: {
          stroke: '#d9d9d9',
          lineWidth: 1.5,
          opacity: 0.8,
        },
      },
      nodeStateStyles: {
        highlight: {
          shadowColor: '#fadb14',
          shadowBlur: 20,
        },
        dim: {
          opacity: 0.3,
        },
      },
      edgeStateStyles: {
        highlight: {
          stroke: '#fadb14',
          lineWidth: 2,
        },
        dim: {
          opacity: 0.2,
        },
      },
    });

    graphRef.current = graph;
    graph.addPlugin(tooltip);

    graph.on('node:click', (evt) => {
      const model = evt.item?.getModel();
      if (!model?.id) return;
      const nodeData = model.data as LinkGraphNode;
      if (nodeData?.expandable) {
        onExpandNode(model.id as string, nodeData.type);
      } else {
        onNodeNavigate?.(nodeData.type, model.id as string);
      }
    });

    graph.on('node:dblclick', (evt) => {
      const model = evt.item?.getModel();
      if (!model?.id) return;
      const nodeData = model.data as LinkGraphNode;
      onNodeNavigate?.(nodeData.type, model.id as string);
    });

    graph.on('node:mouseenter', () => {
      graph.get('canvas').get('el').style.cursor = 'grab';
    });

    graph.on('node:mouseleave', () => {
      graph.get('canvas').get('el').style.cursor = 'default';
    });

    graph.on('node:dragstart', (evt) => {
      graph.get('canvas').get('el').style.cursor = 'grabbing';
      evt.item?.toFront();
    });

    graph.on('node:drag', (evt) => {
      const { item, x, y } = evt;
      if (!item || typeof x !== 'number' || typeof y !== 'number') return;
      // 实时更新节点位置和保存状态
      const nodeId = item.getID();
      nodePositionsRef.current[nodeId] = { x, y };
      graph.updateItem(item, { x, y });
      // 固定位置防止布局重置
      const model = item.getModel();
      model.fx = x;
      model.fy = y;
    });

    graph.on('node:dragend', () => {
      graph.get('canvas').get('el').style.cursor = 'grab';
    });

    graph.on('canvas:dragstart', () => {
      graph.get('canvas').get('el').style.cursor = 'grabbing';
    });

    graph.on('canvas:dragend', () => {
      graph.get('canvas').get('el').style.cursor = 'default';
    });

    return () => {
      graph.destroy();
      graphRef.current = null;
    };
  }, [onExpandNode, onNodeNavigate]);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;

    if (!filteredGraph.nodes.length) {
      graph.clear();
      return;
    }

    const g6Nodes = filteredGraph.nodes.map((node) => {
      const savedPosition = nodePositionsRef.current[node.id];
      return {
        id: node.id,
        type: LINK_CARD_NODE_TYPE,
        data: node,
        size: [220, 120],
        // 使用保存的拖拽位置
        x: savedPosition?.x,
        y: savedPosition?.y,
        fx: savedPosition?.x,
        fy: savedPosition?.y,
      };
    });

    const g6Edges = filteredGraph.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      data: edge,
    }));

    graph.changeData({ nodes: g6Nodes, edges: g6Edges });
    
    // 只在初次渲染时自动调整视图
    if (isInitialRenderRef.current) {
      setTimeout(() => {
        graph.fitView(80);
        graph.zoomTo(0.8, {
          x: (graph.get('width') || 0) / 2,
          y: (graph.get('height') || 0) / 2,
        });
      }, 100);
      isInitialRenderRef.current = false;
    }

    const highlightSet = new Set(highlightedIds);
    if (highlightSet.size > 0) {
      graph.getNodes().forEach((nodeItem) => {
        const id = nodeItem.getID();
        if (highlightSet.has(id)) {
          graph.setItemState(nodeItem, 'highlight', true);
        } else {
          graph.setItemState(nodeItem, 'dim', true);
        }
      });

      graph.getEdges().forEach((edgeItem) => {
        const model = edgeItem.getModel();
        const sourceHighlighted = model?.source ? highlightSet.has(String(model.source)) : false;
        const targetHighlighted = model?.target ? highlightSet.has(String(model.target)) : false;
        if (sourceHighlighted || targetHighlighted) {
          graph.setItemState(edgeItem, 'highlight', true);
        } else {
          graph.setItemState(edgeItem, 'dim', true);
        }
      });
    } else {
      graph.getNodes().forEach((nodeItem) => graph.clearItemStates(nodeItem));
      graph.getEdges().forEach((edgeItem) => graph.clearItemStates(edgeItem));
    }
  }, [filteredGraph, highlightedIds]);

  const hasData = filteredGraph.nodes.length > 0;

  return (
    <Card
      title={
        <Space>
          <LinkOutlined />
          关联关系图谱
          {projectId && <Tag color="#722ed1">项目ID: {projectId.slice(0, 8)}...</Tag>}
        </Space>
      }
      extra={
        <Space size={8}>
          <Tooltip title="视图居中">
            <Button size="small" icon={<ApartmentOutlined />} onClick={handleFitView} />
          </Tooltip>
          <Tooltip title="刷新图谱">
            <Button
              size="small"
              icon={<ReloadOutlined />}
              disabled={!onRefresh}
              loading={loading}
              onClick={onRefresh}
            />
          </Tooltip>
        </Space>
      }
      styles={{ body: { padding: 16 } }}
    >
      <Space direction="vertical" size={12} style={{ width: '100%', marginBottom: 12 }}>
        <Space wrap size={12} align="center" style={{ width: '100%' }}>
          <Input
            allowClear
            value={searchKeyword}
            onChange={(e) => onSearchChange(e.target.value)}
            prefix={<SearchOutlined />}
            placeholder="搜索剧情线/章纲/剧情卡片"
            style={{ width: 260 }}
          />
          <Space size={4} align="center">
            <FilterOutlined style={{ color: '#8c8c8c' }} />
            <Checkbox.Group options={filterOptions} value={filters} onChange={handleFilterChange} />
          </Space>
          <Space size={4} wrap>
            {Object.entries(ENTITY_META).map(([type, meta]) => (
              <Tag key={type} color={meta.color} style={{ marginBottom: 0 }}>
                {meta.label}
              </Tag>
            ))}
          </Space>
        </Space>
        {Object.keys(nodeLoading || {}).filter((key) => nodeLoading[key]).length > 0 && (
          <div style={{ fontSize: 12, color: '#fa8c16' }}>
            正在加载 {Object.keys(nodeLoading || {}).filter((key) => nodeLoading[key]).length} 个节点的关联详情…
          </div>
        )}
      </Space>

      <div style={{ position: 'relative', minHeight: 520 }}>
        <div
          ref={graphContainerRef}
          style={{
            width: '100%',
            height: '520px',
            border: '1px solid #f0f0f0',
            borderRadius: 8,
            background: '#fff',
          }}
        />
        {loading && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(255,255,255,0.65)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 8,
              flexDirection: 'column',
              gap: 8,
            }}
          >
            <Spin />
            <span style={{ fontSize: 12, color: '#8c8c8c' }}>加载关联图谱中…</span>
          </div>
        )}
        {!loading && !hasData && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(255,255,255,0.92)',
              borderRadius: 8,
            }}
          >
            <Empty description="暂无关联数据，调整过滤条件重试" />
          </div>
        )}
      </div>
      <div style={{ marginTop: 12, fontSize: 12, color: '#8c8c8c' }}>
        单击节点可展开或跳转；双击节点快速进入对应管理页面；使用拖拽/滚轮进行漫游与缩放。
      </div>
    </Card>
  );
};

export default LinkVisualization;
