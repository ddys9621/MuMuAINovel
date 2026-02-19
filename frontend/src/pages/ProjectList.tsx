import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Button, Empty, Modal, message, Spin, Row, Col, Space, Tag, Typography, Tooltip, Alert, Upload, Checkbox, Divider, Switch, Dropdown } from 'antd';
import { EditOutlined, BookOutlined, RocketOutlined, CalendarOutlined, FileTextOutlined, TrophyOutlined, SettingOutlined, InfoCircleOutlined, CloseOutlined, UploadOutlined, DownloadOutlined, ApiOutlined, MoreOutlined, BulbOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { projectApi } from '../services/api';
import { useStore } from '../store';
import { useProjectSync } from '../store/hooks';
import type { ReactNode } from 'react';
import UserMenu from '../components/UserMenu';
import WelcomeHeader from '../components/WelcomeHeader';
import StatsCard from '../components/StatsCard';
import FreshCard from '../components/FreshCard';
import ProjectWizardModal from '../components/ProjectWizardModal';
import InspirationDrawer from '../components/InspirationDrawer';
import { freshTheme } from '../styles/theme';

const { Text } = Typography;

export default function ProjectList() {
  const navigate = useNavigate();
  const { projects, loading, projectsInitialized } = useStore();
  const [showApiTip, setShowApiTip] = useState(() => {
    const saved = localStorage.getItem('hideApiTip');
    return saved !== 'true';
  });

  const handleCloseApiTip = () => {
    setShowApiTip(false);
    localStorage.setItem('hideApiTip', 'true');
  };

  const [importModalVisible, setImportModalVisible] = useState(false);
  const [exportModalVisible, setExportModalVisible] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [importing, setImporting] = useState(false);
  const [validating, setValidating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [selectedProjectIds, setSelectedProjectIds] = useState<string[]>([]);
  const [exportOptions, setExportOptions] = useState({
    includeWritingStyles: true,
    includeGenerationHistory: true,
  });

  // 新增：Modal 和 Drawer 状态
  const [wizardModalVisible, setWizardModalVisible] = useState(false);
  const [inspirationDrawerOpen, setInspirationDrawerOpen] = useState(false);

  const { refreshProjects, deleteProject } = useProjectSync();

  useEffect(() => {
    refreshProjects();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        refreshProjects();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDelete = (id: string) => {
    const isMobile = window.innerWidth <= 768;
    Modal.confirm({
      title: '确认删除',
      content: '删除项目将同时删除所有相关数据，此操作不可恢复。确定要删除吗？',
      okText: '确定',
      cancelText: '取消',
      okType: 'danger',
      centered: true,
      ...(isMobile && { style: { top: 'auto' } }),
      onOk: async () => {
        try {
          await deleteProject(id);
          message.success('项目删除成功');
        } catch {
          message.error('删除项目失败');
        }
      },
    });
  };

  const handleEnterProject = (id: string) => {
    navigate(`/project/${id}`);
  };

  const getStatusTag = (status: string) => {
    const statusConfig: Record<string, { color: string; text: string; icon: ReactNode }> = {
      planning: { color: 'blue', text: '规划中', icon: <CalendarOutlined /> },
      writing: { color: 'green', text: '创作中', icon: <EditOutlined /> },
      revising: { color: 'orange', text: '修改中', icon: <FileTextOutlined /> },
      completed: { color: 'purple', text: '已完成', icon: <TrophyOutlined /> },
    };
    const config = statusConfig[status] || statusConfig.planning;
    return (
      <Tag color={config.color} icon={config.icon}>
        {config.text}
      </Tag>
    );
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days === 0) return '今天';
    if (days === 1) return '昨天';
    if (days < 7) return `${days}天前`;
    if (days < 30) return `${Math.floor(days / 7)}周前`;
    return date.toLocaleDateString('zh-CN');
  };

  const totalWords = projects.reduce((sum, p) => sum + (p.current_words || 0), 0);
  const activeProjects = projects.filter(p => p.status === 'writing').length;
  const completedProjects = projects.filter(p => p.status === 'completed').length;

  const handleFileSelect = async (file: File) => {
    setSelectedFile(file);
    setValidationResult(null);
    try {
      setValidating(true);
      const result = await projectApi.validateImportFile(file);
      setValidationResult(result);
      if (!result.valid) {
        message.error('文件验证失败');
      }
    } catch (error) {
      console.error('验证失败:', error);
      message.error('文件验证失败');
    } finally {
      setValidating(false);
    }
    return false;
  };

  const handleImport = async () => {
    if (!selectedFile || !validationResult?.valid) {
      message.warning('请选择有效的导入文件');
      return;
    }
    try {
      setImporting(true);
      const result = await projectApi.importProject(selectedFile);
      if (result.success) {
        message.success(`项目导入成功！${result.message}`);
        setImportModalVisible(false);
        setSelectedFile(null);
        setValidationResult(null);
        await refreshProjects();
        if (result.project_id) {
          navigate(`/project/${result.project_id}`);
        }
      } else {
        message.error(result.message || '导入失败');
      }
    } catch (error) {
      console.error('导入失败:', error);
      message.error('导入失败，请重试');
    } finally {
      setImporting(false);
    }
  };

  const handleCloseImportModal = () => {
    setImportModalVisible(false);
    setSelectedFile(null);
    setValidationResult(null);
  };

  const handleOpenExportModal = () => {
    setExportModalVisible(true);
    setSelectedProjectIds([]);
  };

  const exportableProjects = projects;

  const handleCloseExportModal = () => {
    setExportModalVisible(false);
    setSelectedProjectIds([]);
  };

  const handleToggleProject = (projectId: string) => {
    setSelectedProjectIds(prev =>
      prev.includes(projectId)
        ? prev.filter(id => id !== projectId)
        : [...prev, projectId]
    );
  };

  const handleToggleAll = () => {
    if (selectedProjectIds.length === exportableProjects.length) {
      setSelectedProjectIds([]);
    } else {
      setSelectedProjectIds(exportableProjects.map(p => p.id));
    }
  };

  const handleExport = async () => {
    if (selectedProjectIds.length === 0) {
      message.warning('请至少选择一个项目');
      return;
    }
    try {
      setExporting(true);
      if (selectedProjectIds.length === 1) {
        const projectId = selectedProjectIds[0];
        const project = projects.find(p => p.id === projectId);
        await projectApi.exportProjectData(projectId, {
          include_generation_history: exportOptions.includeGenerationHistory,
          include_writing_styles: exportOptions.includeWritingStyles
        });
        message.success(`项目 "${project?.title}" 导出成功`);
      } else {
        let successCount = 0;
        let failCount = 0;
        for (const projectId of selectedProjectIds) {
          try {
            await projectApi.exportProjectData(projectId, {
              include_generation_history: exportOptions.includeGenerationHistory,
              include_writing_styles: exportOptions.includeWritingStyles
            });
            successCount++;
            await new Promise(resolve => setTimeout(resolve, 500));
          } catch (error) {
            console.error(`导出项目 ${projectId} 失败:`, error);
            failCount++;
          }
        }
        if (failCount === 0) {
          message.success(`成功导出 ${successCount} 个项目`);
        } else {
          message.warning(`导出完成：成功 ${successCount} 个，失败 ${failCount} 个`);
        }
      }
      handleCloseExportModal();
    } catch (error) {
      console.error('导出失败:', error);
      message.error('导出失败，请重试');
    } finally {
      setExporting(false);
    }
  };

  // 页面背景样式
  const pageStyles: React.CSSProperties = {
    minHeight: '100vh',
    background: freshTheme.colors.gradients.page,
    padding: window.innerWidth <= 768 ? '20px 16px' : '40px 24px',
  };

  const containerStyles: React.CSSProperties = {
    maxWidth: 1400,
    margin: '0 auto',
  };



  return (
    <div style={pageStyles}>
      <div style={containerStyles}>
        {/* 欢迎头部 */}
        <WelcomeHeader
          username="创作者"
          onCreateProject={() => setWizardModalVisible(true)}
          onInspirationMode={() => setInspirationDrawerOpen(true)}
        />

        {/* 统计卡片区域 */}
        {projects.length > 0 && (
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={24} sm={12} md={6}>
              <StatsCard
                icon={<BookOutlined style={{ color: freshTheme.colors.primary.sky }} />}
                label="总项目"
                value={projects.length}
                color="sky"
                suffix="个"
              />
            </Col>
            <Col xs={24} sm={12} md={6}>
              <StatsCard
                icon={<ThunderboltOutlined style={{ color: freshTheme.colors.primary.mint }} />}
                label="创作中"
                value={activeProjects}
                color="mint"
                suffix="个"
              />
            </Col>
            <Col xs={24} sm={12} md={6}>
              <StatsCard
                icon={<FileTextOutlined style={{ color: freshTheme.colors.primary.sakura }} />}
                label="总字数"
                value={(totalWords / 1000).toFixed(1)}
                color="sakura"
                suffix="K"
              />
            </Col>
            <Col xs={24} sm={12} md={6}>
              <StatsCard
                icon={<TrophyOutlined style={{ color: freshTheme.colors.primary.lavender }} />}
                label="已完成"
                value={completedProjects}
                color="lavender"
                suffix="个"
              />
            </Col>
          </Row>
        )}



        {/* 首次使用提示 */}
        {showApiTip && projectsInitialized && projects.length === 0 && (
          <Alert
            message={
              <Space align="center">
                <InfoCircleOutlined style={{ color: freshTheme.colors.primary.sky }} />
                <Text strong>首次使用提示</Text>
              </Space>
            }
            description={
              <Space direction="vertical" size={8}>
                <Text>在开始创作之前，请先配置您的AI接口。系统支持OpenAI和Anthropic两种接口。</Text>
                <Space>
                  <Button
                    type="primary"
                    size="small"
                    icon={<SettingOutlined />}
                    onClick={() => navigate('/settings')}
                    style={{
                      borderRadius: freshTheme.radius.sm,
                      background: freshTheme.colors.gradients.sakuraMint,
                      border: 'none',
                    }}
                  >
                    立即配置
                  </Button>
                  <Button size="small" onClick={handleCloseApiTip}>
                    暂不提醒
                  </Button>
                </Space>
              </Space>
            }
            type="info"
            showIcon={false}
            closable
            closeIcon={<CloseOutlined />}
            onClose={handleCloseApiTip}
            style={{
              marginBottom: 24,
              borderRadius: freshTheme.radius.lg,
              background: 'linear-gradient(135deg, rgba(168, 216, 234, 0.1) 0%, rgba(184, 230, 212, 0.1) 100%)',
              border: `1px solid ${freshTheme.colors.primary.sky}40`,
            }}
          />
        )}

        {/* 顶部操作栏 */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginBottom: 24 }}>
          <Button
            icon={<SettingOutlined />}
            onClick={() => navigate('/settings')}
            style={{
              borderRadius: freshTheme.radius.md,
              background: freshTheme.colors.background.card,
              border: `1px solid ${freshTheme.colors.background.border}`,
              color: freshTheme.colors.text.secondary,
            }}
          >
            设置
          </Button>
          <Dropdown
            menu={{
              items: [
                {
                  key: 'export',
                  label: '导出项目',
                  icon: <DownloadOutlined />,
                  onClick: handleOpenExportModal,
                  disabled: exportableProjects.length === 0,
                },
                {
                  key: 'import',
                  label: '导入项目',
                  icon: <UploadOutlined />,
                  onClick: () => setImportModalVisible(true),
                },
                { type: 'divider' },
                {
                  key: 'mcp',
                  label: 'MCP插件',
                  icon: <ApiOutlined />,
                  onClick: () => navigate('/mcp-plugins'),
                },
              ],
            }}
            placement="bottomRight"
          >
            <Button
              icon={<MoreOutlined />}
              style={{
                borderRadius: freshTheme.radius.md,
                background: freshTheme.colors.background.card,
                border: `1px solid ${freshTheme.colors.background.border}`,
                color: freshTheme.colors.text.secondary,
              }}
            >
              更多
            </Button>
          </Dropdown>
          <UserMenu />
        </div>

        {/* 项目列表 */}
        <Spin spinning={loading}>
          {!projectsInitialized ? (
            <div style={{ minHeight: 200 }} />
          ) : !Array.isArray(projects) || projects.length === 0 ? (
            <Card
              style={{
                background: freshTheme.colors.background.card,
                borderRadius: freshTheme.radius.xl,
                boxShadow: freshTheme.shadow.medium,
                border: `1px solid ${freshTheme.colors.background.border}`,
                textAlign: 'center',
                padding: '60px 20px',
              }}
            >
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <Space direction="vertical" size={16}>
                    <Text style={{ color: freshTheme.colors.text.secondary }}>
                      还没有项目，开始创建你的第一个小说项目吧！
                    </Text>
                    <Space>
                      <Button
                        type="primary"
                        icon={<BulbOutlined />}
                        onClick={() => setInspirationDrawerOpen(true)}
                        style={{
                          background: freshTheme.colors.gradients.sakuraMint,
                          border: 'none',
                          borderRadius: freshTheme.radius.md,
                        }}
                      >
                        灵感模式
                      </Button>
                      <Button
                        type="primary"
                        icon={<RocketOutlined />}
                        onClick={() => setWizardModalVisible(true)}
                        style={{
                          background: freshTheme.colors.gradients.skyLavender,
                          border: 'none',
                          borderRadius: freshTheme.radius.md,
                        }}
                      >
                        向导创建
                      </Button>
                    </Space>
                  </Space>
                }
              />
            </Card>
          ) : (
            <Row gutter={[16, 16]}>
              {projects.map((project) => (
                <Col xs={24} sm={12} md={8} lg={6} key={project.id}>
                  <FreshCard
                    id={project.id}
                    title={project.title}
                    description={project.description}
                    genre={project.genre}
                    status={project.status}
                    wordCount={project.current_words}
                    targetWordCount={project.target_words}
                    updatedAt={formatDate(project.updated_at)}
                    onClick={() => handleEnterProject(project.id)}
                    onDelete={() => handleDelete(project.id)}
                    onExport={async () => {
                      try {
                        await projectApi.exportProjectData(project.id, {
                          include_generation_history: true,
                          include_writing_styles: true,
                        });
                        message.success('导出成功');
                      } catch {
                        message.error('导出失败');
                      }
                    }}
                  />
                </Col>
              ))}
            </Row>
          )}
        </Spin>
      </div>

      {/* 导入对话框 */}
      <Modal
        title="导入项目"
        open={importModalVisible}
        onOk={handleImport}
        onCancel={handleCloseImportModal}
        confirmLoading={importing}
        okText="导入"
        cancelText="取消"
        width={window.innerWidth <= 768 ? '90%' : 500}
        centered
        okButtonProps={{ disabled: !validationResult?.valid }}
      >
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <div>
            <p style={{ marginBottom: 12, color: freshTheme.colors.text.secondary }}>
              选择之前导出的 JSON 格式项目文件
            </p>
            <Upload
              accept=".json"
              beforeUpload={handleFileSelect}
              maxCount={1}
              onRemove={() => {
                setSelectedFile(null);
                setValidationResult(null);
              }}
              fileList={selectedFile ? [{ uid: '-1', name: selectedFile.name, status: 'done' }] as any : []}
            >
              <Button icon={<UploadOutlined />} block>选择文件</Button>
            </Upload>
          </div>
          {validating && (
            <div style={{ textAlign: 'center', padding: 20 }}>
              <Spin tip="验证文件中..." />
            </div>
          )}
          {validationResult && (
            <Card size="small" style={{ background: validationResult.valid ? '#f6ffed' : '#fff2f0' }}>
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <Text strong style={{ color: validationResult.valid ? '#52c41a' : '#ff4d4f' }}>
                  {validationResult.valid ? '✓ 文件验证通过' : '✗ 文件验证失败'}
                </Text>
                {validationResult.project_name && (
                  <div>
                    <Text type="secondary">项目名称：</Text>
                    <Text strong>{validationResult.project_name}</Text>
                  </div>
                )}
              </Space>
            </Card>
          )}
        </Space>
      </Modal>

      {/* 导出对话框 */}
      <Modal
        title="导出项目"
        open={exportModalVisible}
        onOk={handleExport}
        onCancel={handleCloseExportModal}
        confirmLoading={exporting}
        okText={selectedProjectIds.length > 0 ? `导出 (${selectedProjectIds.length})` : '导出'}
        cancelText="取消"
        width={window.innerWidth <= 768 ? '90%' : 700}
        centered
        okButtonProps={{ disabled: selectedProjectIds.length === 0 }}
      >
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <Card size="small" style={{ background: freshTheme.colors.background.hover }}>
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <Text strong>导出选项</Text>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Switch
                  checked={exportOptions.includeWritingStyles}
                  onChange={(checked) => setExportOptions(prev => ({ ...prev, includeWritingStyles: checked }))}
                />
                <Text>包含写作风格</Text>
                <Tooltip title="导出项目关联的写作风格数据">
                  <InfoCircleOutlined style={{ color: freshTheme.colors.text.light }} />
                </Tooltip>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Switch
                  checked={exportOptions.includeGenerationHistory}
                  onChange={(checked) => setExportOptions(prev => ({ ...prev, includeGenerationHistory: checked }))}
                />
                <Text>包含生成历史</Text>
                <Tooltip title="导出AI生成的历史记录">
                  <InfoCircleOutlined style={{ color: freshTheme.colors.text.light }} />
                </Tooltip>
              </div>
            </Space>
          </Card>

          <Divider style={{ margin: '8px 0' }} />

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <Text strong>
                选择要导出的项目 <Text type="secondary">({exportableProjects.length}个可导出)</Text>
              </Text>
              <Checkbox
                checked={selectedProjectIds.length === exportableProjects.length && exportableProjects.length > 0}
                indeterminate={selectedProjectIds.length > 0 && selectedProjectIds.length < exportableProjects.length}
                onChange={handleToggleAll}
              >
                全选
              </Checkbox>
            </div>

            <div style={{ maxHeight: 400, overflowY: 'auto' }}>
              {exportableProjects.length === 0 ? (
                <Empty description="暂无可导出的项目" style={{ padding: '40px 0' }} />
              ) : (
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  {exportableProjects.map((project) => (
                    <Card
                      key={project.id}
                      size="small"
                      hoverable
                      style={{
                        cursor: 'pointer',
                        border: selectedProjectIds.includes(project.id) ? `2px solid ${freshTheme.colors.primary.mint}` : `1px solid ${freshTheme.colors.background.border}`,
                        background: selectedProjectIds.includes(project.id) ? 'rgba(184, 230, 212, 0.1)' : freshTheme.colors.background.card,
                      }}
                      onClick={() => handleToggleProject(project.id)}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <Checkbox
                          checked={selectedProjectIds.includes(project.id)}
                          onChange={() => handleToggleProject(project.id)}
                          onClick={(e) => e.stopPropagation()}
                        />
                        <BookOutlined style={{ color: freshTheme.colors.primary.sky }} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <Text strong>{project.title}</Text>
                          <br />
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {project.current_words || 0} 字
                          </Text>
                        </div>
                        {getStatusTag(project.status)}
                      </div>
                    </Card>
                  ))}
                </Space>
              )}
            </div>
          </div>

          {selectedProjectIds.length > 0 && (
            <Alert
              message={`已选择 ${selectedProjectIds.length} 个项目`}
              type="info"
              showIcon
              style={{ marginTop: 8, borderRadius: freshTheme.radius.md }}
            />
          )}
        </Space>
      </Modal>

      {/* 项目创建向导 Modal */}
      <ProjectWizardModal
        visible={wizardModalVisible}
        onClose={() => setWizardModalVisible(false)}
        onSuccess={(projectId) => {
          setWizardModalVisible(false);
          refreshProjects();
          navigate(`/project/${projectId}`);
        }}
      />

      {/* 灵感模式 Drawer */}
      <InspirationDrawer
        open={inspirationDrawerOpen}
        onClose={() => setInspirationDrawerOpen(false)}
        onSuccess={(projectId) => {
          setInspirationDrawerOpen(false);
          refreshProjects();
          navigate(`/project/${projectId}`);
        }}
      />
    </div>
  );
}
