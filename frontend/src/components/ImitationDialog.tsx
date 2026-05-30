/**
 * 一键仿写弹板（V3 R5）
 *
 * 流程：
 * 1. 打开后请求该项目"已挂载参考包"列表，自动按挂载默认值勾选
 * 2. 用户调整 [参考包 / 维度 / 强度 / 目标字数 / 意图]
 * 3. 点击"生成草稿" → SSE 流式接 imitate-chapter-stream
 * 4. 完成后，用户可点击"追加到正文"把累积草稿回写到当前章节编辑器
 *
 * 设计动机：见 @/agent-docs/features/book_dissect_v3_imitation_design.md §5
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Loader2, Sparkles, X } from 'lucide-react';
import { toast } from 'sonner';

import { imitationApi, referencePackApi } from '@/services/api';
import { SSEPostClient } from '@/utils/sseClient';
import type {
  ImitateChapterRequest,
  ImitationPackUsage,
  ProjectReferencePackItem,
  ReferenceDimension,
  ReferenceStrength,
} from '@/types/reference_pack';

interface ImitationDialogProps {
  isOpen: boolean;
  projectId: string;
  targetChapterId: string;
  targetChapterTitle: string;
  onClose: () => void;
  /** 用户点击「追加到正文」后回调（父组件负责把 draft 追加到当前编辑内容末尾） */
  onApply: (draft: string) => void;
}

const DIMENSION_LABELS: Record<ReferenceDimension, string> = {
  synopsis: '故事梗概', // V3.2 Story Bible 层
  // V3.2-P2 模式三维度
  entities: '实体分布',
  relations: '关系频谱',
  events: '事件节奏',
  methodology: '方法论',
  style: '文风',
  structure: '结构手法',
  archetypes: '角色塑造',
  worldbuilding: '世界观',
  // V4.1 维度
  bridges: '桥段范本',
  character_archive: '角色档案',
  corpus: '灵感语料',
};

const STRENGTH_LABELS: Record<ReferenceStrength, string> = {
  light: '轻参考',
  medium: '中参考',
  deep: '深参考',
};

