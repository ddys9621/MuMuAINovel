/**
 * V3 仿写参考包：详情页（7 tab 浏览）
 *
 * Tab 1-5：来自 ReferencePack 的 5 个 JSON 字段（"如何写"指南）
 * Tab 6：灵感语料（实体 / 关系 / 事件，复用 V2 端点）
 * Tab 7：原书章节（chapter_facts，复用 V2 端点）
 *
 * 设计原则：
 * - 5 个 V3 tab 都强调展示 writing_tips（"如何写"提示），不是原书内容复述
 * - 数据按需懒加载（tab 切换时才拉，避免一次性加载大量章节）
 */
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  Brain,
  Building2,
  Compass,
  Download,
  FileText,
  Flame,
  GitBranch,
  Loader2,
  Palette,
  Quote,
  Sparkles,
  UserSquare,
  Users,
  X,
} from 'lucide-react';
import { toast } from 'sonner';

import {
  bookDissectApi,
  projectApi,
  referencePackApi,
  writingStyleApi,
} from '@/services/api';
import type {
  BookDissectV2ChapterSummary,
  BookDissectV2Entity,
  BookDissectV2Event,
  BookDissectV2Relation,
  Project,
} from '@/types';
import type {
  ArchetypeData,
  BridgesData,
  CharacterArchiveData,
  MethodologyData,
  ReferencePackDetail,
  ReferencePackStatus,
  StructureData,
  StyleData,
  WorldbuildingData,
} from '@/types/reference_pack';

// ============================================================
// Tab 定义
// ============================================================

type TabKey =
  | 'synopsis' // V3.2：故事骨架（Story Bible 层）
  | 'methodology'
  | 'style'
  | 'structure'
  | 'archetypes'
  | 'worldbuilding'
  | 'bridges' // V4.1：桥段范本库
  | 'character_archive' // V4.1：完整角色档案
  | 'corpus'
  | 'chapters';

interface TabConfig {
  key: TabKey;
  label: string;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
}

const TABS: TabConfig[] = [
  // V3.2 Story Bible 层放在最前，让用户先看到全局骨架
  { key: 'synopsis', label: '0. 故事骨架', hint: 'V3.2：类型/前提/金手指/升级体系（Story Bible 层）', icon: Sparkles },
  { key: 'methodology', label: '1. 写作方法论', hint: '金手指 / 开篇 / 打脸 / 升级 / 爽点', icon: Brain },
  { key: 'style', label: '2. 文风范本', hint: '可直接挂到项目的笔法 prompt', icon: Palette },
  { key: 'structure', label: '3. 章节结构', hint: '开篇 / 中段冲突 / 结尾钩', icon: FileText },
  { key: 'archetypes', label: '4. 角色塑造', hint: '主角 / 配角 / 反派的塑造手法', icon: Users },
  { key: 'worldbuilding', label: '5. 世界观建模', hint: '时代 / 地点层级 / 规则平衡', icon: Compass },
  // V4.1 维度：桥段反推 + 角色档案
  { key: 'bridges', label: '6. 桥段范本', hint: 'V4.1：原书桥段反推（4 章结构 + 装逼类型分布）', icon: GitBranch },
  { key: 'character_archive', label: '7. 角色档案', hint: 'V4.1：完整角色档案（主角/反派/配角全维度）', icon: UserSquare },
  { key: 'corpus', label: '8. 灵感语料', hint: '具体角色 / 地点 / 事件可作为灵感素材', icon: Quote },
  { key: 'chapters', label: '9. 原书章节', hint: '回查原书章节摘要', icon: BookOpen },
];

const STATUS_CLASS: Record<ReferencePackStatus, string> = {
  generating: 'bg-amber-500/15 text-amber-300',
  ready: 'bg-emerald-500/15 text-emerald-300',
  partial: 'bg-orange-500/15 text-orange-300',
  failed: 'bg-rose-500/15 text-rose-300',
};

const STATUS_LABEL: Record<ReferencePackStatus, string> = {
  generating: '生成中',
  ready: '就绪',
  partial: '部分就绪',
  failed: '失败',
};

// ============================================================
// 主页
// ============================================================

