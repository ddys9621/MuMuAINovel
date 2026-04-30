import { useCallback, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  plotLineApi,
  plotLineLinkApi,
  chapterOutlineLinkApi,
  plotCardLinkApi,
} from '../services/api';
import type {
  ChapterOutline,
  ChapterOutlineWithLinks,
  LinkGraphEdge,
  LinkGraphEntityType,
  LinkGraphNode,
  LinkGraphPayload,
  PlotCard,
  PlotCardWithLinks,
  PlotLine,
  PlotLineWithLinks,
} from '../types';

interface UseLinkGraphOptions {
  initialLimit?: number;
}

interface UseLinkGraphResult {
  graph: LinkGraphPayload;
  filteredGraph: LinkGraphPayload;
  highlightedIds: string[];
  loading: boolean;
  nodeLoading: Record<string, boolean>;
  filters: LinkGraphEntityType[];
  searchKeyword: string;
  initializeGraph: (projectId: string, options?: { limit?: number }) => Promise<void>;
  expandNode: (nodeId: string, type: LinkGraphEntityType) => Promise<void>;
  setFilters: (types: LinkGraphEntityType[]) => void;
  setSearchKeyword: (keyword: string) => void;
  resetGraph: () => void;
}

type RelationMatrix = Record<LinkGraphEntityType, Record<LinkGraphEntityType, LinkGraphEdge['relation']>>;

const relationMap: RelationMatrix = {
  project: {
    project: 'project-line',
    plot_line: 'project-line',
    chapter_outline: 'project-line',
    plot_card: 'project-line',
  },
  plot_line: {
    project: 'project-line',
    plot_line: 'project-line',
    chapter_outline: 'line-outline',
    plot_card: 'line-card',
  },
  chapter_outline: {
    project: 'project-line',
    plot_line: 'outline-line',
    chapter_outline: 'project-line',
    plot_card: 'outline-card',
  },
  plot_card: {
    project: 'project-line',
    plot_line: 'card-line',
    chapter_outline: 'card-outline',
    plot_card: 'project-line',
  },
};

const buildEdgeId = (source: string, target: string, relation: LinkGraphEdge['relation']) => `${source}__${target}__${relation}`;

const truncateText = (text?: string | null, maxLength = 160) => {
  if (!text) return undefined;
  const normalized = text.trim();
  if (!normalized) return undefined;
  return normalized.length > maxLength ? `${normalized.slice(0, maxLength)}…` : normalized;
};

