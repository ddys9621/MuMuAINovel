import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Spin, Result, Button, Modal, Input, message } from 'antd';
import { authApi } from '../services/api';
import AnnouncementModal from '../components/AnnouncementModal';

export default function AuthCallback() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [showAnnouncement, setShowAnnouncement] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [passwordStatus, setPasswordStatus] = useState<any>(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [settingPassword, setSettingPassword] = useState(false);

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // 后端会通过 Cookie 自动设置认证信息
        // 这里只需要验证登录状态
        await authApi.getCurrentUser();
        
        // 检查密码状态
        const pwdStatus = await authApi.getPasswordStatus();
        setPasswordStatus(pwdStatus);
        
        setStatus('success');
        
        // 只有在用户完全没有密码时才显示密码设置提示
        // 如果已经有密码（无论是默认密码还是自定义密码），都不再提示
        if (!pwdStatus.has_password) {
          setTimeout(() => {
            setShowPasswordModal(true);
          }, 1000);
          return;
        }
        
        // 从 sessionStorage 获取重定向地址
        const redirect = sessionStorage.getItem('login_redirect') || '/';
        sessionStorage.removeItem('login_redirect');
        
        // 检查今天是否已经显示过公告
        const doNotShowUntil = localStorage.getItem('announcement_do_not_show_until');
        const now = new Date().getTime();
        
        if (!doNotShowUntil || now > parseInt(doNotShowUntil)) {
          // 延迟一下再显示公告，让用户看到成功提示
          setTimeout(() => {
            setShowAnnouncement(true);
          }, 1000);
        } else {
          // 延迟一下再跳转，让用户看到成功提示
          setTimeout(() => {
            navigate(redirect);
          }, 1000);
        }
      } catch (error) {
        console.error('登录失败:', error);
        setStatus('error');
        setErrorMessage('登录失败，请重试');
      }
    };

    handleCallback();
  }, [navigate]);

  if (status === 'loading') {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      }}>
        <div style={{ textAlign: 'center' }}>
          <Spin size="large" />
          <div style={{ marginTop: 20, color: 'white', fontSize: 16 }}>
            正在处理登录...
          </div>
        </div>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      }}>
        <Result
          status="error"
          title="登录失败"
          subTitle={errorMessage}
          extra={
            <Button type="primary" onClick={() => navigate('/login')}>
              返回登录
            </Button>
          }
          style={{ background: 'white', padding: 40, borderRadius: 8 }}
        />
      </div>
    );
  }

  const handleAnnouncementClose = () => {
    setShowAnnouncement(false);
    const redirect = sessionStorage.getItem('login_redirect') || '/';
    sessionStorage.removeItem('login_redirect');
    navigate(redirect);
  };

  const handleDoNotShowToday = () => {
    // 设置到今天23:59:59不再显示
    const tomorrow = new Date();
    tomorrow.setHours(23, 59, 59, 999);
    localStorage.setItem('announcement_do_not_show_until', tomorrow.getTime().toString());
  };

  const handleSetPassword = async () => {
    if (!newPassword) {
      message.error('请输入新密码');
      return;
    }
    if (newPassword.length < 6) {
      message.error('密码长度至少为6个字符');
      return;
    }
    if (newPassword !== confirmPassword) {
      message.error('两次输入的密码不一致');
      return;
    }

    setSettingPassword(true);
    try {
      await authApi.setPassword(newPassword);
      message.success('密码设置成功');
      setShowPasswordModal(false);
      
      // 继续后续流程
      const redirect = sessionStorage.getItem('login_redirect') || '/';
      sessionStorage.removeItem('login_redirect');
      
      const doNotShowUntil = localStorage.getItem('announcement_do_not_show_until');
      const now = new Date().getTime();
      
      if (!doNotShowUntil || now > parseInt(doNotShowUntil)) {
        setTimeout(() => {
          setShowAnnouncement(true);
        }, 500);
      } else {
        setTimeout(() => {
          navigate(redirect);
        }, 500);
      }
    } catch (error) {
      message.error('密码设置失败，请重试');
    } finally {
      setSettingPassword(false);
    }
  };

  const handleSkipPasswordSetting = () => {
    setShowPasswordModal(false);
    
    // 继续后续流程
    const redirect = sessionStorage.getItem('login_redirect') || '/';
    sessionStorage.removeItem('login_redirect');
    
    const doNotShowUntil = localStorage.getItem('announcement_do_not_show_until');
    const now = new Date().getTime();
    
    if (!doNotShowUntil || now > parseInt(doNotShowUntil)) {
      setTimeout(() => {
        setShowAnnouncement(true);
      }, 500);
    } else {
      setTimeout(() => {
        navigate(redirect);
      }, 500);
    }
  };

  return (
    <>
      <AnnouncementModal
        visible={showAnnouncement}
        onClose={handleAnnouncementClose}
        onDoNotShowToday={handleDoNotShowToday}
      />
      
      <Modal
        title="设置账号密码"
        open={showPasswordModal}
        centered
        onOk={handleSetPassword}
        onCancel={handleSkipPasswordSetting}
        confirmLoading={settingPassword}
        okText="设置密码"
        cancelText="暂不设置"
        width={500}
      >
        <div style={{ marginBottom: 20 }}>
          <p>您已成功通过 Linux DO 授权登录！</p>
          <p>系统已为您自动生成默认密码，您可以选择设置自定义密码或继续使用默认密码。</p>
          {passwordStatus?.default_password && (
            <div style={{
              background: '#f0f2f5',
              padding: 12,
              borderRadius: 4,
              marginTop: 12
            }}>
              <strong>账号：</strong>{passwordStatus.username}<br/>
              <strong>默认密码：</strong><code style={{
                background: '#fff',
                padding: '2px 8px',
                borderRadius: 3,
                color: '#1890ff',
                fontSize: 14
              }}>{passwordStatus.default_password}</code>
            </div>
          )}
        </div>
        
        <div style={{ marginTop: 20 }}>
          <div style={{ marginBottom: 12 }}>
            <label>新密码（至少6个字符）：</label>
            <Input.Password
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="请输入新密码"
              style={{ marginTop: 4 }}
            />
          </div>
          <div>
            <label>确认密码：</label>
            <Input.Password
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="请再次输入密码"
              style={{ marginTop: 4 }}
            />
          </div>
        </div>
      </Modal>

      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      }}>
        <Result
          status="success"
          title="登录成功"
          subTitle={showPasswordModal ? "请设置账号密码..." : (showAnnouncement ? "欢迎使用..." : "正在跳转...")}
          style={{ background: 'white', padding: 40, borderRadius: 8 }}
        />
      </div>
    </>
  );
}