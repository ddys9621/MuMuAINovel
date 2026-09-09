import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutGrid,
  Settings,
  Puzzle,
  Users,
  PanelLeftClose,
  PanelLeft,
  BookOpen,
  Library,
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
      { icon: BookOpen, label: '拆书参考', path: '/book-dissect' },
      { icon: Library, label: '参考库', path: '/reference-packs' },
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
  // 根路径 `/` 也渲染项目列表，需让「我的项目」保持高亮
  const isRootProjects = useLocation().pathname === '/'

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 flex h-screen flex-col overflow-hidden border-r border-white/80 bg-white/55 backdrop-blur-2xl backdrop-saturate-150 shadow-[0_0_0_1px_rgba(15,43,96,0.04),20px_0_60px_-44px_rgba(15,43,96,0.35)] transition-all duration-200',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      <div className={cn('flex h-16 shrink-0 items-center gap-3 border-b border-surface-border/80 px-4', collapsed && 'justify-center px-0')}>
        <BrandLogo size="sm" />
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-tight text-content">HH小说创作</p>
            <p className="truncate text-[11px] text-content-tertiary">专业小说创作平台</p>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-2.5 py-5">
        {navGroups.map((group) => (
          <div key={group.label}>
            {!collapsed && (
              <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-[0.22em] text-content-tertiary">
                {group.label}
              </p>
            )}
            <ul className="space-y-1">
              {group.items.map((item) => {
                const forceActive = isRootProjects && item.path === '/projects'
                return (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    className={({ isActive }) =>
                      cn(
                        'group relative flex items-center gap-3 px-3 py-2.5 text-sm transition-all',
                        collapsed && 'justify-center px-0',
                        isActive || forceActive
                          ? 'bg-brand/10 font-medium text-brand'
                          : 'text-content-secondary hover:bg-white/70 hover:text-content'
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {(isActive || forceActive) && <span className="absolute inset-y-2 left-0 w-[3px] bg-brand" aria-hidden />}
                        <item.icon className="h-[18px] w-[18px] shrink-0" />
                        {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
                        {collapsed && (
                          <span className="hh-glass pointer-events-none absolute left-full ml-3 hidden whitespace-nowrap px-2.5 py-1.5 text-xs text-content group-hover:block">
                            {item.label}
                          </span>
                        )}
                      </>
                    )}
                  </NavLink>
                </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="shrink-0 border-t border-surface-border/80 p-2.5">
        <button
          onClick={onToggle}
          className={cn(
            'flex w-full items-center gap-3 px-3 py-2.5 text-sm text-content-secondary transition-colors hover:bg-white/70 hover:text-content',
            collapsed && 'justify-center px-0'
          )}
          title={collapsed ? '展开侧栏' : '收起侧栏'}
        >
          {collapsed ? (
            <PanelLeft className="h-[18px] w-[18px] shrink-0" />
          ) : (
            <>
              <PanelLeftClose className="h-[18px] w-[18px] shrink-0" />
              <span>收起侧栏</span>
            </>
          )}
        </button>
      </div>
    </aside>
  )
}
