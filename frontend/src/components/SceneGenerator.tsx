/**
 * 场景生成器组件 - 简化版
 * 功能：显示剧情卡片列表，点击生成按钮将内容流式输出到父组件
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Card,
  Button,
  Space,
  List,
  Typography,
  Tag,
  Alert,
  Spin,
  message,
} from 'antd';
import {
  PlayCircleOutlined,
  StopOutlined,
  RocketOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
} from '@ant-design/icons';

const { Text } = Typography;

// 剧情卡片类型
interface PlotCard {
  id: string;
  title: string;
  content?: string;
  generation_status: 'pending' | 'generating' | 'completed';
  word_count_target: number;
  generation_order: number;
}

// 组件属性
interface SceneGeneratorProps {
  chapterOutlineId: string;
  chapterTitle: string;
  targetWordCount?: number;
  writingStyleId?: number;
  // 当前编辑器中的内容（用户可能已修改）
  currentEditorContent?: string;
  // 已生成到第几个场景的索引（0表示没有生成，1表示第一个已生成）
  generatedIndex?: number;
  // 流式内容回调 - 每次收到内容块时调用
  onContentStream?: (chunk: string) => void;
  // 单个场景生成完成回调
  onSceneComplete?: (content: string, wordCount: number) => void;
  // 所有场景生成完成回调
  onAllComplete?: () => void;
  // 取消回调
  onCancel?: () => void;
  // 重新生成回调 - 从指定索引开始重新生成，需要清空该索引及之后的内容
  onRegenerateFrom?: (index: number) => void;
}

const SceneGenerator: React.FC<SceneGeneratorProps> = ({
  chapterOutlineId,
  chapterTitle,
  writingStyleId,
  currentEditorContent,
  generatedIndex = 0,
  onContentStream,
  onSceneComplete,
  onAllComplete,
  onCancel,
  onRegenerateFrom,
}) => {
  const [plotCards, setPlotCards] = useState<PlotCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentCardId, setCurrentCardId] = useState<string | null>(null);
  const [isBatchGenerating, setIsBatchGenerating] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);
  const stopBatchRef = useRef(false);

  // 组件挂载时自动获取剧情卡片
  useEffect(() => {
    loadPlotCards();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterOutlineId]);

  // 获取章纲关联的剧情卡片
  const loadPlotCards = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/scene-generation/chapter-outlines/${chapterOutlineId}/plot-cards`,
        { credentials: 'include' }
      );
      if (!response.ok) {
        throw new Error('获取剧情卡片失败');
      }
      const data = await response.json();
      // 根据 generatedIndex 设置卡片状态
      const cards = (data.plot_cards || []).map((card: PlotCard, index: number) => ({
        ...card,
        generation_status: index < generatedIndex ? 'completed' as const : 'pending' as const
      }));
      setPlotCards(cards);

      if (cards.length === 0) {
        setError('该章纲没有关联的剧情卡片，请先在章纲管理中添加剧情卡片');
      }
    } catch (err: any) {
      setError(err.message || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  // 生成单个场景
  const generateScene = useCallback(async (cardId: string) => {
    setIsGenerating(true);
    setCurrentCardId(cardId);

    // 更新卡片状态
    setPlotCards(prev => prev.map(card =>
      card.id === cardId ? { ...card, generation_status: 'generating' } : card
    ));

    let sceneContent = '';

    try {
      abortControllerRef.current = new AbortController();

      const response = await fetch(
        `/api/scene-generation/generate-scene-stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chapter_outline_id: chapterOutlineId,
            plot_card_id: cardId,
            writing_style_id: writingStyleId ? String(writingStyleId) : undefined,
            previous_generated_content: currentEditorContent || undefined,
          }),
          signal: abortControllerRef.current.signal,
          credentials: 'include',
        }
      );

      if (!response.ok) {
        throw new Error('生成请求失败');
      }

      const reader = response.body?.getReader();
      readerRef.current = reader || null;
      const decoder = new TextDecoder();

      while (reader) {
        if (abortControllerRef.current?.signal.aborted) {
          await reader.cancel();
          break;
        }

        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.content) {
                sceneContent += data.content;
                // 流式输出到父组件
                onContentStream?.(data.content);
              }
              if (data.error) {
                throw new Error(data.error);
              }
            } catch (e) {
              // 忽略解析错误
            }
          }
        }
      }

      // 如果被中断，恢复状态
      if (abortControllerRef.current?.signal.aborted) {
        setPlotCards(prev => prev.map(card =>
          card.id === cardId ? { ...card, generation_status: 'pending' } : card
        ));
        return;
      }

      // 更新卡片状态为完成
      setPlotCards(prev => prev.map(card =>
        card.id === cardId ? { ...card, generation_status: 'completed' } : card
      ));

      // 通知父组件场景生成完成
      onSceneComplete?.(sceneContent, sceneContent.length);
      message.success('场景生成完成');

    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setPlotCards(prev => prev.map(card =>
          card.id === cardId ? { ...card, generation_status: 'pending' } : card
        ));
        message.error('生成失败: ' + (err.message || '未知错误'));
      }
    } finally {
      setIsGenerating(false);
      setCurrentCardId(null);
      abortControllerRef.current = null;
    }
  }, [chapterOutlineId, writingStyleId, currentEditorContent, onContentStream, onSceneComplete]);

  // 停止生成
  const stopGeneration = useCallback(() => {
    // 先取消 reader，立即停止读取流
    if (readerRef.current) {
      readerRef.current.cancel().catch(() => {});
      readerRef.current = null;
    }
    // 再中断 fetch 请求
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsGenerating(false);
    // 将当前正在生成的卡片状态重置为 pending
    if (currentCardId) {
      setPlotCards(prev => prev.map(card =>
        card.id === currentCardId ? { ...card, generation_status: 'pending' } : card
      ));
    }
    setCurrentCardId(null);
    message.info('已停止生成');
    // 同时停止批量生成
    stopBatchRef.current = true;
    setIsBatchGenerating(false);
  }, [currentCardId]);

  // 一键生成全部场景
  const generateAllScenes = useCallback(async () => {
    // 获取所有待生成的卡片
    const pendingCards = plotCards.filter(c => c.generation_status === 'pending');
    if (pendingCards.length === 0) {
      message.info('没有待生成的场景');
      return;
    }

    setIsBatchGenerating(true);
    stopBatchRef.current = false;

    for (const card of pendingCards) {
      // 检查是否被用户停止
      if (stopBatchRef.current) {
        message.info('已停止批量生成');
        break;
      }

      // 生成当前场景
      await generateScene(card.id);

      // 等待一小段时间，确保状态更新
      await new Promise(resolve => setTimeout(resolve, 500));

      // 再次检查是否被停止
      if (stopBatchRef.current) {
        break;
      }
    }

    setIsBatchGenerating(false);

    // 如果全部完成，通知父组件
    if (!stopBatchRef.current) {
      onAllComplete?.();
    }
  }, [plotCards, generateScene, onAllComplete]);

  // 检查是否所有场景都已完成
  const allCompleted = plotCards.length > 0 && plotCards.every(c => c.generation_status === 'completed');
  const completedCount = plotCards.filter(c => c.generation_status === 'completed').length;

  // 获取状态标签
  const getStatusTag = (status: string) => {
    switch (status) {
      case 'pending':
        return <Tag>待生成</Tag>;
      case 'generating':
        return <Tag color="processing">生成中</Tag>;
      case 'completed':
        return <Tag color="success">已完成</Tag>;
      default:
        return <Tag>{status}</Tag>;
    }
  };

  if (loading) {
    return (
      <Card>
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin tip="加载剧情卡片中..." />
        </div>
      </Card>
    );
  }

  return (
    <Card
      title={
        <Space>
          <RocketOutlined />
          <span>场景生成器 - {chapterTitle}</span>
        </Space>
      }
      extra={
        <Space>
          <Text type="secondary">
            进度: {completedCount}/{plotCards.length}
          </Text>
          <Button onClick={onCancel}>关闭</Button>
        </Space>
      }
    >
      {error && (
        <Alert message={error} type="error" showIcon style={{ marginBottom: 16 }} />
      )}

      {plotCards.length > 0 && (
        <>
          <Alert
            message="点击剧情卡片的「生成」按钮，内容将直接显示在章节内容文本框中"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />

          {/* 一键生成全部按钮 */}
          <div style={{ marginBottom: 16, textAlign: 'center' }}>
            {isBatchGenerating ? (
              <Button
                type="primary"
                danger
                icon={<StopOutlined />}
                onClick={stopGeneration}
                size="large"
              >
                停止批量生成
              </Button>
            ) : (
              <Button
                type="primary"
                icon={<RocketOutlined />}
                onClick={generateAllScenes}
                disabled={isGenerating || plotCards.every(c => c.generation_status === 'completed')}
                size="large"
              >
                一键生成全部场景 ({plotCards.filter(c => c.generation_status === 'pending').length} 个待生成)
              </Button>
            )}
          </div>

          <List
            dataSource={plotCards}
            renderItem={(card, index) => (
              <List.Item
                key={card.id}
                style={{
                  background: currentCardId === card.id ? '#f0f5ff' : undefined,
                  padding: '12px',
                  borderRadius: '4px',
                  marginBottom: '8px',
                  border: '1px solid #f0f0f0',
                }}
                actions={[
                  card.generation_status === 'pending' && !isGenerating && (
                    <Button
                      type="primary"
                      size="small"
                      icon={<PlayCircleOutlined />}
                      onClick={() => generateScene(card.id)}
                    >
                      生成
                    </Button>
                  ),
                  card.generation_status === 'generating' && (
                    <Button
                      danger
                      size="small"
                      icon={<StopOutlined />}
                      onClick={stopGeneration}
                    >
                      停止
                    </Button>
                  ),
                  card.generation_status === 'completed' && !isGenerating && (
                    <Space>
                      <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 20 }} />
                      <Button
                        size="small"
                        icon={<ReloadOutlined />}
                        onClick={() => {
                          // 先通知父组件清空内容
                          onRegenerateFrom?.(index);
                          // 将当前及之后的卡片状态重置为 pending
                          setPlotCards(prev => prev.map((c, i) =>
                            i >= index ? { ...c, generation_status: 'pending' as const } : c
                          ));
                          // 延迟一点后自动开始生成当前场景
                          setTimeout(() => {
                            generateScene(card.id);
                          }, 100);
                        }}
                        title="重新生成此场景及之后的内容"
                      >
                        重新生成
                      </Button>
                    </Space>
                  ),
                  card.generation_status === 'completed' && isGenerating && (
                    <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 20 }} />
                  ),
                ].filter(Boolean)}
              >
                <List.Item.Meta
                  title={
                    <Space>
                      <Text strong>{card.title}</Text>
                      {getStatusTag(card.generation_status)}
                      <Text type="secondary">目标: {card.word_count_target}字</Text>
                    </Space>
                  }
                  description={
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {card.content}
                    </Text>
                  }
                />
              </List.Item>
            )}
          />

          {allCompleted && (
            <div style={{ textAlign: 'center', marginTop: 16 }}>
              <Button type="primary" onClick={onAllComplete}>
                全部生成完成，关闭窗口
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  );
};

export default SceneGenerator;

