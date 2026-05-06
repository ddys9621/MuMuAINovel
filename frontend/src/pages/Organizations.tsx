import { useEffect, useState, useCallback } from 'react'
import { Plus, Pencil, Trash2, Building, Loader2, Users, UserPlus, ChevronDown, ChevronUp } from 'lucide-react'
import { toast } from 'sonner'
import { useStore } from '@/store/index'
import { organizationApi, characterApi } from '@/services/api'
import { Modal } from '@/components/ui/Modal'
import type { Character } from '@/types'

/* ------------------------------------------------------------------ */
/*  类型定义（对齐后端 schema）                                          */
/* ------------------------------------------------------------------ */

/** 对应后端 OrganizationDetailResponse */
interface Organization {
  id: string
  character_id: string
  name: string
  type?: string           // 来自 Character.organization_type
  purpose?: string        // 来自 Character.organization_purpose
  member_count: number
  power_level: number     // 0-100
  location?: string
  motto?: string
  color?: string
}

/** 对应后端 OrganizationMemberDetailResponse */
interface OrgMember {
  id: string
  character_id: string
  character_name: string
  position: string
  rank: number
  loyalty: number         // 0-100
  contribution: number    // 0-100
  status: string
  joined_at?: string
  left_at?: string
  notes?: string
}

/** 创建/编辑组织表单 — Character 字段 + Organization 字段 */
interface OrgForm {
  // Character 字段
  name: string
  organization_type: string
  description: string       // 存入 Character.personality
  purpose: string           // 存入 Character.organization_purpose
  // Organization 字段
  power_level: number
  location: string
  motto: string
  color: string
}

/** 添加/编辑成员表单 */
interface MemberForm {
  character_id: string
  position: string
  rank: number
  loyalty: number
}

const EMPTY_ORG_FORM: OrgForm = {
  name: '', organization_type: '', description: '', purpose: '',
  power_level: 50, location: '', motto: '', color: '',
}
const EMPTY_MEMBER_FORM: MemberForm = { character_id: '', position: '', rank: 0, loyalty: 50 }

const ORG_TYPES = ['门派', '帮会', '家族', '王朝', '商会', '军队', '宗教', '学院', '其他'] as const

const TYPE_COLORS: Record<string, string> = {
  门派: 'bg-purple-50 text-purple-600',
  帮会: 'bg-red-50 text-red-600',
  家族: 'bg-amber-50 text-amber-700',
  王朝: 'bg-yellow-50 text-yellow-700',
  商会: 'bg-emerald-50 text-emerald-600',
  军队: 'bg-slate-100 text-slate-600',
  宗教: 'bg-indigo-50 text-indigo-600',
  学院: 'bg-blue-50 text-blue-600',
  其他: 'bg-gray-100 text-gray-500',
}

