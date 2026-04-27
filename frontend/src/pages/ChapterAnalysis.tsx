import React, { useState, useEffect, useCallback } from 'react';
import { Card, List, Button, Space, Empty, Tag, Spin, Alert, Switch, Drawer, message, Popconfirm, Tabs, Collapse } from 'antd';
import {
  EyeOutlined,
  EyeInvisibleOutlined,
  MenuOutlined,
  LeftOutlined,
  RightOutlined,
  UnorderedListOutlined,
  DeleteOutlined,
  CopyOutlined,
} from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import api from '@/services/api';
import { chapterApi } from '@/services/api';
import { normalizeAnalysisData, type NormalizedAnalysisData } from '@/utils/chapterAnalysis';
import AnnotatedText, { type MemoryAnnotation } from '@/components/AnnotatedText';
import MemorySidebar from '@/components/MemorySidebar';
import { useChapterSync } from '@/store/hooks';

interface ChapterItem {
  id: string;
  chapter_number: number;
  title: string;
  content: string;
  word_count: number;
  status: string;
}

interface AnnotationsData {
  chapter_id: string;
  chapter_number: number;
  title: string;
  word_count: number;
  annotations: MemoryAnnotation[];
  has_analysis: boolean;
  summary: {
    total_annotations: number;
    hooks: number;
    foreshadows: number;
    plot_points: number;
    character_events: number;
  };
}

interface NavigationData {
  current: {
    id: string;
    chapter_number: number;
    title: string;
  };
  previous: {
    id: string;
    chapter_number: number;
    title: string;
  } | null;
  next: {
    id: string;
    chapter_number: number;
    title: string;
  } | null;
}

const SEV_COLOR: Record<string, string> = { critical: 'red', high: 'orange', medium: 'gold', low: 'default' }
const SEV_LABEL: Record<string, string> = { critical: '严重', high: '高', medium: '中', low: '低' }
const P_STATUS_COLOR: Record<string, string> = { open: 'blue', progressing: 'orange', resolved: 'green', broken: 'red' }
const P_STATUS_LABEL: Record<string, string> = { open: '未解', progressing: '推进中', resolved: '已回收', broken: '已破裂' }
const P_TYPE_LABEL: Record<string, string> = { foreshadow: '伏笔', promise: '承诺', mystery: '悬念', conflict: '冲突' }

