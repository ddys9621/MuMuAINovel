/** 灵感模式 - 第 2~6 步：从 AI 候选里选一项（书名 / 简介 / 主题 / 类型 / 视角） */

import { useState } from 'react';
import { Check, PenLine, RefreshCw, Send, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';
import { PERSPECTIVE_HINTS, STEP_META } from '../copy';
import type { FlowStep } from '../flow';
import { Notice, OptionSkeleton, StageCard, StageFooter, StageHeader, ThinkingLine } from '../shared';

const REGENERATABLE_STEPS = new Set<FlowStep>(['title', 'description', 'theme', 'genre']);

export function ChoiceStage({
  flowStep,
  stepIndex,
  loading,
  loadingPhrases,
  prompt,
  options,
  isMultiSelect,
  selectedOptions,
  errorMessage,
  manualOpen,
  input,
  canQuickGenerate,
  onInputChange,
  onOptionSelect,
  onOpenManual,
  onCloseManual,
  onConfirmGenres,
  onQuickGenerate,
  onRegenerate,
  onRetry,
  onSend,
}: {
  flowStep: FlowStep;
  stepIndex: number;
  loading: boolean;
  loadingPhrases: string[];
  prompt?: string;
  options: string[];
  isMultiSelect: boolean;
  selectedOptions: string[];
  errorMessage?: string | null;
  manualOpen: boolean;
  input: string;
  canQuickGenerate: boolean;
  onInputChange: (value: string) => void;
  onOptionSelect: (option: string) => void;
  onOpenManual: () => void;
  onCloseManual: () => void;
  onConfirmGenres: () => void;
  onQuickGenerate: () => void;
  onRegenerate: (hint?: string) => void;
  onRetry: () => void;
  onSend: () => void;
}) {
  const meta = STEP_META[flowStep];
  const clampClass = meta.columns === 1 ? 'line-clamp-3' : 'line-clamp-2';
  const canRegenerate = REGENERATABLE_STEPS.has(flowStep) && !errorMessage;

  const handleManualKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (input.trim()) onSend();
    }
    if (event.key === 'Escape') onCloseManual();
  };

  return (
    <StageCard>
      <StageHeader
        eyebrow={meta.eyebrow}
        stepLabel={`第 ${stepIndex + 1} 步`}
        title={meta.title}
        description={loading || errorMessage ? meta.description : prompt || meta.description}
        action={
          canQuickGenerate && !loading ? (
            <button type="button" onClick={onQuickGenerate} className="hh-btn-ghost hh-btn-sm text-brand">
              <Zap className="h-3.5 w-3.5" />
              让 AI 补全剩余项
            </button>
          ) : undefined
        }
      />

      {loading ? (
        <div className="mt-5 space-y-3">
          <ThinkingLine phrases={loadingPhrases} />
          <OptionSkeleton columns={meta.columns} count={meta.columns === 2 ? 4 : 3} />
        </div>
      ) : (
        <>
          {errorMessage && (
            <Notice
              tone="error"
              className="mt-5"
              actions={
                <>
                  <button type="button" onClick={onRetry} className="hh-btn-secondary hh-btn-sm">
                    <RefreshCw className="h-3.5 w-3.5" />
                    重试
                  </button>
                  <button type="button" onClick={onOpenManual} className="hh-btn-ghost hh-btn-sm">
                    <PenLine className="h-3.5 w-3.5" />
                    {meta.manualLabel}
                  </button>
                </>
              }
            >
              {errorMessage}
            </Notice>
          )}

          <div className={cn('mt-5 grid gap-2', meta.columns === 2 && 'sm:grid-cols-2')}>
            {options.map((option, index) => {
              const selected = isMultiSelect && selectedOptions.includes(option);
              return (
                <OptionCard
                  key={option}
                  index={index}
                  label={option}
                  hint={flowStep === 'perspective' ? PERSPECTIVE_HINTS[option] : undefined}
                  clampClass={clampClass}
                  selected={selected}
                  multi={isMultiSelect}
                  onClick={() => onOptionSelect(option)}
                />
              );
            })}
            <button
              type="button"
              onClick={manualOpen ? onCloseManual : onOpenManual}
              aria-expanded={manualOpen}
              className={cn(
                'flex min-h-[56px] w-full items-center gap-3 border border-dashed px-4 py-3 text-left text-sm transition',
                // 候选为偶数时让"自己写"独占一整行，网格不留空洞
                meta.columns === 2 && options.length % 2 === 0 && 'sm:col-span-2',
                manualOpen
                  ? 'border-brand bg-brand/[0.06] text-brand'
                  : 'border-surface-border text-content-secondary hover:border-brand/50 hover:bg-white hover:text-brand',
              )}
            >
              <span className="flex h-5 w-5 shrink-0 items-center justify-center">
                <PenLine className="h-4 w-4" />
              </span>
              {meta.manualLabel}
              <span className="ml-auto text-xs text-content-tertiary">候选都不对时</span>
            </button>
          </div>

          {manualOpen && (
            <div className="mt-3 animate-slide-down border border-brand/40 bg-white/80 p-3">
              <textarea
                value={input}
                onChange={(event) => onInputChange(event.target.value)}
                onKeyDown={handleManualKeyDown}
                rows={flowStep === 'genre' || flowStep === 'perspective' ? 2 : 3}
                placeholder={meta.inputPlaceholder}
                autoFocus
                className="hh-textarea min-h-[72px] leading-6"
              />
              <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <span className="text-xs text-content-tertiary">Enter 确认 · Shift + Enter 换行 · Esc 收起</span>
                <div className="flex items-center gap-2">
                  <button type="button" onClick={onCloseManual} className="hh-btn-ghost hh-btn-sm">
                    取消
                  </button>
                  <button type="button" onClick={onSend} disabled={!input.trim()} className="hh-btn-primary hh-btn-sm">
                    <Send className="h-3.5 w-3.5" />
                    用这一项
                  </button>
                </div>
              </div>
            </div>
          )}

          <StageFooter
            left={canRegenerate ? <RegenerateControls onRegenerate={onRegenerate} /> : meta.next}
            right={
              isMultiSelect ? (
                <button
                  type="button"
                  onClick={onConfirmGenres}
                  disabled={selectedOptions.length === 0}
                  className="hh-btn-primary hh-btn-sm"
                >
                  <Check className="h-3.5 w-3.5" />
                  确认类型{selectedOptions.length > 0 ? ` (${selectedOptions.length})` : ''}
                </button>
              ) : canRegenerate ? (
                <span className="text-xs text-content-tertiary">{meta.next}</span>
              ) : undefined
            }
          />
        </>
      )}
    </StageCard>
  );
}

