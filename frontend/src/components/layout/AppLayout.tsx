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
    <div className="relative flex h-screen overflow-hidden">
      <div className="hh-orb -left-40 -top-40 h-[520px] w-[520px] bg-brand/15 animate-float-soft" />
      <div className="hh-orb -bottom-48 right-[-120px] h-[560px] w-[560px] bg-brand-400/15" />

      {!collapsed && (
        <div
          className="fixed inset-0 z-30 bg-content/25 backdrop-blur-sm md:hidden"
          onClick={toggle}
        />
      )}

      <Sidebar collapsed={collapsed} onToggle={toggle} />

      <div
        className={cn(
          'relative flex flex-1 flex-col transition-all duration-200',
          collapsed ? 'ml-16' : 'ml-60',
          'max-md:ml-0'
        )}
      >
        <Header onMenuClick={toggle} />
        <main className="flex-1 overflow-y-auto px-4 pb-8 pt-6 md:px-8 md:pt-8">
          <div className="mx-auto w-full max-w-[1400px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
