import { useState, useEffect } from 'react';
import {
  Pencil,
  Save,
  X,
  Globe,
  MapPin,
  Cloud,
  ScrollText,
  RefreshCw,
  Trash2,
  Loader2,
  Sparkles,
  BookOpenText,
} from 'lucide-react';
import { toast } from 'sonner';
import { useStore } from '@/store';
import { useProjectSync } from '@/store/hooks';
import { wizardStreamApi } from '@/services/api';
import { MCPSelector } from '@/components/MCPSelector';

interface WorldBlock {
  key: 'world_time_period' | 'world_location' | 'world_atmosphere' | 'world_rules';
  label: string;
  icon: typeof Globe;
  tone: string;
  accent: string;
  panel: string;
  glow: string;
  placeholder: string;
  description: string;
}

const BLOCKS: WorldBlock[] = [
  {
    key: 'world_time_period',
    label: '时代背景',
    icon: Globe,
    tone: 'text-blue-700',
    accent: 'bg-blue-600',
    panel: 'from-blue-50 via-white to-blue-100/70',
    glow: 'shadow-[0_18px_45px_-32px_rgba(37,99,235,0.55)]',
    placeholder: '描述故事发生的时代背景…',
    description: '交代时代演进、社会结构与故事发生前的历史惯性。',
  },
  {
    key: 'world_location',
    label: '地点设定',
    icon: MapPin,
    tone: 'text-emerald-700',
    accent: 'bg-emerald-500',
    panel: 'from-emerald-50 via-white to-emerald-100/70',
    glow: 'shadow-[0_18px_45px_-32px_rgba(16,185,129,0.5)]',
    placeholder: '描述故事发生的主要地点…',
    description: '明确核心舞台、地理关系与关键势力的空间分布。',
  },
  {
    key: 'world_atmosphere',
    label: '氛围基调',
    icon: Cloud,
    tone: 'text-orange-700',
    accent: 'bg-orange-500',
    panel: 'from-orange-50 via-white to-amber-100/70',
    glow: 'shadow-[0_18px_45px_-32px_rgba(249,115,22,0.5)]',
    placeholder: '描述故事的整体氛围和基调…',
    description: '定义读者进入这个世界时最先感受到的情绪温度与质地。',
  },
  {
    key: 'world_rules',
    label: '世界规则',
    icon: ScrollText,
    tone: 'text-rose-700',
    accent: 'bg-rose-500',
    panel: 'from-rose-50 via-white to-red-100/70',
    glow: 'shadow-[0_18px_45px_-32px_rgba(244,63,94,0.5)]',
    placeholder: '描述世界中的特殊规则或设定…',
    description: '写清这个世界的底层运作方式、禁忌、约束与代价。',
  },
];

