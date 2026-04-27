import { useState, useCallback } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { cn } from '@/lib/utils'

export function AppLayout() {
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem('sidebar-collapsed') === 'true'
  })

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev
      localStorage.setItem('sidebar-collapsed', String(next))
      return next
    })
  }, [])

  return (
    <div className="relative flex h-screen overflow-hidden bg-transparent">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,130,91,0.12),transparent_28%),radial-gradient(circle_at_bottom_right,rgba(255,202,133,0.14),transparent_26%)]" />

      {!collapsed && (
        <div
          className="fixed inset-0 z-30 bg-[#2d130d]/45 backdrop-blur-sm md:hidden"
          onClick={toggle}
        />
      )}

      <Sidebar collapsed={collapsed} onToggle={toggle} />

      <div
        className={cn(
          'relative z-10 flex flex-1 flex-col transition-all duration-200',
          collapsed ? 'ml-16' : 'ml-60',
          'max-md:ml-0'
        )}
      >
        <Header onMenuClick={toggle} />
        <main className="flex-1 overflow-y-auto px-4 pb-5 pt-4 md:px-6 md:pb-6 md:pt-5">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
