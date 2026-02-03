import React, { useState, useEffect } from 'react';
import { Card, Table, InputNumber, Button, Space, Alert, message, Tag, Progress, Tooltip } from 'antd';
import { SaveOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { chapterOutlineLinkApi } from '../services/api';
import type { PlotLineWithLinks, BeatCoverage, TimelineBeat } from '../types';

interface BeatsCoverageEditorProps {
  plotLines: PlotLineWithLinks[];
  chapterId: string;
  onSave: (linkId: string, data: { beats_covered: BeatCoverage[] }) => Promise<void>;
}

interface BeatContribution {
  total_coverage: number;
  chapters: Array<{
    chapter_id: string;
    chapter_number: number;
    chapter_title: string;
    coverage: number;
  }>;
}

const BeatsCoverageEditor: React.FC<BeatsCoverageEditorProps> = ({
  plotLines,
  chapterId,
  onSave,
}) => {
  const [coverageData, setCoverageData] = useState<Map<string, Map<number, number>>>(new Map());
  const [contributionsMap, setContributionsMap] = useState<Map<string, Record<number, BeatContribution>>>(new Map());
  const [saving, setSaving] = useState(false);
  const [loadingContributions, setLoadingContributions] = useState(false);

  // 初始化覆盖度数据
  useEffect(() => {
    const initialData = new Map<string, Map<number, number>>();

    plotLines.forEach(plotLine => {
      if (plotLine.link_id && plotLine.timeline_data?.beats) {
        const beatCoverageMap = new Map<number, number>();

        // 先初始化所有节点为0
        plotLine.timeline_data.beats.forEach(beat => {
          beatCoverageMap.set(beat.index, 0);
        });

        // 从已保存的timeline_coverage中读取覆盖度
        if (plotLine.timeline_coverage?.beats_covered) {
          plotLine.timeline_coverage.beats_covered.forEach(beatCov => {
            beatCoverageMap.set(beatCov.beat_index, beatCov.coverage);
          });
        }

        initialData.set(plotLine.link_id, beatCoverageMap);
      }
    });

    setCoverageData(initialData);
  }, [plotLines]);

  // 加载所有剧情线的贡献度分布
  useEffect(() => {
    const loadContributions = async () => {
      setLoadingContributions(true);
      const newContributionsMap = new Map<string, Record<number, BeatContribution>>();

      for (const plotLine of plotLines) {
        if (plotLine.id) {
          try {
            const contributions = await chapterOutlineLinkApi.getBeatContributions(plotLine.id);
            newContributionsMap.set(plotLine.id, contributions);
          } catch (error) {
            console.error(`加载剧情线 ${plotLine.id} 的贡献度失败:`, error);
          }
        }
      }

      setContributionsMap(newContributionsMap);
      setLoadingContributions(false);
    };

    if (plotLines.length > 0) {
      loadContributions();
    }
  }, [plotLines]);

  // 更新单个节点的贡献度
  const handleCoverageChange = (linkId: string, beatIndex: number, coverage: number | null) => {
    if (coverage === null) return;

    // 限制在0-1之间
    const validCoverage = Math.max(0, Math.min(1, coverage));

    setCoverageData(prev => {
      const newData = new Map(prev);
      const beatMap = newData.get(linkId) || new Map();
      beatMap.set(beatIndex, validCoverage);
      newData.set(linkId, beatMap);
      return newData;
    });
  };

  // 保存覆盖度数据
  const handleSave = async (linkId: string, plotLineId: string) => {
    const beatMap = coverageData.get(linkId);
    if (!beatMap) return;

    const beats_covered: BeatCoverage[] = Array.from(beatMap.entries()).map(([beat_index, coverage]) => ({
      beat_index,
      coverage,
    }));

    try {
      setSaving(true);
      await onSave(linkId, { beats_covered });
      message.success('贡献度保存成功');

      // 重新加载贡献度分布
      const contributions = await chapterOutlineLinkApi.getBeatContributions(plotLineId);
      setContributionsMap(prev => {
        const newMap = new Map(prev);
        newMap.set(plotLineId, contributions);
        return newMap;
      });
    } catch (error: any) {
      console.error('保存失败:', error);
      const errorMsg = error?.response?.data?.detail || '贡献度保存失败';
      message.error(errorMsg);
    } finally {
      setSaving(false);
    }
  };

  // 获取节点状态标签
  const getBeatStatusTag = (totalCoverage: number) => {
    if (totalCoverage >= 1.0) {
      return <Tag color="success">✅ 已完成</Tag>;
    } else if (totalCoverage > 0) {
      return <Tag color="processing">🔵 进行中 ({Math.round(totalCoverage * 100)}%)</Tag>;
    } else {
      return <Tag color="default">⚪ 未开始</Tag>;
    }
  };

  // 计算剧情线的总体进度(基于所有章纲的贡献度)
  const calculateProgress = (plotLineId: string, beats: TimelineBeat[]) => {
    const contributions = contributionsMap.get(plotLineId);
    if (!contributions || beats.length === 0) return 0;

    let totalProgress = 0;
    beats.forEach(beat => {
      const beatContribution = contributions[beat.index];
      const totalCoverage = beatContribution?.total_coverage || 0;
      // 节点完成度 = min(总贡献度, 1.0),因为可能超过100%
      const completionRate = Math.min(totalCoverage, 1.0);
      totalProgress += completionRate * beat.weight;
    });

    return Math.round(totalProgress * 100);
  };

  return (
    <div>
      {plotLines.length === 0 && (
        <Alert
          type="info"
          message="暂无关联的剧情线"
          description="请先在章纲中关联剧情线，并确保剧情线已配置时间线数据"
        />
      )}

      {plotLines.map(plotLine => {
        if (!plotLine.timeline_data?.beats || plotLine.timeline_data.beats.length === 0) {
          return (
            <Card
              key={plotLine.id}
              title={plotLine.title}
              style={{ marginBottom: 16 }}
            >
              <Alert
                type="warning"
                message="该剧情线尚未配置时间线"
                description="请先在剧情线管理页面配置时间线数据"
              />
            </Card>
          );
        }

        const beats = plotLine.timeline_data.beats;
        const linkId = plotLine.link_id!;
        const progress = calculateProgress(plotLine.id, beats);
        const contributions = contributionsMap.get(plotLine.id) || {};

        const columns = [
          {
            title: '序号',
            dataIndex: 'index',
            key: 'index',
            width: 60,
          },
          {
            title: '节点标题',
            dataIndex: 'title',
            key: 'title',
            width: 150,
          },
          {
            title: '权重',
            dataIndex: 'weight',
            key: 'weight',
            width: 80,
            render: (weight: number) => `${(weight * 100).toFixed(0)}%`,
          },
          {
            title: (
              <Space>
                本章贡献度
                <Tooltip title="本章对该节点的完成贡献度(0-100%)">
                  <InfoCircleOutlined />
                </Tooltip>
              </Space>
            ),
            key: 'current_coverage',
            width: 150,
            render: (_: any, record: TimelineBeat) => {
              const coverage = coverageData.get(linkId)?.get(record.index) || 0;
              const beatContribution = contributions[record.index];
              const otherCoverage = beatContribution ? beatContribution.total_coverage - coverage : 0;
              const maxAllowed = 1.0 - otherCoverage;

              return (
                <InputNumber
                  min={0}
                  max={maxAllowed}
                  step={0.01}
                  value={coverage}
                  onChange={(value) => handleCoverageChange(linkId, record.index, value)}
                  formatter={value => `${Math.round((value || 0) * 100)}%`}
                  parser={value => (parseFloat(value?.replace('%', '') || '0') / 100)}
                  style={{ width: 100 }}
                  status={coverage > maxAllowed ? 'error' : undefined}
                />
              );
            },
          },
          {
            title: (
              <Space>
                其他章节
                <Tooltip title="其他章节对该节点的贡献度总和">
                  <InfoCircleOutlined />
                </Tooltip>
              </Space>
            ),
            key: 'other_coverage',
            width: 200,
            render: (_: any, record: TimelineBeat) => {
              const beatContribution = contributions[record.index];
              const currentCoverage = coverageData.get(linkId)?.get(record.index) || 0;
              const otherCoverage = beatContribution ? beatContribution.total_coverage - currentCoverage : 0;

              if (!beatContribution || beatContribution.chapters.length === 0) {
                return <Tag color="default">无</Tag>;
              }

              const otherChapters = beatContribution.chapters.filter(
                ch => ch.chapter_id !== chapterId
              );

              if (otherChapters.length === 0) {
                return <Tag color="default">无</Tag>;
              }

              return (
                <Tooltip
                  title={
                    <div>
                      {otherChapters.map(ch => (
                        <div key={ch.chapter_id}>
                          第{ch.chapter_number}章: {Math.round(ch.coverage * 100)}%
                        </div>
                      ))}
                    </div>
                  }
                >
                  <Tag color="blue">{Math.round(otherCoverage * 100)}%</Tag>
                </Tooltip>
              );
            },
          },
          {
            title: '剩余可分配',
            key: 'remaining',
            width: 100,
            render: (_: any, record: TimelineBeat) => {
              const beatContribution = contributions[record.index];
              const currentCoverage = coverageData.get(linkId)?.get(record.index) || 0;
              const otherCoverage = beatContribution ? beatContribution.total_coverage - currentCoverage : 0;
              const remaining = 1.0 - otherCoverage - currentCoverage;

              return (
                <Tag color={remaining < 0 ? 'error' : remaining === 0 ? 'success' : 'default'}>
                  {Math.round(remaining * 100)}%
                </Tag>
              );
            },
          },
          {
            title: '状态',
            key: 'status',
            width: 120,
            render: (_: any, record: TimelineBeat) => {
              const beatContribution = contributions[record.index];
              const totalCoverage = beatContribution?.total_coverage || 0;
              return getBeatStatusTag(totalCoverage);
            },
          },
        ];

        return (
          <Card
            key={plotLine.id}
            title={
              <Space>
                <span>{plotLine.title}</span>
                <Tag color="blue">{plotLine.line_type}</Tag>
                <Progress
                  type="circle"
                  percent={progress}
                  width={40}
                  strokeColor={progress === 100 ? '#52c41a' : '#1890ff'}
                />
              </Space>
            }
            extra={
              <Button
                type="primary"
                icon={<SaveOutlined />}
                loading={saving || loadingContributions}
                onClick={() => handleSave(linkId, plotLine.id)}
              >
                保存贡献度
              </Button>
            }
            style={{ marginBottom: 16 }}
          >
            {plotLine.description && (
              <Alert
                type="info"
                message={plotLine.description}
                style={{ marginBottom: 16 }}
              />
            )}

            <Alert
              type="info"
              message="贡献度说明"
              description="每个章节可以对剧情线节点贡献一定的完成度(0-100%)。同一节点在所有章节中的贡献度总和不能超过100%。"
              style={{ marginBottom: 16 }}
              showIcon
            />

            <Table
              dataSource={beats}
              columns={columns}
              rowKey="index"
              pagination={false}
              size="small"
            />
          </Card>
        );
      })}
    </div>
  );
};

export default BeatsCoverageEditor;

