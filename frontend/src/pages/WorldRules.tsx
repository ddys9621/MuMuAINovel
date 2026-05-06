import { useEffect, useState, useCallback } from 'react'
import { Plus, Pencil, Trash2, Shield, Map, Sword, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useStore } from '@/store/index'
import { worldRulesApi } from '@/services/api'
import { Modal } from '@/components/ui/Modal'
import type { WorldRule, WorldRuleCreate, WorldRuleUpdate } from '@/types'

const CATEGORIES = [
  { value: 'cultivation_realm' as const, label: '修炼境界', icon: Shield },
  { value: 'equipment_template' as const, label: '装备模板', icon: Sword },
  { value: 'map_location' as const, label: '地图位置', icon: Map },
]

type Category = WorldRule['category']

export default function WorldRules() {
  const { currentProject } = useStore()
  const [rules, setRules] = useState<WorldRule[]>([])
  const [loading, setLoading] = useState(false)
  const [activeCategory, setActiveCategory] = useState<Category | 'all'>('all')
  const [showModal, setShowModal] = useState(false)
  const [editingRule, setEditingRule] = useState<WorldRule | null>(null)

  // 表单
  const [form, setForm] = useState<WorldRuleCreate>({
    category: 'cultivation_realm',
    key: '',
    name: '',
    order_index: 0,
    summary: '',
    details: '',
  })

  const fetchRules = useCallback(async () => {
    if (!currentProject?.id) return
    try {
      setLoading(true)
      const cat = activeCategory === 'all' ? undefined : activeCategory
      const res = await worldRulesApi.list(currentProject.id, cat)
      setRules(res.items)
    } catch {
      // api 层已 toast
    } finally {
      setLoading(false)
    }
  }, [currentProject?.id, activeCategory])

  useEffect(() => { fetchRules() }, [fetchRules])

  const openCreate = () => {
    setEditingRule(null)
    setForm({ category: 'cultivation_realm', key: '', name: '', order_index: rules.length, summary: '', details: '' })
    setShowModal(true)
  }

  const openEdit = (rule: WorldRule) => {
    setEditingRule(rule)
    setForm({ category: rule.category, key: rule.key, name: rule.name, order_index: rule.order_index, summary: rule.summary || '', details: rule.details || '' })
    setShowModal(true)
  }

  const handleSubmit = async () => {
    if (!currentProject?.id) return
    if (!form.key.trim() || !form.name.trim()) {
      toast.error('请填写标识和名称')
      return
    }
    try {
      if (editingRule) {
        const data: WorldRuleUpdate = { ...form }
        const updated = await worldRulesApi.update(editingRule.id, data)
        setRules(prev => prev.map(r => r.id === updated.id ? updated : r))
        toast.success('规则已更新')
      } else {
        const created = await worldRulesApi.create(currentProject.id, form)
        setRules(prev => [...prev, created])
        toast.success('规则已创建')
      }
      setShowModal(false)
    } catch {
      // api 层已 toast
    }
  }

  const handleDelete = async (rule: WorldRule) => {
    if (!confirm(`确定删除「${rule.name}」？`)) return
    try {
      await worldRulesApi.delete(rule.id)
      setRules(prev => prev.filter(r => r.id !== rule.id))
      toast.success('规则已删除')
    } catch {
      // api 层已 toast
    }
  }

  const filtered = activeCategory === 'all' ? rules : rules.filter(r => r.category === activeCategory)
  const getCategoryLabel = (cat: Category) => CATEGORIES.find(c => c.value === cat)?.label || cat

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-content">世界规则</h1>
        <button onClick={openCreate} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5">
          <Plus className="w-4 h-4" />
          添加规则
        </button>
      </div>

      {/* 分类筛选 */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setActiveCategory('all')}
          className={`rounded-btn px-3 py-1.5 text-sm transition-colors ${activeCategory === 'all' ? 'bg-brand text-white' : 'border border-surface-border text-content-secondary hover:bg-surface-hover'}`}
        >
          全部
        </button>
        {CATEGORIES.map(cat => (
          <button
            key={cat.value}
            onClick={() => setActiveCategory(cat.value)}
            className={`rounded-btn px-3 py-1.5 text-sm transition-colors inline-flex items-center gap-1.5 ${activeCategory === cat.value ? 'bg-brand text-white' : 'border border-surface-border text-content-secondary hover:bg-surface-hover'}`}
          >
            <cat.icon className="w-3.5 h-3.5" />
            {cat.label}
          </button>
        ))}
      </div>

      {/* 列表 */}
      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-content-secondary" /></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-content-secondary text-sm">暂无规则，点击上方按钮添加</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map(rule => (
            <div key={rule.id} className="bg-white border border-surface-border rounded-card p-4 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="text-xs text-content-secondary bg-surface-hover rounded px-1.5 py-0.5">{getCategoryLabel(rule.category)}</span>
                  <h3 className="text-sm font-semibold text-content mt-1">{rule.name}</h3>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => openEdit(rule)} className="p-1.5 rounded hover:bg-surface-hover text-content-secondary transition-colors"><Pencil className="w-3.5 h-3.5" /></button>
                  <button onClick={() => handleDelete(rule)} className="p-1.5 rounded hover:bg-red-50 text-content-secondary hover:text-red-500 transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
              {rule.summary && <p className="text-xs text-content-secondary line-clamp-2">{rule.summary}</p>}
              {rule.details && <p className="text-xs text-content-secondary/70 line-clamp-3">{rule.details}</p>}
            </div>
          ))}
        </div>
      )}

      {/* 弹窗 */}
      {showModal && (
        <Modal
          title={editingRule ? '编辑规则' : '添加规则'}
          onClose={() => setShowModal(false)}
          size="xl"
          footer={(
            <>
              <button onClick={() => setShowModal(false)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm">取消</button>
              <button onClick={handleSubmit} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors">确定</button>
            </>
          )}
        >
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-content-secondary mb-1">分类</label>
              <select
                value={form.category}
                onChange={e => setForm(f => ({ ...f, category: e.target.value as Category }))}
                className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors"
              >
                {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">标识 (key)</label>
              <input value={form.key} onChange={e => setForm(f => ({ ...f, key: e.target.value }))} placeholder="如 qi_refining" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">名称</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder="如 炼气期" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">摘要</label>
              <input value={form.summary || ''} onChange={e => setForm(f => ({ ...f, summary: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">详情</label>
              <textarea value={form.details || ''} onChange={e => setForm(f => ({ ...f, details: e.target.value }))} rows={3} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors resize-none" />
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
