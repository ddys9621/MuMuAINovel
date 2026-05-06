import { useEffect, useState, useCallback } from 'react'
import { Plus, Pencil, Trash2, Star, Palette, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useStore } from '@/store/index'
import { writingStyleApi } from '@/services/api'
import { Modal } from '@/components/ui/Modal'
import type { WritingStyle, PresetStyle, WritingStyleCreate, WritingStyleUpdate } from '@/types'

export default function WritingStyles() {
  const { currentProject } = useStore()
  const [styles, setStyles] = useState<WritingStyle[]>([])
  const [presets, setPresets] = useState<PresetStyle[]>([])
  const [loading, setLoading] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [editingStyle, setEditingStyle] = useState<WritingStyle | null>(null)
  const [form, setForm] = useState({ name: '', description: '', prompt_content: '', style_type: 'custom' as 'preset' | 'custom', preset_id: '' })

  const fetchData = useCallback(async () => {
    if (!currentProject?.id) return
    try {
      setLoading(true)
      const [stylesRes, presetsRes] = await Promise.all([
        writingStyleApi.getProjectStyles(currentProject.id),
        writingStyleApi.getPresetStyles(),
      ])
      setStyles(stylesRes.styles)
      setPresets(presetsRes)
    } catch { /* api 层已 toast */ } finally { setLoading(false) }
  }, [currentProject?.id])

  useEffect(() => { fetchData() }, [fetchData])

  const openCreate = () => {
    setEditingStyle(null)
    setForm({ name: '', description: '', prompt_content: '', style_type: 'custom', preset_id: '' })
    setShowModal(true)
  }

  const openEdit = (s: WritingStyle) => {
    setEditingStyle(s)
    setForm({ name: s.name, description: s.description || '', prompt_content: s.prompt_content, style_type: s.style_type, preset_id: s.preset_id || '' })
    setShowModal(true)
  }

  const handlePresetSelect = (presetId: string) => {
    const preset = presets.find(p => p.id === presetId)
    if (preset) {
      setForm(f => ({ ...f, preset_id: presetId, name: preset.name, description: preset.description, prompt_content: preset.prompt_content, style_type: 'preset' }))
    }
  }

  const handleSubmit = async () => {
    if (!currentProject?.id) return
    if (!form.name.trim()) { toast.error('请填写名称'); return }
    try {
      if (editingStyle) {
        const data: WritingStyleUpdate = { name: form.name, description: form.description, prompt_content: form.prompt_content }
        const updated = await writingStyleApi.updateStyle(editingStyle.id, data)
        setStyles(prev => prev.map(s => s.id === updated.id ? updated : s))
        toast.success('风格已更新')
      } else {
        const data: WritingStyleCreate = { project_id: currentProject.id, name: form.name, description: form.description, prompt_content: form.prompt_content, style_type: form.style_type, preset_id: form.preset_id || undefined }
        const created = await writingStyleApi.createStyle(data)
        setStyles(prev => [...prev, created])
        toast.success('风格已创建')
      }
      setShowModal(false)
    } catch { /* api 层已 toast */ }
  }

  const handleDelete = async (s: WritingStyle) => {
    if (!confirm(`确定删除「${s.name}」？`)) return
    try {
      await writingStyleApi.deleteStyle(s.id)
      setStyles(prev => prev.filter(x => x.id !== s.id))
      toast.success('风格已删除')
    } catch { /* api 层已 toast */ }
  }

  const handleSetDefault = async (s: WritingStyle) => {
    if (!currentProject?.id) return
    try {
      await writingStyleApi.setDefaultStyle(s.id, currentProject.id)
      setStyles(prev => prev.map(x => ({ ...x, is_default: x.id === s.id })))
      toast.success(`已将「${s.name}」设为默认风格`)
    } catch { /* api 层已 toast */ }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-content">写作风格</h1>
        <button onClick={openCreate} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5">
          <Plus className="w-4 h-4" />
          添加风格
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-content-secondary" /></div>
      ) : styles.length === 0 ? (
        <div className="text-center py-12 text-content-secondary text-sm">
          <Palette className="w-8 h-8 mx-auto mb-2 opacity-40" />
          暂无风格，点击上方按钮添加
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {styles.map(s => (
            <div key={s.id} className={`bg-white border rounded-card p-4 space-y-2 ${s.is_default ? 'border-brand' : 'border-surface-border'}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-1.5">
                    <h3 className="text-sm font-semibold text-content">{s.name}</h3>
                    {s.is_default && <Star className="w-3.5 h-3.5 text-brand fill-brand" />}
                  </div>
                  <span className="text-xs text-content-secondary">{s.style_type === 'preset' ? '预设' : '自定义'}</span>
                </div>
                <div className="flex gap-1 shrink-0">
                  {!s.is_default && (
                    <button onClick={() => handleSetDefault(s)} title="设为默认" className="p-1.5 rounded hover:bg-surface-hover text-content-secondary transition-colors"><Star className="w-3.5 h-3.5" /></button>
                  )}
                  <button onClick={() => openEdit(s)} className="p-1.5 rounded hover:bg-surface-hover text-content-secondary transition-colors"><Pencil className="w-3.5 h-3.5" /></button>
                  <button onClick={() => handleDelete(s)} className="p-1.5 rounded hover:bg-red-50 text-content-secondary hover:text-red-500 transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
              {s.description && <p className="text-xs text-content-secondary line-clamp-2">{s.description}</p>}
              <p className="text-xs text-content-secondary/70 line-clamp-3 font-mono">{s.prompt_content}</p>
            </div>
          ))}
        </div>
      )}

      {/* 弹窗 */}
      {showModal && (
        <Modal
          title={editingStyle ? '编辑风格' : '添加风格'}
          onClose={() => setShowModal(false)}
          size="xl"
          footer={(
            <>
              <button onClick={() => setShowModal(false)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm">取消</button>
              <button onClick={handleSubmit} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors">确定</button>
            </>
          )}
        >
          {/* 预设选择 */}
          {!editingStyle && presets.length > 0 && (
            <div className="mb-3">
              <label className="block text-sm text-content-secondary mb-1">从预设创建</label>
              <select
                value={form.preset_id}
                onChange={e => handlePresetSelect(e.target.value)}
                className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors"
              >
                <option value="">自定义风格</option>
                {presets.map(p => <option key={p.id} value={p.id}>{p.name} — {p.description}</option>)}
              </select>
            </div>
          )}

          <div className="space-y-3">
            <div>
              <label className="block text-sm text-content-secondary mb-1">名称</label>
              <input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">描述</label>
              <input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">Prompt 内容</label>
              <textarea value={form.prompt_content} onChange={e => setForm(f => ({ ...f, prompt_content: e.target.value }))} rows={6} className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors resize-none font-mono" />
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