function OptionCard({
  index,
  label,
  hint,
  clampClass,
  selected,
  multi,
  onClick,
}: {
  index: number;
  label: string;
  hint?: string;
  clampClass: string;
  selected: boolean;
  multi: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={multi ? selected : undefined}
      title={label}
      className={cn(
        'group flex min-h-[56px] w-full items-start gap-3 border px-4 py-3 text-left transition',
        selected ? 'border-brand bg-brand/[0.06]' : 'border-surface-border bg-white/70 hover:border-brand/50 hover:bg-white',
      )}
    >
      <span
        className={cn(
          'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center border text-[11px] tabular-nums transition',
          selected
            ? 'border-brand bg-brand text-white'
            : 'border-surface-border text-content-tertiary group-hover:border-brand group-hover:text-brand',
        )}
      >
        {selected ? <Check className="h-3 w-3" /> : index + 1}
      </span>
      <span className="min-w-0 flex-1">
        <span className={cn('text-sm leading-6 text-content', clampClass)}>{label}</span>
        {hint && <span className="mt-0.5 block text-xs leading-5 text-content-tertiary">{hint}</span>}
      </span>
    </button>
  );
}

/** 换一批：可选的方向提示 + 触发按钮 */
function RegenerateControls({ onRegenerate }: { onRegenerate: (hint?: string) => void }) {
  const [hint, setHint] = useState('');

  const submit = () => {
    onRegenerate(hint.trim() || undefined);
    setHint('');
  };

  return (
    <div className="flex w-full items-center gap-2">
      <input
        type="text"
        value={hint}
        onChange={(event) => setHint(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault();
            submit();
          }
        }}
        placeholder="想换个方向？告诉 AI（可选）"
        className="hh-field h-9 min-w-0 flex-1 text-[13px] sm:max-w-[280px]"
      />
      <button type="button" onClick={submit} className="hh-btn-secondary hh-btn-sm shrink-0">
        <RefreshCw className="h-3.5 w-3.5" />
        换一批
      </button>
    </div>
  );
}
