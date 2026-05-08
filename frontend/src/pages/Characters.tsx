import { useState, useEffect, useCallback } from 'react';
import { Plus, Sparkles, Pencil, Trash2, X, Loader2, Building, Users, UserPlus, UserMinus } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { useStore } from '@/store';
import { useCharacterSync } from '@/store/hooks';
import { characterApi, organizationApi } from '@/services/api';
import { MCPSelector } from '@/components/MCPSelector';
import type { Character } from '@/types';
import { ROLE_OPTIONS, getRoleDisplayName, normalizeRoleType } from '@/utils/characterRole';

const ROLE_COLORS: Record<string, string> = {
  主角: 'bg-brand/10 text-brand-600',
  配角: 'bg-blue-50 text-blue-600',
  反派: 'bg-red-50 text-red-700',
  导师: 'bg-purple-50 text-purple-600',
  盟友: 'bg-emerald-50 text-emerald-600',
  路人: 'bg-gray-100 text-gray-500',
  组织: 'bg-amber-50 text-amber-700',
};

const AVATAR_COLORS = [
  'bg-brand-500', 'bg-blue-500', 'bg-emerald-500', 'bg-purple-500',
  'bg-orange-500', 'bg-pink-500', 'bg-teal-500', 'bg-indigo-500',
];

function getAvatarColor(name: string) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

interface FormData {
  name: string;
  role_type: string;
  personality: string;
  background: string;
  is_organization: boolean;
  organization_type: string;
  organization_purpose: string;
  reason: string;
}

const EMPTY_FORM: FormData = { name: '', role_type: 'protagonist', personality: '', background: '', is_organization: false, organization_type: '', organization_purpose: '', reason: '' };