export default function ReferencePackDetailPage() {
  const { packId } = useParams<{ packId: string }>();
  const [pack, setPack] = useState<ReferencePackDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // V3.2：默认优先 synopsis（Story Bible 层），让用户先看到全局骨架
  const [tab, setTab] = useState<TabKey>('synopsis');

  useEffect(() => {
    if (!packId) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const data = await referencePackApi.get(packId);
        if (!cancelled) {
          setPack(data);
          // 默认打开第一个有内容的 tab（synopsis 优先；老包没 synopsis 自动落到 methodology）
          const firstReady = TABS.find(({ key }) => {
            if (key === 'corpus' || key === 'chapters') return false;
            return data[key as keyof ReferencePackDetail] != null;
          });
          if (firstReady) setTab(firstReady.key);
        }
      } catch (err) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : '加载失败';
          setError(msg);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [packId]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-content-secondary">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        加载中...
      </div>
    );
  }
  if (error || !pack) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/5 p-6 text-rose-300">
          <AlertTriangle className="mb-2 h-5 w-5" />
          <p className="font-medium">加载参考包失败</p>
          <p className="mt-1 text-sm">{error || '未找到参考包'}</p>
          <Link to="/reference-packs" className="mt-3 inline-flex items-center gap-1 text-xs text-brand hover:underline">
            <ArrowLeft className="h-3 w-3" />
            返回参考库
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-6">
      <Header pack={pack} />
      <TabBar tab={tab} setTab={setTab} pack={pack} />
      <div className="mt-4">
        {tab === 'synopsis' && (
          <SynopsisTab data={pack.synopsis ?? null} />
        )}
        {tab === 'methodology' && (
          <MethodologyTab data={pack.methodology as MethodologyData | null} />
        )}
        {tab === 'style' && (
          <StyleTab
            data={pack.style as StyleData | null}
            sourceBookTitle={pack.source_book_title}
          />
        )}
        {tab === 'structure' && <StructureTab data={pack.structure as StructureData | null} />}
        {tab === 'archetypes' && <ArchetypeTab data={pack.archetypes as ArchetypeData | null} />}
        {tab === 'worldbuilding' && <WorldbuildingTab data={pack.worldbuilding as WorldbuildingData | null} />}
        {tab === 'bridges' && <BridgesTab data={pack.bridges as BridgesData | null} />}
        {tab === 'character_archive' && <CharacterArchiveTab data={pack.character_archive as CharacterArchiveData | null} />}
        {tab === 'corpus' && <CorpusTab taskId={pack.task_id} />}
        {tab === 'chapters' && <ChaptersTab taskId={pack.task_id} />}
      </div>
    </div>
  );
}

// ============================================================
// 头部
// ============================================================

function Header({ pack }: { pack: ReferencePackDetail }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
      <div>
        <Link
          to="/reference-packs"
          className="inline-flex items-center gap-1 text-xs text-content-secondary hover:text-brand"
        >
          <ArrowLeft className="h-3 w-3" />
          返回参考库
        </Link>
        <h1 className="mt-1 flex flex-wrap items-center gap-2 text-2xl font-semibold text-content">
          <BookOpen className="h-6 w-6 text-brand" />
          {pack.source_book_title}
          <span className={`inline-flex items-center rounded-pill px-2 py-0.5 text-xs font-medium ${STATUS_CLASS[pack.status]}`}>
            {STATUS_LABEL[pack.status]}
          </span>
        </h1>
        <p className="mt-1 text-xs text-content-tertiary">
          已挂载到 {pack.attached_project_count} 个项目 · 创建于{' '}
          {new Date(pack.created_at).toLocaleString('zh-CN', { hour12: false })}
        </p>
        {pack.error_message && (
          <div className="mt-2 inline-flex items-center gap-1 rounded-md bg-orange-500/10 px-2 py-1 text-xs text-orange-300">
            <AlertTriangle className="h-3 w-3" />
            {pack.error_message}
          </div>
        )}
      </div>
    </div>
  );
}

