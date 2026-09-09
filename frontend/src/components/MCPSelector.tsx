/** MCP 插件选择器 - 用于向导/灵感模式选择 MCP 增强插件 */

import { useState, useEffect } from 'react'
import { Plug, Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import { mcpPluginApi } from '@/services/api'
import type { MCPPlugin } from '@/types'

export interface MCPSelectorValue {
  enable: boolean
  selected: string[]
}

interface MCPSelectorProps {
  value: MCPSelectorValue
  onChange: (value: MCPSelectorValue) => void
}

export function MCPSelector({ value, onChange }: MCPSelectorProps) {
  const [plugins, setPlugins] = useState<MCPPlugin[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    if (expanded && plugins.length === 0) {
      setLoading(true)
      mcpPluginApi.getPlugins({ enabled_only: true })
        .then(setPlugins)
        .catch(() => {})
        .finally(() => setLoading(false))
    }
  }, [expanded, plugins.length])

  const togglePlugin = (id: string) => {
    const next = value.selected.includes(id)
      ? value.selected.filter(s => s !== id)
      : [...value.selected, id]
    onChange({ ...value, selected: next })
  }

  return (
    <div className="hh-subpanel">
      <button
        type="button"
        onClick={() => {
          const nextExpanded = !expanded
          setExpanded(nextExpanded)
          if (!nextExpanded) {
            onChange({ enable: false, selected: [] })
          }
        }}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm transition-colors hover:bg-white/70"
      >
        <span className="flex items-center gap-2">
          <Plug className="h-4 w-4 text-content-secondary" />
          <span className="font-medium text-content">MCP 工具增强</span>
          {value.enable && value.selected.length > 0 && (
            <span className="hh-tag px-1.5 py-0.5 text-[11px] tabular-nums">{value.selected.length} 个插件</span>
          )}
        </span>
        {expanded ? <ChevronUp className="h-4 w-4 text-content-tertiary" /> : <ChevronDown className="h-4 w-4 text-content-tertiary" />}
      </button>

      {expanded && (
        <div className="space-y-2 border-t border-surface-border/80 px-4 py-3">
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={value.enable}
              onChange={e => onChange({ ...value, enable: e.target.checked })}
            />
            <span className="text-content-secondary">启用 MCP 工具增强生成</span>
          </label>

          {value.enable && (
            <div className="ml-6 space-y-1">
              {loading ? (
                <div className="flex items-center gap-2 py-1 text-xs text-content-secondary">
                  <Loader2 className="h-3 w-3 animate-spin text-brand" />加载插件列表...
                </div>
              ) : plugins.length === 0 ? (
                <p className="text-xs text-content-tertiary">暂无可用插件</p>
              ) : (
                plugins.map(p => (
                  <label key={p.id} className="flex cursor-pointer items-center gap-2 py-0.5 text-sm">
                    <input
                      type="checkbox"
                      checked={value.selected.includes(p.id)}
                      onChange={() => togglePlugin(p.id)}
                    />
                    <span className="truncate text-content">{p.display_name || p.plugin_name}</span>
                    {p.description && (
                      <span className="truncate text-xs text-content-tertiary">— {p.description}</span>
                    )}
                  </label>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
