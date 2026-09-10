/** MCP 商城 - 内置精选目录浏览 + 一键安装（数据来自后端 /api/mcp/marketplace） */

import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react'
import { BadgeCheck, Check, Download, ExternalLink, Eye, EyeOff, Globe, Loader2, MapPin, Search, Sparkles, Store, TriangleAlert } from 'lucide-react'
import { toast } from 'sonner'
import { mcpMarketplaceApi } from '@/services/api'
import { Modal } from '@/components/ui/Modal'
import { cn } from '@/lib/utils'
import type { MCPMarketplaceCategory, MCPMarketplaceItem, MCPPlugin } from '@/types'

interface MCPMarketplaceProps {
  /** 安装成功后回调（父组件刷新「我的插件」列表） */
  onInstalled?: (plugin: MCPPlugin) => void
}

const ALL = 'all'

/** 用 CSS 遮罩代替 type=password（非标准属性，Chrome / Edge / Safari 支持；Firefox 明文显示） */
const SECRET_MASK_STYLE = { WebkitTextSecurity: 'disc' } as unknown as CSSProperties

export function MCPMarketplace({ onInstalled }: MCPMarketplaceProps) {
  const [categories, setCategories] = useState<MCPMarketplaceCategory[]>([])
  const [items, setItems] = useState<MCPMarketplaceItem[]>([])
  const [loading, setLoading] = useState(false)
  const [category, setCategory] = useState<string>(ALL)
  const [query, setQuery] = useState('')

  // 安装弹窗
  const [installing, setInstalling] = useState<MCPMarketplaceItem | null>(null)
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [revealed, setRevealed] = useState<Record<string, boolean>>({})
  const [submitting, setSubmitting] = useState(false)

  const fetchCatalog = useCallback(async () => {
    try {
      setLoading(true)
      const data = await mcpMarketplaceApi.list()
      setCategories(data.categories)
      setItems(data.items)
    } catch { /* api 层已 toast */ } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchCatalog() }, [fetchCatalog])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return items.filter(item => {
      if (category !== ALL && item.category !== category) return false
      if (!q) return true
      return [item.name, item.description, item.pricing, ...item.tags].some(s => s.toLowerCase().includes(q))
    })
  }, [items, category, query])

  const countByCategory = useMemo(() => {
    const m: Record<string, number> = {}
    items.forEach(i => { m[i.category] = (m[i.category] || 0) + 1 })
    return m
  }, [items])

  const submitInstall = useCallback(async (item: MCPMarketplaceItem, values: Record<string, string>) => {
    try {
      setSubmitting(true)
      const plugin = await mcpMarketplaceApi.install(item.id, { inputs: values, enabled: true })
      setItems(prev => prev.map(i => i.id === item.id ? { ...i, installed_plugin_id: plugin.id, installed_status: plugin.status } : i))
      toast.success(`${item.installed_plugin_id ? '已重新安装' : '已安装'} ${item.name}${plugin.status === 'active' ? '' : '（加载失败，请到「我的插件」测试连接）'}`)
      onInstalled?.(plugin)
      setInstalling(null)
    } catch { /* api 层已 toast */ } finally { setSubmitting(false) }
  }, [onInstalled])

  const handleInstallClick = (item: MCPMarketplaceItem) => {
    if (item.inputs.length === 0) {
      submitInstall(item, {})
      return
    }
    setInputs(Object.fromEntries(item.inputs.map(i => [i.key, ''])))
    setRevealed({})
    setInstalling(item)
  }

  const missingRequired = installing ? installing.inputs.filter(i => i.required && !(inputs[i.key] || '').trim()) : []

  const inputCls = 'w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors'

  return (
    <div className="space-y-4">
      {/* 说明 + 搜索 */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs text-content-secondary flex items-center gap-1.5">
          <Store className="w-3.5 h-3.5 shrink-0" />
          精选适合写小说的远程 MCP 服务，填好 Key 即可一键安装；已安装的可在「我的插件」里测试、编辑、删除
        </p>
        <div className="relative sm:w-64">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-content-tertiary" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="搜索名称 / 用途 / 标签"
            className={`${inputCls} pl-8`}
          />
        </div>
      </div>

      {/* 分类 chips */}
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => setCategory(ALL)} className={cn('hh-chip', category === ALL && 'hh-chip--active')}>
          全部 <span className="tabular-nums opacity-70">{items.length}</span>
        </button>
        {categories.map(c => (
          <button key={c.id} type="button" onClick={() => setCategory(c.id)} className={cn('hh-chip', category === c.id && 'hh-chip--active')}>
            {c.label} <span className="tabular-nums opacity-70">{countByCategory[c.id] || 0}</span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-content-secondary" /></div>
      ) : visible.length === 0 ? (
        <div className="text-center py-12 text-content-secondary text-sm">
          <Store className="w-8 h-8 mx-auto mb-2 opacity-40" />
          没有匹配的服务
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map(item => (
            <MarketplaceCard key={item.id} item={item} busy={submitting && installing?.id === item.id} onInstall={() => handleInstallClick(item)} />
          ))}
        </div>
      )}

      {/* 安装弹窗：填写 API Key 等 */}
      {installing && (
        <Modal
          title={`${installing.installed_plugin_id ? '重新安装' : '安装'} ${installing.name}`}
          onClose={() => !submitting && setInstalling(null)}
          size="lg"
          footer={(
            <>
              <button onClick={() => setInstalling(null)} disabled={submitting} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm disabled:opacity-50">取消</button>
              <button
                onClick={() => submitInstall(installing, inputs)}
                disabled={submitting || missingRequired.length > 0}
                className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                {installing.installed_plugin_id ? '重新安装' : '安装'}
              </button>
            </>
          )}
        >
          <div className="space-y-4">
            <p className="text-xs text-content-secondary">{installing.description}</p>
            {installing.inputs.map(field => (
              <div key={field.key}>
                <label className="block text-sm text-content-secondary mb-1">
                  {field.label}{field.required && <span className="text-red-500 ml-0.5">*</span>}
                </label>
                <div className="relative">
                  {/* 不用 type=password：浏览器会把它当登录表单，把本站保存的账号密码自动灌进 SecretId / Key 里。
                      用 text + -webkit-text-security 遮罩，密码管理器不会介入 */}
                  <input
                    type="text"
                    name={`mcp-marketplace-${installing.id}-${field.key}`}
                    value={inputs[field.key] || ''}
                    onChange={e => setInputs(prev => ({ ...prev, [field.key]: e.target.value }))}
                    placeholder={field.placeholder || (field.required ? '' : '可留空')}
                    autoComplete="off"
                    autoCorrect="off"
                    autoCapitalize="off"
                    spellCheck={false}
                    data-lpignore="true"
                    data-1p-ignore="true"
                    data-form-type="other"
                    style={field.secret && !revealed[field.key] ? SECRET_MASK_STYLE : undefined}
                    className={`${inputCls} font-mono ${field.secret ? 'pr-9' : ''}`}
                  />
                  {field.secret && (
                    <button
                      type="button"
                      onClick={() => setRevealed(prev => ({ ...prev, [field.key]: !prev[field.key] }))}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-content-tertiary hover:text-content"
                      title={revealed[field.key] ? '隐藏' : '显示'}
                    >
                      {revealed[field.key] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  )}
                </div>
                {(field.help_text || field.help_url) && (
                  <p className="mt-1 text-xs text-content-tertiary flex flex-wrap items-center gap-x-2">
                    {field.help_text && <span>{field.help_text}</span>}
                    {field.help_url && (
                      <a href={field.help_url} target="_blank" rel="noreferrer" className="text-brand hover:underline inline-flex items-center gap-0.5">
                        {field.help_label || '获取 Key'} <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </p>
                )}
              </div>
            ))}
            {installing.notes && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-btn px-3 py-2 flex items-start gap-1.5">
                <TriangleAlert className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                <span>{installing.notes}</span>
              </p>
            )}
            <p className="text-[11px] text-content-tertiary break-all">
              服务地址：<span className="font-mono">{installing.server_url}</span>
            </p>
          </div>
        </Modal>
      )}
    </div>
  )
}

interface MarketplaceCardProps {
  item: MCPMarketplaceItem
  busy: boolean
  onInstall: () => void
}

function MarketplaceCard({ item, busy, onInstall }: MarketplaceCardProps) {
  const installed = !!item.installed_plugin_id
  const needsKey = item.inputs.some(i => i.required)
  return (
    <div className="bg-white border border-surface-border rounded-card p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <h3 className="text-sm font-semibold text-content truncate">{item.name}</h3>
            {item.recommended && (
              <span className="hh-tag px-1.5 py-0.5 text-[11px]"><Sparkles className="w-3 h-3" />推荐</span>
            )}
          </div>
          <p className="text-xs text-content-secondary flex items-center gap-1.5 flex-wrap mt-0.5">
            <span className="inline-flex items-center gap-0.5">
              {item.official ? <BadgeCheck className="w-3 h-3 text-brand" /> : null}
              {item.official ? '官方' : '社区'}
            </span>
            <span>·</span>
            <span className="inline-flex items-center gap-0.5">
              {item.region === 'cn' ? <MapPin className="w-3 h-3" /> : <Globe className="w-3 h-3" />}
              {item.region === 'cn' ? '国内直连' : '海外服务'}
            </span>
            <span>·</span>
            <span>{item.transport === 'sse' ? 'SSE' : 'HTTP'}</span>
          </p>
        </div>
        {installed && (
          <span className={cn(
            'text-xs px-1.5 py-0.5 rounded shrink-0 inline-flex items-center gap-1',
            item.installed_status === 'active' ? 'bg-green-100 text-green-700' : item.installed_status === 'error' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600',
          )}>
            <Check className="w-3 h-3" />已安装
          </span>
        )}
      </div>

      <p className="text-xs text-content-secondary leading-5 line-clamp-3">{item.description}</p>

      {item.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {item.tags.map(t => (
            <span key={t} className="text-[11px] px-1.5 py-0.5 bg-surface-hover text-content-secondary rounded">{t}</span>
          ))}
        </div>
      )}

      <p className="text-xs text-content-secondary"><span className="text-content-tertiary">费用：</span>{item.pricing}</p>

      {item.notes && (
        <p className="text-[11px] text-amber-700 flex items-start gap-1">
          <TriangleAlert className="w-3 h-3 mt-0.5 shrink-0" />
          <span className="line-clamp-2">{item.notes}</span>
        </p>
      )}

      <div className="flex items-center justify-between pt-2 mt-auto border-t border-surface-border">
        <a href={item.homepage} target="_blank" rel="noreferrer" className="text-xs text-content-secondary hover:text-brand inline-flex items-center gap-1" title={item.homepage}>
          <ExternalLink className="w-3.5 h-3.5" />文档
        </a>
        <button
          onClick={onInstall}
          disabled={busy}
          className={cn(
            'rounded-btn px-3 py-1.5 text-xs font-medium transition-colors inline-flex items-center gap-1.5 disabled:opacity-50',
            installed
              ? 'border border-surface-border text-content-secondary hover:bg-surface-hover'
              : 'bg-brand hover:bg-brand-600 text-white',
          )}
          title={needsKey ? '需要填写 API Key' : '无需配置，直接安装'}
        >
          {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
          {installed ? '重新安装' : needsKey ? '填 Key 安装' : '一键安装'}
        </button>
      </div>
    </div>
  )
}
