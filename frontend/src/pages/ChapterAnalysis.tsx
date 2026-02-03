import React, { useState, useEffect, useCallback } from 'react';
import { Card, List, Button, Space, Empty, Tag, Spin, Alert, Switch, Drawer, message, Popconfirm } from 'antd';
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
import api from '../services/api';
import AnnotatedText, { type MemoryAnnotation } from '../components/AnnotatedText';
import MemorySidebar from '../components/MemorySidebar';
import { useChapterSync } from '../store/hooks';

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

              {/* 右侧记忆侧边栏（桌面端） */}
              {hasAnnotations && annotationsData && !isMobile && (
                <Card
                  style={{ width: 400, overflow: 'auto' }}
                  styles={{ body: { padding: 0 } }}
                >
                  <MemorySidebar
                    annotations={annotationsData.annotations}
                    activeAnnotationId={activeAnnotationId}
                    onAnnotationClick={(annotation) => handleAnnotationClick(annotation, 'sidebar')}
                    scrollToAnnotation={scrollToSidebarAnnotation}
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