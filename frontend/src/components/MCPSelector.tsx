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
    <div className="border border-surface-border rounded-card">
      <button
        type="button"
        onClick={() => {
          const nextExpanded = !expanded
          setExpanded(nextExpanded)
          if (!nextExpanded) {
            onChange({ enable: false, selected: [] })
          }
        }}
        className="w-full flex items-center justify-between px-3 py-2.5 text-sm hover:bg-surface-hover transition-colors rounded-card"
      >
        <div className="flex items-center gap-2">
          <Plug className="w-4 h-4 text-content-secondary" />
          <span className="text-content">MCP 工具增强</span>
          {value.enable && value.selected.length > 0 && (
            <span className="text-xs bg-brand/10 text-brand rounded px-1.5 py-0.5">
              {value.selected.length} 个插件
            </span>
          )}
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 text-content-secondary" /> : <ChevronDown className="w-4 h-4 text-content-secondary" />}
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-surface-border pt-2">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={value.enable}
              onChange={e => onChange({ ...value, enable: e.target.checked })}
              className="rounded"
            />
            <span className="text-content-secondary">启用 MCP 工具增强生成</span>
          </label>

          {value.enable && (
            <div className="space-y-1 ml-5">
              {loading ? (
                <div className="flex items-center gap-2 text-xs text-content-secondary py-1">
                  <Loader2 className="w-3 h-3 animate-spin" />加载插件列表...
                </div>
              ) : plugins.length === 0 ? (
                <p className="text-xs text-content-tertiary">暂无可用插件</p>
              ) : (
                plugins.map(p => (
                  <label key={p.id} className="flex items-center gap-2 text-sm cursor-pointer py-0.5">
                    <input
                      type="checkbox"
                      checked={value.selected.includes(p.id)}
                      onChange={() => togglePlugin(p.id)}
                      className="rounded"
                    />
                    <span className="text-content truncate">{p.display_name || p.plugin_name}</span>
                    {p.description && (
                      <span className="text-xs text-content-tertiary truncate">— {p.description}</span>
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