function NarrativeStatePanel({ data, loading }: { data: NormalizedAnalysisData | null; loading: boolean }) {
  if (loading) return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
  if (!data) return <Empty description="暂无叙事状态数据" style={{ marginTop: 60 }} />

  const ns = data.narrative_state
  const ca = data.consistency_audit
  const promises = ns?.promises ?? []
  const timeline = ns?.timeline_events ?? []
  const relGraph = ns?.relationship_graph
  const causal = ns?.causal_links ?? []
  const issues = ca?.issues ?? []
  const summary = ca?.summary

  const sections: { key: string; label: string; badge: number; children: React.ReactNode }[] = []

  if (promises.length > 0) {
    sections.push({
      key: 'promises',
      label: '🔮 承诺 / 伏笔',
      badge: promises.length,
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {promises.map((p, i) => {
            const st = String(p.status || 'open')
            const pt = String(p.promise_type || '')
            const pr = String(p.priority || '')
            return (
              <Card key={String(p.id || i)} size="small" style={{ borderLeft: `3px solid ${st === 'resolved' ? '#52c41a' : st === 'broken' ? '#ff4d4f' : '#1890ff'}` }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 4 }}>
                  {pt && <Tag color="purple">{P_TYPE_LABEL[pt] || pt}</Tag>}
                  <Tag color={P_STATUS_COLOR[st] || 'default'}>{P_STATUS_LABEL[st] || st}</Tag>
                  {pr === 'critical' && <Tag color="red">紧急</Tag>}
                  {pr === 'high' && <Tag color="orange">高优</Tag>}
                </div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{String(p.title || '未命名')}</div>
                {Boolean(p.content) && <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>{String(p.content)}</div>}
                <div style={{ fontSize: 11, color: '#999', marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {Boolean(p.owner_character_name) && <span>发起: {String(p.owner_character_name)}</span>}
                  {Boolean(p.target_character_name) && <span>对象: {String(p.target_character_name)}</span>}
                  {p.source_chapter_number != null && <span>第{String(p.source_chapter_number)}章埋设</span>}
                  {p.resolved_chapter_number != null && <span>第{String(p.resolved_chapter_number)}章回收</span>}
                </div>
              </Card>
            )
          })}
        </div>
      ),
    })
  }

  if (timeline.length > 0) {
    sections.push({
      key: 'timeline',
      label: '⏱️ 时间轴事件',
      badge: timeline.length,
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {timeline.map((evt, i) => {
            const actors = (evt.actor_names as string[]) || []
            const targets = (evt.target_names as string[]) || []
            return (
              <Card key={String(evt.id || i)} size="small" style={{ borderLeft: '3px solid #1890ff' }}>
                <div style={{ display: 'flex', gap: 4, marginBottom: 4 }}>
                  {Boolean(evt.event_type) && <Tag color="blue">{String(evt.event_type)}</Tag>}
                  {evt.public_visibility === 'secret' && <Tag>秘密</Tag>}
                </div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{String(evt.title || '未命名事件')}</div>
                {Boolean(evt.description) && <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>{String(evt.description)}</div>}
                <div style={{ fontSize: 11, color: '#999', marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {Boolean(evt.location) && <span>📍 {String(evt.location)}</span>}
                  {Boolean(evt.time_marker) && <span>🕐 {String(evt.time_marker)}</span>}
                  {actors.length > 0 && <span>参与: {actors.join(', ')}</span>}
                  {targets.length > 0 && <span>目标: {targets.join(', ')}</span>}
                </div>
              </Card>
            )
          })}
        </div>
      ),
    })
  }

  if (relGraph && relGraph.edges.length > 0) {
    sections.push({
      key: 'relationship',
      label: '💞 关系变化',
      badge: relGraph.edges.length,
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {relGraph.edges.map((e, i) => {
            const d = Number(e.delta || 0)
            return (
              <Card key={i} size="small" style={{ borderLeft: `3px solid ${d > 0 ? '#52c41a' : d < 0 ? '#ff4d4f' : '#d9d9d9'}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
                  <span style={{ fontWeight: 600 }}>{String(e.source)}</span>
                  <span style={{ color: '#999' }}>→</span>
                  <span style={{ fontWeight: 600 }}>{String(e.target)}</span>
                  <Tag color={d > 0 ? 'green' : d < 0 ? 'red' : 'default'} style={{ marginLeft: 'auto' }}>{d > 0 ? '+' : ''}{d}</Tag>
                </div>
                <div style={{ fontSize: 11, color: '#999', marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {Boolean(e.reason) && <span>{String(e.reason)}</span>}
                  {Boolean(e.new_status) && <span>状态: {String(e.new_status)}</span>}
                </div>
              </Card>
            )
          })}
        </div>
      ),
    })
  }

  if (causal.length > 0) {
    sections.push({
      key: 'causal',
      label: '🔗 因果链',
      badge: causal.length,
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {causal.map((lk, i) => (
            <Card key={i} size="small" style={{ borderLeft: '3px solid #faad14' }}>
              <div style={{ display: 'flex', gap: 4, marginBottom: 4 }}>
                <Tag color="gold">重要度 {Number(lk.importance || 0)}</Tag>
                {Boolean(lk.reversible) && <Tag color="green">可逆</Tag>}
              </div>
              <div style={{ fontSize: 12, lineHeight: 1.8 }}>
                {Boolean(lk.cause) && <div><b>起因：</b>{String(lk.cause)}</div>}
                {Boolean(lk.event) && <div><b>事件：</b>{String(lk.event)}</div>}
                {Boolean(lk.decision) && <div><b>决策：</b>{String(lk.decision)}</div>}
                {Boolean(lk.effect) && <div><b>影响：</b>{String(lk.effect)}</div>}
              </div>
            </Card>
          ))}
        </div>
      ),
    })
  }

  if (summary && summary.total > 0) {
    sections.push({
      key: 'audit',
      label: '🛡️ 一致性审计',
      badge: summary.total,
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {summary.critical > 0 && <Tag color="red">严重 {summary.critical}</Tag>}
            {summary.high > 0 && <Tag color="orange">高 {summary.high}</Tag>}
            {summary.medium > 0 && <Tag color="gold">中 {summary.medium}</Tag>}
            {summary.low > 0 && <Tag>低 {summary.low}</Tag>}
          </div>
          {issues.map((iss, i) => {
            const sev = String(iss.severity || 'medium')
            return (
              <Card key={i} size="small" style={{ borderLeft: `3px solid ${sev === 'critical' ? '#ff4d4f' : sev === 'high' ? '#fa8c16' : sev === 'medium' ? '#fadb14' : '#d9d9d9'}` }}>
                <div style={{ display: 'flex', gap: 4, marginBottom: 4 }}>
                  <Tag color={SEV_COLOR[sev] || 'default'}>{SEV_LABEL[sev] || sev}</Tag>
                  {Boolean(iss.issue_type) && <Tag>{String(iss.issue_type)}</Tag>}
                </div>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{String(iss.title || '未命名问题')}</div>
                {Boolean(iss.details) && <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>{String(iss.details)}</div>}
                <div style={{ fontSize: 11, color: '#999', marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {Boolean(iss.character_name) && <span>角色: {String(iss.character_name)}</span>}
                  {iss.reference_chapter_number != null && <span>参考: 第{String(iss.reference_chapter_number)}章</span>}
                </div>
              </Card>
            )
          })}
        </div>
      ),
    })
  }

  if (sections.length === 0) {
    return <Empty description="本章暂无叙事状态数据" style={{ marginTop: 60 }} />
  }

  return (
    <div style={{ padding: 12 }}>
      <Collapse
        defaultActiveKey={sections.map(s => s.key)}
        ghost
        items={sections.map(s => ({
          key: s.key,
          label: (
            <span style={{ fontWeight: 600, fontSize: 13 }}>
              {s.label} <Tag style={{ marginLeft: 4 }}>{s.badge}</Tag>
            </span>
          ),
          children: s.children,
        }))}
      />
    </div>
  )
}

/**
 * 项目内的章节剧情分析页面
 * 显示章节列表和带标注的章节内容
 */
const ChapterAnalysis: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const { deleteChapter } = useChapterSync();
  
  const [chapters, setChapters] = useState<ChapterItem[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<ChapterItem | null>(null);
  const [annotationsData, setAnnotationsData] = useState<AnnotationsData | null>(null);
  const [navigation, setNavigation] = useState<NavigationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [contentLoading, setContentLoading] = useState(false);
  const [showAnnotations, setShowAnnotations] = useState(true);
  const [activeAnnotationId, setActiveAnnotationId] = useState<string | undefined>();
  const [sidebarVisible, setSidebarVisible] = useState(false);
  const [chapterListVisible, setChapterListVisible] = useState(false);
  const [scrollToContentAnnotation, setScrollToContentAnnotation] = useState<string | undefined>();
  const [scrollToSidebarAnnotation, setScrollToSidebarAnnotation] = useState<string | undefined>();
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [narrativeData, setNarrativeData] = useState<NormalizedAnalysisData | null>(null);
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const [sidebarTab, setSidebarTab] = useState<string>('memory');

  // 监听窗口大小变化
  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < 768);
    };
    
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // 加载章节内容和标注
  const loadChapterContent = useCallback(async (chapterId: string) => {
    try {
      setContentLoading(true);

      const [chapterResponse, annotationsResponse, navigationResponse] = await Promise.all([
        api.get(`/chapters/${chapterId}`),
        api.get(`/chapters/${chapterId}/annotations`).catch(() => null),
        api.get(`/chapters/${chapterId}/navigation`).catch(() => null),
      ]);

      // 同时加载叙事状态
      setNarrativeLoading(true);
      chapterApi.getAnalysis(chapterId)
        .then((data) => setNarrativeData(normalizeAnalysisData(data as unknown as Record<string, unknown>)))
        .catch(() => setNarrativeData(null))
        .finally(() => setNarrativeLoading(false));

      // 提取 data 属性
      setSelectedChapter(chapterResponse.data || chapterResponse);
      setAnnotationsData(annotationsResponse ? (annotationsResponse.data || annotationsResponse) : null);
      setNavigation(navigationResponse ? (navigationResponse.data || navigationResponse) : null);
    } catch (error) {
      console.error('加载章节内容失败:', error);
      message.error('加载章节内容失败');
    } finally {
      setContentLoading(false);
    }
  }, []);

  // 加载章节列表
  useEffect(() => {
    const loadChapters = async () => {
      if (!projectId) return;

      try {
        setLoading(true);
        const response = await api.get(`/chapters/project/${projectId}`);
        // API 拦截器已经解析了 response.data，所以直接使用
        const data = response.data || response;
        const chapterList = data.items || [];
        setChapters(chapterList);

        // 自动选择第一个有内容的章节
        const firstChapterWithContent = chapterList.find((ch: ChapterItem) => ch.content && ch.content.trim() !== '');
        if (firstChapterWithContent) {
          loadChapterContent(firstChapterWithContent.id);
        }
      } catch (error) {
        console.error('加载章节列表失败:', error);
        message.error('加载章节列表失败');
      } finally {
        setLoading(false);
      }
    };

    loadChapters();
  }, [projectId, loadChapterContent]);

  const handleChapterSelect = (chapterId: string) => {
    loadChapterContent(chapterId);
    if (isMobile) {
      setChapterListVisible(false);
    }
  };

  const handleDeleteChapter = async (chapterId: string, chapterTitle: string) => {
    try {
      await deleteChapter(chapterId);
      
      // 从本地状态中移除已删除的章节
      setChapters(prev => prev.filter(ch => ch.id !== chapterId));
      
      // 如果删除的是当前选中的章节，清空选中状态
      if (selectedChapter?.id === chapterId) {
        setSelectedChapter(null);
        setAnnotationsData(null);
        setNavigation(null);
      }
      
      message.success(`章节《${chapterTitle}》删除成功`);
    } catch (error) {
      console.error('删除章节失败:', error);
      message.error('删除章节失败');
    }
  };

  const handlePreviousChapter = () => {
    if (navigation?.previous) {
      loadChapterContent(navigation.previous.id);
    }
  };

  const handleNextChapter = () => {
    if (navigation?.next) {
      loadChapterContent(navigation.next.id);
    }
  };

  // 复制章节标题
  const handleCopyTitle = async () => {
    if (!selectedChapter) {
      message.warning('请先选择一个章节');
      return;
    }

    const titleText = `第${selectedChapter.chapter_number}章: ${selectedChapter.title}`;

    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(titleText);
        message.success('章节标题已复制到剪贴板');
        return;
      }

      const textarea = document.createElement('textarea');
      textarea.value = titleText;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      const successful = document.execCommand('copy');
      document.body.removeChild(textarea);

      if (successful) {
        message.success('章节标题已复制到剪贴板');
      } else {
        message.error('复制失败，请稍后重试');
      }
    } catch (error) {
      console.error('复制章节标题失败:', error);
      message.error('复制失败，请稍后重试');
    }
  };

  // 复制章节内容
  const handleCopyContent = async () => {
    if (!selectedChapter?.content) {
      message.warning('当前章节没有可复制的内容');
      return;
    }

    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(selectedChapter.content);
        message.success('章节内容已复制到剪贴板');
        return;
      }

      const textarea = document.createElement('textarea');
      textarea.value = selectedChapter.content;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      const successful = document.execCommand('copy');
      document.body.removeChild(textarea);

      if (successful) {
        message.success('章节内容已复制到剪贴板');
      } else {
        message.error('复制失败，请稍后重试');
      }
    } catch (error) {
      console.error('复制章节内容失败:', error);
      message.error('复制失败，请稍后重试');
    }
  };

  const handleAnnotationClick = (annotation: MemoryAnnotation, source: 'content' | 'sidebar' = 'content') => {
    setActiveAnnotationId(annotation.id);
    
    if (source === 'content') {
      // 从内容区点击，滚动到侧边栏
      setScrollToSidebarAnnotation(annotation.id);
      // 清除滚动状态
      setTimeout(() => setScrollToSidebarAnnotation(undefined), 100);
      
      if (isMobile) {
        setSidebarVisible(true);
      }
    } else {
      // 从侧边栏点击，滚动到内容区
      setScrollToContentAnnotation(annotation.id);
      // 清除滚动状态
      setTimeout(() => setScrollToContentAnnotation(undefined), 100);
    }
  };

  const hasAnnotations = annotationsData && annotationsData.annotations.length > 0;

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" tip="加载章节中...">
          <div style={{ minHeight: 100 }} />
        </Spin>
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      height: '100%',
      gap: isMobile ? 0 : 16,
      flexDirection: isMobile ? 'column' : 'row'
    }}>
      {/* 左侧章节列表 - 桌面端 */}
      {!isMobile && (
        <Card
          title="章节列表"
          style={{ width: 280, height: '100%', overflow: 'hidden' }}
          styles={{ body: { padding: 0, height: 'calc(100% - 57px)', overflow: 'auto' } }}
        >
          {chapters.length === 0 ? (
            <Empty description="暂无章节" style={{ marginTop: 60 }} />
          ) : (
            <List
              dataSource={chapters}
              renderItem={(chapter) => (
                <List.Item
                  key={chapter.id}
                  onClick={() => handleChapterSelect(chapter.id)}
                  style={{
                    cursor: 'pointer',
                    padding: '12px 16px',
                    background: selectedChapter?.id === chapter.id ? '#e6f7ff' : 'transparent',
                    borderLeft: selectedChapter?.id === chapter.id ? '3px solid #1890ff' : '3px solid transparent',
                  }}
                  actions={[
                    <Popconfirm
                      key="delete"
                      title="删除章节"
                      description={`确定要删除章节《${chapter.title}》吗？此操作不可恢复。`}
                      onConfirm={(e) => {
                        e?.stopPropagation();
                        handleDeleteChapter(chapter.id, chapter.title);
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button
                        type="text"
                        size="small"
                        icon={<DeleteOutlined />}
                        danger
                        onClick={(e) => e.stopPropagation()}
                        style={{ color: '#ff4d4f' }}
                      />
                    </Popconfirm>
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <span style={{ fontSize: 14, fontWeight: selectedChapter?.id === chapter.id ? 600 : 400 }}>
                        第{chapter.chapter_number}章: {chapter.title}
                      </span>
                    }
                    description={
                      <Space size={4}>
                        <Tag color={chapter.content && chapter.content.trim() !== '' ? 'success' : 'default'}>
                          {chapter.word_count || 0}字
                        </Tag>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </Card>
      )}

      {/* 移动端章节列表抽屉 */}
      {isMobile && (
        <Drawer
          title="章节列表"
          placement="left"
          onClose={() => setChapterListVisible(false)}
          open={chapterListVisible}
          width="85%"
          styles={{ body: { padding: 0 } }}
        >
          {chapters.length === 0 ? (
            <Empty description="暂无章节" style={{ marginTop: 60 }} />
          ) : (
            <List
              dataSource={chapters}
              renderItem={(chapter) => (
                <List.Item
                  key={chapter.id}
                  onClick={() => handleChapterSelect(chapter.id)}
                  style={{
                    cursor: 'pointer',
                    padding: '12px 16px',
                    background: selectedChapter?.id === chapter.id ? '#e6f7ff' : 'transparent',
                    borderLeft: selectedChapter?.id === chapter.id ? '3px solid #1890ff' : '3px solid transparent',
                  }}
                  actions={[
                    <Popconfirm
                      key="delete"
                      title="删除章节"
                      description={`确定要删除章节《${chapter.title}》吗？此操作不可恢复。`}
                      onConfirm={(e) => {
                        e?.stopPropagation();
                        handleDeleteChapter(chapter.id, chapter.title);
                      }}
                      onCancel={(e) => e?.stopPropagation()}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button
                        type="text"
                        size="small"
                        icon={<DeleteOutlined />}
                        danger
                        onClick={(e) => e.stopPropagation()}
                        style={{ color: '#ff4d4f' }}
                      />
                    </Popconfirm>
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <span style={{ fontSize: 14, fontWeight: selectedChapter?.id === chapter.id ? 600 : 400 }}>
                        第{chapter.chapter_number}章: {chapter.title}
                      </span>
                    }
                    description={
                      <Space size={4}>
                        <Tag color={chapter.content && chapter.content.trim() !== '' ? 'success' : 'default'}>
                          {chapter.word_count || 0}字
                        </Tag>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </Drawer>
      )}

      {/* 右侧内容区域 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        {!selectedChapter ? (
          <Card style={{ height: '100%' }}>
            <Empty description="请从左侧选择一个章节查看" style={{ marginTop: 100 }} />
          </Card>
        ) : (
          <>
            {/* 工具栏 */}
            <Card size="small" style={{ marginBottom: isMobile ? 8 : 16 }}>
              {isMobile ? (
                // 移动端布局：两行显示
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {/* 第一行：标题和翻页按钮 */}
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 8
                  }}>
                    <Button
                      icon={<LeftOutlined />}
                      onClick={handlePreviousChapter}
                      disabled={!navigation?.previous}
                      title={navigation?.previous ? `上一章: ${navigation.previous.title}` : '已是第一章'}
                      size="small"
                    />
                    <span style={{
                      fontSize: 14,
                      fontWeight: 600,
                      flex: 1,
                      textAlign: 'center',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      padding: '0 8px'
                    }}>
                      第{selectedChapter.chapter_number}章: {selectedChapter.title}
                    </span>
                    <Button
                      icon={<RightOutlined />}
                      onClick={handleNextChapter}
                      disabled={!navigation?.next}
                      title={navigation?.next ? `下一章: ${navigation.next.title}` : '已是最后一章'}
                      size="small"
                    />
                  </div>

                  {/* 第二行：章节、复制按钮、开关、分析按钮 */}
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 8
                  }}>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <Button
                        icon={<UnorderedListOutlined />}
                        onClick={() => setChapterListVisible(true)}
                        size="small"
                      >
                        章节
                      </Button>
                      <Button
                        icon={<CopyOutlined />}
                        onClick={handleCopyTitle}
                        size="small"
                        title="复制章节标题"
                      >
                        复制标题
                      </Button>
                      <Button
                        icon={<CopyOutlined />}
                        onClick={handleCopyContent}
                        size="small"
                        disabled={!selectedChapter?.content}
                        title="复制章节内容"
                      >
                        复制内容
                      </Button>
                    </div>

                    {hasAnnotations && (
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <Switch
                          checked={showAnnotations}
                          onChange={setShowAnnotations}
                          checkedChildren={<EyeOutlined />}
                          unCheckedChildren={<EyeInvisibleOutlined />}
                          size="small"
                          style={{
                            flexShrink: 0,
                            height: 16,
                            minHeight: 16,
                            lineHeight: '16px'
                          }}
                        />
                        <Button
                          icon={<MenuOutlined />}
                          onClick={() => setSidebarVisible(true)}
                          size="small"
                        >
                          分析
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                // 桌面端布局：保持原样
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <Space>
                    <Button
                      icon={<LeftOutlined />}
                      onClick={handlePreviousChapter}
                      disabled={!navigation?.previous}
                      title={navigation?.previous ? `上一章: ${navigation.previous.title}` : '已是第一章'}
                    >
                      上一章
                    </Button>
                    <span style={{ fontSize: 16, fontWeight: 600 }}>
                      第{selectedChapter.chapter_number}章: {selectedChapter.title}
                    </span>
                    <Button
                      icon={<RightOutlined />}
                      onClick={handleNextChapter}
                      disabled={!navigation?.next}
                      title={navigation?.next ? `下一章: ${navigation.next.title}` : '已是最后一章'}
                    >
                      下一章
                    </Button>
                  </Space>

                  <Space>
                    <Button
                      icon={<CopyOutlined />}
                      onClick={handleCopyTitle}
                      title="复制章节标题"
                    >
                      复制标题
                    </Button>
                    <Button
                      icon={<CopyOutlined />}
                      onClick={handleCopyContent}
                      disabled={!selectedChapter?.content}
                      title="复制章节内容"
                    >
                      复制内容
                    </Button>
                    {hasAnnotations && (
                      <>
                        <Switch
                          checked={showAnnotations}
                          onChange={setShowAnnotations}
                          checkedChildren={<EyeOutlined />}
                          unCheckedChildren={<EyeInvisibleOutlined />}
                        />
                        <span style={{ fontSize: 13, color: '#666' }}>显示标注</span>
                      </>
                    )}
                  </Space>
                </div>
              )}

              {hasAnnotations && annotationsData && (
                <div style={{
                  marginTop: 12,
                  fontSize: isMobile ? 11 : 12,
                  color: '#999',
                  lineHeight: 1.5
                }}>
                  共有 {annotationsData.summary.total_annotations} 个标注：
                  {annotationsData.summary.hooks > 0 && ` 🎣${annotationsData.summary.hooks}个钩子`}
                  {annotationsData.summary.foreshadows > 0 &&
                    ` 🌟${annotationsData.summary.foreshadows}个伏笔`}
                  {annotationsData.summary.plot_points > 0 &&
                    ` 💎${annotationsData.summary.plot_points}个情节点`}
                  {annotationsData.summary.character_events > 0 &&
                    ` 👤${annotationsData.summary.character_events}个角色事件`}
                </div>
              )}
            </Card>

            {/* 内容区域 */}
            <div style={{
              flex: 1,
              display: 'flex',
              gap: isMobile ? 0 : 16,
              overflow: 'hidden'
            }}>
              {/* 章节内容 */}
              <Card
                style={{ flex: 1, overflow: 'auto' }}
                styles={{ body: { padding: isMobile ? '12px' : '24px' } }}
                loading={contentLoading}
              >
                {!contentLoading && (
                  <>
                    {!hasAnnotations && (
                      <Alert
                        message="暂无分析数据"
                        description="该章节尚未进行AI分析，无法显示记忆标注。"
                        type="info"
                        showIcon
                        style={{ marginBottom: 24 }}
                      />
                    )}

                    {showAnnotations && hasAnnotations && annotationsData ? (
                      <AnnotatedText
                        content={selectedChapter.content}
                        annotations={annotationsData.annotations}
                        onAnnotationClick={(annotation) => handleAnnotationClick(annotation, 'content')}
                        activeAnnotationId={activeAnnotationId}
                        scrollToAnnotation={scrollToContentAnnotation}
                        style={{
                          lineHeight: isMobile ? 1.8 : 2,
                          fontSize: isMobile ? 14 : 16,
                        }}
                      />
                    ) : (
                      <div
                        style={{
                          lineHeight: isMobile ? 1.8 : 2,
                          fontSize: isMobile ? 14 : 16,
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                        }}
                      >
                        {selectedChapter.content}
                      </div>
                    )}
                  </>
                )}
              </Card>

              {/* 右侧侧边栏（桌面端）：记忆标注 + 叙事状态 */}
              {!isMobile && (
                <Card
                  style={{ width: 420, overflow: 'auto' }}
                  styles={{ body: { padding: 0 } }}
                >
                  <Tabs
                    activeKey={sidebarTab}
                    onChange={setSidebarTab}
                    centered
                    size="small"
                    style={{ height: '100%' }}
                    items={[
                      {
                        key: 'memory',
                        label: '记忆标注',
                        children: hasAnnotations && annotationsData ? (
                          <MemorySidebar
                            annotations={annotationsData.annotations}
                            activeAnnotationId={activeAnnotationId}
                            onAnnotationClick={(annotation) => handleAnnotationClick(annotation, 'sidebar')}
                            scrollToAnnotation={scrollToSidebarAnnotation}
                          />
                        ) : (
                          <Empty description="暂无标注数据" style={{ marginTop: 60 }} />
                        ),
                      },
                      {
                        key: 'narrative',
                        label: '叙事状态',
                        children: (
                          <NarrativeStatePanel data={narrativeData} loading={narrativeLoading} />
                        ),
                      },
                    ]}
                  />
                </Card>
              )}
            </div>

            {/* 移动端抽屉 */}
            {hasAnnotations && annotationsData && (
              <Drawer
                title="章节分析"
                placement="right"
                onClose={() => setSidebarVisible(false)}
                open={sidebarVisible}
                width={isMobile ? '90%' : '80%'}
              >
                <MemorySidebar
                  annotations={annotationsData.annotations}
                  activeAnnotationId={activeAnnotationId}
                  onAnnotationClick={(annotation) => {
                    handleAnnotationClick(annotation, 'sidebar');
                    setSidebarVisible(false);
                  }}
                  scrollToAnnotation={scrollToSidebarAnnotation}
                />
              </Drawer>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default ChapterAnalysis;