export default function Characters() {
  const { currentProject, characters } = useStore();
  const { refreshCharacters, deleteCharacter, generateCharacter } = useCharacterSync();

  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormData>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [showGenModal, setShowGenModal] = useState(false);
  const [genForm, setGenForm] = useState({ name: '', role_type: 'supporting', background: '', requirements: '' });
  const [enableMcp, setEnableMcp] = useState(false);
  const [selectedPlugins, setSelectedPlugins] = useState<string[]>([]);
  const [filter, setFilter] = useState<'all' | 'character' | 'organization'>('all');
  const [orgMembers, setOrgMembers] = useState<Array<Record<string, unknown>>>([]);
  const [orgId, setOrgId] = useState<string | null>(null);
  const [addMemberId, setAddMemberId] = useState('');
  const [addMemberPos, setAddMemberPos] = useState('成员');
  const [showGenOrgModal, setShowGenOrgModal] = useState(false);
  const [genOrgForm, setGenOrgForm] = useState({ name: '', requirements: '' });
  const [generatingOrg, setGeneratingOrg] = useState(false);

  const filteredCharacters = characters.filter(c => {
    if (filter === 'character') return !c.is_organization;
    if (filter === 'organization') return c.is_organization;
    return true;
  });
  const charCount = characters.filter(c => !c.is_organization).length;
  const orgCount = characters.filter(c => c.is_organization).length;

  useEffect(() => {
    if (currentProject?.id) refreshCharacters();
  }, [currentProject?.id, refreshCharacters]);

  const openAdd = useCallback(() => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setShowModal(true);
  }, []);

  const openAddOrg = useCallback(() => {
    setEditingId(null);
    setForm({ ...EMPTY_FORM, is_organization: true, role_type: 'supporting' });
    setShowModal(true);
  }, []);

  const loadOrgMembers = useCallback(async (characterId: string) => {
    try {
      const orgs = currentProject?.id
        ? await organizationApi.getProjectOrganizations(currentProject.id) as Array<Record<string, unknown>>
        : [];
      const org = orgs.find((o) => o.character_id === characterId);
      if (org && org.id) {
        setOrgId(org.id as string);
        const members = await organizationApi.getMembers(org.id as string);
        setOrgMembers(members);
      } else {
        setOrgId(null);
        setOrgMembers([]);
      }
    } catch {
      setOrgMembers([]);
    }
  }, [currentProject?.id]);

  const handleAddMember = async () => {
    if (!orgId || !addMemberId) return;
    try {
      await organizationApi.addMember(orgId, { character_id: addMemberId, position: addMemberPos || '成员' });
      toast.success('成员已添加');
      setAddMemberId('');
      setAddMemberPos('成员');
      await loadOrgMembers(editingId!);
    } catch {
      toast.error('添加成员失败');
    }
  };

  const handleRemoveMember = async (memberId: string) => {
    try {
      await organizationApi.removeMember(memberId);
      toast.success('成员已移除');
      if (editingId) await loadOrgMembers(editingId);
    } catch {
      toast.error('移除失败');
    }
  };

  const openEdit = useCallback((c: Character) => {
    setEditingId(c.id);
    setForm({
      name: c.name,
      role_type: normalizeRoleType(c.role_type, c.is_organization ? 'supporting' : 'protagonist'),
      personality: c.personality || '',
      background: c.background || '',
      is_organization: c.is_organization,
      organization_type: c.organization_type || '',
      organization_purpose: c.organization_purpose || '',
      reason: '',
    });
    setOrgMembers([]);
    setOrgId(null);
    setAddMemberId('');
    setAddMemberPos('成员');
    if (c.is_organization) {
      loadOrgMembers(c.id);
    }
    setShowModal(true);
  }, [loadOrgMembers]);

  const handleSubmit = async () => {
    if (!currentProject || !form.name.trim()) return;
    setSubmitting(true);
    try {
      let bg = form.background;
      if (form.reason.trim()) {
        const prefix = editingId ? '[手动编辑]' : '[手动添加]';
        const reasonLine = `${prefix} ${form.reason.trim()}`;
        bg = bg.trim() ? `${bg.trim()}\n${reasonLine}` : reasonLine;
      }
      const payload: Record<string, unknown> = {
        name: form.name,
        role_type: normalizeRoleType(form.role_type, 'supporting'),
        personality: form.personality,
        background: bg,
      };
      if (form.is_organization) {
        payload.is_organization = true;
        payload.organization_type = form.organization_type;
        payload.organization_purpose = form.organization_purpose;
      }
      if (editingId) {
        await characterApi.updateCharacter(editingId, payload);
        toast.success(form.is_organization ? '组织已更新' : '角色已更新');
      } else {
        await characterApi.createCharacter({ project_id: currentProject.id, name: form.name, ...payload });
        toast.success(form.is_organization ? '组织已创建' : '角色已创建');
      }
      await refreshCharacters();
      setShowModal(false);
    } catch {
      toast.error(editingId ? '更新失败' : '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string, name: string, isOrg: boolean) => {
    const label = isOrg ? '组织' : '角色';
    const reason = prompt(`确定删除${label}「${name}」吗？\n\n请填写删除原因（AI 后续会参考此信息）：`);
    if (reason === null) return;
    try {
      if (reason.trim()) {
        await characterApi.updateCharacter(id, {
          background: `[已删除] ${reason.trim()}`,
        });
      }
      await deleteCharacter(id);
      toast.success(`${label}已删除`);
    } catch {
      toast.error('删除失败');
    }
  };

  const handleGenerateOrg = async () => {
    if (!currentProject) return;
    setGeneratingOrg(true);
    try {
      await organizationApi.generateOrganization({
        project_id: currentProject.id,
        requirements: genOrgForm.requirements.trim() || undefined,
      });
      toast.success('AI 组织已生成');
      await refreshCharacters();
      setShowGenOrgModal(false);
      setGenOrgForm({ name: '', requirements: '' });
    } catch {
      toast.error('AI 生成组织失败');
    } finally {
      setGeneratingOrg(false);
    }
  };

  const handleGenerate = async () => {
    if (!currentProject) return;
    setGenerating(true);
    try {
      await generateCharacter({
        project_id: currentProject.id,
        name: genForm.name.trim() || undefined,
        role_type: genForm.role_type || undefined,
        background: genForm.background.trim() || undefined,
        requirements: genForm.requirements.trim() || undefined,
        enable_mcp: enableMcp,
        selected_plugins: selectedPlugins,
      });
      toast.success('AI 角色已生成');
      await refreshCharacters();
      setShowGenModal(false);
      setGenForm({ name: '', role_type: 'supporting', background: '', requirements: '' });
    } catch {
      toast.error('AI 生成失败');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="animate-fade-in space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-content">角色与组织</h1>
          <p className="text-sm text-content-secondary mt-1">
            {charCount} 个人物 · {orgCount} 个组织
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowGenModal(true)}
            disabled={generating}
            className="inline-flex items-center gap-1.5 border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors disabled:opacity-50"
          >
            {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            AI 生成
          </button>
          <button
            onClick={openAdd}
            className="inline-flex items-center gap-1.5 bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            添加角色
          </button>
          <button
            onClick={() => setShowGenOrgModal(true)}
            disabled={generatingOrg}
            className="inline-flex items-center gap-1.5 border border-amber-300 text-amber-700 hover:bg-amber-50 rounded-btn px-4 py-2 text-sm transition-colors disabled:opacity-50"
          >
            {generatingOrg ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            AI 生成组织
          </button>
          <button
            onClick={openAddOrg}
            className="inline-flex items-center gap-1.5 border border-amber-300 text-amber-700 hover:bg-amber-50 rounded-btn px-4 py-2 text-sm transition-colors"
          >
            <Building className="w-4 h-4" />
            添加组织
          </button>
        </div>
      </div>

      {/* 筛选 Tab */}
      <div className="flex items-center gap-1 border-b border-surface-border">
        {([
          { key: 'all', label: '全部', count: characters.length, icon: null },
          { key: 'character', label: '人物', count: charCount, icon: Users },
          { key: 'organization', label: '组织', count: orgCount, icon: Building },
        ] as const).map(tab => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className={cn(
              'inline-flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors',
              filter === tab.key
                ? 'border-brand text-brand'
                : 'border-transparent text-content-secondary hover:text-content'
            )}
          >
            {tab.icon && <tab.icon className="w-4 h-4" />}
            {tab.label}
            <span className={cn(
              'text-xs rounded-full px-1.5 py-0.5',
              filter === tab.key ? 'bg-brand/10 text-brand' : 'bg-surface text-content-tertiary'
            )}>{tab.count}</span>
          </button>
        ))}
      </div>

      {/* 卡片网格 */}
      {filteredCharacters.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredCharacters.map((c) => (
            <div
              key={c.id}
              className={cn(
                "bg-white border rounded-card p-4 hover:shadow-card transition-shadow",
                c.is_organization ? "border-l-4 border-l-amber-400 border-surface-border" : "border-surface-border"
              )}
            >
              {(() => {
                const roleLabel = getRoleDisplayName(c.role_type, c.is_organization ? '组织' : '路人');
                return (
              <div className="flex items-start gap-3">
                {/* 头像 */}
                <div
                  className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-white font-semibold text-sm ${getAvatarColor(c.name)}`}
                >
                  {c.name.charAt(0)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-content text-sm truncate">{c.name}</span>
                    {c.role_type && (
                      <span
                        className={`flex-shrink-0 text-xs px-2 py-0.5 rounded-full ${ROLE_COLORS[roleLabel] || ROLE_COLORS['路人']}`}
                      >
                        {roleLabel}
                      </span>
                    )}
                  </div>
                  {c.is_organization ? (
                    <div className="mt-1 space-y-0.5">
                      {c.organization_type && <p className="text-xs text-amber-600">{c.organization_type}</p>}
                      <p className="text-xs text-content-secondary line-clamp-2">
                        {c.organization_purpose || c.background || '暂无描述'}
                      </p>
                      {c.organization_members && (() => {
                        try {
                          const members = JSON.parse(c.organization_members);
                          if (Array.isArray(members) && members.length > 0) {
                            return <p className="text-[11px] text-content-tertiary">成员: {members.slice(0, 5).join('、')}{members.length > 5 ? ` 等${members.length}人` : ''}</p>
                          }
                        } catch { /* ignore */ }
                        return null;
                      })()}
                    </div>
                  ) : (
                    <p className="text-xs text-content-secondary mt-1 line-clamp-2">
                      {c.personality || c.background || '暂无简介'}
                    </p>
                  )}
                </div>
              </div>
                )
              })()}
              {/* 操作 */}
              <div className="flex items-center justify-end gap-1 mt-3 pt-3 border-t border-surface-border-light">
                <button
                  onClick={() => openEdit(c)}
                  className="inline-flex items-center gap-1 text-xs text-content-secondary hover:text-brand px-2 py-1 rounded transition-colors"
                >
                  <Pencil className="w-3.5 h-3.5" />
                  编辑
                </button>
                <button
                  onClick={() => handleDelete(c.id, c.name, c.is_organization)}
                  className="inline-flex items-center gap-1 text-xs text-content-secondary hover:text-red-600 px-2 py-1 rounded transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-16 text-content-secondary text-sm">
          还没有角色，点击"添加角色"或"AI 生成"开始创建
        </div>
      )}

      {/* AI 生成角色弹窗 */}
      {showGenModal && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 px-4 py-8 sm:py-12">
          <div className="relative my-auto bg-white shadow-xl w-full max-w-xl mx-4 animate-scale-in max-h-[calc(100vh-4rem)] flex flex-col">
            <div className="flex items-center justify-between px-6 pt-5 pb-3 flex-shrink-0 border-b border-surface-border">
              <h2 className="text-lg font-bold text-content">AI 生成角色</h2>
              <button onClick={() => setShowGenModal(false)} className="text-content-tertiary hover:text-content">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="px-6 py-5 space-y-4 overflow-y-auto flex-1">
              <div>
                <label className="block text-sm font-medium text-content mb-1">角色名称（可选）</label>
                <input
                  value={genForm.name}
                  onChange={e => setGenForm(p => ({ ...p, name: e.target.value }))}
                  placeholder="留空由 AI 自动取名"
                  className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-content mb-1">角色定位</label>
                <select
                  value={genForm.role_type}
                  onChange={e => setGenForm(p => ({ ...p, role_type: e.target.value }))}
                  className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
                >
                  <option value="protagonist">主角</option>
                  <option value="supporting">配角</option>
                  <option value="antagonist">反派</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-content mb-1">背景设定（可选）</label>
                <textarea
                  value={genForm.background}
                  onChange={e => setGenForm(p => ({ ...p, background: e.target.value }))}
                  placeholder="对角色背景的描述或要求..."
                  rows={2}
                  className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-content mb-1">额外要求（可选）</label>
                <textarea
                  value={genForm.requirements}
                  onChange={e => setGenForm(p => ({ ...p, requirements: e.target.value }))}
                  placeholder="如：需要有修仙背景、性格冷酷..."
                  rows={2}
                  className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none resize-none"
                />
              </div>
              <MCPSelector
                value={{ enable: enableMcp, selected: selectedPlugins }}
                onChange={({ enable, selected }) => {
                  setEnableMcp(enable);
                  setSelectedPlugins(selected);
                }}
              />
            </div>
            <div className="flex justify-end gap-2 px-6 py-3 border-t border-surface-border bg-white flex-shrink-0">
              <button
                onClick={() => setShowGenModal(false)}
                className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="inline-flex items-center gap-1.5 bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm transition-colors disabled:opacity-50"
              >
                {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                {generating ? '生成中...' : '开始生成'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* AI 生成组织弹窗 */}
      {showGenOrgModal && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 px-4 py-8 sm:py-12">
          <div className="relative my-auto bg-white shadow-xl w-full max-w-lg mx-4 animate-scale-in max-h-[calc(100vh-4rem)] flex flex-col">
            <div className="flex items-center justify-between px-6 pt-5 pb-3 flex-shrink-0 border-b border-surface-border">
              <h2 className="text-lg font-bold text-content">AI 生成组织</h2>
              <button onClick={() => setShowGenOrgModal(false)} className="text-content-tertiary hover:text-content">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="px-6 py-5 space-y-4 overflow-y-auto flex-1">
              <div>
                <label className="block text-sm font-medium text-content mb-1">组织名称（可选）</label>
                <input
                  value={genOrgForm.name}
                  onChange={e => setGenOrgForm(p => ({ ...p, name: e.target.value }))}
                  placeholder="留空由 AI 自动命名"
                  className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-content mb-1">组织要求描述</label>
                <textarea
                  value={genOrgForm.requirements}
                  onChange={e => setGenOrgForm(p => ({ ...p, requirements: e.target.value }))}
                  placeholder="如：一个修仙宗门、纪律森严、位于北方雪山..."
                  rows={4}
                  className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none resize-none"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 px-6 py-3 border-t border-surface-border bg-white flex-shrink-0">
              <button
                onClick={() => setShowGenOrgModal(false)}
                className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleGenerateOrg}
                disabled={generatingOrg}
                className="inline-flex items-center gap-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded-btn px-4 py-2 text-sm transition-colors disabled:opacity-50"
              >
                {generatingOrg ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                {generatingOrg ? '生成中...' : '开始生成'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 手动添加/编辑弹窗 */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 px-4 py-8 sm:py-12">
          <div className="relative my-auto bg-white shadow-xl w-full max-w-2xl mx-4 animate-scale-in max-h-[calc(100vh-4rem)] flex flex-col">
            <div className="flex items-center justify-between px-6 pt-5 pb-3 flex-shrink-0">
              <h2 className="text-lg font-bold text-content">
                {editingId ? (form.is_organization ? '编辑组织' : '编辑角色') : '添加角色'}
              </h2>
              <button onClick={() => setShowModal(false)} className="text-content-tertiary hover:text-content">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="px-6 pb-6 space-y-4 overflow-y-auto flex-1">
              <div>
                <label className="block text-sm font-medium text-content mb-1">名称</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder={form.is_organization ? '组织名称' : '角色名字'}
                  className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
                />
              </div>

              {form.is_organization ? (
                <>
                  <div>
                    <label className="block text-sm font-medium text-content mb-1">组织类型</label>
                    <input
                      value={form.organization_type}
                      onChange={(e) => setForm((p) => ({ ...p, organization_type: e.target.value }))}
                      placeholder="如：宗门、家族、商会、势力"
                      className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-content mb-1">组织宗旨</label>
                    <textarea
                      value={form.organization_purpose}
                      onChange={(e) => setForm((p) => ({ ...p, organization_purpose: e.target.value }))}
                      placeholder="组织的宗旨或核心目标…"
                      rows={2}
                      className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none resize-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-content mb-1">组织风格/氛围</label>
                    <textarea
                      value={form.personality}
                      onChange={(e) => setForm((p) => ({ ...p, personality: e.target.value }))}
                      placeholder="如：纪律严明、唯利是图…"
                      rows={2}
                      className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none resize-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-content mb-1">背景描述</label>
                    <textarea
                      value={form.background}
                      onChange={(e) => setForm((p) => ({ ...p, background: e.target.value }))}
                      placeholder="组织的历史、势力范围等…"
                      rows={3}
                      className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none resize-none"
                    />
                  </div>

                  {/* 成员管理区 */}
                  {editingId && (
                    <div className="border border-surface-border rounded-[14px] p-3 space-y-3">
                      <div className="flex items-center gap-2">
                        <Users className="w-4 h-4 text-content-secondary" />
                        <span className="text-sm font-medium text-content">组织成员</span>
                        <span className="text-xs text-content-tertiary">({orgMembers.length}人)</span>
                      </div>

                      {orgMembers.length > 0 ? (
                        <div className="space-y-1.5 max-h-40 overflow-y-auto">
                          {orgMembers.map((m) => (
                            <div key={String(m.id)} className="flex items-center justify-between gap-2 bg-surface/50 rounded-btn px-2.5 py-1.5">
                              <div className="flex-1 min-w-0">
                                <span className="text-xs font-medium text-content">{String(m.character_name || '未知')}</span>
                                <span className="text-[11px] text-content-tertiary ml-1.5">{String(m.position || '成员')}</span>
                                {Boolean(m.status) && m.status !== 'active' && <span className="text-[10px] text-red-500 ml-1">({String(m.status)})</span>}
                              </div>
                              <button
                                onClick={() => handleRemoveMember(String(m.id))}
                                className="text-content-tertiary hover:text-red-500 transition-colors p-0.5"
                                title="移除成员"
                              >
                                <UserMinus className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-content-tertiary text-center py-2">暂无成员</p>
                      )}

                      {/* 添加成员 */}
                      <div className="flex items-end gap-2">
                        <div className="flex-1">
                          <label className="block text-[11px] text-content-tertiary mb-0.5">选择角色</label>
                          <select
                            value={addMemberId}
                            onChange={(e) => setAddMemberId(e.target.value)}
                            className="w-full border border-surface-border rounded-btn px-2 py-1.5 text-xs focus:border-brand outline-none bg-white"
                          >
                            <option value="">选择角色加入…</option>
                            {characters
                              .filter(c => !c.is_organization && !orgMembers.some(m => m.character_id === c.id))
                              .map(c => <option key={c.id} value={c.id}>{c.name}</option>)
                            }
                          </select>
                        </div>
                        <div className="w-24">
                          <label className="block text-[11px] text-content-tertiary mb-0.5">职位</label>
                          <input
                            value={addMemberPos}
                            onChange={(e) => setAddMemberPos(e.target.value)}
                            placeholder="成员"
                            className="w-full border border-surface-border rounded-btn px-2 py-1.5 text-xs focus:border-brand outline-none"
                          />
                        </div>
                        <button
                          onClick={handleAddMember}
                          disabled={!addMemberId}
                          className="inline-flex items-center gap-1 border border-emerald-300 text-emerald-700 hover:bg-emerald-50 rounded-btn px-2 py-1.5 text-xs transition-colors disabled:opacity-40"
                        >
                          <UserPlus className="w-3.5 h-3.5" />
                          添加
                        </button>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <>
                  <div>
                    <label className="block text-sm font-medium text-content mb-1">角色类型</label>
                    <select
                      value={form.role_type}
                      onChange={(e) => setForm((p) => ({ ...p, role_type: e.target.value }))}
                      className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none"
                    >
                      {ROLE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-content mb-1">性格特点</label>
                    <textarea
                      value={form.personality}
                      onChange={(e) => setForm((p) => ({ ...p, personality: e.target.value }))}
                      placeholder="描述角色的性格特点…"
                      rows={3}
                      className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none resize-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-content mb-1">背景故事</label>
                    <textarea
                      value={form.background}
                      onChange={(e) => setForm((p) => ({ ...p, background: e.target.value }))}
                      placeholder="描述角色的背景故事…"
                      rows={3}
                      className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none resize-none"
                    />
                  </div>
                </>
              )}

              <div className="rounded-[14px] border border-brand/20 bg-brand/5 p-3">
                <label className="block text-sm font-medium text-brand-600 mb-1">
                  {editingId ? '修改原因' : '添加原因'}
                  <span className="text-xs font-normal text-content-tertiary ml-1">（AI 生成时会参考此信息）</span>
                </label>
                <input
                  value={form.reason}
                  onChange={(e) => setForm((p) => ({ ...p, reason: e.target.value }))}
                  placeholder={editingId ? '如：修正角色设定、补充信息…' : '如：剧情需要新增此角色…'}
                  className="w-full border border-brand/20 rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none bg-white"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setShowModal(false)}
                  className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={submitting || !form.name.trim()}
                  className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm transition-colors disabled:opacity-50"
                >
                  {submitting ? '保存中…' : '保存'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
