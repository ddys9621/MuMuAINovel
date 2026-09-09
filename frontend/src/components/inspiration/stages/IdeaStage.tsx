/** 灵感模式 - 第 1 步：输入故事种子 */

import { Loader2, Sparkles, Wand2 } from 'lucide-react';
import { SAMPLE_SEEDS, STEP_META } from '../copy';
import { StageCard, StageFooter, StageHeader } from '../shared';

const META = STEP_META.idea;

export function IdeaStage({
  value,
  loading,
  onChange,
  onSubmit,
}: {
  value: string;
  loading: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
}) {
  const canSubmit = Boolean(value.trim()) && !loading;

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (canSubmit) onSubmit();
    }
  };

  return (
    <StageCard>
      <StageHeader eyebrow={META.eyebrow} stepLabel="第 1 步" title={META.title} description={META.description} />

      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        rows={6}
        disabled={loading}
        placeholder={META.inputPlaceholder}
        className="hh-textarea mt-4 min-h-[160px] leading-7"
      />

      <div className="mt-3 grid grid-cols-1 items-center gap-2 sm:grid-cols-[auto_repeat(3,minmax(0,1fr))]">
        <span className="inline-flex items-center gap-1 text-xs text-content-tertiary">
          <Sparkles className="h-3.5 w-3.5" />
          试试
        </span>
        {SAMPLE_SEEDS.map((seed) => (
          <button
            key={seed}
            type="button"
            onClick={() => onChange(seed)}
            disabled={loading}
            className="hh-chip min-w-0 font-normal"
            title={seed}
          >
            <span className="truncate">{seed}</span>
          </button>
        ))}
      </div>

      <StageFooter
        left={
          <>
            Enter 发送 · Shift + Enter 换行 · {META.next}
          </>
        }
        right={
          <button type="button" onClick={onSubmit} disabled={!canSubmit} className="hh-btn-primary">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
            生成书名候选
          </button>
        }
      />
    </StageCard>
  );
}
