/** 灵感模式 - 各阶段共用的展示原子：阶段卡、标题、摘要列表、等待指示、骨架、提示条 */

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, ChevronDown, Info, Loader2, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

export function StageCard({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn('hh-subpanel animate-fade-in p-5', className)}>{children}</section>;
}

export function StageHeader({
  eyebrow,
  stepLabel,
  title,
  description,
  action,
}: {
  eyebrow: string;
  stepLabel?: string;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em]">
          <span className="text-brand">{eyebrow}</span>
          {stepLabel && <span className="text-content-tertiary">· {stepLabel}</span>}
        </div>
        <h3 className="mt-1.5 text-lg font-semibold leading-7 tracking-tight text-content">{title}</h3>
        {description && (
          <p className="mt-1 line-clamp-2 text-sm leading-6 text-content-secondary" title={typeof description === 'string' ? description : undefined}>
            {description}
          </p>
        )}
      </div>
      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </div>
  );
}

export function StageFooter({ left, right }: { left?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mt-5 flex flex-col gap-3 border-t border-surface-border/80 pt-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 flex-1 text-xs leading-5 text-content-tertiary">{left}</div>
      {right && <div className="flex shrink-0 flex-wrap items-center gap-2">{right}</div>}
    </div>
  );
}

export interface SummaryItem {
  key: string;
  label: string;
  value?: string;
}

/** 已确定字段的"收据"列表：固定标签列 + 单行截断的值，点一行展开全文 */
export function SummaryList({
  items,
  defaultOpen = true,
  title = '已确定',
}: {
  items: SummaryItem[];
  defaultOpen?: boolean;
  title?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const visible = items.filter((item) => item.value?.trim());

  useEffect(() => {
    setOpen(defaultOpen);
  }, [defaultOpen]);

  if (visible.length === 0) return null;

  return (
    <section className="hh-subpanel overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-5 py-3 text-left transition hover:bg-white/70"
      >
        <span className="flex items-center gap-2 text-sm font-medium text-content">
          {title}
          <span className="hh-tag px-1.5 py-0 text-[11px] tabular-nums">{visible.length}</span>
        </span>
        <span className="flex items-center gap-2 text-xs text-content-tertiary">
          {!open && <span className="hidden truncate sm:inline">{visible.map((item) => item.label).join(' · ')}</span>}
          <ChevronDown className={cn('h-4 w-4 transition-transform', open && 'rotate-180')} />
        </span>
      </button>

      {open && (
        <ul className="divide-y divide-surface-border/70 border-t border-surface-border/80">
          {visible.map((item) => {
            const isExpanded = Boolean(expanded[item.key]);
            return (
              <li key={item.key} className="animate-slide-down">
                <button
                  type="button"
                  onClick={() => setExpanded((current) => ({ ...current, [item.key]: !isExpanded }))}
                  aria-expanded={isExpanded}
                  className="grid w-full grid-cols-[3.5rem_minmax(0,1fr)_1rem] items-start gap-3 px-5 py-2.5 text-left transition hover:bg-brand/[0.04]"
                >
                  <span className="pt-1 text-xs font-medium text-content-tertiary">{item.label}</span>
                  <span
                    className={cn(
                      'text-sm leading-6 text-content',
                      isExpanded ? 'whitespace-pre-wrap break-words' : 'truncate',
                    )}
                  >
                    {item.value}
                  </span>
                  <ChevronDown
                    className={cn('mt-1.5 h-3.5 w-3.5 text-content-tertiary transition-transform', isExpanded && 'rotate-180')}
                  />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/** 等待 AI 返回时的状态行：轮播短句 + 计时；挂载即开始计时 */
export function ThinkingLine({ phrases, className }: { phrases: string[]; className?: string }) {
  const startedAt = useRef(Date.now());
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const rotate = window.setInterval(() => setPhraseIndex((index) => (index + 1) % phrases.length), 2400);
    const tick = window.setInterval(() => setElapsed(Math.floor((Date.now() - startedAt.current) / 1000)), 1000);
    return () => {
      window.clearInterval(rotate);
      window.clearInterval(tick);
    };
  }, [phrases.length]);

  const phrase = phrases[phraseIndex] ?? phrases[0] ?? '正在思考';

  return (
    <div className={cn('flex items-center gap-2 text-sm text-content-secondary', className)} role="status" aria-live="polite">
      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-brand" />
      <span key={phrase} className="animate-fade-in">
        {phrase}
        <span className="inline-block w-4 text-left">…</span>
      </span>
      {elapsed >= 5 && <span className="text-xs text-content-tertiary tabular-nums">{elapsed}s</span>}
      {elapsed >= 30 && <span className="text-xs text-content-tertiary">模型响应较慢，请稍候</span>}
    </div>
  );
}

/** 长时间等待时轮播的提示文案，每条停留 intervalMs */
export function RotatingTip({ tips, intervalMs = 7000 }: { tips: string[]; intervalMs?: number }) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (tips.length <= 1) return;
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % tips.length), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs, tips.length]);

  const tip = tips[index] ?? tips[0];
  return (
    <span key={tip} className="block animate-fade-in">
      {tip}
    </span>
  );
}

const SKELETON_WIDTHS = ['w-3/4', 'w-1/2', 'w-2/3', 'w-5/6', 'w-3/5', 'w-4/5'];

/** 候选卡片骨架：与真实候选网格同构，避免加载完成后跳动 */
export function OptionSkeleton({ columns, count = 4 }: { columns: 1 | 2; count?: number }) {
  return (
    <div className={cn('grid gap-2', columns === 2 && 'sm:grid-cols-2')} aria-hidden>
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="flex min-h-[56px] items-start gap-3 border border-surface-border/80 bg-white/50 px-4 py-3">
          <span className="mt-0.5 h-5 w-5 shrink-0 animate-pulse bg-brand/10" />
          <span className="flex min-w-0 flex-1 flex-col gap-2 pt-1">
            <span className={cn('h-3 animate-pulse bg-brand/10', SKELETON_WIDTHS[index % SKELETON_WIDTHS.length])} />
            {columns === 1 && <span className={cn('h-3 animate-pulse bg-brand/[0.07]', SKELETON_WIDTHS[(index + 3) % SKELETON_WIDTHS.length])} />}
          </span>
        </div>
      ))}
    </div>
  );
}

type NoticeTone = 'info' | 'warning' | 'error' | 'success';

const NOTICE_STYLE: Record<NoticeTone, { box: string; Icon: typeof Info }> = {
  info: { box: 'border-brand/20 bg-brand/[0.05] text-content-secondary', Icon: Info },
  warning: { box: 'border-amber-200 bg-amber-50/80 text-amber-800', Icon: AlertTriangle },
  error: { box: 'border-red-200 bg-red-50/80 text-red-700', Icon: XCircle },
  success: { box: 'border-emerald-200 bg-emerald-50/80 text-emerald-700', Icon: CheckCircle2 },
};

export function Notice({
  tone = 'info',
  children,
  actions,
  className,
}: {
  tone?: NoticeTone;
  children: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  const { box, Icon } = NOTICE_STYLE[tone];
  return (
    <div
      role="status"
      className={cn(
        'flex flex-col gap-3 border px-4 py-3 text-sm leading-6 sm:flex-row sm:items-center sm:justify-between',
        box,
        className,
      )}
    >
      <div className="flex min-w-0 items-start gap-2">
        <Icon className="mt-1 h-4 w-4 shrink-0" />
        <span className="min-w-0 break-words">{children}</span>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