/* ------------------------------------------------------------------ */
/*  主组件                                                              */
/* ------------------------------------------------------------------ */
export default function Organizations() {
  const { currentProject } = useStore()

  /* ---- 状态 ---- */
  const [orgs, setOrgs] = useState<Organization[]>([])
  const [loading, setLoading] = useState(false)
  const [showOrgModal, setShowOrgModal] = useState(false)
  const [editingOrg, setEditingOrg] = useState<Organization | null>(null)
  const [orgForm, setOrgForm] = useState<OrgForm>(EMPTY_ORG_FORM)

  // 成员管理
  const [expandedOrgId, setExpandedOrgId] = useState<string | null>(null)
  const [members, setMembers] = useState<OrgMember[]>([])
  const [membersLoading, setMembersLoading] = useState(false)
  const [showMemberModal, setShowMemberModal] = useState(false)
  const [editingMember, setEditingMember] = useState<OrgMember | null>(null)
  const [memberForm, setMemberForm] = useState<MemberForm>(EMPTY_MEMBER_FORM)
  const [characters, setCharacters] = useState<Character[]>([])

  /* ---- 数据获取 ---- */
  const fetchOrgs = useCallback(async () => {
    if (!currentProject?.id) return
    try {
      setLoading(true)
      const data = await organizationApi.getProjectOrganizations(currentProject.id)
      setOrgs((Array.isArray(data) ? data : []) as unknown as Organization[])
    } catch { /* api 层已 toast */ } finally { setLoading(false) }
  }, [currentProject?.id])

  const fetchMembers = useCallback(async (orgId: string) => {
    try {
      setMembersLoading(true)
      const data = await organizationApi.getMembers(orgId)
      setMembers((Array.isArray(data) ? data : []) as unknown as OrgMember[])
    } catch { /* api 层已 toast */ } finally { setMembersLoading(false) }
  }, [])

  const fetchCharacters = useCallback(async () => {
    if (!currentProject?.id) return
    try {
      const data = await characterApi.getCharacters(currentProject.id)
      setCharacters((Array.isArray(data) ? data : []).filter(c => !c.is_organization))
    } catch { /* ignore */ }
  }, [currentProject?.id])

  useEffect(() => { fetchOrgs() }, [fetchOrgs])

  /* ---- 组织 CRUD ---- */
  const openCreateOrg = () => {
    setEditingOrg(null)
    setOrgForm(EMPTY_ORG_FORM)
    setShowOrgModal(true)
  }

  const openEditOrg = (org: Organization) => {
    setEditingOrg(org)
    setOrgForm({
      name: org.name,
      organization_type: org.type || '',
      description: '',  // Character.personality 不在列表响应中，留空
      purpose: org.purpose || '',
      power_level: org.power_level ?? 50,
      location: org.location || '',
      motto: org.motto || '',
      color: org.color || '',
    })
    setShowOrgModal(true)
  }

  const handleOrgSubmit = async () => {
    if (!currentProject?.id) return
    if (!orgForm.name.trim()) { toast.error('请填写组织名称'); return }
    try {
      if (editingOrg) {
        // 编辑模式：分别更新 Character 和 Organization
        // 1. 更新 Character 基本信息
        await characterApi.updateCharacter(editingOrg.character_id, {
          name: orgForm.name,
          organization_type: orgForm.organization_type || undefined,
          organization_purpose: orgForm.purpose || undefined,
          personality: orgForm.description || undefined,
        })
        // 2. 更新 Organization 额外属性
        await organizationApi.updateOrganization(editingOrg.id, {
          power_level: orgForm.power_level,
          location: orgForm.location || undefined,
          motto: orgForm.motto || undefined,
          color: orgForm.color || undefined,
        })
        toast.success('组织已更新')
        await fetchOrgs()
      } else {
        // 创建模式：两步操作
        // 第一步：创建 is_organization=true 的 Character
        const char = await characterApi.createCharacter({
          project_id: currentProject.id,
          name: orgForm.name,
          role_type: '组织',
          personality: orgForm.description || undefined,
          is_organization: true,
          organization_type: orgForm.organization_type || undefined,
          organization_purpose: orgForm.purpose || undefined,
        })
        // 第二步：用 character_id 创建 Organization 记录
        await organizationApi.createOrganization({
          character_id: char.id,
          project_id: currentProject.id,
          power_level: orgForm.power_level,
          location: orgForm.location || undefined,
          motto: orgForm.motto || undefined,
          color: orgForm.color || undefined,
        })
        toast.success('组织已创建')
        await fetchOrgs()
      }
      setShowOrgModal(false)
    } catch { /* api 层已 toast */ }
  }

  const handleDeleteOrg = async (org: Organization) => {
    if (!confirm(`确定删除「${org.name}」？此操作不可撤销。`)) return
    try {
      await organizationApi.deleteOrganization(org.id)
      setOrgs(prev => prev.filter(o => o.id !== org.id))
      if (expandedOrgId === org.id) { setExpandedOrgId(null); setMembers([]) }
      toast.success('组织已删除')
    } catch { /* api 层已 toast */ }
  }

  /* ---- 成员管理 ---- */
  const toggleMembers = async (orgId: string) => {
    if (expandedOrgId === orgId) {
      setExpandedOrgId(null)
      setMembers([])
      return
    }
    setExpandedOrgId(orgId)
    await fetchMembers(orgId)
  }

  const openAddMember = async () => {
    setEditingMember(null)
    setMemberForm(EMPTY_MEMBER_FORM)
    await fetchCharacters()
    setShowMemberModal(true)
  }

  const openEditMember = (m: OrgMember) => {
    setEditingMember(m)
    setMemberForm({
      character_id: m.character_id,
      position: m.position || '',
      rank: m.rank ?? 0,
      loyalty: m.loyalty ?? 50,
    })
    setShowMemberModal(true)
  }

  const handleMemberSubmit = async () => {
    if (!expandedOrgId) return
    try {
      if (editingMember) {
        // 编辑成员：不传 character_id
        const updated = await organizationApi.updateMember(editingMember.id, {
          position: memberForm.position || undefined,
          rank: memberForm.rank,
          loyalty: memberForm.loyalty,
        }) as unknown as OrgMember
        setMembers(prev => prev.map(m => m.id === updated.id ? updated : m))
        toast.success('成员信息已更新')
      } else {
        if (!memberForm.character_id) { toast.error('请选择角色'); return }
        if (!memberForm.position.trim()) { toast.error('请填写职位'); return }
        const created = await organizationApi.addMember(expandedOrgId, {
          character_id: memberForm.character_id,
          position: memberForm.position,
          rank: memberForm.rank,
          loyalty: memberForm.loyalty,
        }) as unknown as OrgMember
        setMembers(prev => [...prev, created])
        toast.success('成员已添加')
      }
      setShowMemberModal(false)
    } catch { /* api 层已 toast */ }
  }

  const handleRemoveMember = async (m: OrgMember) => {
    const name = m.character_name || '该成员'
    if (!confirm(`确定移除「${name}」？`)) return
    try {
      await organizationApi.removeMember(m.id)
      setMembers(prev => prev.filter(x => x.id !== m.id))
      toast.success('成员已移除')
    } catch { /* api 层已 toast */ }
  }

  /* ---- 渲染：标题区 + 卡片网格 ---- */
  return (
    <div className="space-y-6">
      {/* 标题区 */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-content">组织管理</h1>
        <button onClick={openCreateOrg} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors inline-flex items-center gap-1.5">
          <Plus className="w-4 h-4" />
          创建组织
        </button>
      </div>

      {/* 主体 */}
      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin text-content-secondary" /></div>
      ) : orgs.length === 0 ? (
        <div className="text-center py-12 text-content-secondary text-sm">
          <Building className="w-8 h-8 mx-auto mb-2 opacity-40" />
          暂无组织，点击上方按钮创建
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {orgs.map(org => (
            <div key={org.id} className="bg-white border border-surface-border rounded-card p-4 space-y-3">
              {/* 卡片头部 */}
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-content truncate">{org.name}</h3>
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    {org.type && (
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${TYPE_COLORS[org.type] || TYPE_COLORS['其他']}`}>
                        {org.type}
                      </span>
                    )}
                    <span className="text-xs text-content-secondary">
                      {org.member_count ?? 0} 名成员
                    </span>
                    {org.power_level != null && (
                      <span className="text-xs text-content-secondary">
                        势力 {org.power_level}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => toggleMembers(org.id)} className="p-1.5 rounded hover:bg-surface-hover text-content-secondary transition-colors" title="查看成员">
                    <Users className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => openEditOrg(org)} className="p-1.5 rounded hover:bg-surface-hover text-content-secondary transition-colors" title="编辑">
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button onClick={() => handleDeleteOrg(org)} className="p-1.5 rounded hover:bg-red-50 text-content-secondary hover:text-red-500 transition-colors" title="删除">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* 额外信息 */}
              {org.purpose && <p className="text-xs text-content-secondary/80">目标：{org.purpose}</p>}
              {org.location && <p className="text-xs text-content-secondary/80">所在地：{org.location}</p>}
              {org.motto && <p className="text-xs text-content-secondary/80 italic">「{org.motto}」</p>}

              {/* 展开/收起成员面板 */}
              <button
                onClick={() => toggleMembers(org.id)}
                className="flex items-center gap-1 text-xs text-brand hover:text-brand-600 transition-colors"
              >
                {expandedOrgId === org.id ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                {expandedOrgId === org.id ? '收起成员' : '查看成员'}
              </button>

              {/* 成员面板 */}
              {expandedOrgId === org.id && (
                <div className="border-t border-surface-border pt-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-content-secondary">成员列表</span>
                    <button onClick={openAddMember} className="inline-flex items-center gap-1 text-xs text-brand hover:text-brand-600 transition-colors">
                      <UserPlus className="w-3 h-3" /> 添加成员
                    </button>
                  </div>

                  {membersLoading ? (
                    <div className="flex justify-center py-4"><Loader2 className="w-4 h-4 animate-spin text-content-secondary" /></div>
                  ) : members.length === 0 ? (
                    <p className="text-xs text-content-secondary/60 py-2 text-center">暂无成员</p>
                  ) : (
                    <div className="space-y-1.5">
                      {members.map(m => (
                        <div key={m.id} className="flex items-center justify-between bg-surface-hover/50 rounded px-3 py-2">
                          <div className="min-w-0">
                            <span className="text-sm text-content font-medium">{m.character_name || '未知角色'}</span>
                            {(m.position || m.rank) && (
                              <span className="ml-2 text-xs text-content-secondary">
                                {[m.position, m.rank ? `等级${m.rank}` : ''].filter(Boolean).join(' · ')}
                              </span>
                            )}
                            {m.loyalty != null && (
                              <span className="ml-2 text-xs text-content-secondary/70">
                                忠诚 {m.loyalty}
                              </span>
                            )}
                          </div>
                          <div className="flex gap-1 shrink-0">
                            <button onClick={() => openEditMember(m)} className="p-1 rounded hover:bg-white text-content-secondary transition-colors" title="编辑">
                              <Pencil className="w-3 h-3" />
                            </button>
                            <button onClick={() => handleRemoveMember(m)} className="p-1 rounded hover:bg-red-50 text-content-secondary hover:text-red-500 transition-colors" title="移除">
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 创建/编辑组织弹窗 */}
      {showOrgModal && (
        <Modal
          title={editingOrg ? '编辑组织' : '创建组织'}
          onClose={() => setShowOrgModal(false)}
          size="xl"
          footer={(
            <>
              <button onClick={() => setShowOrgModal(false)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors">取消</button>
              <button onClick={handleOrgSubmit} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors">确定</button>
            </>
          )}
        >
          <div className="space-y-3">
            <div>
              <label className="block text-sm text-content-secondary mb-1">名称 <span className="text-red-500">*</span></label>
              <input value={orgForm.name} onChange={e => setOrgForm(f => ({ ...f, name: e.target.value }))} placeholder="组织名称" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">类型</label>
              <div className="flex flex-wrap gap-1.5">
                {ORG_TYPES.map(t => (
                  <button key={t} onClick={() => setOrgForm(f => ({ ...f, organization_type: f.organization_type === t ? '' : t }))}
                    className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${orgForm.organization_type === t ? 'bg-brand text-white' : 'bg-gray-100 text-content-secondary hover:bg-gray-200'}`}
                  >{t}</button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">描述</label>
              <textarea value={orgForm.description} onChange={e => setOrgForm(f => ({ ...f, description: e.target.value }))} rows={3} placeholder="组织的背景描述…" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors resize-none" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">目标/宗旨</label>
              <textarea value={orgForm.purpose} onChange={e => setOrgForm(f => ({ ...f, purpose: e.target.value }))} rows={2} placeholder="组织的核心目标…" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors resize-none" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">势力等级 ({orgForm.power_level})</label>
              <input type="range" min={0} max={100} value={orgForm.power_level} onChange={e => setOrgForm(f => ({ ...f, power_level: Number(e.target.value) }))} className="w-full" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">所在地</label>
              <input value={orgForm.location} onChange={e => setOrgForm(f => ({ ...f, location: e.target.value }))} placeholder="如：昆仑山、中原…" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">座右铭</label>
              <input value={orgForm.motto} onChange={e => setOrgForm(f => ({ ...f, motto: e.target.value }))} placeholder="组织的座右铭…" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">代表颜色</label>
              <input type="color" value={orgForm.color || '#6366f1'} onChange={e => setOrgForm(f => ({ ...f, color: e.target.value }))} className="w-10 h-8 rounded border border-surface-border cursor-pointer" />
            </div>
          </div>
        </Modal>
      )}

      {/* 添加/编辑成员弹窗 */}
      {showMemberModal && (
        <Modal
          title={editingMember ? '编辑成员' : '添加成员'}
          onClose={() => setShowMemberModal(false)}
          size="lg"
          footer={(
            <>
              <button onClick={() => setShowMemberModal(false)} className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors">取消</button>
              <button onClick={handleMemberSubmit} className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm font-medium transition-colors">确定</button>
            </>
          )}
        >
          <div className="space-y-3">
            {!editingMember && (
              <div>
                <label className="block text-sm text-content-secondary mb-1">选择角色 <span className="text-red-500">*</span></label>
                <select
                  value={memberForm.character_id}
                  onChange={e => setMemberForm(f => ({ ...f, character_id: e.target.value }))}
                  className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors"
                >
                  <option value="">请选择角色…</option>
                  {characters
                    .filter(c => !members.some(m => m.character_id === c.id))
                    .map(c => <option key={c.id} value={c.id}>{c.name}{c.role_type ? ` (${c.role_type})` : ''}</option>)
                  }
                </select>
              </div>
            )}
            <div>
              <label className="block text-sm text-content-secondary mb-1">职位 <span className="text-red-500">*</span></label>
              <input value={memberForm.position} onChange={e => setMemberForm(f => ({ ...f, position: e.target.value }))} placeholder="如：掌门、长老、弟子…" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">等级</label>
              <input type="number" min={0} value={memberForm.rank} onChange={e => setMemberForm(f => ({ ...f, rank: Number(e.target.value) }))} placeholder="职位等级（数字）" className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors" />
            </div>
            <div>
              <label className="block text-sm text-content-secondary mb-1">忠诚度 ({memberForm.loyalty})</label>
              <input type="range" min={0} max={100} value={memberForm.loyalty} onChange={e => setMemberForm(f => ({ ...f, loyalty: Number(e.target.value) }))} className="w-full" />
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
