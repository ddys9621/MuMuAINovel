import { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate, Outlet, Link, useLocation } from 'react-router-dom';
import { Layout, Menu, Spin, Button, Statistic, Row, Col, Card, Drawer } from 'antd';
import {
  ArrowLeftOutlined,
  FileTextOutlined,
  TeamOutlined,
  BookOutlined,
  // ToolOutlined,
  GlobalOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  ApartmentOutlined,
  BankOutlined,
  EditOutlined,
  FundOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import { useStore } from '../store';
import { useCharacterSync, useOutlineSync, useChapterSync } from '../store/hooks';
import { projectApi } from '../services/api';

const { Header, Sider, Content } = Layout;

// 判断是否为移动端
const isMobile = () => window.innerWidth <= 768;

export default function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [mobile, setMobile] = useState(isMobile());

  // 监听窗口大小变化
  useEffect(() => {
    const handleResize = () => {
      setMobile(isMobile());
      if (!isMobile()) {
        setDrawerVisible(false);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);
  const {
    currentProject,
    setCurrentProject,
    clearProjectData,
    loading,
    setLoading,
    outlines,
    characters,
    chapters,
  } = useStore();

  // 使用同步 hooks
  const { refreshCharacters } = useCharacterSync();
  const { refreshOutlines } = useOutlineSync();
  const { refreshChapters } = useChapterSync();

  useEffect(() => {
    const loadProjectData = async (id: string) => {
      try {
        setLoading(true);
        // 加载项目基本信息
        const project = await projectApi.getProject(id);
        setCurrentProject(project);
        
        // 并行加载其他数据
        await Promise.all([
          refreshOutlines(id),
          refreshCharacters(id),
          refreshChapters(id),
        ]);
      } catch (error) {
        console.error('加载项目数据失败:', error);
      } finally {
        setLoading(false);
      }
    };

    if (projectId) {
      loadProjectData(projectId);
    }

    return () => {
      clearProjectData();
    };
  }, [projectId]);

  // 移除事件监听，避免无限循环
  // Hook 内部已经更新了 store，不需要再次刷新

  const menuItems = [
    {
      key: 'world-setting',
      icon: <GlobalOutlined />,
      label: <Link to={`/project/${projectId}/world-setting`}>世界设定</Link>,
    },
    {
      key: 'world-rules',
      icon: <DatabaseOutlined />,
      label: <Link to={`/project/${projectId}/world-rules`}>世界规则系统</Link>,
    },
    {
      key: 'characters',
      icon: <TeamOutlined />,
      label: <Link to={`/project/${projectId}/characters`}>角色管理</Link>,
    },
    {
      key: 'relationships',
      icon: <ApartmentOutlined />,
      label: <Link to={`/project/${projectId}/relationships`}>关系管理</Link>,
    },
    {
      key: 'organizations',
      icon: <BankOutlined />,
      label: <Link to={`/project/${projectId}/organizations`}>组织管理</Link>,
    },
    {
      key: 'outline',
      icon: <FileTextOutlined />,
      label: <Link to={`/project/${projectId}/outline`}>故事大纲 & 剧情</Link>,
    },
    {
      key: 'chapters',
      icon: <BookOutlined />,
      label: <Link to={`/project/${projectId}/chapters`}>章节管理</Link>,
    },
    {
      key: 'chapter-analysis',
      icon: <FundOutlined />,
      label: <Link to={`/project/${projectId}/chapter-analysis`}>剧情分析</Link>,
    },
    {
      key: 'writing-styles',
      icon: <EditOutlined />,
      label: <Link to={`/project/${projectId}/writing-styles`}>写作风格</Link>,
    },
    // {
    //   key: 'polish',
    //   icon: <ToolOutlined />,
    //   label: <Link to={`/project/${projectId}/polish`}>AI去味</Link>,
    // },
  ];

  // 根据当前路径动态确定选中的菜单项
  const selectedKey = useMemo(() => {
    const path = location.pathname;
    if (path.includes('/world-setting')) return 'world-setting';
    if (path.includes('/relationships')) return 'relationships';
    if (path.includes('/organizations')) return 'organizations';
    if (path.includes('/outline')) return 'outline';
    if (path.includes('/characters')) return 'characters';
    if (path.includes('/chapter-analysis')) return 'chapter-analysis';
    if (path.includes('/chapters')) return 'chapters';
    if (path.includes('/writing-styles')) return 'writing-styles';
    // if (path.includes('/polish')) return 'polish';
    return 'world-setting'; // 默认选中世界设定
  }, [location.pathname]);

  if (loading || !currentProject) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  // 渲染菜单内容
  const renderMenu = () => (
    <div style={{
      flex: 1,
      overflowY: 'auto',
      overflowX: 'hidden'
    }}>
      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        style={{
          borderRight: 0,
          paddingTop: '16px'
        }}
        items={menuItems}
        onClick={() => mobile && setDrawerVisible(false)}
      />
    </div>
  );

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        padding: mobile ? '0 12px' : '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 1000,
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        height: mobile ? 56 : 70
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', zIndex: 1 }}>
          <Button
            type="text"
            icon={mobile ? <MenuUnfoldOutlined /> : (collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />)}
            onClick={() => mobile ? setDrawerVisible(true) : setCollapsed(!collapsed)}
            style={{
              fontSize: mobile ? '18px' : '20px',
              color: '#fff',
              width: mobile ? '36px' : '40px',
              height: mobile ? '36px' : '40px'
            }}
          />
          {!mobile && (
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate('/')}
              style={{
                fontSize: '16px',
                color: '#fff',
                height: '40px',
                padding: '0 16px'
              }}
            >
              返回主页
            </Button>
          )}
        </div>
        
        <h2 style={{
          margin: 0,
          color: '#fff',
          fontSize: mobile ? '16px' : '24px',
          fontWeight: 600,
          textShadow: '0 2px 4px rgba(0,0,0,0.1)',
          position: mobile ? 'static' : 'absolute',
          left: mobile ? 'auto' : '50%',
          transform: mobile ? 'none' : 'translateX(-50%)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          flex: mobile ? 1 : 'none',
          textAlign: mobile ? 'center' : 'left',
          paddingLeft: mobile ? '8px' : '0',
          paddingRight: mobile ? '8px' : '0'
        }}>
          {currentProject.title}
        </h2>
        
        {mobile && (
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/')}
            style={{
              fontSize: '14px',
              color: '#fff',
              height: '36px',
              padding: '0 8px',
              zIndex: 1
            }}
          >
            主页
          </Button>
        )}
        
        {!mobile && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', zIndex: 1 }}>
            <Row gutter={12} style={{ width: '450px', justifyContent: 'flex-end' }}>
            <Col>
              <Card
                size="small"
                style={{
                  background: 'rgba(255,255,255,0.95)',
                  borderRadius: '6px',
                  border: 'none',
                  minWidth: '80px',
                  textAlign: 'center',
                  padding: '4px 8px'
                }}
                styles={{ body: { padding: '8px' } }}
              >
                <Statistic
                  title={<span style={{ fontSize: '11px', color: '#666' }}>大纲</span>}
                  value={outlines.length}
                  suffix="条"
                  valueStyle={{ fontSize: '16px', fontWeight: 600, color: '#667eea' }}
                />
              </Card>
            </Col>
            <Col>
              <Card
                size="small"
                style={{
                  background: 'rgba(255,255,255,0.95)',
                  borderRadius: '6px',
                  border: 'none',
                  minWidth: '80px',
                  textAlign: 'center',
                  padding: '4px 8px'
                }}
                styles={{ body: { padding: '8px' } }}
              >
                <Statistic
                  title={<span style={{ fontSize: '11px', color: '#666' }}>角色</span>}
                  value={characters.length}
                  suffix="个"
                  valueStyle={{ fontSize: '16px', fontWeight: 600, color: '#52c41a' }}
                />
              </Card>
            </Col>
            <Col>
              <Card
                size="small"
                style={{
                  background: 'rgba(255,255,255,0.95)',
                  borderRadius: '6px',
                  border: 'none',
                  minWidth: '80px',
                  textAlign: 'center',
                  padding: '4px 8px'
                }}
                styles={{ body: { padding: '8px' } }}
              >
                <Statistic
                  title={<span style={{ fontSize: '11px', color: '#666' }}>章节</span>}
                  value={chapters.length}
                  suffix="章"
                  valueStyle={{ fontSize: '16px', fontWeight: 600, color: '#1890ff' }}
                />
              </Card>
            </Col>
            <Col>
              <Card
                size="small"
                style={{
                  background: 'rgba(255,255,255,0.95)',
                  borderRadius: '6px',
                  border: 'none',
                  minWidth: '80px',
                  textAlign: 'center',
                  padding: '4px 8px'
                }}
                styles={{ body: { padding: '8px' } }}
              >
                <Statistic
                  title={<span style={{ fontSize: '11px', color: '#666' }}>已写</span>}
                  value={currentProject.current_words}
                  suffix="字"
                  valueStyle={{ fontSize: '16px', fontWeight: 600, color: '#fa8c16' }}
                />
              </Card>
            </Col>
            </Row>
          </div>
        )}
      </Header>

      <Layout style={{ marginTop: mobile ? 56 : 70 }}>
        {mobile ? (
          <Drawer
            title="导航菜单"
            placement="left"
            onClose={() => setDrawerVisible(false)}
            open={drawerVisible}
            width={280}
            styles={{ body: { padding: 0, display: 'flex', flexDirection: 'column' } }}
          >
            {renderMenu()}
          </Drawer>
        ) : (
          <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          trigger={null}
          width={220}
          collapsedWidth={60}
          style={{
            background: '#fff',
            position: 'fixed',
            left: 0,
            top: 70,
            bottom: 0,
            overflow: 'hidden',
            boxShadow: '2px 0 12px rgba(0,0,0,0.08)',
            transition: 'all 0.2s',
            height: 'calc(100vh - 70px)'
          }}
          >
            <div style={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column'
            }}>
              {renderMenu()}
            </div>
          </Sider>
        )}

        <Layout style={{
          marginLeft: mobile ? 0 : (collapsed ? 60 : 220),
          transition: 'all 0.2s'
        }}>
          <Content
            style={{
              background: '#f5f7fa',
              padding: mobile ? 12 : 24,
              minHeight: mobile ? 'calc(100vh - 56px)' : 'calc(100vh - 70px)',
              display: 'flex',
              flexDirection: 'column'
            }}
          >
            <div style={{
              background: '#fff',
              padding: mobile ? 12 : 24,
              borderRadius: mobile ? '8px' : '12px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
              minHeight: '100%',
              display: 'flex',
              flexDirection: 'column'
            }}>
              <Outlet />
            </div>
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
}