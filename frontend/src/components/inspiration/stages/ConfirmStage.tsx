/** 灵感模式 - 第 7 步：创建前确认（字段本身由上方"已确定"列表承载，这里只展示将要生成什么） */

import { ChevronRight, Play, RotateCcw, Wand2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { NODE_META, STEP_META } from '../copy';
import { formatBookTitle } from '../flow';
import { Notice, StageCard, StageFooter, StageHeader } from '../shared';
import type { GenStepStatus } from '../types';
import type { GenerationNodeKey } from '../useProjectGeneration';

const META = STEP_META.confirm;

interface ResumeOption {
  /** 中断在哪个环节 */
  node: GenerationNodeKey;
  /** 各环节当前状态，用于在流水线格子上标出已完成 / 失败 */
  steps: Record<GenerationNodeKey, GenStepStatus>;
  onResume: () => void;
}

export function ConfirmStage({
  bookTitle,
  errorMessage,
  missingFields,
  resume,
  onConfirm,
  onRestart,
}: {
  bookTitle?: string;
  errorMessage?: string | null;
  /** 仍为空的必填字段名；非空时不允许创建 */
  missingFields: string[];
  /** 项目已建但中途失败：提供从失败环节继续的入口，避免重建出一个重复项目 */
  resume?: ResumeOption;
  onConfirm: () => void;
  onRestart: () => void;
}) {
  const blocked = missingFields.length > 0;
  const title = formatBookTitle(bookTitle);
  const resumeLabel = resume ? NODE_META.find((node) => node.key === resume.node)?.label ?? '' : '';

  return (
    <StageCard>
      <StageHeader
        eyebrow={META.eyebrow}
        stepLabel="第 7 步"
        title={resume ? `${title}创建中断，可从「${resumeLabel}」继续` : `一切就绪，准备创建${title}`}
        description={
          resume
            ? '已完成的环节保留在项目里；继续时会先清理中断环节的残留数据，再从这里往后重新生成。'
            : META.description
        }
      />

      {blocked && (
        <Notice tone="warning" className="mt-5">
          还缺少{missingFields.join('、')}，暂时无法创建；请「重新开始」补齐这些信息。
        </Notice>
      )}
      {!blocked && errorMessage && (
        <Notice tone="warning" className="mt-5">
          {resume ? `「${resumeLabel}」环节中断：` : '上一次创建没有完整结束：'}
          {errorMessage}
          {resume && errorMessage.toLowerCase().includes('fetch') ? '（浏览器与后端的连接断开了，后端可能已在后台把该环节做完，继续前会自动清理）' : ''}
        </Notice>
      )}

      <ol className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {NODE_META.map((node, index) => {
          const status = resume?.steps[node.key];
          return (
            <li
              key={node.key}
              className={cn(
                'relative flex items-center gap-2.5 border px-3.5 py-3',
                status === 'completed'
                  ? 'border-emerald-200 bg-emerald-50/60'
                  : status === 'error'
                    ? 'border-red-200 bg-red-50/60'
                    : 'border-surface-border/80 bg-white/70',
              )}
            >
              <node.icon
                className={cn(
                  'h-4 w-4 shrink-0',
                  status === 'completed' ? 'text-emerald-600' : status === 'error' ? 'text-red-500' : 'text-brand',
                )}
              />
              <span className="min-w-0">
                <span className="block text-sm font-medium leading-5 text-content">{node.label}</span>
                <span className="block truncate text-xs leading-5 text-content-tertiary">
                  {status === 'completed' ? '已完成，保留' : status === 'error' ? '中断，从这里继续' : node.hint}
                </span>
              </span>
              {index < NODE_META.length - 1 && (
                <ChevronRight className="absolute -right-[11px] top-1/2 hidden h-3.5 w-3.5 -translate-y-1/2 text-content-tertiary sm:block" />
              )}
            </li>
          );
        })}
      </ol>

      <StageFooter
        left={
          resume
            ? '重新开始会放弃这个项目的向导流程（项目本身仍保留在列表里）。'
            : '通常需要几分钟，期间请留在当前页面；每一步的结果之后都能在项目里单独修改。'
        }
        right={
          <>
            <button type="button" onClick={onRestart} className="hh-btn-ghost hh-btn-sm">
              <RotateCcw className="h-3.5 w-3.5" />
              重新开始
            </button>
            {resume ? (
              <button type="button" onClick={resume.onResume} disabled={blocked} className="hh-btn-primary">
                <Play className="h-4 w-4" />
                从「{resumeLabel}」继续
              </button>
            ) : (
              <button type="button" onClick={onConfirm} disabled={blocked} className="hh-btn-primary">
                <Wand2 className="h-4 w-4" />
                {errorMessage ? '重新创建项目' : '开始创建项目'}
              </button>
            )}
          </>
        }
      />
    </StageCard>
  );
}
