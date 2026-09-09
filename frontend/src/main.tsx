import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ConfigProvider } from 'antd'
import { Toaster } from 'sonner'
import App from './App'
import './globals.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#007aff',
          colorText: '#0b1a33',
          colorTextSecondary: '#5f7090',
          colorTextTertiary: '#93a4be',
          colorBorder: '#d9e4f3',
          colorBorderSecondary: '#e8eff8',
          fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
          borderRadius: 0,
          borderRadiusXS: 0,
          borderRadiusSM: 0,
          borderRadiusLG: 0,
          borderRadiusOuter: 0,
        },
      }}
    >
      <Toaster
        position="top-center"
        richColors
        toastOptions={{
          style: { borderRadius: 0 },
          duration: 3000,
        }}
      />
      <App />
    </ConfigProvider>
  </StrictMode>,
)