export function useLinkGraph(options?: UseLinkGraphOptions): UseLinkGraphResult {
  const initialLimit = options?.initialLimit ?? 30;
  const [graph, setGraph] = useState<LinkGraphPayload>({ nodes: [], edges: [] });
  const [filters, setFiltersState] = useState<LinkGraphEntityType[]>([]);
  const [searchKeyword, setSearchKeywordState] = useState('');
  const [loading, setLoading] = useState(false);
  const [nodeLoading, setNodeLoading] = useState<Record<string, boolean>>({});
  const expandedRef = useRef<Set<string>>(new Set());
  const projectIdRef = useRef<string | null>(null);

  const upsertNodes = useCallback((nodes: LinkGraphNode[]) => {
    setGraph((prev) => {
      const existing = new Map(prev.nodes.map((node) => [node.id, node]));
      nodes.forEach((node) => {
        const prevNode = existing.get(node.id);
        existing.set(node.id, { ...prevNode, ...node });
      });
      return { ...prev, nodes: Array.from(existing.values()) };
    });
  }, []);

  const upsertEdges = useCallback((edges: LinkGraphEdge[]) => {
    setGraph((prev) => {
      const existing = new Map(prev.edges.map((edge) => [edge.id, edge]));
      edges.forEach((edge) => {
        existing.set(edge.id, edge);
      });
      return { ...prev, edges: Array.from(existing.values()) };
    });
  }, []);

  const removeDescendants = useCallback((nodeId: string) => {
    setGraph((prev) => {
      const descendants = new Set<string>();
      const visited = new Set<string>();
      const traverse = (id: string) => {
        if (visited.has(id)) return;
        visited.add(id);
        prev.edges.forEach((edge) => {
          if (edge.source === id) {
            descendants.add(edge.target);
            traverse(edge.target);
          }
        });
      };
      traverse(nodeId);
      const nodes = prev.nodes.map((node) =>
        node.id === nodeId ? { ...node, expanded: false } : node
      ).filter((node) => !descendants.has(node.id));
      const edges = prev.edges.filter(
        (edge) => !descendants.has(edge.source) && !descendants.has(edge.target)
      );
      return { nodes, edges };
    });
  }, []);

  const resolveLineStats = useCallback((line: PlotLine | PlotLineWithLinks) => {
    const directChapterCount =
      'chapter_count' in line && typeof line.chapter_count === 'number'
        ? line.chapter_count
        : 'chapter_outline_count' in line && typeof line.chapter_outline_count === 'number'
          ? line.chapter_outline_count
          : undefined;
    const chapterCount =
      directChapterCount ??
      ('chapter_outlines' in line && Array.isArray(line.chapter_outlines)
        ? line.chapter_outlines.length
        : 0);

    const directCardCount =
      'card_count' in line && typeof line.card_count === 'number'
        ? line.card_count
        : 'plot_card_count' in line && typeof line.plot_card_count === 'number'
          ? line.plot_card_count
          : undefined;
    const cardCount =
      directCardCount ??
      ('plot_cards' in line && Array.isArray(line.plot_cards)
        ? line.plot_cards.length
        : 0);

    return { chapterCount, cardCount };
  }, []);

  const buildPlotLineNode = useCallback((line: PlotLine | PlotLineWithLinks): LinkGraphNode => {
    const { chapterCount, cardCount } = resolveLineStats(line);
    return {
      id: line.id,
      title: line.title,
      type: 'plot_line',
      level: 1,
      description: truncateText(line.description),
      stats: {
        chapterCount,
        plotCardCount: cardCount,
      },
      expandable: chapterCount + cardCount > 0,
    };
  }, [resolveLineStats]);

  const resolveOutlineStats = useCallback((outline: ChapterOutline | ChapterOutlineWithLinks) => {
    const directLineCount =
      'plot_line_count' in outline && typeof outline.plot_line_count === 'number'
        ? outline.plot_line_count
        : undefined;
    const plotLineCount =
      directLineCount ??
      ('plot_lines' in outline && Array.isArray(outline.plot_lines)
        ? outline.plot_lines.length
        : 0);

    const directCardCount =
      'card_count' in outline && typeof outline.card_count === 'number'
        ? outline.card_count
        : 'plot_card_count' in outline && typeof outline.plot_card_count === 'number'
          ? outline.plot_card_count
          : undefined;
    const cardCount =
      directCardCount ??
      ('plot_cards' in outline && Array.isArray(outline.plot_cards)
        ? outline.plot_cards.length
        : 0);

    return { plotLineCount, cardCount };
  }, []);

  const buildOutlineNode = useCallback((outline: ChapterOutline | ChapterOutlineWithLinks): LinkGraphNode => {
    const { plotLineCount, cardCount } = resolveOutlineStats(outline);
    return {
      id: outline.id,
      title: `第${outline.chapter_number}章：${outline.title}`,
      type: 'chapter_outline',
      level: 2,
      description: truncateText(outline.summary),
      stats: {
        plotLineCount,
        plotCardCount: cardCount,
      },
      expandable: cardCount > 0,
    };
  }, [resolveOutlineStats]);

  const resolveCardStats = useCallback((card: PlotCard | PlotCardWithLinks) => {
    const directLineCount =
      'plot_line_count' in card && typeof card.plot_line_count === 'number'
        ? card.plot_line_count
        : undefined;
    const plotLineCount =
      directLineCount ??
      ('plot_lines' in card && Array.isArray(card.plot_lines)
        ? card.plot_lines.length
        : 0);

    const directChapterCount =
      'chapter_count' in card && typeof card.chapter_count === 'number'
        ? card.chapter_count
        : 'chapter_outline_count' in card && typeof card.chapter_outline_count === 'number'
          ? card.chapter_outline_count
          : undefined;
    const chapterCount =
      directChapterCount ??
      ('chapter_outlines' in card && Array.isArray(card.chapter_outlines)
        ? card.chapter_outlines.length
        : 0);

    return { plotLineCount, chapterCount };
  }, []);

  const buildPlotCardNode = useCallback((card: PlotCard | PlotCardWithLinks): LinkGraphNode => {
    const { plotLineCount, chapterCount } = resolveCardStats(card);
    return {
      id: card.id,
      title: card.title,
      type: 'plot_card',
      level: 3,
      description: truncateText(card.content),
      stats: {
        plotLineCount,
        chapterCount,
      },
      expandable: plotLineCount + chapterCount > 0,
    };
  }, [resolveCardStats]);

  const initializeGraph = useCallback(async (projectId: string, opts?: { limit?: number }) => {
    if (!projectId) return;
    setLoading(true);
    projectIdRef.current = projectId;
    expandedRef.current = new Set();
    try {
      const limit = opts?.limit ?? initialLimit;
      const response = await plotLineApi.getPlotLines(projectId, { limit, skip: 0 });
      const projectNode: LinkGraphNode = {
        id: projectId,
        title: '项目中心',
        type: 'project',
        level: 0,
        expandable: true,
        expanded: true,
      };
      const lineNodes = response.items.map(buildPlotLineNode);
      const edges: LinkGraphEdge[] = lineNodes.map((node) => ({
        id: buildEdgeId(projectNode.id, node.id, 'project-line'),
        source: projectNode.id,
        target: node.id,
        relation: 'project-line',
        weight: (node.stats?.chapterCount ?? 0) + (node.stats?.plotCardCount ?? 0),
      }));
      setGraph({
        nodes: [projectNode, ...lineNodes],
        edges,
      });
      expandedRef.current.add(projectNode.id);
    } catch (error) {
      console.error('初始化图谱失败', error);
      toast.error('加载关联图谱失败');
    } finally {
      setLoading(false);
    }
  }, [buildPlotLineNode, initialLimit]);

  const fetchLineChildren = useCallback(async (lineId: string) => {
    const [outlines, cards] = await Promise.all([
      plotLineLinkApi.getChapterOutlines(lineId),
      plotLineLinkApi.getPlotCards(lineId),
    ]);
    return { outlines, cards };
  }, []);

  const fetchOutlineChildren = useCallback(async (outlineId: string) => {
    const [lines, cards] = await Promise.all([
      chapterOutlineLinkApi.getPlotLines(outlineId),
      chapterOutlineLinkApi.getPlotCards(outlineId),
    ]);
    return { lines, cards };
  }, []);

  const fetchCardChildren = useCallback(async (cardId: string) => {
    const [lines, outlines] = await Promise.all([
      plotCardLinkApi.getPlotLines(cardId),
      plotCardLinkApi.getChapterOutlines(cardId),
    ]);
    return { lines, outlines };
  }, []);

  const handleExpandLine = useCallback(async (nodeId: string) => {
    const { outlines, cards } = await fetchLineChildren(nodeId);
    const outlineNodes = outlines.map(buildOutlineNode);
    const cardNodes = cards.map(buildPlotCardNode);

    upsertNodes([
      ...outlineNodes,
      ...cardNodes,
      { id: nodeId, expanded: true } as LinkGraphNode,
    ]);

    const edges: LinkGraphEdge[] = [];
    outlineNodes.forEach((outline) => {
      edges.push({
        id: buildEdgeId(nodeId, outline.id, relationMap.plot_line.chapter_outline),
        source: nodeId,
        target: outline.id,
        relation: relationMap.plot_line.chapter_outline,
      });
    });
    cardNodes.forEach((card) => {
      edges.push({
        id: buildEdgeId(nodeId, card.id, relationMap.plot_line.plot_card),
        source: nodeId,
        target: card.id,
        relation: relationMap.plot_line.plot_card,
      });
    });
    upsertEdges(edges);
  }, [buildOutlineNode, buildPlotCardNode, fetchLineChildren, upsertEdges, upsertNodes]);

  const handleExpandOutline = useCallback(async (nodeId: string) => {
    const { lines, cards } = await fetchOutlineChildren(nodeId);
    const lineNodes = lines.map(buildPlotLineNode);
    const cardNodes = cards.map(buildPlotCardNode);
    upsertNodes([
      ...lineNodes,
      ...cardNodes,
      { id: nodeId, expanded: true } as LinkGraphNode,
    ]);
    const edges: LinkGraphEdge[] = [];
    lineNodes.forEach((line) => {
      edges.push({
        id: buildEdgeId(nodeId, line.id, relationMap.chapter_outline.plot_line),
        source: nodeId,
        target: line.id,
        relation: relationMap.chapter_outline.plot_line,
      });
    });
    cardNodes.forEach((card) => {
      edges.push({
        id: buildEdgeId(nodeId, card.id, relationMap.chapter_outline.plot_card),
        source: nodeId,
        target: card.id,
        relation: relationMap.chapter_outline.plot_card,
      });
    });
    upsertEdges(edges);
  }, [buildPlotCardNode, buildPlotLineNode, fetchOutlineChildren, upsertEdges, upsertNodes]);

  const handleExpandCard = useCallback(async (nodeId: string) => {
    const { lines, outlines } = await fetchCardChildren(nodeId);
    const lineNodes = lines.map(buildPlotLineNode);
    const outlineNodes = outlines.map(buildOutlineNode);
    upsertNodes([
      ...lineNodes,
      ...outlineNodes,
      { id: nodeId, expanded: true } as LinkGraphNode,
    ]);
    const edges: LinkGraphEdge[] = [];
    lineNodes.forEach((line) => {
      edges.push({
        id: buildEdgeId(nodeId, line.id, relationMap.plot_card.plot_line),
        source: nodeId,
        target: line.id,
        relation: relationMap.plot_card.plot_line,
      });
    });
    outlineNodes.forEach((outline) => {
      edges.push({
        id: buildEdgeId(nodeId, outline.id, relationMap.plot_card.chapter_outline),
        source: nodeId,
        target: outline.id,
        relation: relationMap.plot_card.chapter_outline,
      });
    });
    upsertEdges(edges);
  }, [buildOutlineNode, buildPlotLineNode, fetchCardChildren, upsertEdges, upsertNodes]);

  const expandNode = useCallback(async (nodeId: string, type: LinkGraphEntityType) => {
    if (expandedRef.current.has(nodeId)) {
      removeDescendants(nodeId);
      expandedRef.current.delete(nodeId);
      return;
    }
    if (nodeLoading[nodeId]) return;
    setNodeLoading((prev) => ({ ...prev, [nodeId]: true }));
    try {
      if (type === 'plot_line') {
        await handleExpandLine(nodeId);
      } else if (type === 'chapter_outline') {
        await handleExpandOutline(nodeId);
      } else if (type === 'plot_card') {
        await handleExpandCard(nodeId);
      }
      expandedRef.current.add(nodeId);
    } catch (error) {
      console.error('展开节点失败', error);
      toast.error('加载节点关联失败');
    } finally {
      setNodeLoading((prev) => {
        const next = { ...prev };
        delete next[nodeId];
        return next;
      });
    }
  }, [handleExpandCard, handleExpandLine, handleExpandOutline, nodeLoading, removeDescendants]);

  const filteredGraph = useMemo(() => {
    if (!filters.length && !searchKeyword) return graph;
    const keyword = searchKeyword.trim().toLowerCase();
    const allowedTypes = new Set(filters);
    const visibleNodes = graph.nodes.filter((node) => {
      const keywordMatch = keyword ? node.title.toLowerCase().includes(keyword) : true;
      const typeMatch = filters.length ? allowedTypes.has(node.type) : true;
      return keywordMatch && typeMatch;
    });
    const visibleIds = new Set(visibleNodes.map((node) => node.id));
    const edges = graph.edges.filter(
      (edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target)
    );
    return {
      nodes: visibleNodes,
      edges,
    };
  }, [filters, graph, searchKeyword]);

  const highlightedIds = useMemo(() => {
    if (!searchKeyword) return [];
    const keyword = searchKeyword.trim().toLowerCase();
    return graph.nodes
      .filter((node) => node.title.toLowerCase().includes(keyword))
      .map((node) => node.id);
  }, [graph.nodes, searchKeyword]);

  const setFilters = useCallback((types: LinkGraphEntityType[]) => {
    setFiltersState(types);
  }, []);

  const setSearchKeyword = useCallback((keyword: string) => {
    setSearchKeywordState(keyword);
  }, []);

  const resetGraph = useCallback(() => {
    setGraph({ nodes: [], edges: [] });
    setFiltersState([]);
    setSearchKeywordState('');
    expandedRef.current = new Set();
    setNodeLoading({});
  }, []);

  return {
    graph,
    filteredGraph,
    highlightedIds,
    loading,
    nodeLoading,
    filters,
    searchKeyword,
    initializeGraph,
    expandNode,
    setFilters,
    setSearchKeyword,
    resetGraph,
  };
}
