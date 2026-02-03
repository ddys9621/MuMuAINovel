import { useState, useEffect, useRef } from 'react';
import { Modal, Progress, Spin, Alert, Tabs, Card, Tag, List, Empty, Statistic, Row, Col, Button } from 'antd';
import {
  ThunderboltOutlined,
  BulbOutlined,
  FireOutlined,
  HeartOutlined,
  TeamOutlined,
  TrophyOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  ReloadOutlined,
  EditOutlined
} from '@ant-design/icons';
import type { AnalysisTask, ChapterAnalysisResponse } from '../types';
import ChapterRegenerationModal from './ChapterRegenerationModal';
import ChapterContentComparison from './ChapterContentComparison';

// 判断是否为移动设备
const isMobileDevice = () => window.innerWidth < 768;

interface ChapterAnalysisProps {
  chapterId: string;
  visible: boolean;
  onClose: () => void;
}

export default function ChapterAnalysis({ chapterId, visible, onClose }: ChapterAnalysisProps) {
  const [task, setTask] = useState<AnalysisTask | null>(null);
  const [analysis, setAnalysis] = useState<ChapterAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(isMobileDevice());
  const [regenerationModalVisible, setRegenerationModalVisible] = useState(false);
  const [comparisonModalVisible, setComparisonModalVisible] = useState(false);
  const [chapterInfo, setChapterInfo] = useState<{ title: string; chapter_number: number; content: string } | null>(null);
  const [newGeneratedContent, setNewGeneratedContent] = useState('');
  const [newContentWordCount, setNewContentWordCount] = useState(0);

  // 用于保存轮询定时器的引用，防止内存泄漏
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 用于标记组件是否已卸载，防止更新已卸载组件的状态
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;

    if (visible && chapterId) {
      fetchAnalysisStatus();
    }

    // 监听窗口大小变化
    const handleResize = () => {
      if (isMountedRef.current) {
        setIsMobile(isMobileDevice());
      }
    };

    window.addEventListener('resize', handleResize);

    // 清理函数：组件卸载或关闭时清除轮询
    return () => {
      isMountedRef.current = false;
      window.removeEventListener('resize', handleResize);
      // 清除轮询定时器
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
      // 清除超时定时器
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
        pollTimeoutRef.current = null;
      }
    };
  }, [visible, chapterId]);

  const fetchAnalysisStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // 同时获取章节信息
      const chapterResponse = await fetch(`/api/chapters/${chapterId}`);
      if (chapterResponse.ok) {
        const chapterData = await chapterResponse.json();
        setChapterInfo({
          title: chapterData.title,
          chapter_number: chapterData.chapter_number,
          content: chapterData.content || ''
        });
      }
      
      const response = await fetch(`/api/chapters/${chapterId}/analysis/status`);
      
      if (response.status === 404) {
        setTask(null);
        setError('该章节还未进行分析');
        return;
      }
      
      if (!response.ok) {
        throw new Error('获取分析状态失败');
      }
      
      const taskData: AnalysisTask = await response.json();
      
      // 如果状态为 none（无任务），设置 task 为 null，让前端显示"开始分析"按钮
      if (taskData.status === 'none' || !taskData.has_task) {
        setTask(null);
        setError(null); // 清除错误，这不是错误状态
        return;
      }
      
      setTask(taskData);
      
      if (taskData.status === 'completed') {
        await fetchAnalysisResult();
      } else if (taskData.status === 'running' || taskData.status === 'pending') {
        // 开始轮询
        startPolling();
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const fetchAnalysisResult = async () => {
    try {
      const response = await fetch(`/api/chapters/${chapterId}/analysis`);
      if (!response.ok) {
        throw new Error('获取分析结果失败');
      }
      const data: ChapterAnalysisResponse = await response.json();
      setAnalysis(data);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const startPolling = () => {
    // 先清理之前可能存在的轮询
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
    }

    pollIntervalRef.current = setInterval(async () => {
      // 检查组件是否已卸载
      if (!isMountedRef.current) {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        return;
      }

      try {
        const response = await fetch(`/api/chapters/${chapterId}/analysis/status`);
        if (!response.ok || !isMountedRef.current) return;

        const taskData: AnalysisTask = await response.json();

        if (isMountedRef.current) {
          setTask(taskData);
        }

        if (taskData.status === 'completed') {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          if (isMountedRef.current) {
            await fetchAnalysisResult();
          }
        } else if (taskData.status === 'failed') {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
          if (isMountedRef.current) {
            setError(taskData.error_message || '分析失败');
          }
        }
      } catch (err) {
        console.error('轮询错误:', err);
      }
    }, 2000);

    // 5分钟超时
    pollTimeoutRef.current = setTimeout(() => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    }, 300000);
  };

  const triggerAnalysis = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`/api/chapters/${chapterId}/analyze`, {
        method: 'POST'
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '触发分析失败');
      }
      
      // 触发成功后立即关闭Modal，让父组件的状态管理接管
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };


  const renderStatusIcon = () => {
    if (!task) return null;
    
    switch (task.status) {
      case 'pending':
        return <ClockCircleOutlined style={{ color: '#faad14' }} />;
      case 'running':
        return <Spin />;
      case 'completed':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'failed':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return null;
    }
  };

  const renderProgress = () => {
    if (!task || task.status === 'completed') return null;
    
    return (
      <div style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
          {renderStatusIcon()}
          <span style={{ marginLeft: 8, fontSize: 16 }}>
            {task.status === 'pending' && '等待分析...'}
            {task.status === 'running' && 'AI正在分析中...'}
            {task.status === 'failed' && '分析失败'}
          </span>
        </div>
        <Progress 
          percent={task.progress} 
          status={task.status === 'failed' ? 'exception' : 'active'}
        />
        {task.status === 'failed' && task.error_message && (
          <Alert 
            message="分析失败" 
            description={task.error_message} 
            type="error" 
            showIcon 
            style={{ marginTop: 16 }}
          />
        )}
      </div>
    );
  };

  // 将分析建议转换为重新生成组件需要的格式
  const convertSuggestionsForRegeneration = () => {
    if (!analysis?.analysis?.suggestions) return [];
    
    return analysis.analysis.suggestions.map((suggestion, index) => ({
      category: '改进建议',
      content: suggestion,
      priority: index < 3 ? 'high' : 'medium'
    }));
  };

  const renderAnalysisResult = () => {
    if (!analysis) return null;
    
    const { analysis: analysis_data, memories } = analysis;
    
    return (
      <Tabs
        defaultActiveKey="overview"
        style={{ height: '100%' }}
        items={[
          {
            key: 'overview',
            label: '概览',
            icon: <TrophyOutlined />,
            children: (
              <div style={{ height: isMobile ? 'calc(80vh - 180px)' : 'calc(90vh - 220px)', overflowY: 'auto', paddingRight: '8px' }}>
                {/* 根据建议重新生成按钮 */}
                {analysis_data.suggestions && analysis_data.suggestions.length > 0 && (
                  <Alert
                    message="发现改进建议"
                    description={
                      <div>
                        <p style={{ marginBottom: 12 }}>AI已分析出 {analysis_data.suggestions.length} 条改进建议，您可以根据这些建议重新生成章节内容。</p>
                        <Button
                          type="primary"
                          icon={<EditOutlined />}
                          onClick={() => setRegenerationModalVisible(true)}
                          size={isMobile ? 'small' : 'middle'}
                        >
                          根据建议重新生成
                        </Button>
                      </div>
                    }
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                )}
                
                <Card title="整体评分" style={{ marginBottom: 16 }} size={isMobile ? 'small' : 'default'}>
                  <Row gutter={isMobile ? 8 : 16}>
                    <Col span={isMobile ? 12 : 6}>
                      <Statistic
                        title="整体质量"
                        value={analysis_data.overall_quality_score || 0}
                        suffix="/ 10"
                        valueStyle={{ color: '#3f8600' }}
                      />
                    </Col>
                    <Col span={isMobile ? 12 : 6}>
                      <Statistic
                        title="节奏把控"
                        value={analysis_data.pacing_score || 0}
                        suffix="/ 10"
                      />
                    </Col>
                    <Col span={isMobile ? 12 : 6}>
                      <Statistic
                        title="吸引力"
                        value={analysis_data.engagement_score || 0}
                        suffix="/ 10"
                      />
                    </Col>
                    <Col span={isMobile ? 12 : 6}>
                      <Statistic
                        title="连贯性"
                        value={analysis_data.coherence_score || 0}
                        suffix="/ 10"
                      />
                    </Col>
                  </Row>
                </Card>
                
                {analysis_data.analysis_report && (
                  <Card title="分析摘要" style={{ marginBottom: 16 }} size={isMobile ? 'small' : 'default'}>
                    <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: isMobile ? 13 : 14 }}>
                      {analysis_data.analysis_report}
                    </pre>
                  </Card>
                )}
                
                {analysis_data.suggestions && analysis_data.suggestions.length > 0 && (
                  <Card title={<><BulbOutlined /> 改进建议</>} size={isMobile ? 'small' : 'default'}>
                    <List
                      dataSource={analysis_data.suggestions}
                      renderItem={(item, index) => (
                        <List.Item>
                          <span>{index + 1}. {item}</span>
                        </List.Item>
                      )}
                    />
                  </Card>
                )}
              </div>
            )
          },
          {
            key: 'hooks',
            label: `钩子 (${analysis_data.hooks?.length || 0})`,
            icon: <ThunderboltOutlined />,
            children: (
              <div style={{ height: isMobile ? 'calc(80vh - 180px)' : 'calc(90vh - 220px)', overflowY: 'auto', paddingRight: '8px' }}>
                <Card size={isMobile ? 'small' : 'default'}>
                {analysis_data.hooks && analysis_data.hooks.length > 0 ? (
                  <List
                    dataSource={analysis_data.hooks}
                    renderItem={(hook) => (
                      <List.Item>
                        <List.Item.Meta
                          title={
                            <div>
                              <Tag color="blue">{hook.type}</Tag>
                              <Tag color="orange">{hook.position}</Tag>
                              <Tag color="red">强度: {hook.strength}/10</Tag>
                            </div>
                          }
                          description={hook.content}
                        />
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty description="暂无钩子" />
                )}
                </Card>
              </div>
            )
          },
          {
            key: 'foreshadows',
            label: `伏笔 (${analysis_data.foreshadows?.length || 0})`,
            icon: <FireOutlined />,
            children: (
              <div style={{ height: isMobile ? 'calc(80vh - 180px)' : 'calc(90vh - 220px)', overflowY: 'auto', paddingRight: '8px' }}>
                <Card size={isMobile ? 'small' : 'default'}>
                {analysis_data.foreshadows && analysis_data.foreshadows.length > 0 ? (
                  <List
                    dataSource={analysis_data.foreshadows}
                    renderItem={(foreshadow) => (
                      <List.Item>
                        <List.Item.Meta
                          title={
                            <div>
                              <Tag color={foreshadow.type === 'planted' ? 'green' : 'purple'}>
                                {foreshadow.type === 'planted' ? '已埋下' : '已回收'}
                              </Tag>
                              <Tag>强度: {foreshadow.strength}/10</Tag>
                              <Tag>隐藏度: {foreshadow.subtlety}/10</Tag>
                              {foreshadow.reference_chapter && (
                                <Tag color="cyan">呼应第{foreshadow.reference_chapter}章</Tag>
                              )}
                            </div>
                          }
                          description={foreshadow.content}
                        />
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty description="暂无伏笔" />
                )}
                </Card>
              </div>
            )
          },
          {
            key: 'emotion',
            label: '情感曲线',
            icon: <HeartOutlined />,
            children: (
              <div style={{ height: isMobile ? 'calc(80vh - 180px)' : 'calc(90vh - 220px)', overflowY: 'auto', paddingRight: '8px' }}>
                <Card size={isMobile ? 'small' : 'default'}>
                {analysis_data.emotional_tone ? (
                  <div>
                    <Row gutter={isMobile ? 8 : 16} style={{ marginBottom: isMobile ? 16 : 24 }}>
                      <Col span={isMobile ? 24 : 12}>
                        <Statistic
                          title="主导情绪"
                          value={analysis_data.emotional_tone}
                        />
                      </Col>
                      <Col span={isMobile ? 24 : 12}>
                        <Statistic
                          title="情感强度"
                          value={(analysis_data.emotional_intensity * 10).toFixed(1)}
                          suffix="/ 10"
                        />
                      </Col>
                    </Row>
                    <Card type="inner" title="剧情阶段" size="small">
                      <p><strong>阶段：</strong>{analysis_data.plot_stage}</p>
                      <p><strong>冲突等级：</strong>{analysis_data.conflict_level} / 10</p>
                      {analysis_data.conflict_types && analysis_data.conflict_types.length > 0 && (
                        <div style={{ marginTop: 8 }}>
                          <strong>冲突类型：</strong>
                          {analysis_data.conflict_types.map((type, idx) => (
                            <Tag key={idx} color="red" style={{ margin: 4 }}>
                              {type}
                            </Tag>
                          ))}
                        </div>
                      )}
                    </Card>
                  </div>
                ) : (
                  <Empty description="暂无情感分析" />
                )}
                </Card>
              </div>
            )
          },
          {
            key: 'characters',
            label: `角色 (${analysis_data.character_states?.length || 0})`,
            icon: <TeamOutlined />,
            children: (
              <div style={{ height: isMobile ? 'calc(80vh - 180px)' : 'calc(90vh - 220px)', overflowY: 'auto', paddingRight: '8px' }}>
                <Card size={isMobile ? 'small' : 'default'}>
                {analysis_data.character_states && analysis_data.character_states.length > 0 ? (
                  <List
                    dataSource={analysis_data.character_states}
                    renderItem={(char) => (
                      <List.Item>
                        <Card 
                          type="inner" 
                          title={char.character_name}
                          size="small"
                          style={{ width: '100%' }}
                        >
                          <p><strong>状态变化：</strong>{char.state_before} → {char.state_after}</p>
                          <p><strong>心理变化：</strong>{char.psychological_change}</p>
                          <p><strong>关键事件：</strong>{char.key_event}</p>
                          {char.relationship_changes && Object.keys(char.relationship_changes).length > 0 && (
                            <div>
                              <strong>关系变化：</strong>
                              {Object.entries(char.relationship_changes).map(([name, change]) => (
                                <Tag key={name} color="blue" style={{ margin: 4 }}>
                                  与{name}: {change}
                                </Tag>
                              ))}
                            </div>
                          )}
                        </Card>
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty description="暂无角色分析" />
                )}
                </Card>
              </div>
            )
          },
          {
            key: 'memories',
            label: `记忆 (${memories?.length || 0})`,
            icon: <FireOutlined />,
            children: (
              <div style={{ height: isMobile ? 'calc(80vh - 180px)' : 'calc(90vh - 220px)', overflowY: 'auto', paddingRight: '8px' }}>
                <Card size={isMobile ? 'small' : 'default'}>
                {memories && memories.length > 0 ? (
                  <List
                    dataSource={memories}
                    renderItem={(memory) => (
                      <List.Item>
                        <List.Item.Meta
                          title={
                            <div>
                              <Tag color="blue">{memory.type}</Tag>
                              <Tag color="orange">重要性: {memory.importance.toFixed(1)}</Tag>
                              {memory.is_foreshadow === 1 && <Tag color="green">已埋下伏笔</Tag>}
                              {memory.is_foreshadow === 2 && <Tag color="purple">已回收伏笔</Tag>}
                              <span style={{ marginLeft: 8 }}>{memory.title}</span>
                            </div>
                          }
                          description={
                            <div>
                              <p>{memory.content}</p>
                              <div>
                                {memory.tags.map((tag, idx) => (
                                  <Tag key={idx} style={{ margin: 2 }}>{tag}</Tag>
                                ))}
                              </div>
                            </div>
                          }
                        />
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty description="暂无记忆片段" />
                )}
                </Card>
              </div>
            )
          }
        ]}
      />
    );
  };

  return (
    <Modal
      title="章节分析"
      open={visible}
      onCancel={onClose}
      width={isMobile ? '100%' : '90%'}
      centered={!isMobile}
      style={{
        maxWidth: isMobile ? '100%' : '1400px',
        paddingBottom: 0,
        top: isMobile ? 0 : undefined,
        margin: isMobile ? 0 : undefined,
        maxHeight: isMobile ? '100vh' : undefined
      }}
      styles={{
        body: {
          padding: isMobile ? '12px' : '24px',
          paddingBottom: 0,
          maxHeight: isMobile ? 'calc(100vh - 110px)' : undefined,
          overflowY: isMobile ? 'auto' : undefined
        }
      }}
      footer={[
        <Button key="close" onClick={onClose} size={isMobile ? 'small' : 'middle'}>
          关闭
        </Button>,
        !task && !loading && (
          <Button
            key="analyze"
            type="primary"
            icon={<ReloadOutlined />}
            onClick={triggerAnalysis}
            loading={loading}
            size={isMobile ? 'small' : 'middle'}
          >
            开始分析
          </Button>
        ),
        task && (task.status === 'failed') && (
          <Button
            key="reanalyze"
            type="primary"
            icon={<ReloadOutlined />}
            onClick={triggerAnalysis}
            loading={loading}
            danger
            size={isMobile ? 'small' : 'middle'}
          >
            重新分析
          </Button>
        ),
        task && task.status === 'completed' && (
          <Button
            key="reanalyze"
            type="default"
            icon={<ReloadOutlined />}
            onClick={triggerAnalysis}
            loading={loading}
            size={isMobile ? 'small' : 'middle'}
          >
            重新分析
          </Button>
        )
      ].filter(Boolean)}
    >
      {loading && !task && (
        <div style={{ textAlign: 'center', padding: '48px' }}>
          <Spin size="large" />
          <p style={{ marginTop: 16 }}>加载中...</p>
        </div>
      )}
      
      {error && (
        <Alert
          message="错误"
          description={error}
          type="error"
          showIcon
        />
      )}
      
      {task && task.status !== 'completed' && renderProgress()}
      {task && task.status === 'completed' && analysis && renderAnalysisResult()}
      
      {/* 重新生成Modal */}
      {chapterInfo && (
        <ChapterRegenerationModal
          visible={regenerationModalVisible}
          onCancel={() => setRegenerationModalVisible(false)}
          onSuccess={(newContent: string, wordCount: number) => {
            // 保存新生成的内容
            setNewGeneratedContent(newContent);
            setNewContentWordCount(wordCount);
            // 关闭重新生成对话框
            setRegenerationModalVisible(false);
            // 打开对比界面
            setComparisonModalVisible(true);
          }}
          chapterId={chapterId}
          chapterTitle={chapterInfo.title}
          chapterNumber={chapterInfo.chapter_number}
          suggestions={convertSuggestionsForRegeneration()}
          hasAnalysis={true}
        />
      )}
      
      {/* 内容对比组件 */}
      {chapterInfo && comparisonModalVisible && (
        <ChapterContentComparison
          visible={comparisonModalVisible}
          onClose={() => setComparisonModalVisible(false)}
          chapterId={chapterId}
          chapterTitle={chapterInfo.title}
          originalContent={chapterInfo.content}
          newContent={newGeneratedContent}
          wordCount={newContentWordCount}
          onApply={() => {
            // 应用新内容后刷新章节信息
            fetchAnalysisStatus();
          }}
          onDiscard={() => {
            // 放弃新内容，清空状态
            setNewGeneratedContent('');
            setNewContentWordCount(0);
          }}
        />
      )}
    </Modal>
  );
}