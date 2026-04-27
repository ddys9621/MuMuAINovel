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
