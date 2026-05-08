import { NavLink } from 'react-router-dom'
import {
  LayoutGrid,
  Settings,
  Puzzle,
  Users,
  PanelLeftClose,
  PanelLeft,
  Sparkles,
  Flame,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { BrandLogo } from '@/components/ui/BrandLogo'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

const navGroups = [
  {
    label: '创作台',
    items: [
      { icon: LayoutGrid, label: '我的项目', path: '/projects' },
      { icon: Settings, label: '设置', path: '/settings' },
      { icon: Puzzle, label: 'MCP 插件', path: '/mcp-plugins' },
    ],
  },
  {
    label: '管理台',
    items: [
      { icon: Users, label: '用户管理', path: '/user-management' },
    ],
  },
]

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 flex h-screen flex-col overflow-hidden border-r border-white/10 bg-[linear-gradient(180deg,#3b1d16_0%,#2d140f_38%,#24110d_100%)] shadow-[20px_0_60px_-44px_rgba(34,17,11,0.85)] transition-all duration-200',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      <div className="relative border-b border-white/10 px-3 pb-4 pt-4">
        <div className="absolute inset-x-6 top-0 h-24 rounded-full bg-brand/15 blur-3xl" />
        <div className={cn('relative flex items-center gap-3 rounded-[22px] border border-white/10 bg-white/5 px-3 py-3 backdrop-blur-sm', collapsed && 'justify-center px-0')}>
          <BrandLogo size="md" />
          {!collapsed && (
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold tracking-wide text-white">HH小说创作</p>
              <p className="mt-0.5 text-xs text-sidebar-text/85">专业小说创作平台</p>
            </div>
          )}
        </div>

        {!collapsed && (
          <div className="hh-sidebar-note mt-4">
            <div className="flex items-center gap-2 text-xs font-medium text-white/90">
              <Sparkles className="h-3.5 w-3.5 text-brand-200" />
              今日重点
            </div>
            <p className="mt-2 text-sm leading-6 text-white/95">
              先确认设定与角色信息，再继续推进章节写作。
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <span className="rounded-pill bg-white/10 px-2.5 py-1 text-[11px] text-sidebar-text/90">设定检查</span>
              <span className="rounded-pill bg-white/10 px-2.5 py-1 text-[11px] text-sidebar-text/90">角色同步</span>
              <span className="rounded-pill bg-white/10 px-2.5 py-1 text-[11px] text-sidebar-text/90">章节推进</span>
            </div>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-2 py-4">
        {navGroups.map((group) => (
          <div key={group.label}>
            {!collapsed && (
              <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-sidebar-text/55">
                {group.label}
              </p>
            )}
            <ul className="space-y-1.5">
              {group.items.map((item) => (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    className={({ isActive }) =>
                      cn(
                        'group relative flex items-center gap-3 rounded-[18px] px-3 py-3 text-sm transition-all',
                        collapsed && 'justify-center px-0',
                        isActive
                          ? 'bg-[linear-gradient(90deg,rgba(255,113,72,0.24),rgba(255,189,112,0.16))] text-white shadow-[0_18px_40px_-30px_rgba(255,113,72,0.95)] ring-1 ring-white/10'
                          : 'text-sidebar-text hover:bg-white/8 hover:text-white'
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <span className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl transition-all', isActive ? 'bg-white/14 text-white' : 'bg-white/5 text-sidebar-text group-hover:bg-white/10 group-hover:text-white')}>
                          <item.icon className="h-[18px] w-[18px]" />
                        </span>
                        {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
                        {!collapsed && isActive && <Flame className="h-4 w-4 text-gold" />}
                        {collapsed && (
                          <span className="pointer-events-none absolute left-full ml-2 hidden whitespace-nowrap rounded-xl border border-white/10 bg-[#23120f] px-2.5 py-1.5 text-xs text-white shadow-xl group-hover:block">
                            {item.label}
                          </span>
                        )}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="shrink-0 border-t border-white/10 px-2 pb-3 pt-2">
        {!collapsed && (
          <div className="mb-2 rounded-[18px] border border-white/10 bg-white/5 px-3 py-2 text-xs text-sidebar-text">
            <div className="flex items-center gap-2 text-white/90">
              <Flame className="h-3.5 w-3.5 text-gold" />
              创作状态已就绪
            </div>
          </div>
        )}
        <button
          onClick={onToggle}
          className={cn(
            'flex w-full items-center gap-3 rounded-[18px] px-3 py-3 text-sm text-sidebar-text transition-colors hover:bg-white/8 hover:text-white',
            collapsed && 'justify-center px-0'
          )}
        >
          {collapsed ? (
            <PanelLeft className="h-5 w-5 shrink-0" />
          ) : (
            <>
              <PanelLeftClose className="h-5 w-5 shrink-0" />
              <span>收起侧栏</span>
            </>
          )}
        </button>
      </div>
    </aside>
  )
}
