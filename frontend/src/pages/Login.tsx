import { useEffect, useState } from 'react';
import { Button, Typography, message, Spin, Form, Input, Tabs } from 'antd';
import { UserOutlined, LockOutlined, CheckCircleFilled } from '@ant-design/icons';
import { authApi } from '../services/api';
import { useNavigate, useSearchParams } from 'react-router-dom';
import AnnouncementModal from '../components/AnnouncementModal';
import { freshTheme } from '../styles/theme';

const { Title, Paragraph } = Typography;

/* ── 特性列表数据 ── */
const features = [
  'AI 驱动的智能小说创作体验',
  '全面的角色、世界观管理系统',
  '可视化大纲与章节编辑器',
  '一键生成，优雅的写作流程',
  '多种写作风格，自由切换',
  '独立数据空间，安全可靠',
];

export default function Login() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const [localAuthEnabled, setLocalAuthEnabled] = useState(false);
  const [linuxdoEnabled, setLinuxdoEnabled] = useState(false);
  const [form] = Form.useForm();
  const [showAnnouncement, setShowAnnouncement] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        await authApi.getCurrentUser();
        const redirect = searchParams.get('redirect') || '/';
        navigate(redirect);
      } catch {
        try {
          const config = await authApi.getAuthConfig();
          setLocalAuthEnabled(config.local_auth_enabled);
          setLinuxdoEnabled(config.linuxdo_enabled);
        } catch (error) {
          console.error('获取认证配置失败:', error);
          setLinuxdoEnabled(true);
        }
        setChecking(false);
      }
    };
    checkAuth();
  }, [navigate, searchParams]);

  const handleLocalLogin = async (values: { username: string; password: string }) => {
    try {
      setLoading(true);
      const response = await authApi.localLogin(values.username, values.password);
      if (response.success) {
        message.success('登录成功！');
        const doNotShowUntil = localStorage.getItem('announcement_do_not_show_until');
        const now = new Date().getTime();
        if (!doNotShowUntil || now > parseInt(doNotShowUntil)) {
          setShowAnnouncement(true);
        } else {
          const redirect = searchParams.get('redirect') || '/';
          navigate(redirect);
        }
      }
    } catch (error) {
      console.error('本地登录失败:', error);
      setLoading(false);
    }
  };

  const handleLinuxDOLogin = async () => {
    try {
      setLoading(true);
      const response = await authApi.getLinuxDOAuthUrl();
      const redirect = searchParams.get('redirect');
      if (redirect) sessionStorage.setItem('login_redirect', redirect);
      window.location.href = response.auth_url;
    } catch (error) {
      console.error('获取授权地址失败:', error);
      message.error('获取授权地址失败，请稍后重试');
      setLoading(false);
    }
  };

  const handleAnnouncementClose = () => {
    setShowAnnouncement(false);
    const redirect = searchParams.get('redirect') || '/';
    navigate(redirect);
  };

  const handleDoNotShowToday = () => {
    const tomorrow = new Date();
    tomorrow.setHours(23, 59, 59, 999);
    localStorage.setItem('announcement_do_not_show_until', tomorrow.getTime().toString());
  };

  /* ── Loading 态 ── */
  if (checking) {
    return (
      <div style={{
        display: 'flex', justifyContent: 'center', alignItems: 'center',
        minHeight: '100vh',
        background: freshTheme.colors.gradients.page,
      }}>
        <Spin size="large" />
      </div>
    );
  }

  /* ── 本地登录表单 ── */
  const renderLocalLogin = () => (
    <Form form={form} onFinish={handleLocalLogin} size="large" style={{ marginTop: 16 }}>
      <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
        <Input
          prefix={<UserOutlined style={{ color: freshTheme.colors.text.light }} />}
          placeholder="用户名"
          autoComplete="username"
          style={{
            borderRadius: freshTheme.radius.md,
            border: `1px solid ${freshTheme.colors.background.border}`,
            height: 48,
          }}
        />
      </Form.Item>
      <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
        <Input.Password
          prefix={<LockOutlined style={{ color: freshTheme.colors.text.light }} />}
          placeholder="密码"
          autoComplete="current-password"
          style={{
            borderRadius: freshTheme.radius.md,
            border: `1px solid ${freshTheme.colors.background.border}`,
            height: 48,
          }}
        />
      </Form.Item>
      <Form.Item style={{ marginBottom: 0 }}>
        <Button type="primary" htmlType="submit" loading={loading} block style={loginBtnStyle}>
          登 录
        </Button>
      </Form.Item>
    </Form>
  );

  /* ── LinuxDO 登录 ── */
  const renderLinuxDOLogin = () => (
    <div style={{ padding: '16px 0 0' }}>
      <Button
        type="primary" size="large" loading={loading}
        onClick={handleLinuxDOLogin} block
        icon={<img src="/favicon.ico" alt="LinuxDO" style={{ width: 20, height: 20, marginRight: 8, verticalAlign: 'middle' }} />}
        style={loginBtnStyle}
      >
        使用 LinuxDO 登录
      </Button>
    </div>
  );

  return (
    <>
      <AnnouncementModal visible={showAnnouncement} onClose={handleAnnouncementClose} onDoNotShowToday={handleDoNotShowToday} />

      <div className="login-container" style={containerStyle}>
        {/* ====== 左侧品牌展示区 ====== */}
        <div className="login-left-panel" style={leftPanelStyle}>
          {/* 装饰光晕 */}
          <div style={{ position: 'absolute', top: '-80px', right: '-80px', width: 300, height: 300, borderRadius: '50%', background: 'rgba(255,255,255,0.12)', filter: 'blur(60px)', pointerEvents: 'none' }} />
          <div style={{ position: 'absolute', bottom: '-60px', left: '-60px', width: 240, height: 240, borderRadius: '50%', background: 'rgba(255,255,255,0.08)', filter: 'blur(60px)', pointerEvents: 'none' }} />

          <div style={{ position: 'relative', zIndex: 1 }}>
            {/* Logo */}
            <div style={{
              width: 64, height: 64, borderRadius: freshTheme.radius.lg,
              background: 'rgba(255,255,255,0.2)', backdropFilter: 'blur(10px)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              marginBottom: 28, border: '1px solid rgba(255,255,255,0.3)',
            }}>
              <img src="/logo.svg" alt="Logo" style={{ width: 40, height: 40, filter: 'brightness(0) invert(1)' }} />
            </div>

            <Title level={2} style={{ color: '#fff', fontWeight: 700, marginBottom: 4, fontSize: 30 }}>
              AI小说创作助手
            </Title>
            <div style={{ width: 40, height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.5)', margin: '16px 0 20px' }} />
            <Paragraph style={{ color: 'rgba(255,255,255,0.85)', fontSize: 18, fontWeight: 500, marginBottom: 36 }}>
              更优雅的创作体验
            </Paragraph>

            {/* 特性列表 */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {features.map((text, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <CheckCircleFilled style={{ color: 'rgba(255,255,255,0.85)', fontSize: 16 }} />
                  <span style={{ color: 'rgba(255,255,255,0.9)', fontSize: 15 }}>{text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ====== 右侧登录表单区 ====== */}
        <div className="login-right-panel" style={rightPanelStyle}>
          <div style={formWrapperStyle}>
            <Title level={3} style={{ color: freshTheme.colors.text.primary, fontWeight: 700, marginBottom: 4 }}>
              登录
            </Title>
            <Paragraph style={{ color: freshTheme.colors.text.secondary, marginBottom: 28 }}>
              {localAuthEnabled && linuxdoEnabled ? '没有账号？首次登录自动注册 >' :
               localAuthEnabled ? '使用账户密码登录' :
               '使用 LinuxDO 账号登录'}
            </Paragraph>

            {localAuthEnabled && linuxdoEnabled ? (
              <Tabs
                defaultActiveKey="local" centered
                items={[
                  { key: 'local', label: '账户密码', children: renderLocalLogin() },
                  { key: 'linuxdo', label: 'LinuxDO', children: renderLinuxDOLogin() },
                ]}
              />
            ) : localAuthEnabled ? renderLocalLogin() : renderLinuxDOLogin()}

            {/* 底部提示 */}
            <div style={{
              marginTop: 28, padding: 16,
              background: `linear-gradient(135deg, ${freshTheme.colors.primary.sakura}18 0%, ${freshTheme.colors.primary.mint}18 100%)`,
              borderRadius: freshTheme.radius.md,
              border: `1px solid ${freshTheme.colors.background.border}`,
            }}>
              <Paragraph style={{ fontSize: 13, color: freshTheme.colors.text.secondary, marginBottom: 0, lineHeight: 1.8 }}>
                🎉 首次登录将自动创建账号<br />
                🔒 每个用户拥有独立的数据空间
              </Paragraph>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

/* ══════════ 样式常量 ══════════ */

const containerStyle: React.CSSProperties = {
  display: 'flex',
  minHeight: '100vh',
  background: freshTheme.colors.gradients.page,
};

const leftPanelStyle: React.CSSProperties = {
  flex: '0 0 45%',
  background: `linear-gradient(135deg, ${freshTheme.colors.primary.sakura} 0%, #E8A0B4 30%, ${freshTheme.colors.primary.lavender} 70%, ${freshTheme.colors.primary.mint} 100%)`,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '60px 48px',
  position: 'relative',
  overflow: 'hidden',
};

const rightPanelStyle: React.CSSProperties = {
  flex: 1,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '40px 24px',
  background: freshTheme.colors.background.card,
};

const formWrapperStyle: React.CSSProperties = {
  width: '100%',
  maxWidth: 400,
};

const loginBtnStyle: React.CSSProperties = {
  height: 48,
  fontSize: 16,
  fontWeight: 600,
  background: freshTheme.colors.gradients.sakuraMint,
  border: 'none',
  borderRadius: freshTheme.radius.md,
  boxShadow: freshTheme.shadow.soft,
  color: freshTheme.colors.text.primary,
  transition: freshTheme.transition.normal,
};