export function ImitationDialog({
  isOpen,
  projectId,
  targetChapterId,
  targetChapterTitle,
  onClose,
  onApply,
}: ImitationDialogProps) {
  const [loadingAttachments, setLoadingAttachments] = useState(false);
  const [attachments, setAttachments] = useState<ProjectReferencePackItem[]>([]);

  // 表单
  const [selectedPackIds, setSelectedPackIds] = useState<string[]>([]);
  const [dimensions, setDimensions] = useState<ReferenceDimension[]>([]);
  const [strength, setStrength] = useState<ReferenceStrength>('medium');
  const [userIntent, setUserIntent] = useState('');
  const [targetWordCount, setTargetWordCount] = useState(2000);

  // 流式
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMsg, setProgressMsg] = useState('');
  const [draft, setDraft] = useState('');
  const [meta, setMeta] = useState<{
    used_packs: ImitationPackUsage[];
    used_dimensions: string[];
    strength: ReferenceStrength;
  } | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const sseClientRef = useRef<SSEPostClient | null>(null);
  const draftRef = useRef<HTMLTextAreaElement | null>(null);

  // 加载挂载列表 + 初始化默认值
  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setLoadingAttachments(true);
    setErrorMsg(null);
    referencePackApi
      .listAttachments(projectId)
      .then((items) => {
        if (cancelled) return;
        setAttachments(items);
        // 默认全选已就绪的 pack
        const readyIds = items
          .filter((x) => x.pack_summary.status === 'ready' || x.pack_summary.status === 'partial')
          .map((x) => x.pack_id);
        setSelectedPackIds(readyIds);
        // 默认维度 = 选中 pack 的 default_dimensions 并集
        const dimUnion = new Set<ReferenceDimension>();
        items
          .filter((x) => readyIds.includes(x.pack_id))
          .forEach((x) => x.default_dimensions.forEach((d) => dimUnion.add(d)));
        setDimensions(Array.from(dimUnion));
        // 默认强度 = 最深
        const rank: ReferenceStrength[] = ['light', 'medium', 'deep'];
        const max = items
          .filter((x) => readyIds.includes(x.pack_id))
          .reduce<ReferenceStrength>((acc, x) => {
            return rank.indexOf(x.default_strength) > rank.indexOf(acc) ? x.default_strength : acc;
          }, 'light');
        setStrength(max);
      })
      .catch(() => {
        if (!cancelled) toast.error('加载已挂载参考包失败');
      })
      .finally(() => {
        if (!cancelled) setLoadingAttachments(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, projectId]);

  // 关闭时清理流式连接
  useEffect(() => {
    if (!isOpen) {
      sseClientRef.current?.abort();
      sseClientRef.current = null;
      setGenerating(false);
      setProgress(0);
      setDraft('');
      setMeta(null);
      setErrorMsg(null);
    }
  }, [isOpen]);

  const togglePack = (id: string) => {
    setSelectedPackIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const toggleDimension = (d: ReferenceDimension) => {
    setDimensions((prev) => (prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d]));
  };

  // 已选 pack 真实生成的维度（用于灰显不可用项）
  const availableDimensions = useMemo(() => {
    const set = new Set<ReferenceDimension>(['corpus']); // corpus 永远可用
    attachments
      .filter((x) => selectedPackIds.includes(x.pack_id))
      .forEach((x) => x.pack_summary.generated_dimensions.forEach((d) => set.add(d as ReferenceDimension)));
    return set;
  }, [attachments, selectedPackIds]);

  const handleStart = async () => {
    if (!userIntent.trim()) {
      toast.error('请填写本次创作意图');
      return;
    }
    if (selectedPackIds.length === 0) {
      toast.error('请至少选择一个参考包');
      return;
    }

    const validDims = dimensions.filter((d) => availableDimensions.has(d));
    const finalDims = validDims.length > 0 ? validDims : ['corpus' as ReferenceDimension];

    const payload: ImitateChapterRequest = {
      user_intent: userIntent.trim(),
      target_chapter_id: targetChapterId,
      pack_ids: selectedPackIds,
      dimensions: finalDims,
      strength,
      target_word_count: targetWordCount,
    };

    setGenerating(true);
    setDraft('');
    setProgress(0);
    setProgressMsg('启动中…');
    setMeta(null);
    setErrorMsg(null);

    const client = new SSEPostClient(imitationApi.streamUrl(projectId), payload, {
      onProgress: (message, p) => {
        setProgress(p);
        if (message) setProgressMsg(message);
      },
      onChunk: (chunk) => {
        setDraft((prev) => {
          const next = prev + chunk;
          requestAnimationFrame(() => {
            if (draftRef.current) draftRef.current.scrollTop = draftRef.current.scrollHeight;
          });
          return next;
        });
      },
      onError: (err) => {
        setErrorMsg(err);
        toast.error(`仿写失败：${err}`);
      },
      onComplete: () => {
        setGenerating(false);
      },
    });
    sseClientRef.current = client;

    try {
      await client.connect();
    } catch (err) {
      const e = err as { name?: string; message?: string };
      if (e?.name !== 'AbortError') {
        if (!errorMsg) setErrorMsg(e?.message || '生成中断');
      }
    } finally {
      setGenerating(false);
      sseClientRef.current = null;
    }
  };

  // 拦截 meta 事件：sseClient 走 default 分支，我们注入一个手动监听
  // 通过 eventStream 不方便额外回调，这里用一种取巧方法：每次 onChunk 之前若 draft 还为空，可以借助一段内置文本透出 meta；
  // 改进的思路：扩展 sseClient 增加 onMessage hook。当前简单做法 — 调用 preview 也能拿到 meta，但费一次请求。
  // 折中：开始流之前先发一次 preview 请求，预填 meta（开销低且立即给用户反馈）。
  const fetchMetaPreview = async () => {
    if (!userIntent.trim() || selectedPackIds.length === 0) return;
    try {
      const validDims = dimensions.filter((d) => availableDimensions.has(d));
      const finalDims = validDims.length > 0 ? validDims : ['corpus' as ReferenceDimension];
      const res = await imitationApi.preview(projectId, {
        user_intent: userIntent.trim() || '占位意图',
        target_chapter_id: targetChapterId,
        pack_ids: selectedPackIds,
        dimensions: finalDims,
        strength,
        target_word_count: targetWordCount,
      });
      setMeta({
        used_packs: res.used_packs,
        used_dimensions: res.used_dimensions,
        strength: res.strength,
      });
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      const detail = err?.response?.data?.detail || err?.message || '';
      if (detail) setErrorMsg(detail);
    }
  };

  const handleCancel = () => {
    sseClientRef.current?.abort();
    sseClientRef.current = null;
    setGenerating(false);
    toast.info('已取消生成');
  };

  const handleApply = () => {
    if (!draft.trim()) {
      toast.error('当前没有可应用的草稿');
      return;
    }
    onApply(draft);
    toast.success('已追加到正文');
    onClose();
  };

  if (!isOpen) return null;

  const readyAttachments = attachments.filter(
    (x) => x.pack_summary.status === 'ready' || x.pack_summary.status === 'partial',
  );

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-black/50 px-4 py-8">
      <div className="relative my-auto bg-white shadow-xl w-full max-w-3xl mx-4 rounded-modal animate-scale-in max-h-[calc(100vh-4rem)] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-5 pb-3 border-b border-surface-border flex-shrink-0">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-brand" />
            <h2 className="text-lg font-bold text-content">
              一键仿写：{targetChapterTitle}
            </h2>
          </div>
          <button onClick={onClose} className="text-content-tertiary hover:text-content">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-4 space-y-4 overflow-y-auto flex-1">
          {/* 已挂载参考包选择 */}
          <section>
            <label className="block text-sm font-medium text-content mb-1.5">参考包（多选）</label>
            {loadingAttachments ? (
              <div className="flex items-center gap-2 text-sm text-content-tertiary">
                <Loader2 className="w-4 h-4 animate-spin" />加载已挂载参考包…
              </div>
            ) : readyAttachments.length === 0 ? (
              <div className="rounded-card border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                当前项目尚未挂载任何就绪的参考包。请先到「项目设置 · 参考库」挂载至少一个参考包后再使用一键仿写。
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                {readyAttachments.map((item) => (
                  <label
                    key={item.pack_id}
                    className={`flex items-start gap-2 rounded-btn border px-3 py-2 cursor-pointer transition-colors ${
                      selectedPackIds.includes(item.pack_id)
                        ? 'border-brand bg-brand/5'
                        : 'border-surface-border hover:bg-surface-hover'
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="mt-0.5 accent-brand"
                      checked={selectedPackIds.includes(item.pack_id)}
                      onChange={() => togglePack(item.pack_id)}
                    />
                    <span className="flex-1 min-w-0">
                      <span className="block text-sm font-medium text-content truncate">
                        {item.pack_summary.source_book_title}
                      </span>
                      <span className="block text-[11px] text-content-tertiary mt-0.5">
                        生成维度：{item.pack_summary.generated_dimensions.length} 个 · 默认强度：
                        {STRENGTH_LABELS[item.default_strength] || item.default_strength}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            )}
          </section>

          {/* 维度多选 */}
          <section>
            <label className="block text-sm font-medium text-content mb-1.5">参考维度（多选）</label>
            <div className="flex flex-wrap gap-1.5">
              {(Object.keys(DIMENSION_LABELS) as ReferenceDimension[]).map((d) => {
                const enabled = availableDimensions.has(d);
                const checked = dimensions.includes(d);
                return (
                  <button
                    key={d}
                    type="button"
                    disabled={!enabled}
                    onClick={() => toggleDimension(d)}
                    className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                      !enabled
                        ? 'border-surface-border text-content-tertiary opacity-40 cursor-not-allowed'
                        : checked
                          ? 'border-brand bg-brand text-white'
                          : 'border-surface-border text-content-secondary hover:bg-surface-hover'
                    }`}
                  >
                    {DIMENSION_LABELS[d]}
                  </button>
                );
              })}
            </div>
            <p className="mt-1 text-[11px] text-content-tertiary">
              灰色项表示所选参考包未生成该维度，无法启用。"灵感语料"始终可用（来自原书章节摘要）。
            </p>
          </section>

          {/* 强度 */}
          <section>
            <label className="block text-sm font-medium text-content mb-1.5">参考强度</label>
            <div className="inline-flex rounded-btn border border-surface-border overflow-hidden">
              {(Object.keys(STRENGTH_LABELS) as ReferenceStrength[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStrength(s)}
                  className={`px-3 py-1.5 text-xs transition-colors ${
                    strength === s ? 'bg-brand text-white' : 'text-content-secondary hover:bg-surface-hover'
                  }`}
                >
                  {STRENGTH_LABELS[s]}
                </button>
              ))}
            </div>
            <p className="mt-1 text-[11px] text-content-tertiary">
              轻：仅文风 · 中：核心维度按需裁剪 · 深：全维度足量参考（成本最高）
            </p>
          </section>

          {/* 目标字数 */}
          <section>
            <label className="block text-sm font-medium text-content mb-1">
              目标字数：{targetWordCount.toLocaleString()} 字
            </label>
            <input
              type="range"
              min={500}
              max={6000}
              step={250}
              value={targetWordCount}
              onChange={(e) => setTargetWordCount(Number(e.target.value))}
              className="w-full accent-brand"
            />
          </section>

          {/* 意图 */}
          <section>
            <label className="block text-sm font-medium text-content mb-1">本次创作意图</label>
            <textarea
              value={userIntent}
              onChange={(e) => setUserIntent(e.target.value)}
              onBlur={fetchMetaPreview}
              placeholder="例如：主角第一次面对宿敌；要写出从压抑到爆发的情绪曲线，结尾留个钩子"
              rows={3}
              className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none resize-y leading-relaxed"
            />
          </section>

          {/* Meta 预览 */}
          {meta && !generating && (
            <div className="rounded-card border border-surface-border bg-surface/40 px-3 py-2 text-xs text-content-secondary leading-6">
              本次将启用 <strong>{meta.used_packs.length}</strong> 个参考包，
              共 <strong>{meta.used_dimensions.length}</strong> 个维度（
              {meta.used_dimensions.map((d) => DIMENSION_LABELS[d as ReferenceDimension] || d).join(' · ')}），
              强度 <strong>{STRENGTH_LABELS[meta.strength] || meta.strength}</strong>。
            </div>
          )}

          {errorMsg && (
            <div className="rounded-card border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
              {errorMsg}
            </div>
          )}

          {/* 草稿区 */}
          {(generating || draft) && (
            <section className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-medium text-content">生成草稿</label>
                <span className="text-xs text-content-tertiary">
                  {draft.length.toLocaleString()} 字 · {progress}%
                  {progressMsg ? ` · ${progressMsg}` : ''}
                </span>
              </div>
              <textarea
                ref={draftRef}
                value={draft}
                readOnly
                rows={10}
                className="w-full border border-surface-border rounded-btn px-3 py-2 text-sm bg-surface/30 leading-relaxed resize-y"
                placeholder={generating ? 'AI 正在创作中…' : '生成完成'}
              />
            </section>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 px-6 py-3 border-t border-surface-border flex-shrink-0">
          <button
            onClick={onClose}
            className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors"
          >
            关闭
          </button>
          {generating ? (
            <button
              onClick={handleCancel}
              className="border border-red-200 text-red-600 hover:bg-red-50 rounded-btn px-4 py-2 text-sm transition-colors"
            >
              取消生成
            </button>
          ) : draft ? (
            <>
              <button
                onClick={handleStart}
                disabled={selectedPackIds.length === 0}
                className="border border-surface-border text-content-secondary hover:bg-surface-hover rounded-btn px-4 py-2 text-sm transition-colors disabled:opacity-50"
              >
                重新生成
              </button>
              <button
                onClick={handleApply}
                className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm transition-colors"
              >
                追加到正文
              </button>
            </>
          ) : (
            <button
              onClick={handleStart}
              disabled={selectedPackIds.length === 0 || !userIntent.trim() || readyAttachments.length === 0}
              className="bg-brand hover:bg-brand-600 text-white rounded-btn px-4 py-2 text-sm transition-colors disabled:opacity-50"
            >
              生成草稿
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default ImitationDialog;