export default function WorldSetting() {
  const { currentProject } = useStore();
  const { updateProject } = useProjectSync();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [showRegenModal, setShowRegenModal] = useState(false);
  const [regenEnableMcp, setRegenEnableMcp] = useState(false);
  const [regenPlugins, setRegenPlugins] = useState<string[]>([]);
  const [form, setForm] = useState({
    world_time_period: '',
    world_location: '',
    world_atmosphere: '',
    world_rules: '',
  });

  useEffect(() => {
    if (currentProject) {
      setForm({
        world_time_period: currentProject.world_time_period || '',
        world_location: currentProject.world_location || '',
        world_atmosphere: currentProject.world_atmosphere || '',
        world_rules: currentProject.world_rules || '',
      });
    }
  }, [currentProject]);

  const handleRegenerate = async () => {
    if (!currentProject) return;
    setRegenerating(true);
    setShowRegenModal(false);
    try {
      await wizardStreamApi.regenerateWorldBuildingStream(
        currentProject.id,
        {
          enable_mcp: regenEnableMcp,
          selected_plugins: regenPlugins,
        },
        {
          onProgress: (msg) => toast.info(msg, { id: 'regen-world' }),
          onResult: () => {
            toast.success('世界设定重新生成完成', { id: 'regen-world' });
            window.location.reload();
          },
          onError: (err) => toast.error(`重新生成失败: ${err}`, { id: 'regen-world' }),
        }
      );
    } catch {
      toast.error('重新生成失败');
    } finally {
      setRegenerating(false);
    }
  };

  const handleCleanup = async () => {
    if (!currentProject) return;
    if (!confirm('清理将删除向导生成的角色、大纲等数据，确定继续？')) return;
    setCleaning(true);
    try {
      await wizardStreamApi.cleanupWizardDataStream(currentProject.id, {
        onResult: (data) => {
          const d = data as { deleted?: { characters?: number; outlines?: number; chapters?: number } };
          toast.success(
            `清理完成：角色 ${d.deleted?.characters ?? 0}、大纲 ${d.deleted?.outlines ?? 0}、章节 ${d.deleted?.chapters ?? 0}`
          );
        },
        onError: (err) => toast.error(`清理失败: ${err}`),
      });
    } catch {
      toast.error('清理失败');
    } finally {
      setCleaning(false);
    }
  };

  const handleSave = async () => {
    if (!currentProject) return;
    setSaving(true);
    try {
      await updateProject(currentProject.id, form);
      toast.success('世界设定已保存');
      setEditing(false);
    } catch {
      toast.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    if (currentProject) {
      setForm({
        world_time_period: currentProject.world_time_period || '',
        world_location: currentProject.world_location || '',
        world_atmosphere: currentProject.world_atmosphere || '',
        world_rules: currentProject.world_rules || '',
      });
    }
    setEditing(false);
  };

  const filledBlocks = BLOCKS.filter((block) => form[block.key].trim()).length;
  const totalChars = BLOCKS.reduce((sum, block) => sum + form[block.key].trim().length, 0);
  const hasContent = filledBlocks > 0;

  return (
    <div className="animate-fade-in space-y-6">
      <section className="relative overflow-hidden rounded-[28px] border border-surface-border bg-white shadow-card">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(228,57,60,0.12),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(212,165,116,0.16),transparent_28%)]" />
        <div className="absolute -right-20 top-8 h-40 w-40 rounded-full bg-brand/10 blur-3xl" />
        <div className="absolute left-1/3 top-0 h-24 w-24 rounded-full bg-gold/20 blur-2xl" />

        <div className="relative flex flex-col gap-6 p-6 lg:p-8">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
            <div className="max-w-3xl space-y-4">
              <span className="inline-flex items-center gap-2 rounded-pill border border-brand/15 bg-brand/5 px-3 py-1 text-xs font-medium text-brand">
                <Sparkles className="h-3.5 w-3.5" />
                世界观设定面板
              </span>

              <div className="space-y-2">
                <h1 className="text-2xl font-bold tracking-tight text-content lg:text-[30px]">
                  世界设定
                </h1>
                <p className="max-w-2xl text-sm leading-6 text-content-secondary lg:text-[15px]">
                  把时代、空间、氛围和规则拆开整理，先建立清晰框架，再往里填充细节。这个页面现在更适合长文本阅读和后续补全。
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <SummaryPill
                  label="完成模块"
                  value={`${filledBlocks}/${BLOCKS.length}`}
                  hint={filledBlocks === BLOCKS.length ? '结构完整' : '仍可补充'}
                />
                <SummaryPill
                  label="内容字数"
                  value={String(totalChars)}
                  hint={totalChars > 0 ? '当前已录入' : '尚未填写'}
                />
                <SummaryPill
                  label="当前状态"
                  value={editing ? '编辑中' : hasContent ? '已成稿' : '空白'}
                  hint={editing ? '可直接修改' : '支持 AI 重生成'}
                />
              </div>
            </div>

            {!editing ? (
              <div className="flex flex-wrap items-center gap-2 xl:max-w-[420px] xl:justify-end">
                <ActionButton
                  onClick={() => setShowRegenModal(true)}
                  disabled={regenerating}
                  icon={regenerating ? Loader2 : RefreshCw}
                  label="重新生成"
                  className="border border-surface-border bg-white text-content-secondary hover:border-brand/20 hover:bg-brand/5 hover:text-brand"
                  spinning={regenerating}
                />
                <ActionButton
                  onClick={handleCleanup}
                  disabled={cleaning}
                  icon={cleaning ? Loader2 : Trash2}
                  label="清理向导数据"
                  className="border border-red-200 bg-red-50/70 text-red-600 hover:bg-red-50"
                  spinning={cleaning}
                />
                <ActionButton
                  onClick={() => setEditing(true)}
                  icon={Pencil}
                  label="编辑内容"
                  className="bg-brand text-white shadow-[0_14px_30px_-18px_rgba(228,57,60,0.8)] hover:bg-brand-600"
                />
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-2 xl:max-w-[360px] xl:justify-end">
                <ActionButton
                  onClick={handleCancel}
                  icon={X}
                  label="取消"
                  className="border border-surface-border bg-white text-content-secondary hover:bg-surface-hover"
                />
                <ActionButton
                  onClick={handleSave}
                  disabled={saving}
                  icon={saving ? Loader2 : Save}
                  label={saving ? '保存中…' : '保存修改'}
                  className="bg-brand text-white shadow-[0_14px_30px_-18px_rgba(228,57,60,0.8)] hover:bg-brand-600"
                  spinning={saving}
                />
              </div>
            )}
          </div>
        </div>
      </section>

      {!hasContent && !editing ? (
        <section className="rounded-[24px] border border-dashed border-surface-border bg-white/80 p-10 text-center shadow-xs">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-brand/6 text-brand">
            <BookOpenText className="h-7 w-7" />
          </div>
          <h2 className="mt-4 text-lg font-semibold text-content">还没有任何世界设定</h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-content-secondary">
            先手动填写，或者用“重新生成”让系统根据项目资料自动生成初稿，再回来细修。
          </p>
        </section>
      ) : (
        <section className="grid gap-5 xl:grid-cols-2">
          {BLOCKS.map((block) => {
            const Icon = block.icon;
            const value = form[block.key];
            const filled = value.trim().length > 0;
            const wordCount = value.trim().length;

            return (
              <article
                key={block.key}
                className={`group relative overflow-hidden rounded-[24px] border border-surface-border bg-gradient-to-br ${block.panel} p-5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg ${block.glow}`}
              >
                <div className="absolute right-0 top-0 h-24 w-24 translate-x-8 -translate-y-8 rounded-full bg-white/50 blur-2xl" />
                <div className="relative flex h-full flex-col">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <span className={`mt-0.5 inline-flex h-11 w-11 items-center justify-center rounded-2xl text-white shadow-md ${block.accent}`}>
                        <Icon className="h-5 w-5" />
                      </span>
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-base font-semibold text-content">{block.label}</h3>
                          <span
                            className={`rounded-pill px-2.5 py-1 text-[11px] font-medium ${filled ? 'bg-white text-content shadow-xs' : 'bg-white/70 text-content-secondary'}`}
                          >
                            {filled ? '已设定' : '待补充'}
                          </span>
                        </div>
                        <p className="text-sm leading-6 text-content-secondary">
                          {block.description}
                        </p>
                      </div>
                    </div>
                    <span className={`shrink-0 text-xs font-medium ${block.tone}`}>
                      {wordCount} 字
                    </span>
                  </div>

                  <div className="mt-5 flex-1">
                    {editing ? (
                      <textarea
                        value={value}
                        onChange={(e) => setForm((prev) => ({ ...prev, [block.key]: e.target.value }))}
                        placeholder={block.placeholder}
                        rows={8}
                        className="min-h-[220px] w-full rounded-[18px] border border-white/80 bg-white/90 px-4 py-3 text-sm leading-7 text-content shadow-inner outline-none transition focus:border-brand/30 focus:bg-white focus:ring-4 focus:ring-brand/10 resize-none"
                      />
                    ) : (
                      <div className="min-h-[220px] rounded-[18px] border border-white/80 bg-white/80 p-4 shadow-inner">
                        <p className="text-[15px] leading-8 text-content-secondary whitespace-pre-wrap">
                          {filled ? value : '暂未设定'}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </article>
            );
          })}
        </section>
      )}

      {showRegenModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm"
          onClick={() => setShowRegenModal(false)}
        >
          <div
            className="w-full max-w-lg rounded-[24px] border border-white/60 bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="space-y-2">
              <h2 className="text-xl font-bold text-content">重新生成世界设定</h2>
              <p className="text-sm leading-6 text-content-secondary">
                系统会基于项目已有信息生成新版本，当前四个模块的内容会被覆盖。确认前建议先手动保存重要文本。
              </p>
            </div>

            <div className="mt-5 rounded-[18px] border border-surface-border bg-surface/60 p-4">
              <MCPSelector
                value={{ enable: regenEnableMcp, selected: regenPlugins }}
                onChange={({ enable, selected }) => {
                  setRegenEnableMcp(enable);
                  setRegenPlugins(selected);
                }}
              />
            </div>

            <div className="mt-6 flex flex-wrap justify-end gap-2">
              <ActionButton
                onClick={() => setShowRegenModal(false)}
                icon={X}
                label="取消"
                className="border border-surface-border bg-white text-content-secondary hover:bg-surface-hover"
              />
              <ActionButton
                onClick={handleRegenerate}
                disabled={regenerating}
                icon={regenerating ? Loader2 : RefreshCw}
                label="确认重新生成"
                className="bg-brand text-white hover:bg-brand-600"
                spinning={regenerating}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryPill({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-[18px] border border-white/70 bg-white/80 px-4 py-3 shadow-xs backdrop-blur">
      <div className="text-xs font-medium uppercase tracking-[0.14em] text-content-tertiary">
        {label}
      </div>
      <div className="mt-2 text-lg font-semibold text-content">{value}</div>
      <div className="mt-1 text-xs text-content-secondary">{hint}</div>
    </div>
  );
}

function ActionButton({
  onClick,
  disabled,
  icon: Icon,
  label,
  className,
  spinning = false,
}: {
  onClick: () => void;
  disabled?: boolean;
  icon: typeof Pencil;
  label: string;
  className: string;
  spinning?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-2 rounded-[14px] px-4 py-2.5 text-sm font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      <Icon className={`h-4 w-4 ${spinning ? 'animate-spin' : ''}`} />
      {label}
    </button>
  );
}
