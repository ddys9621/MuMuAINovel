import { useEffect, useState, useCallback } from 'react'
import { GitBranch, Plus, Pencil, Trash2, Loader2, Heart, Swords, Users, Handshake, Minus } from 'lucide-react'
import { toast } from 'sonner'
import { useStore } from '@/store/index'
import { relationshipApi, characterApi } from '@/services/api'
import { Modal } from '@/components/ui/Modal'
import type { Character } from '@/types'

/** 后端 RelationshipTypeResponse */
interface RelationshipTypeItem {
  id: number
  name: string
  category: string
  reverse_name?: string
  intimacy_range?: string
  icon?: string
  description?: string
}

/** 后端返回的关系记录 */
interface RelationshipItem {
  id: string
  project_id: string
  character_from_id: string
  character_to_id: string
  relationship_type_id?: number
  relationship_name?: string
  intimacy_level: number
  status: string
  description?: string
}

/** 表单状态 */
interface RelationshipForm {
  character_from_id: string
  character_to_id: string
  relationship_type_id: number | ''
  relationship_name: string
  intimacy_level: number
  status: string
  description: string
}

const CATEGORY_STYLES: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
  friendly:  { bg: 'bg-green-100', text: 'text-green-700', icon: <Handshake className="w-3.5 h-3.5" /> },
  hostile:   { bg: 'bg-red-100',   text: 'text-red-700',   icon: <Swords className="w-3.5 h-3.5" /> },
  neutral:   { bg: 'bg-gray-100',  text: 'text-gray-600',  icon: <Minus className="w-3.5 h-3.5" /> },
  romantic:  { bg: 'bg-pink-100',  text: 'text-pink-700',  icon: <Heart className="w-3.5 h-3.5" /> },
  family:    { bg: 'bg-blue-100',  text: 'text-blue-700',  icon: <Users className="w-3.5 h-3.5" /> },
}
const DEFAULT_STYLE = { bg: 'bg-gray-100', text: 'text-gray-600', icon: <GitBranch className="w-3.5 h-3.5" /> }

const STATUS_OPTIONS = [
  { value: 'active', label: '进行中' },
  { value: 'broken', label: '已破裂' },
  { value: 'past', label: '已结束' },
  { value: 'complicated', label: '复杂' },
]

const emptyForm: RelationshipForm = {
  character_from_id: '',
  character_to_id: '',
  relationship_type_id: '',
  relationship_name: '',
  intimacy_level: 50,
  status: 'active',
  description: '',
}