function TabBar({
  tab,
  setTab,
  pack,
}: {
  tab: TabKey;
  setTab: (k: TabKey) => void;
  pack: ReferencePackDetail;
}) {
  function isAvailable(key: TabKey): boolean {
    if (key === 'corpus' || key === 'chapters') return true; // V2 数据始终可用
    return pack[key as keyof ReferencePackDetail] != null;
  }
  return (
    <div className="border-b border-surface-border">
      <div className="flex flex-wrap gap-1">
        {TABS.map((t) => {
          const active = tab === t.key;
          const available = isAvailable(t.key);
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => setTab(t.key)}
              className={`group relative flex items-center gap-2 px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
                active
                  ? 'border-brand text-brand'
                  : available
                    ? 'border-transparent text-content-secondary hover:text-content'
                    : 'border-transparent text-content-tertiary opacity-60'
              }`}
              title={t.hint}
            >
              <t.icon className="h-3.5 w-3.5" />
              {t.label}
              {!available && (
                <span className="text-xs text-content-tertiary">(无)</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================
// Tab 0：故事骨架（V3.2 Story Bible 层）
// ============================================================

const SYNOPSIS_FIELD_LABELS: Record<string, string> = {
  genre: '类型',
  sub_genre: '子类型',
  core_premise: '核心前提',
  golden_finger: '金手指',
  power_system: '升级体系',
  central_conflict: '主线冲突',
  ultimate_goal: '终极目标',
  selling_points: '卖点',
  target_audience_signals: '目标读者信号',
};

// 字段顺序（与 SYNOPSIS_PROMPT 输出一致）；其它字段排在最后
const SYNOPSIS_FIELD_ORDER = [
  'genre',
  'sub_genre',
  'core_premise',
  'central_conflict',
  'ultimate_goal',
  'golden_finger',
  'power_system',
  'selling_points',
  'target_audience_signals',
];

function SynopsisTab({ data }: { data: Record<string, unknown> | null }) {
  if (!data) return <NoDataHint label="故事骨架（V3.2）" />;
  const knownKeys = new Set(SYNOPSIS_FIELD_ORDER);
  const orderedKeys = [
    ...SYNOPSIS_FIELD_ORDER.filter((k) => k in data),
    ...Object.keys(data).filter((k) => !knownKeys.has(k)),
  ];
  return (
    <div className="space-y-4">
      <SectionTip>
        <strong>Story Bible 层</strong>：故事「类型骨架」抽象描述，作为生成时的全局风向引导。
        <strong>不含原书具体人/地/物名</strong>，仅作方向参考，禁止复刻具体设定。
      </SectionTip>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {orderedKeys.map((key) => {
          const v = data[key];
          if (v == null || v === '') return null;
          const label = SYNOPSIS_FIELD_LABELS[key] || key;
          // 标量直接 Field；对象/数组用 DimensionCard 展开
          if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
            return (
              <Card key={key}>
                <Field label={label} value={v} multiline />
              </Card>
            );
          }
          if (Array.isArray(v)) {
            return (
              <Card key={key}>
                <Field label={label} value={v.join('、')} multiline />
              </Card>
            );
          }
          if (typeof v === 'object') {
            return (
              <DimensionCard
                key={key}
                icon={Sparkles}
                title={label}
                data={v as Record<string, unknown>}
              />
            );
          }
          return null;
        })}
      </div>
    </div>
  );
}

// ============================================================
// Tab 1：写作方法论
// ============================================================

function MethodologyTab({ data }: { data: MethodologyData | null }) {
  if (!data) return <NoDataHint label="方法论" />;
  return (
    <div className="space-y-4">
      <SectionTip>
        本 tab 总结的是<strong>"作者怎么写"</strong>的方法论，而不是原书剧情。
        请把 <em>writing_tips</em> 当成你写自己项目时的借鉴清单。
      </SectionTip>
      <DimensionCard
        icon={Flame}
        title="金手指模式"
        data={data.golden_finger_pattern}
        fields={[
          ['type', '类型'],
          ['balance_mechanism', '平衡机制'],
          ['evolution_pattern', '演化模式'],
          ['writing_tips', '怎么用'],
        ]}
      />
      <DimensionCard
        icon={Flame}
        title="开篇钩子"
        data={data.opening_hook_pattern}
        fields={[
          ['hook_type', '钩子类型'],
          ['first_chapter_strategy', '首章策略'],
          ['writing_tips', '怎么用'],
        ]}
      />
      <DimensionCard
        icon={Flame}
        title="打脸节奏"
        data={data.facepunch_rhythm}
        fields={[
          ['small_facepunch_freq', '小打脸频率'],
          ['big_facepunch_freq', '大打脸频率'],
          ['three_elements_pattern', '三要素模式'],
          ['writing_tips', '怎么用'],
        ]}
      />
      <DimensionCard
        icon={Flame}
        title="升级路线"
        data={data.power_progression}
        fields={[
          ['system_type', '体系类型'],
          ['level_count', '层级数'],
          ['pace', '节奏'],
          ['writing_tips', '怎么用'],
        ]}
      />
      <DimensionCard
        icon={Flame}
        title="爽点密度"
        data={data.highlight_density}
        fields={[
          ['small_per_n_chapters', '每 N 章一小爽点'],
          ['medium_per_n_chapters', '每 N 章一中爽点'],
          ['big_per_n_chapters', '每 N 章一大爽点'],
          ['writing_tips', '怎么用'],
        ]}
      />
    </div>
  );
}

// ============================================================
// Tab 2：文风范本
// ============================================================

function StyleTab({
  data,
  sourceBookTitle,
}: {
  data: StyleData | null;
  sourceBookTitle: string;
}) {
  const [importOpen, setImportOpen] = useState(false);
  if (!data) return <NoDataHint label="文风范本" />;
  const canImport = !!data.prompt_content;
  return (
    <div className="space-y-4">
      <SectionTip>
        <strong>prompt_content</strong> 可直接挂载为项目的写作风格 prompt，
        让 AI 写章节时自动遵循该笔法。
      </SectionTip>
      <Card>
        <Field label="风格名称" value={data.name} />
        <Field label="描述" value={data.description} multiline />
        {data.traits && data.traits.length > 0 && (
          <div className="mt-3">
            <div className="mb-1 text-xs font-medium text-content-tertiary">关键特征</div>
            <div className="flex flex-wrap gap-1.5">
              {data.traits.map((t) => (
                <span
                  key={t}
                  className="rounded-pill bg-brand/10 px-2 py-0.5 text-xs text-brand"
                >
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}
        <div className="mt-3">
          <div className="mb-1 text-xs font-medium text-content-tertiary">prompt_content（可复用）</div>
          <pre className="whitespace-pre-wrap rounded-lg border border-surface-border bg-surface-deeper p-3 text-sm text-content">
            {data.prompt_content || '（缺失）'}
          </pre>
          {canImport && (
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(data.prompt_content || '');
                  toast.success('已复制 prompt_content');
                }}
                className="rounded-pill border border-surface-border bg-surface px-3 py-1 text-xs text-content-secondary hover:bg-surface-hover"
              >
                复制
              </button>
              <button
                type="button"
                onClick={() => setImportOpen(true)}
                className="inline-flex items-center gap-1 rounded-pill bg-brand px-3 py-1 text-xs font-medium text-white hover:bg-brand-600"
                title="把这份文风作为新的写作风格条目添加到某个项目"
              >
                <Download className="h-3 w-3" />
                导入到项目写作风格库
              </button>
            </div>
          )}
        </div>
      </Card>
      {importOpen && (
        <ImportStyleDialog
          style={data}
          sourceBookTitle={sourceBookTitle}
          onClose={() => setImportOpen(false)}
        />
      )}
    </div>
  );
}

// ============================================================
// 文风导入对话框：把参考包的 style 拷贝到指定项目的写作风格库
// ============================================================

function ImportStyleDialog({
  style,
  sourceBookTitle,
  onClose,
}: {
  style: StyleData;
  sourceBookTitle: string;
  onClose: () => void;
}) {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [projectId, setProjectId] = useState<string>('');
  const baseName = style.name?.trim() || '未命名风格';
  const [name, setName] = useState<string>(`${baseName} · 拆书：${sourceBookTitle}`);
  const [submitting, setSubmitting] = useState(false);
  const [createdStyleId, setCreatedStyleId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    projectApi
      .getProjects()
      .then((res) => {
        if (cancelled) return;
        const items = (res?.items ?? []) as Project[];
        setProjects(items);
        if (items.length > 0) setProjectId(items[0].id);
      })
      .catch(() => {
        if (!cancelled) toast.error('加载项目列表失败');
      })
      .finally(() => {
        if (!cancelled) setLoadingProjects(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = async () => {
    if (!projectId) {
      toast.error('请先选择目标项目');
      return;
    }
    if (!name.trim()) {
      toast.error('请填写风格名称');
      return;
    }
    if (!style.prompt_content) {
      toast.error('该参考包文风缺少 prompt_content，无法导入');
      return;
    }
    setSubmitting(true);
    try {
      const created = await writingStyleApi.createStyle({
        project_id: projectId,
        name: name.trim(),
        description: style.description || `来自拆书：${sourceBookTitle}`,
        prompt_content: style.prompt_content,
        style_type: 'custom',
      });
      // createStyle 返回 WritingStyle，含 id
      setCreatedStyleId((created as { id: number }).id);
      toast.success('已导入到项目写作风格库');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : '导入失败');
    } finally {
      setSubmitting(false);
    }
  };

  // 已导入完成的成功视图
  if (createdStyleId !== null) {
    return (
      <DialogShell title="导入成功" onClose={onClose}>
        <div className="space-y-3 text-sm text-content">
          <p>
            已把「<strong>{name}</strong>」添加到目标项目的写作风格库。
          </p>
          <p className="text-xs text-content-secondary">
            接下来你可以在「项目 → 写作风格」里把它设为默认，或在章节生成时手动选择。
          </p>
          <div className="flex gap-2 pt-1">
            <Link
              to={`/project/${projectId}/writing-styles`}
              className="rounded-pill bg-brand px-3 py-1 text-xs font-medium text-white hover:bg-brand-600"
            >
              去查看 →
            </Link>
            <button
              type="button"
              onClick={onClose}
              className="rounded-pill border border-surface-border bg-surface px-3 py-1 text-xs text-content-secondary hover:bg-surface-hover"
            >
              关闭
            </button>
          </div>
        </div>
      </DialogShell>
    );
  }

  return (
    <DialogShell title="导入到项目写作风格库" onClose={onClose}>
      <div className="space-y-4 text-sm">
        <div>
          <label className="mb-1 block text-xs font-medium text-content-tertiary">
            目标项目
          </label>
          {loadingProjects ? (
            <div className="flex items-center gap-2 text-xs text-content-secondary">
              <Loader2 className="h-3 w-3 animate-spin" />
              加载项目列表…
            </div>
          ) : !projects || projects.length === 0 ? (
            <div className="rounded-lg border border-dashed border-surface-border bg-surface px-3 py-2 text-xs text-content-secondary">
              你还没有创建任何项目。请先在
              <Link to="/projects" className="mx-1 text-brand hover:underline">
                项目列表
              </Link>
              里新建一个。
            </div>
          ) : (
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="w-full rounded-lg border border-surface-border bg-white px-3 py-2 text-sm text-content focus:border-brand focus:outline-none"
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                </option>
              ))}
            </select>
          )}
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-content-tertiary">
            写作风格名称
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-surface-border bg-white px-3 py-2 text-sm text-content focus:border-brand focus:outline-none"
            placeholder="给这份风格起个名字"
          />
          <p className="mt-1 text-[11px] text-content-tertiary">
            默认带"拆书：原书名"后缀，方便日后区分来源。
          </p>
        </div>

        <div className="rounded-lg border border-surface-border bg-surface-deeper p-3">
          <div className="mb-1 text-[11px] font-medium text-content-tertiary">
            将作为 prompt_content 的内容（只读预览）
          </div>
          <pre className="max-h-32 overflow-auto whitespace-pre-wrap text-xs text-content">
            {style.prompt_content || '（缺失）'}
          </pre>
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="rounded-pill border border-surface-border bg-surface px-3 py-1.5 text-xs text-content-secondary hover:bg-surface-hover disabled:opacity-60"
          >
            取消
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting || loadingProjects || !projects || projects.length === 0}
            className="inline-flex items-center gap-1.5 rounded-pill bg-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-600 disabled:opacity-60"
          >
            {submitting ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Download className="h-3 w-3" />
            )}
            确认导入
          </button>
        </div>
      </div>
    </DialogShell>
  );
}

function DialogShell({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-black/50 px-4 py-8">
      <div className="relative my-auto w-full max-w-lg rounded-modal bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-surface-border px-5 py-3">
          <h3 className="text-sm font-semibold text-content">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-content-tertiary hover:text-content"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

// ============================================================
// Tab 3：章节结构
// ============================================================

function StructureTab({ data }: { data: StructureData | null }) {
  if (!data) return <NoDataHint label="章节结构手法" />;
  return (
    <div className="space-y-4">
      <SectionTip>
        从原书的开篇 / 中段 / 结尾抽样，反推作者的<strong>章节级结构手法</strong>。
        每段都给"具体怎么写"的建议（writing_tips）。
      </SectionTip>
      <DimensionCard icon={FileText} title="开篇模式" data={data.opening_pattern} />
      <DimensionCard icon={FileText} title="中段冲突升级" data={data.midpoint_conflict_escalation} />
      <DimensionCard icon={FileText} title="结尾钩子" data={data.ending_hook_pattern} />
    </div>
  );
}

// ============================================================
// Tab 4：角色塑造
// ============================================================

function ArchetypeTab({ data }: { data: ArchetypeData | null }) {
  if (!data) return <NoDataHint label="角色塑造手法" />;
  return (
    <div className="space-y-4">
      <SectionTip>
        <strong>不是抽角色本身</strong>，而是反推作者怎么塑造主角 / 配角 / 反派 ——
        这些手法可以套到你自己设计的角色上。
      </SectionTip>
      <DimensionCard icon={Users} title="主角塑造手法" data={data.protagonist_archetype} />
      <DimensionCard icon={Users} title="配角塑造手法" data={data.supporting_archetype} />
      <DimensionCard icon={Users} title="反派塑造手法" data={data.antagonist_archetype} />
    </div>
  );
}

// ============================================================
// Tab 5：世界观建模
// ============================================================

function WorldbuildingTab({ data }: { data: WorldbuildingData | null }) {
  if (!data) return <NoDataHint label="世界观建模手法" />;
  return (
    <div className="space-y-4">
      <SectionTip>
        <strong>不是抽世界本身</strong>，而是反推作者怎么搭这种世界 ——
        时代锚点选什么、地点怎么分层、规则怎么平衡。
      </SectionTip>
      <DimensionCard icon={Compass} title="时代设计" data={data.era_design} />
      <DimensionCard icon={Building2} title="地点层级设计" data={data.location_hierarchy_design} />
      <DimensionCard icon={Compass} title="规则平衡设计" data={data.rule_balance_design} />
    </div>
  );
}

// ============================================================
// Tab 6：灵感语料
// ============================================================

function CorpusTab({ taskId }: { taskId: string }) {
  const [entities, setEntities] = useState<BookDissectV2Entity[] | null>(null);
  const [relations, setRelations] = useState<BookDissectV2Relation[] | null>(null);
  const [events, setEvents] = useState<BookDissectV2Event[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [es, rs, evs] = await Promise.all([
          bookDissectApi.v2ListEntities(taskId),
          bookDissectApi.v2ListRelations(taskId),
          bookDissectApi.v2ListEvents(taskId),
        ]);
        if (!cancelled) {
          setEntities(Array.isArray(es) ? es : []);
          setRelations(Array.isArray(rs) ? rs : []);
          setEvents(Array.isArray(evs) ? evs : []);
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : '加载失败');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [taskId]);

  if (loading) return <CenterLoader />;
  if (err) return <NoDataHint label={`灵感语料加载失败：${err}`} />;

  return (
    <div className="space-y-4">
      <SectionTip>
        这里是从原书抽出的具体<strong>实体 / 关系 / 事件</strong>。
        可作为灵感素材参考，但不要直接复刻（这会成为抄袭风险）。
      </SectionTip>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <CountCard label="实体" count={entities?.length ?? 0} />
        <CountCard label="关系" count={relations?.length ?? 0} />
        <CountCard label="事件" count={events?.length ?? 0} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <h3 className="mb-2 text-sm font-medium text-content">实体（前 20）</h3>
          <ul className="space-y-1 text-xs">
            {(entities || []).slice(0, 20).map((e) => (
              <li key={e.id} className="flex items-center justify-between text-content-secondary">
                <span className="truncate">{e.canonical_name}</span>
                <span className="text-content-tertiary">{e.entity_type}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <h3 className="mb-2 text-sm font-medium text-content">事件（前 20）</h3>
          <ul className="space-y-1 text-xs">
            {(events || []).slice(0, 20).map((ev) => (
              <li key={ev.id} className="text-content-secondary">
                <span className="text-content-tertiary">第{ev.chapter_number}章</span>{' '}
                <span className="truncate">{ev.title}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <h3 className="mb-2 text-sm font-medium text-content">关系（前 20）</h3>
          <ul className="space-y-1 text-xs">
            {(relations || []).slice(0, 20).map((r) => (
              <li key={r.id} className="text-content-secondary">
                <span className="truncate">{r.relation_type}</span>{' '}
                <span className="text-content-tertiary">({r.relation_category})</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}

// ============================================================
// Tab 7：原书章节
// ============================================================

function ChaptersTab({ taskId }: { taskId: string }) {
  const [chapters, setChapters] = useState<BookDissectV2ChapterSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await bookDissectApi.v2ListChapters(taskId);
        if (!cancelled) setChapters(Array.isArray(data) ? data : []);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : '加载失败');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [taskId]);

  if (loading) return <CenterLoader />;
  if (err) return <NoDataHint label={`章节加载失败：${err}`} />;

  return (
    <div className="space-y-4">
      <SectionTip>
        原书章节列表，便于核对参考包内容是否准确反映原书结构。
        如需查看完整章节事实详情，请到拆书页打开任务的 V2 视图。
      </SectionTip>
      <Card>
        <ul className="divide-y divide-surface-border">
          {chapters.map((c) => (
            <li key={c.id} className="flex items-center gap-3 py-2 text-xs">
              <span className="rounded-pill bg-brand/10 px-2 py-0.5 text-brand shrink-0">
                第{c.chapter_number}章
              </span>
              <span className="truncate font-medium text-content">{c.chapter_title || '—'}</span>
              <span className="ml-auto shrink-0 text-content-tertiary">
                {c.extraction_status}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

// ============================================================
// 共用小组件
// ============================================================

function NoDataHint({ label }: { label: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-surface-border bg-surface px-6 py-12 text-center text-content-secondary">
      <AlertTriangle className="mx-auto h-6 w-6 text-content-tertiary" />
      <p className="mt-2 text-sm">该参考包未生成「{label}」维度</p>
      <p className="mt-1 text-xs text-content-tertiary">可能是 LLM 调用失败，可重新拆书生成</p>
    </div>
  );
}

function CenterLoader() {
  return (
    <div className="flex items-center justify-center py-10 text-content-secondary">
      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      加载中...
    </div>
  );
}

function SectionTip({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-brand/20 bg-brand/5 px-4 py-2.5 text-xs text-content-secondary">
      {children}
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-surface-border bg-surface p-4">
      {children}
    </div>
  );
}

function CountCard({ label, count }: { label: string; count: number }) {
  return (
    <div className="rounded-xl border border-surface-border bg-surface px-4 py-3">
      <div className="text-xs text-content-tertiary">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-content">{count}</div>
    </div>
  );
}

function Field({
  label,
  value,
  multiline = false,
}: {
  label: string;
  value: unknown;
  multiline?: boolean;
}) {
  if (value == null || value === '') return null;
  return (
    <div className="mb-2 last:mb-0">
      <div className="text-xs font-medium text-content-tertiary">{label}</div>
      <div
        className={`text-sm text-content ${multiline ? 'whitespace-pre-wrap leading-6' : ''}`}
      >
        {String(value)}
      </div>
    </div>
  );
}

interface DimensionCardProps {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  data: Record<string, unknown> | null | undefined;
  /** 字段顺序提示。若不传，则按 data 自身 key 渲染。 */
  fields?: Array<[string, string]>;
}

/**
 * 把任意 dimension value 安全渲染为字符串（支持嵌套 dict / array / primitive）。
 *
 * 修复 V4.1/V4.2 bridge_length_distribution 等嵌套 dict 字段渲染为
 * "[object Object]" 的 bug。
 */
function renderDimensionValue(v: unknown): string {
  if (v == null) return '';
  if (Array.isArray(v)) {
    return v
      .map((item) =>
        typeof item === 'object' && item !== null
          ? renderDimensionValue(item)
          : String(item),
      )
      .join('、');
  }
  if (typeof v === 'object') {
    // 嵌套对象：键值对扁平化为 "key: value" 形式，逗号分隔
    return Object.entries(v as Record<string, unknown>)
      .map(([k, val]) => `${k}: ${renderDimensionValue(val)}`)
      .join('，');
  }
  return String(v);
}

function DimensionCard({ icon: Icon, title, data, fields }: DimensionCardProps) {
  if (!data) {
    return (
      <Card>
        <div className="flex items-center gap-2 text-sm text-content-tertiary">
          <Icon className="h-4 w-4" />
          {title}
          <span className="ml-2 text-xs">(未生成)</span>
        </div>
      </Card>
    );
  }
  const entries: Array<[string, string]> = fields
    ? fields
    : Object.keys(data).map((k) => [k, k]);
  return (
    <Card>
      <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-content">
        <Icon className="h-4 w-4 text-brand" />
        {title}
      </h3>
      <div className="space-y-2">
        {entries.map(([key, label]) => {
          const v = (data as Record<string, unknown>)[key];
          if (v == null || v === '') return null;
          const isTip = key.includes('writing_tips') || key === 'writing_tips';
          return (
            <div
              key={key}
              className={`rounded-lg px-3 py-2 ${
                isTip
                  ? 'bg-brand/10 ring-1 ring-brand/20'
                  : 'bg-surface-deeper'
              }`}
            >
              <div className="text-xs font-medium text-content-tertiary">
                {isTip && '💡 '}
                {label}
              </div>
              <div className="mt-0.5 whitespace-pre-wrap text-sm leading-6 text-content">
                {renderDimensionValue(v)}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ============================================================
// Tab 6（V4.1）：桥段范本库
// ============================================================

function BridgesTab({ data }: { data: BridgesData | null }) {
  if (!data) return <NoDataHint label="桥段范本库（V4.1）" />;

  const total = (data.total_bridges_detected as number | undefined) ?? 0;
  const standard = (data.standard_bridges as number | undefined) ?? 0;
  const variant = (data.variant_bridges as number | undefined) ?? 0;
  const types = Array.isArray(data.bridge_types) ? data.bridge_types : [];

  return (
    <div className="space-y-4">
      <SectionTip>
        <strong>V4.1 桥段反推</strong>：从原书 ChapterFact 用 4 章滑动窗口反推标准桥段（代入/拉扯/兑现/善后）。
        <strong>用于桥段规划场景做范本参考</strong>，让 AI 不是凭空想，而是参考原书装逼节奏。
      </SectionTip>

      {/* 总览 3 数字 */}
      <div className="grid grid-cols-3 gap-3">
        <Card>
          <div className="text-xs text-content-tertiary">识别桥段总数</div>
          <div className="mt-1 text-2xl font-semibold text-brand">{total}</div>
        </Card>
        <Card>
          <div className="text-xs text-content-tertiary">标准 4 章桥段</div>
          <div className="mt-1 text-2xl font-semibold text-emerald-300">{standard}</div>
        </Card>
        <Card>
          <div className="text-xs text-content-tertiary">变体桥段</div>
          <div className="mt-1 text-2xl font-semibold text-amber-300">{variant}</div>
        </Card>
      </div>

      {/* 桥段类型分布 */}
      {types.length > 0 && (
        <Card>
          <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-content">
            <GitBranch className="h-4 w-4 text-brand" />
            桥段类型分布（按出现次数排序）
          </h3>
          <div className="space-y-2">
            {types.map((t, i) => {
              const typeName = String((t as Record<string, unknown>).type ?? '未分类');
              const count = (t as Record<string, unknown>).count as number | undefined;
              const avgScore = (t as Record<string, unknown>).avg_score as number | undefined;
              const examples = Array.isArray((t as Record<string, unknown>).typical_examples)
                ? ((t as Record<string, unknown>).typical_examples as Array<Record<string, unknown>>)
                : [];
              return (
                <div key={`${typeName}-${i}`} className="rounded-lg bg-surface-deeper px-3 py-2">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-content">{typeName}</span>
                    <span className="text-xs text-content-tertiary">
                      {count ?? 0} 次 · 平均评分 {avgScore != null ? avgScore.toFixed(2) : '-'}
                    </span>
                  </div>
                  {examples.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {examples.slice(0, 3).map((ex, j) => {
                        const chapters = Array.isArray(ex.chapters) ? ex.chapters.join('-') : '';
                        const goal = ex.goal ? String(ex.goal) : '';
                        const showoff = ex.showoff_point ? String(ex.showoff_point) : '';
                        return (
                          <li key={j} className="rounded bg-surface px-2 py-1 text-xs text-content-secondary">
                            <span className="text-content-tertiary">第 {chapters} 章</span>
                            {goal && <span className="ml-2">· 目标：{goal}</span>}
                            {showoff && <span className="ml-2">· 装逼点：{showoff}</span>}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* 节奏指标 */}
      {data.rhythm_stats != null && (
        <DimensionCard
          icon={Flame}
          title="节奏指标"
          data={data.rhythm_stats as Record<string, unknown>}
        />
      )}

      {/* 金手指多样性 */}
      {data.golden_finger_diversity != null && (
        <DimensionCard
          icon={Sparkles}
          title="金手指多样性"
          data={data.golden_finger_diversity as Record<string, unknown>}
        />
      )}
    </div>
  );
}

// ============================================================
// Tab 7（V4.1）：完整角色档案
// ============================================================

function CharacterArchiveTab({ data }: { data: CharacterArchiveData | null }) {
  if (!data) return <NoDataHint label="完整角色档案（V4.1）" />;

  const protagonists = Array.isArray(data.protagonist_archetypes)
    ? data.protagonist_archetypes
    : [];
  const antagonists = Array.isArray(data.antagonist_progression)
    ? data.antagonist_progression
    : [];
  const supports = Array.isArray(data.support_character_techniques)
    ? data.support_character_techniques
    : [];

  // V4.2.3：统计 fallback 兜底升级的主角数量（前端可见 hint）
  const inferredCount = protagonists.filter(
    (p) => (p as Record<string, unknown>)._inferred === true,
  ).length;

  return (
    <div className="space-y-4">
      <SectionTip>
        <strong>V4.1 完整角色档案</strong>：从 Entity + Relation + Event 聚合的全维度角色信息。
        <strong>给角色生成场景做范本</strong>，让 AI 知道原书是怎么塑造主角/反派/配角的。
      </SectionTip>

      {inferredCount > 0 && (
        <div className="rounded-lg border border-amber-300/60 bg-amber-50 px-3 py-2 text-xs text-amber-700">
          <strong>⚙ 系统推断提示</strong>：本档案中 {inferredCount} 位主角是因 LLM 未明确标注 protagonist
          而由系统按出场频次兜底升级（短篇 / 反派当主角 / 反英雄故事常见）。
          鼠标悬停 ⚙ 标记可查看原 LLM 标记。
        </div>
      )}

      {/* 主角范式 */}
      <section>
        <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-content">
          <UserSquare className="h-4 w-4 text-brand" />
          主角范式 <span className="text-xs text-content-tertiary">({protagonists.length})</span>
        </h3>
        {protagonists.length === 0 ? (
          <Card>
            <p className="text-xs text-content-tertiary">
              未识别主角（V4.2.3 三层兜底后理论上不会发生，除非无任何 person 实体）
            </p>
          </Card>
        ) : (
          <div className="space-y-3">
            {protagonists.map((p, i) => {
              const rec = p as Record<string, unknown>;
              const isInferred = rec._inferred === true;
              const origRole =
                typeof rec._inferred_original_role === 'string'
                  ? (rec._inferred_original_role as string)
                  : null;
              const ORIG_LABEL: Record<string, string> = {
                protagonist: '主角',
                supporting: '配角',
                antagonist: '反派',
                minor: '次要',
              };
              const baseName = String(rec.name ?? `主角 ${i + 1}`);
              // 标题字符串内嵌 ⚙ 标记（保持 DimensionCard.title: string 不变）
              const title = isInferred ? `${baseName} ⚙` : baseName;
              const wrapperTooltip = isInferred
                ? `系统推断主角（原 LLM 标记：${origRole && ORIG_LABEL[origRole] ? ORIG_LABEL[origRole] : origRole ?? '未标记'}）`
                : undefined;
              return (
                <div
                  key={i}
                  className={isInferred ? 'rounded-lg border border-amber-300/40 p-0.5' : ''}
                  title={wrapperTooltip}
                >
                  <DimensionCard icon={UserSquare} title={title} data={rec} />
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 反派演进 */}
      <section>
        <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-content">
          <Flame className="h-4 w-4 text-brand" />
          反派演进 <span className="text-xs text-content-tertiary">({antagonists.length})</span>
        </h3>
        {antagonists.length === 0 ? (
          <Card>
            <p className="text-xs text-content-tertiary">未识别反派</p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {antagonists.map((p, i) => (
              <DimensionCard
                key={i}
                icon={Flame}
                title={String((p as Record<string, unknown>).name ?? `反派 ${i + 1}`)}
                data={p as Record<string, unknown>}
              />
            ))}
          </div>
        )}
      </section>

      {/* 配角手法 */}
      <section>
        <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-content">
          <Users className="h-4 w-4 text-brand" />
          配角手法 <span className="text-xs text-content-tertiary">({supports.length})</span>
        </h3>
        {supports.length === 0 ? (
          <Card>
            <p className="text-xs text-content-tertiary">未识别配角分类</p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
            {supports.map((s, i) => (
              <DimensionCard
                key={i}
                icon={Users}
                title={String((s as Record<string, unknown>).category ?? (s as Record<string, unknown>).type ?? `配角组 ${i + 1}`)}
                data={s as Record<string, unknown>}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
