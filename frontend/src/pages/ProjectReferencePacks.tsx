/**
 * V3 仿写：项目挂载的参考包管理页
 *
 * 路由：/project/:projectId/reference-packs
 *
 * 功能：
 * - 列出该项目已挂载的参考包
 * - 点击"挂载"打开侧抽屉，从我的参考库中选择
 * - 支持配置默认引用维度（multi-checkbox）+ 默认强度（light/medium/deep）
 * - 卸载（弹窗确认）
 *
 * 此页是 R5 一键仿写的前置：用户必须先在这里挂载至少 1 个参考包。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  Library,
  Link2,
  Link2Off,
  Loader2,
  Plus,
  Settings2,
  Sparkles,
  X,
} from 'lucide-react';
import { toast } from 'sonner';

import { referencePackApi } from '@/services/api';
import { invalidateAttachmentsCache } from '@/components/ReferencePackSelector';
import type {
  ProjectReferencePackItem,
  ReferenceDimension,
  ReferencePackSummary,
  ReferenceStrength,
} from '@/types/reference_pack';

const DIMENSION_LABEL: Record<ReferenceDimension, string> = {
  synopsis: '故事梗概', // V3.2 Story Bible 层（粗粒度全局引导）
  // V3.2-P2 模式三维度（来自 V2 实体/关系/事件聚合，仅给类型分布与节奏信号）
  entities: '实体分布',
  relations: '关系频谱',
  events: '事件节奏',
  methodology: '写作方法论',
  style: '文风范本',
  structure: '章节结构',
  archetypes: '角色塑造',
  worldbuilding: '世界观建模',
  corpus: '灵感语料',
};

const STRENGTH_LABEL: Record<ReferenceStrength, string> = {
  light: '轻 · 仅文风',
  medium: '中 · 文风+方法论',
  deep: '深 · 全维度',
};

function inferDefaultDimensions(strength: ReferenceStrength): ReferenceDimension[] {
  if (strength === 'light') return ['style'];
  // V3.2 deep：5 手法 + Story Bible(synopsis) + 模式三维度(entities/relations/events) + corpus
  if (strength === 'deep')
    return [
      'synopsis',
      'entities',
      'relations',
      'events',
      'methodology',
      'style',
      'structure',
      'archetypes',
      'worldbuilding',
      'corpus',
    ];
  // V3.2 medium：保留与后端 _wizard_infer_default_dimensions 一致：synopsis + methodology + style + corpus
  return ['synopsis', 'methodology', 'style', 'corpus'];
}

export default function ProjectReferencePacksPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [items, setItems] = useState<ProjectReferencePackItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<ProjectReferencePackItem | null>(null);

  const fetchItems = useCallback(async () => {
    if (!projectId) return;
    try {
      setError(null);
      const data = await referencePackApi.listAttachments(projectId);
      setItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  const handleDetach = useCallback(
    async (item: ProjectReferencePackItem) => {
      if (!projectId) return;
      if (!window.confirm(`确定从本项目卸载「${item.pack_summary.source_book_title}」吗？\n（不会删除参考包本身）`)) {
        return;
      }
      try {
        await referencePackApi.detach(projectId, item.pack_id);
        setItems((prev) => prev.filter((p) => p.id !== item.id));
        invalidateAttachmentsCache(projectId); // P2-1：失效选择器缓存
        toast.success('已卸载');
      } catch (err) {
        toast.error(err instanceof Error ? err.message : '卸载失败');
      }
    },
    [projectId],
  );

  if (!projectId) {
    return null;
  }

  return (
    <div className="space-y-5 p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-semibold text-content">
            <Link2 className="h-5 w-5 text-brand" />
            仿写参考包
          </h2>
          <p className="mt-1 text-sm text-content-secondary">
            挂载到本项目的参考包，将作为一键仿写章节时的笔法 / 节奏 / 结构 / 角色 / 世界观 来源。
          </p>
        </div>
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          className="inline-flex items-center gap-1.5 rounded-pill bg-brand px-3.5 py-2 text-sm font-medium text-white hover:bg-brand-600"
        >
          <Plus className="h-4 w-4" />
          挂载参考包
        </button>
      </header>

      {loading ? (
        <CenterLoader />
      ) : error ? (
        <ErrorBox msg={error} />
      ) : items.length === 0 ? (
        <EmptyState onAdd={() => setDrawerOpen(true)} />
      ) : (
        <ul className="space-y-3">
          {items.map((it) => (
            <AttachmentRow
              key={it.id}
              item={it}
              onDetach={() => handleDetach(it)}
              onEdit={() => setEditing(it)}
            />
          ))}
        </ul>
      )}

      {drawerOpen && (
        <AttachDrawer
          projectId={projectId}
          existingPackIds={new Set(items.map((i) => i.pack_id))}
          onClose={() => setDrawerOpen(false)}
          onAttached={() => {
            setDrawerOpen(false);
            fetchItems();
          }}
        />
      )}

      {editing && (
        <EditDrawer
          item={editing}
          projectId={projectId}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            fetchItems();
          }}
        />
      )}
    </div>
  );
}

// ============================================================
// 行卡片
// ============================================================

function AttachmentRow({
  item,
  onDetach,
  onEdit,
}: {
  item: ProjectReferencePackItem;
  onDetach: () => void;
  onEdit: () => void;
}) {
  return (
    <li className="rounded-2xl border border-surface-border bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-brand shrink-0" />
            <Link
              to={`/reference-packs/${item.pack_id}`}
              className="truncate text-base font-semibold text-content hover:text-brand"
            >
              {item.pack_summary.source_book_title}
            </Link>
            <span className="rounded-pill bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300">
              {STRENGTH_LABEL[item.default_strength]}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {item.default_dimensions.map((d) => (
              <span
                key={d}
                className="rounded-pill bg-brand/10 px-2 py-0.5 text-xs text-brand"
              >
                {DIMENSION_LABEL[d]}
              </span>
            ))}
          </div>
          <div className="mt-2 text-xs text-content-tertiary">
            挂载于 {new Date(item.attached_at).toLocaleString('zh-CN', { hour12: false })}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onEdit}
            className="inline-flex items-center gap-1 rounded-pill border border-surface-border bg-surface px-3 py-1.5 text-xs font-medium text-content-secondary hover:bg-surface-hover"
          >
            <Settings2 className="h-3 w-3" />
            配置
          </button>
          <button
            type="button"
            onClick={onDetach}
            className="inline-flex items-center gap-1 rounded-pill border border-surface-border bg-surface px-3 py-1.5 text-xs font-medium text-content-tertiary hover:border-rose-500/40 hover:text-rose-300"
          >
            <Link2Off className="h-3 w-3" />
            卸载
          </button>
        </div>
      </div>
    </li>
  );
}

// ============================================================
// 挂载抽屉：从参考库选择
// ============================================================

function AttachDrawer({
  projectId,
  existingPackIds,
  onClose,
  onAttached,
}: {
  projectId: string;
  existingPackIds: Set<string>;
  onClose: () => void;
  onAttached: () => void;
}) {
  const [packs, setPacks] = useState<ReferencePackSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [strength, setStrength] = useState<ReferenceStrength>('medium');
  const [dimensions, setDimensions] = useState<ReferenceDimension[]>(inferDefaultDimensions('medium'));
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const data = await referencePackApi.list();
        setPacks(Array.isArray(data) ? data : []);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : '加载参考库失败');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const availablePacks = useMemo(
    () =>
      packs.filter(
        (p) =>
          (p.status === 'ready' || p.status === 'partial') &&
          !existingPackIds.has(p.id),
      ),
    [packs, existingPackIds],
  );

  const handleSubmit = async () => {
    if (!selected) {
      toast.warning('请先选择参考包');
      return;
    }
    setSubmitting(true);
    try {
      await referencePackApi.attach(projectId, {
        pack_id: selected,
        default_dimensions: dimensions,
        default_strength: strength,
      });
      invalidateAttachmentsCache(projectId); // P2-1：失效选择器缓存
      toast.success('挂载成功');
      onAttached();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '挂载失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStrengthChange = (s: ReferenceStrength) => {
    setStrength(s);
    setDimensions(inferDefaultDimensions(s));
  };

  return (
    <DrawerShell title="挂载参考包" onClose={onClose}>
      {loading ? (
        <CenterLoader />
      ) : availablePacks.length === 0 ? (
        <div className="rounded-xl border border-dashed border-surface-border bg-surface px-4 py-10 text-center text-sm text-content-secondary">
          <Library className="mx-auto h-6 w-6 text-content-tertiary" />
          <p className="mt-2">没有可用参考包</p>
          <p className="mt-1 text-xs text-content-tertiary">
            （已全部挂载，或参考包尚未就绪）
          </p>
          <Link
            to="/reference-packs"
            className="mt-3 inline-flex items-center gap-1 text-xs text-brand hover:underline"
          >
            去参考库 →
          </Link>
        </div>
      ) : (
        <>
          <div className="space-y-2">
            <div className="text-xs font-medium text-content-tertiary">从参考库选择</div>
            <ul className="max-h-72 space-y-1.5 overflow-y-auto rounded-xl border border-surface-border bg-surface-deeper p-2">
              {availablePacks.map((p) => {
                const active = selected === p.id;
                return (
                  <li
                    key={p.id}
                    onClick={() => setSelected(p.id)}
                    className={`cursor-pointer rounded-lg px-3 py-2 text-sm transition ${
                      active
                        ? 'bg-brand/15 ring-1 ring-brand/40 text-content'
                        : 'text-content-secondary hover:bg-surface-hover'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <BookOpen className="h-3.5 w-3.5 shrink-0 text-brand" />
                      <span className="truncate">{p.source_book_title}</span>
                      {active && <CheckCircle2 className="ml-auto h-4 w-4 shrink-0 text-brand" />}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {p.generated_dimensions.map((d) => (
                        <span
                          key={d}
                          className="rounded-pill bg-brand/10 px-1.5 py-0 text-[10px] text-brand"
                        >
                          {DIMENSION_LABEL[d as ReferenceDimension] || d}
                        </span>
                      ))}
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>

          <DimensionConfig
            strength={strength}
            dimensions={dimensions}
            onStrengthChange={handleStrengthChange}
            onDimensionsChange={setDimensions}
          />

          <div className="flex justify-end gap-2 pt-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-pill border border-surface-border bg-surface px-4 py-1.5 text-sm text-content-secondary hover:bg-surface-hover"
            >
              取消
            </button>
            <button
              type="button"
              disabled={!selected || submitting}
              onClick={handleSubmit}
              className="inline-flex items-center gap-1 rounded-pill bg-brand px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
            >
              {submitting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              挂载
            </button>
          </div>
        </>
      )}
    </DrawerShell>
  );
}

// ============================================================
// 编辑抽屉：调整已挂载的默认配置
// ============================================================

function EditDrawer({
  item,
  projectId,
  onClose,
  onSaved,
}: {
  item: ProjectReferencePackItem;
  projectId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [strength, setStrength] = useState<ReferenceStrength>(item.default_strength);
  const [dimensions, setDimensions] = useState<ReferenceDimension[]>(item.default_dimensions);
  const [submitting, setSubmitting] = useState(false);

  const handleSave = async () => {
    setSubmitting(true);
    try {
      await referencePackApi.updateAttachment(projectId, item.pack_id, {
        default_strength: strength,
        default_dimensions: dimensions,
      });
      invalidateAttachmentsCache(projectId); // P2-1：失效选择器缓存
      toast.success('已保存');
      onSaved();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <DrawerShell title={`配置「${item.pack_summary.source_book_title}」`} onClose={onClose}>
      <DimensionConfig
        strength={strength}
        dimensions={dimensions}
        onStrengthChange={(s) => {
          setStrength(s);
          setDimensions(inferDefaultDimensions(s));
        }}
        onDimensionsChange={setDimensions}
      />
      <div className="flex justify-end gap-2 pt-3">
        <button
          type="button"
          onClick={onClose}
          className="rounded-pill border border-surface-border bg-surface px-4 py-1.5 text-sm text-content-secondary hover:bg-surface-hover"
        >
          取消
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={handleSave}
          className="inline-flex items-center gap-1 rounded-pill bg-brand px-4 py-1.5 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
        >
          {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          保存
        </button>
      </div>
    </DrawerShell>
  );
}

// ============================================================
// 维度 + 强度配置（共用）
// ============================================================

function DimensionConfig({
  strength,
  dimensions,
  onStrengthChange,
  onDimensionsChange,
}: {
  strength: ReferenceStrength;
  dimensions: ReferenceDimension[];
  onStrengthChange: (s: ReferenceStrength) => void;
  onDimensionsChange: (d: ReferenceDimension[]) => void;
}) {
  const ALL_DIMS: ReferenceDimension[] = [
    'methodology', 'style', 'structure', 'archetypes', 'worldbuilding', 'corpus',
  ];

  return (
    <div className="mt-4 space-y-3">
      <div>
        <div className="text-xs font-medium text-content-tertiary">默认参考强度</div>
        <div className="mt-1.5 flex gap-1.5">
          {(['light', 'medium', 'deep'] as ReferenceStrength[]).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => onStrengthChange(s)}
              className={`rounded-pill px-3 py-1 text-xs font-medium transition ${
                strength === s
                  ? 'bg-brand text-white'
                  : 'border border-surface-border bg-surface text-content-secondary hover:bg-surface-hover'
              }`}
            >
              {STRENGTH_LABEL[s]}
            </button>
          ))}
        </div>
      </div>

      <div>
        <div className="text-xs font-medium text-content-tertiary">默认引用维度（可手动调整）</div>
        <div className="mt-1.5 grid grid-cols-2 gap-1.5">
          {ALL_DIMS.map((d) => {
            const checked = dimensions.includes(d);
            return (
              <label
                key={d}
                className={`flex cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs transition ${
                  checked
                    ? 'border-brand/50 bg-brand/10 text-brand'
                    : 'border-surface-border bg-surface text-content-secondary hover:bg-surface-hover'
                }`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(e) => {
                    if (e.target.checked) {
                      onDimensionsChange([...dimensions, d]);
                    } else {
                      onDimensionsChange(dimensions.filter((x) => x !== d));
                    }
                  }}
                  className="h-3 w-3 rounded text-brand focus:ring-brand"
                />
                {DIMENSION_LABEL[d]}
              </label>
            );
          })}
        </div>
        <p className="mt-1.5 text-[11px] text-content-tertiary">
          一键仿写时这些维度会自动注入 prompt；可在写章节时再次调整。
        </p>
      </div>
    </div>
  );
}

// ============================================================
// 共用小组件
// ============================================================

function DrawerShell({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-stretch justify-end bg-black/40 backdrop-blur-sm">
      <div
        className="absolute inset-0"
        onClick={onClose}
        aria-hidden
      />
      <aside className="relative z-10 flex w-full max-w-md flex-col bg-card shadow-2xl">
        <header className="flex items-center justify-between border-b border-surface-border px-5 py-3">
          <h3 className="text-base font-semibold text-content">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-content-tertiary hover:bg-surface-hover hover:text-content"
          >
            <X className="h-4 w-4" />
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </aside>
    </div>
  );
}

function CenterLoader() {
  return (
    <div className="flex items-center justify-center py-12 text-content-secondary">
      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      加载中...
    </div>
  );
}

function ErrorBox({ msg }: { msg: string }) {
  return (
    <div className="rounded-2xl border border-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-300">
      <AlertTriangle className="mb-1 inline h-4 w-4" />
      {msg}
    </div>
  );
}

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="rounded-2xl border border-dashed border-surface-border bg-surface px-6 py-16 text-center">
      <Library className="mx-auto h-8 w-8 text-content-tertiary" />
      <p className="mt-3 text-base font-medium text-content">还没有挂载参考包</p>
      <p className="mt-1 text-sm text-content-secondary">
        挂载后，写章节时可一键调用其笔法 / 结构 / 角色塑造 / 世界观。
      </p>
      <button
        type="button"
        onClick={onAdd}
        className="mt-4 inline-flex items-center gap-1.5 rounded-pill bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-600"
      >
        <Plus className="h-3.5 w-3.5" />
        挂载第一个参考包
      </button>
    </div>
  );
}