export default function Relationships() {
  const { currentProject } = useStore()

  const [relationships, setRelationships] = useState<RelationshipItem[]>([])
  const [characters, setCharacters] = useState<Character[]>([])
  const [types, setTypes] = useState<RelationshipTypeItem[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  const [showModal, setShowModal] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<RelationshipForm>(emptyForm)
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)

  const projectId = currentProject?.id

  const fetchData = useCallback(async () => {
    if (!projectId) return
    try {
      setLoading(true)
      const [rels, chars, typeList] = await Promise.all([
        relationshipApi.getProjectRelationships(projectId),
        characterApi.getCharacters(projectId),
        relationshipApi.getTypes(),
      ])
      setRelationships(rels as unknown as RelationshipItem[])
      setCharacters(Array.isArray(chars) ? chars : [])
      setTypes(Array.isArray(typeList) ? typeList : [])
    } catch {
      /* api 层已 toast */
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => { fetchData() }, [fetchData])

  const charMap = new Map(characters.filter(c => !c.is_organization).map(c => [c.id, c]))
  const typeMap = new Map(types.map(t => [t.id, t]))

  const getCharName = (id: string) => charMap.get(id)?.name ?? '未知角色'
  const getTypeName = (typeId?: number) => {
    if (typeId == null) return '未分类'
    return typeMap.get(typeId)?.name ?? '未知类型'
  }
  const getTypeStyle = (typeId?: number) => {
    if (typeId == null) return DEFAULT_STYLE
    const t = typeMap.get(typeId)
    if (!t) return DEFAULT_STYLE
    return CATEGORY_STYLES[t.category] ?? DEFAULT_STYLE
  }

  const openCreate = () => {
    setEditingId(null)
    setForm(emptyForm)
    setShowModal(true)
  }

  const openEdit = (rel: RelationshipItem) => {
    setEditingId(rel.id)
    setForm({
      character_from_id: rel.character_from_id,
      character_to_id: rel.character_to_id,
      relationship_type_id: rel.relationship_type_id ?? '',
      relationship_name: rel.relationship_name ?? '',
      intimacy_level: rel.intimacy_level ?? 50,
      status: rel.status ?? 'active',
      description: rel.description ?? '',
    })
    setShowModal(true)
  }

  const closeModal = () => {
    setShowModal(false)
    setEditingId(null)
    setForm(emptyForm)
  }

  const handleSave = async () => {
    if (!projectId) return
    if (!form.character_from_id || !form.character_to_id) {
      toast.error('请选择角色A和角色B')
      return
    }
    if (form.character_from_id === form.character_to_id) {
      toast.error('角色A和角色B不能相同')
      return
    }
    try {
      setSaving(true)
      if (editingId) {
        await relationshipApi.updateRelationship(editingId, {
          relationship_type_id: form.relationship_type_id === '' ? undefined : form.relationship_type_id,
          relationship_name: form.relationship_name || undefined,
          intimacy_level: form.intimacy_level,
          status: form.status,
          description: form.description || undefined,
        })
        toast.success('关系已更新')
      } else {
        await relationshipApi.createRelationship({
          project_id: projectId,
          character_from_id: form.character_from_id,
          character_to_id: form.character_to_id,
          relationship_type_id: form.relationship_type_id === '' ? undefined : form.relationship_type_id,
          relationship_name: form.relationship_name || undefined,
          intimacy_level: form.intimacy_level,
          status: form.status,
          description: form.description || undefined,
        })
        toast.success('关系已创建')
      }
      closeModal()
      fetchData()
    } catch {
      /* api 层已 toast */
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await relationshipApi.deleteRelationship(id)
      toast.success('关系已删除')
      setDeleteConfirmId(null)
      fetchData()
    } catch {
      /* api 层已 toast */
    }
  }

  const selectableChars = characters.filter(c => !c.is_organization)

  return (
    <div className="space-y-6">
      {/* 标题区 */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-content">关系管理</h1>
        <button onClick={openCreate} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5">
          <Plus className="w-4 h-4" />
          添加关系
        </button>
      </div>

      {/* 内容区 */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-content-secondary" />
        </div>
      ) : relationships.length === 0 ? (
        <div className="text-center py-16 text-content-secondary text-sm">
          <GitBranch className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p className="mb-4">还没有角色关系</p>
          <button onClick={openCreate} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5">
            <Plus className="w-4 h-4" />
            创建第一个关系
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {relationships.map(rel => {
            const style = getTypeStyle(rel.relationship_type_id)
            return (
              <div key={rel.id} className="bg-white border border-surface-border rounded-card p-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <span className="text-sm font-medium text-content shrink-0">{getCharName(rel.character_from_id)}</span>
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium shrink-0 ${style.bg} ${style.text}`}>
                      {style.icon}
                      {rel.relationship_name || getTypeName(rel.relationship_type_id)}
                    </span>
                    <span className="text-sm font-medium text-content shrink-0">{getCharName(rel.character_to_id)}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-content-secondary">亲密度: {rel.intimacy_level}</span>
                    <button onClick={() => openEdit(rel)} className="p-1.5 text-content-secondary hover:text-brand rounded transition-colors" title="编辑">
                      <Pencil className="w-4 h-4" />
                    </button>
                    {deleteConfirmId === rel.id ? (
                      <div className="flex items-center gap-1">
                        <button onClick={() => handleDelete(rel.id)} className="px-2 py-1 text-xs bg-red-500 text-white rounded-btn hover:bg-red-600 transition-colors">确认</button>
                        <button onClick={() => setDeleteConfirmId(null)} className="px-2 py-1 text-xs border border-surface-border text-content-secondary rounded-btn hover:bg-surface-hover transition-colors">取消</button>
                      </div>
                    ) : (
                      <button onClick={() => setDeleteConfirmId(rel.id)} className="p-1.5 text-content-secondary hover:text-red-500 rounded transition-colors" title="删除">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
                {rel.description && (
                  <p className="mt-2 text-xs text-content-secondary leading-relaxed">{rel.description}</p>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* 添加/编辑弹窗 */}
      {showModal && (
        <Modal
          title={editingId ? '编辑关系' : '添加关系'}
          onClose={closeModal}
          size="xl"
          footer={(
            <>
              <button onClick={closeModal} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors">
                取消
              </button>
              <button onClick={handleSave} disabled={saving} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50 inline-flex items-center gap-1.5">
                {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                {editingId ? '保存' : '创建'}
              </button>
            </>
          )}
        >
          <div className="space-y-4">
            {/* 角色A */}
            <div>
              <label className="block text-sm font-medium text-content mb-1">角色A</label>
              <select
                value={form.character_from_id}
                onChange={e => setForm(f => ({ ...f, character_from_id: e.target.value }))}
                disabled={!!editingId}
                className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <option value="">请选择角色</option>
                {selectableChars.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>

            {/* 角色B */}
            <div>
              <label className="block text-sm font-medium text-content mb-1">角色B</label>
              <select
                value={form.character_to_id}
                onChange={e => setForm(f => ({ ...f, character_to_id: e.target.value }))}
                disabled={!!editingId}
                className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <option value="">请选择角色</option>
                {selectableChars.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>

            {/* 关系类型 */}
            <div>
              <label className="block text-sm font-medium text-content mb-1">关系类型</label>
              <select
                value={form.relationship_type_id}
                onChange={e => {
                  const val = e.target.value
                  setForm(f => ({ ...f, relationship_type_id: val === '' ? '' : Number(val) }))
                }}
                className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
              >
                <option value="">请选择关系类型</option>
                {types.map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>

            {/* 自定义关系名称 */}
            <div>
              <label className="block text-sm font-medium text-content mb-1">自定义关系名称（可选）</label>
              <input
                type="text"
                value={form.relationship_name}
                onChange={e => setForm(f => ({ ...f, relationship_name: e.target.value }))}
                placeholder="如不填则使用关系类型名称"
                className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
              />
            </div>

            {/* 亲密度 */}
            <div>
              <label className="block text-sm font-medium text-content mb-1">
                亲密度: {form.intimacy_level}
              </label>
              <input
                type="range"
                min={-100}
                max={100}
                value={form.intimacy_level}
                onChange={e => setForm(f => ({ ...f, intimacy_level: Number(e.target.value) }))}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-content-secondary">
                <span>-100 (敌对)</span>
                <span>0</span>
                <span>100 (亲密)</span>
              </div>
            </div>

            {/* 状态 */}
            <div>
              <label className="block text-sm font-medium text-content mb-1">状态</label>
              <select
                value={form.status}
                onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
                className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
              >
                {STATUS_OPTIONS.map(o => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>

            {/* 关系描述 */}
            <div>
              <label className="block text-sm font-medium text-content mb-1">关系描述</label>
              <textarea
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                placeholder="描述两个角色之间的关系..."
                rows={3}
                className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none resize-none"
              />
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
