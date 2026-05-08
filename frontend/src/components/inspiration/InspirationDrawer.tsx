import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import {
  BookOpenText,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Globe,
  Loader2,
  RefreshCw,
  RotateCcw,
  Send,
  Sparkles,
  Users,
  Wand2,
  X,
  XCircle,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { MCPSelector } from '@/components/MCPSelector';
import { useInspirationMachine } from '@/components/inspiration/useInspirationMachine';
import {
  type GenerationArtifacts,
  type GenerationNodeKey,
  useProjectGeneration,
} from '@/components/inspiration/useProjectGeneration';
import type { GenStepStatus, Message, Step, WizardData } from '@/components/inspiration/types';
import type { MCPSelectorValue } from '@/components/MCPSelector';

interface InspirationDrawerProps {
  open: boolean;
  onClose: () => void;
  onEnterProject: (projectId: string) => void;
  onProjectCreated?: (projectId: string) => void | Promise<void>;
}

const NODE_META: Array<{
  key: GenerationNodeKey;
  label: string;
  hint: string;
}> = [
  { key: 'worldBuilding', label: '世界观', hint: '先把舞台和规则搭稳。' },
  { key: 'characters', label: '角色', hint: '再补主角群和关系。' },
  { key: 'outline', label: '大纲', hint: '最后落成可执行故事线。' },
];

const FLOW_STEPS = ['idea', 'title', 'description', 'theme', 'genre', 'perspective', 'confirm'] as const;
type FlowStep = (typeof FLOW_STEPS)[number];

const CONFIRM_CREATE_OPTION = '✅ 确认创建';
const MANUAL_INPUT_OPTIONS = new Set(['我自己输入书名', '我自己输入']);
const INLINE_INPUT_STEPS = new Set<FlowStep>(['title', 'description', 'theme', 'genre', 'perspective']);

const STEP_META: Record<
  FlowStep,
  {
    eyebrow: string;
    title: string;
    description: string;
    inputPlaceholder?: string;
    inputHint?: string;
  }
> = {
  idea: {
    eyebrow: '灵感原稿',
    title: '先把故事种子说完整',
    description: '首屏只做一件事：收下你的灵感原稿。书名、简介和主题都应该在下一步再出现。',
  },
  title: {
    eyebrow: '书名',
    title: '先定一个抓人的书名方向',
    description: '这一屏只解决书名，不再把历史记录和确认动作塞进来。',
    inputPlaceholder: '不满意候选时，直接写一版你自己的书名方向',
    inputHint: '自己写的内容会直接成为下一轮简介生成的依据。',
  },
  description: {
    eyebrow: '简介',
    title: '把故事简介收紧成一句主卖点',
    description: '先把前提和主冲突说清楚，再进入主题判断。',
    inputPlaceholder: '直接写你想要的简介版本',
    inputHint: 'AI 会基于这版简介继续推主题和类型。',
  },
  theme: {
    eyebrow: '主题',
    title: '确认作品真正想讨论的主题',
    description: '这一步只保留主题候选和自定义输入，不再让其他 CTA 抢主导。',
    inputPlaceholder: '如果候选不对，直接写下你要表达的主题',
    inputHint: '主题会继续影响后面的类型和视角生成。',
  },
  genre: {
    eyebrow: '类型',
    title: '多选出最贴近的类型组合',
    description: '类型阶段应该是选择面板，不该再出现全局聊天输入。',
    inputPlaceholder: '例如：洪荒流、系统流、轻喜剧修仙',
    inputHint: '自定义类型会直接进入视角选择，不需要再额外确认。',
  },
  perspective: {
    eyebrow: '视角',
    title: '只决定叙事视角',
    description: '这一步只保留视角选择和一个明确的“其他视角”入口。',
    inputPlaceholder: '例如：限知第三人称、双主角交替视角',
    inputHint: '确认视角后，页面会进入最终评审，不再显示输入区。',
  },
  confirm: {
    eyebrow: '确认',
    title: '信息已收齐，进入创建前评审',
    description: '确认页应该像评审页，而不是再塞进普通聊天消息里。',
  },
};

const LOADING_COPY: Partial<Record<Step, string>> = {
  loading_title: 'AI 正在拆你的灵感锚点，先生成一轮书名候选。',
  loading_desc: 'AI 正在把书名扩成简介候选，主舞台保持当前问题，不再跳空。',
  loading_theme: 'AI 正在从简介里抽主题，接下来只会出现主题候选。',
  loading_genre: 'AI 正在组合类型标签，下一屏会切到多选面板。',
};

export default function InspirationDrawer({
  open,
  onClose,
  onEnterProject,
  onProjectCreated,
}: InspirationDrawerProps) {
  const {
    state,
    dispatch,
    sendMessage,
    selectOption,
    confirmGenres,
    quickGenerate,
    regenerateOptions,
    reset,
  } = useInspirationMachine();

  const [input, setInput] = useState('');
  const [manualInputOpen, setManualInputOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [mcpSettings, setMcpSettings] = useState<MCPSelectorValue>({ enable: false, selected: [] });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const announcedProjectIdRef = useRef('');

  const { artifacts, runningNode, startGeneration, regenerateFrom, cancelGeneration, resetArtifacts } =
    useProjectGeneration({
      dispatch,
      mcpSettings,
    });

  const wizardData = state.wizardData as Partial<WizardData>;
  const flowStep = getFlowStep(state.currentStep);
  const flowMeta = STEP_META[flowStep];
  const activeStepIndex = FLOW_STEPS.indexOf(flowStep);
  const readyToGenerate = Boolean(
    wizardData.title &&
      wizardData.description &&
      wizardData.theme &&
      wizardData.genre?.length &&
      wizardData.narrative_perspective,
  );

  const originalBrief = useMemo(
    () => state.messages.find((message) => message.type === 'user')?.content,
    [state.messages],
  );

  const activeQuestion = useMemo(
    () =>
      [...state.messages]
        .reverse()
        .find((message) => message.type === 'ai' && message.options?.length && !message.disabled),
    [state.messages],
  );

  const historyMessages = useMemo(
    () => state.messages.filter((message) => message.id !== activeQuestion?.id),
    [activeQuestion?.id, state.messages],
  );

  const stageOptions = useMemo(
    () => activeQuestion?.options?.filter((option) => !MANUAL_INPUT_OPTIONS.has(option)) ?? [],
    [activeQuestion?.options],
  );

  const showGenerationBoard =
    state.projectId || Object.values(state.generationSteps).some((status) => status !== 'pending');
  const hasCollectedSummary = Boolean(
    originalBrief ||
      wizardData.title ||
      wizardData.description ||
      wizardData.theme ||
      wizardData.genre?.length ||
      wizardData.narrative_perspective,
  );

  const isGenerating = state.currentStep === 'generating';
  const isIdeaStep = state.currentStep === 'idea';
  const isComplete = state.currentStep === 'complete';
  const stagePrompt = activeQuestion?.content || LOADING_COPY[state.currentStep] || flowMeta.description;
  const showInlineInput =
    !state.loading && !isGenerating && !isComplete && INLINE_INPUT_STEPS.has(flowStep) && manualInputOpen;
  const canQuickGenerate =
    !isIdeaStep &&
    flowStep !== 'confirm' &&
    !isGenerating &&
    !isComplete &&
    Boolean(wizardData.title || wizardData.description || wizardData.theme || wizardData.genre?.length) &&
    !(state.currentStep === 'genre' && state.selectedOptions.length > 0);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleEscape);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleEscape);
    };
  }, [onClose, open]);

  useEffect(() => {
    return () => {
      cancelGeneration();
    };
  }, [cancelGeneration]);

  useEffect(() => {
    if (historyOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [historyMessages, historyOpen]);

  useEffect(() => {
    if (state.currentStep === 'idea') {
      resetArtifacts();
    }
  }, [resetArtifacts, state.currentStep]);

  useEffect(() => {
    setManualInputOpen(false);
  }, [state.currentStep]);

  useEffect(() => {
    if (isComplete) {
      setHistoryOpen(true);
    }
  }, [isComplete]);

  useEffect(() => {
    if (state.currentStep !== 'generating' || runningNode || state.progress > 0 || !readyToGenerate) {
      return;
    }
    void startGeneration(wizardData as WizardData);
  }, [readyToGenerate, runningNode, startGeneration, state.currentStep, state.progress, wizardData]);

  useEffect(() => {
    if (!state.projectId || announcedProjectIdRef.current === state.projectId) {
      return;
    }
    announcedProjectIdRef.current = state.projectId;
    void onProjectCreated?.(state.projectId);
  }, [onProjectCreated, state.projectId]);

  const handleSend = async () => {
    if (!input.trim() || state.loading) return;
    const value = input.trim();
    setInput('');
    await sendMessage(value);
    setManualInputOpen(false);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  };

  const handleOptionSelect = async (option: string) => {
    if (MANUAL_INPUT_OPTIONS.has(option)) {
      setManualInputOpen(true);
      return;
    }
    setManualInputOpen(false);
    await selectOption(option);
  };

  const handleRegenerate = async (node: GenerationNodeKey) => {
    if (!state.projectId || !readyToGenerate || runningNode) return;

    if (
      node !== 'outline' &&
      !window.confirm('会清理该节点后的旧角色、大纲和章节，再从当前节点向后重跑。继续吗？')
    ) {
      return;
    }

    await regenerateFrom(node, wizardData as WizardData, state.projectId);
  };

  const handleReset = () => {
    const hasStartedWorkflow = Boolean(state.projectId || state.progress > 0 || historyMessages.length > 0);
    if (
      hasStartedWorkflow &&
      !window.confirm('这会清空当前创作流程，并忽略正在返回的旧生成结果。继续吗？')
    ) {
      return;
    }

    announcedProjectIdRef.current = '';
    cancelGeneration();
    setInput('');
    setManualInputOpen(false);
    setHistoryOpen(false);
    setAdvancedOpen(false);
    resetArtifacts();
    reset();
  };

  return (
    <div className={cn('fixed inset-0 z-50 transition', open ? 'pointer-events-auto' : 'pointer-events-none')} aria-hidden={!open}>
      <div
        className={cn('absolute inset-0 bg-slate-950/24 transition-opacity duration-200', open ? 'opacity-100' : 'opacity-0')}
        onClick={onClose}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="inspiration-drawer-title"
        className={cn(
          'absolute right-0 top-0 flex h-full w-full max-w-[840px] flex-col border-l border-slate-200 bg-[#fcfbf8] shadow-[0_20px_80px_-36px_rgba(15,23,42,0.35)] transition-transform duration-300',
          open ? 'translate-x-0' : 'translate-x-full',
        )}
      >
        <header className="border-b border-slate-200 bg-[#fcfbf8]/95 px-4 py-4 backdrop-blur md:px-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="inline-flex items-center gap-1.5 rounded-full border border-brand/10 bg-brand/8 px-3 py-1 text-xs font-medium text-brand">
                <Sparkles className="h-3.5 w-3.5" />
                灵感创作
              </div>
              <h2 id="inspiration-drawer-title" className="mt-2 text-lg font-semibold text-content">从灵感直接到建项</h2>
              <p className="mt-1 text-sm text-content-secondary">
                不再跳独立页面。当前步骤、已填内容和生成进度都放在右侧抽屉里。
              </p>
            </div>

            <div className="flex shrink-0 items-center gap-2">
              <button
                onClick={handleReset}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-content-secondary transition hover:text-content"
              >
                <RotateCcw className="h-4 w-4" />
                重新开始
              </button>
              <button
                onClick={onClose}
                className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-content-secondary transition hover:text-content"
                aria-label="关闭灵感创作抽屉"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_120px]">
            <div className="flex gap-2 overflow-x-auto pb-1">
              {FLOW_STEPS.map((step, index) => (
                <FlowStepChip
                  key={step}
                  label={getFlowStepLabel(step)}
                  status={getFlowChipStatus(index, activeStepIndex, state.currentStep)}
                />
              ))}
            </div>

            <div className="rounded-xl border border-slate-200 bg-white px-3 py-2">
              <div className="flex items-center justify-between text-[11px] uppercase tracking-[0.14em] text-content-tertiary">
                <span>进度</span>
                <span>{getFlowProgressLabel(state.currentStep, activeStepIndex)}</span>
              </div>
              <div className="mt-2 h-1.5 rounded-full bg-surface-border">
                <div
                  className="h-1.5 rounded-full bg-brand transition-all duration-500"
                  style={{ width: `${getFlowProgressValue(state.currentStep, activeStepIndex)}%` }}
                />
              </div>
            </div>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="space-y-4 px-4 py-4 md:px-5 md:py-5">
            {hasCollectedSummary && !isComplete && (
              <CollectedSummary
                originalBrief={originalBrief}
                wizardData={wizardData}
                currentStep={state.currentStep}
                progress={state.progress}
                progressMessage={state.progressMessage}
              />
            )}

            {isGenerating || isComplete ? (
              <GenerationStageCard
                state={state}
                wizardData={wizardData}
                originalBrief={originalBrief}
                onEnterProject={() => state.projectId && onEnterProject(state.projectId)}
              />
            ) : flowStep === 'confirm' ? (
              <ConfirmStageCard
                state={state}
                wizardData={wizardData}
                originalBrief={originalBrief}
                onConfirm={() => void selectOption(CONFIRM_CREATE_OPTION)}
                onReset={handleReset}
              />
            ) : isIdeaStep ? (
              <IdeaStageCard
                state={state}
                input={input}
                onInputChange={setInput}
                onKeyDown={handleKeyDown}
                onSend={() => void handleSend()}
              />
            ) : (
              <QuestionStageCard
                state={state}
                flowStep={flowStep}
                flowMeta={flowMeta}
                prompt={stagePrompt}
                options={stageOptions}
                activeQuestion={activeQuestion}
                manualInputOpen={manualInputOpen}
                input={input}
                showInlineInput={showInlineInput}
                canQuickGenerate={canQuickGenerate}
                onInputChange={setInput}
                onOptionSelect={handleOptionSelect}
                onOpenManualInput={() => setManualInputOpen(true)}
                onCloseManualInput={() => setManualInputOpen(false)}
                onConfirmGenres={confirmGenres}
                onQuickGenerate={() => void quickGenerate()}
                onRegenerateOptions={(hint) => void regenerateOptions(hint)}
                onKeyDown={handleKeyDown}
                onSend={() => void handleSend()}
              />
            )}

            {showGenerationBoard && (
              <section className="space-y-3">
                <div>
                  <div className="text-sm font-medium text-content">生成节点</div>
                  <p className="mt-1 text-sm text-content-secondary">这里只保留必要进度和重跑入口，不再铺满首屏。</p>
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  {NODE_META.map((node) => (
                    <NodeCard
                      key={node.key}
                      node={node}
                      status={state.generationSteps[node.key]}
                      artifacts={artifacts}
                      runningNode={runningNode}
                      onRegenerate={handleRegenerate}
                      canRegenerate={Boolean(state.projectId && readyToGenerate)}
                    />
                  ))}
                </div>
              </section>
            )}

            <AdvancedSection
              open={advancedOpen}
              onToggle={() => setAdvancedOpen((value) => !value)}
              mcpSettings={mcpSettings}
              setMcpSettings={setMcpSettings}
            />

            {historyMessages.length > 0 && (
              <HistoryPanel
                open={historyOpen}
                onToggle={() => setHistoryOpen((value) => !value)}
                messages={historyMessages}
                messagesEndRef={messagesEndRef}
              />
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}

function CollectedSummary({
  originalBrief,
  wizardData,
  currentStep,
  progress,
  progressMessage,
}: {
  originalBrief?: string;
  wizardData: Partial<WizardData>;
  currentStep: Step;
  progress: number;
  progressMessage: string;
}) {
  const isGenerating = currentStep === 'generating' || currentStep === 'complete';

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-content">已收集内容</div>
          <p className="mt-1 text-sm text-content-secondary">当前抽屉只保留原始灵感和已确认字段。</p>
        </div>

        {isGenerating && (
          <div className="min-w-[180px] rounded-xl border border-slate-200 bg-[#faf7f2] px-3 py-2">
            <div className="flex items-center justify-between text-xs text-content-tertiary">
              <span>创建进度</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="mt-2 h-1.5 rounded-full bg-surface-border">
              <div
                className="h-1.5 rounded-full bg-brand transition-all duration-500"
                style={{ width: `${Math.min(progress, 100)}%` }}
              />
            </div>
            <p className="mt-2 text-xs leading-5 text-content-secondary">{progressMessage || '正在准备...'}</p>
          </div>
        )}
      </div>

      {originalBrief && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-[#faf7f2] p-3">
          <div className="text-xs uppercase tracking-[0.14em] text-content-tertiary">原始灵感</div>
          <p className="mt-2 text-sm leading-7 text-content-secondary">{originalBrief}</p>
        </div>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <SummaryField label="书名" value={wizardData.title} />
        <SummaryField label="简介" value={wizardData.description} />
        <SummaryField label="主题" value={wizardData.theme} />
        <SummaryField label="类型" value={wizardData.genre?.join('、')} />
        <SummaryField label="视角" value={wizardData.narrative_perspective} />
      </div>
    </section>
  );
}

function IdeaStageCard({
  state,
  input,
  onInputChange,
  onKeyDown,
  onSend,
}: {
  state: ReturnType<typeof useInspirationMachine>['state'];
  input: string;
  onInputChange: React.Dispatch<React.SetStateAction<string>>;
  onKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSend: () => void;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-2">
        <div className="text-xs uppercase tracking-[0.14em] text-content-tertiary">灵感输入</div>
        <h3 className="text-xl font-semibold text-content">先写故事种子</h3>
        <p className="text-sm leading-7 text-content-secondary">
          这里直接输入灵感原稿，不再额外点按钮打开第二层抽屉。
        </p>
      </div>

      <div className="mt-4 rounded-xl border border-dashed border-slate-300 bg-[#faf7f2] px-3 py-3 text-sm leading-6 text-content-secondary">
        可以写人物关系、时代背景、冲突核心，越自然越好。下一步只会生成书名候选。
      </div>

      <div className="mt-4 flex flex-col gap-3">
        <textarea
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          onKeyDown={onKeyDown}
          rows={10}
          placeholder="例如：民国旧报馆里，一个专写奇闻的女记者，卷进带民俗色彩的连环失踪案……"
          className="min-h-[260px] resize-none rounded-xl border border-slate-200 bg-[#fffdfa] px-4 py-3 text-sm leading-7 text-content outline-none transition focus:border-brand/25 focus:ring-4 focus:ring-brand/10"
        />

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs leading-6 text-content-tertiary">
            `Enter` 发送，`Shift + Enter` 换行。
          </p>
          <button
            onClick={onSend}
            disabled={!input.trim() || state.loading}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand px-4 py-3 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-50"
          >
            {state.loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
            生成书名候选
          </button>
        </div>
      </div>
    </section>
  );
}

function QuestionStageCard({
  state,
  flowStep,
  flowMeta,
  prompt,
  options,
  activeQuestion,
  manualInputOpen,
  input,
  showInlineInput,
  canQuickGenerate,
  onInputChange,
  onOptionSelect,
  onOpenManualInput,
  onCloseManualInput,
  onConfirmGenres,
  onQuickGenerate,
  onRegenerateOptions,
  onKeyDown,
  onSend,
}: {
  state: ReturnType<typeof useInspirationMachine>['state'];
  flowStep: FlowStep;
  flowMeta: (typeof STEP_META)[FlowStep];
  prompt: string;
  options: string[];
  activeQuestion?: Message;
  manualInputOpen: boolean;
  input: string;
  showInlineInput: boolean;
  canQuickGenerate: boolean;
  onInputChange: React.Dispatch<React.SetStateAction<string>>;
  onOptionSelect: (option: string) => Promise<void>;
  onOpenManualInput: () => void;
  onCloseManualInput: () => void;
  onConfirmGenres: () => void;
  onQuickGenerate: () => void;
  onRegenerateOptions: (hint?: string) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  onSend: () => void;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <div className="text-xs uppercase tracking-[0.18em] text-content-tertiary">{flowMeta.eyebrow}</div>
          <h3 className="mt-2 text-xl font-semibold text-content">{flowMeta.title}</h3>
          <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-content-secondary">{prompt}</p>
        </div>

        <div className="flex flex-wrap gap-2">
          {canQuickGenerate && (
            <button
              onClick={onQuickGenerate}
              disabled={state.loading}
              className="inline-flex items-center gap-2 rounded-full border border-brand/18 bg-brand/8 px-3 py-2 text-xs font-medium text-brand transition hover:bg-brand/12 disabled:opacity-50"
            >
              <Zap className="h-3.5 w-3.5" />
              快速补全
            </button>
          )}
          {state.loading && (
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-[#faf7f2] px-3 py-2 text-xs text-content-secondary">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              正在准备下一步
            </div>
          )}
        </div>
      </div>

      {options.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2">
          {options.map((option) => {
            const selected = activeQuestion?.isMultiSelect && state.selectedOptions.includes(option);
            return (
              <button
                key={option}
                onClick={() => void onOptionSelect(option)}
                disabled={state.loading}
                className={cn(
                  'rounded-full border px-3.5 py-2 text-xs transition',
                  selected
                    ? 'border-brand bg-brand text-white'
                    : 'border-slate-200 bg-[#fffdfa] text-content-secondary hover:border-brand/25 hover:text-brand',
                  state.loading && 'opacity-50',
                )}
              >
                {option}
              </button>
            );
          })}
        </div>
      )}

      {flowStep === 'genre' && activeQuestion?.isMultiSelect && (
        <div className="mt-5 rounded-xl border border-slate-200 bg-[#faf7f2] p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-sm font-medium text-content">类型确认条</div>
              <p className="mt-1 text-xs leading-6 text-content-secondary">
                已选 {state.selectedOptions.length} 项。确认后才会进入视角选择，所以这里必须给一个明确主按钮。
              </p>
            </div>
            <button
              onClick={onConfirmGenres}
              disabled={state.selectedOptions.length === 0 || state.loading}
              className="inline-flex items-center justify-center gap-2 rounded-full bg-brand px-4 py-2 text-xs font-medium text-white transition hover:bg-brand-600 disabled:opacity-50"
            >
              <Wand2 className="h-3.5 w-3.5" />
              确认类型 ({state.selectedOptions.length})
            </button>
          </div>
        </div>
      )}

      {!state.loading && (
        <RegenerateBar
          flowStep={flowStep}
          selectedOptionsCount={state.selectedOptions.length}
          onRegenerate={onRegenerateOptions}
          onOpenManualInput={onOpenManualInput}
        />
      )}

      {manualInputOpen && showInlineInput && (
        <div className="mt-5 rounded-xl border border-slate-200 bg-[#faf7f2] p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium text-content">{getManualInputLabel(flowStep)}</div>
              <p className="mt-1 text-xs leading-6 text-content-secondary">{flowMeta.inputHint}</p>
            </div>
            <button
              onClick={onCloseManualInput}
              className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-content-secondary"
            >
              收起
            </button>
          </div>

          <div className="mt-4 flex items-end gap-3">
            <textarea
              value={input}
              onChange={(event) => onInputChange(event.target.value)}
              onKeyDown={onKeyDown}
              rows={flowStep === 'genre' ? 3 : 4}
              placeholder={flowMeta.inputPlaceholder}
              className="min-h-[108px] flex-1 resize-none rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-7 text-content outline-none transition focus:border-brand/25 focus:ring-4 focus:ring-brand/10"
            />
            <button
              onClick={onSend}
              disabled={!input.trim() || state.loading}
              className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-brand text-white shadow-[0_18px_42px_-24px_rgba(228,57,60,0.75)] transition hover:bg-brand-600 disabled:opacity-50"
            >
              <Send className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function ConfirmStageCard({
  state,
  wizardData,
  originalBrief,
  onConfirm,
  onReset,
}: {
  state: ReturnType<typeof useInspirationMachine>['state'];
  wizardData: Partial<WizardData>;
  originalBrief?: string;
  onConfirm: () => void;
  onReset: () => void;
}) {
  const hasGenerationError = Boolean(
    state.progressMessage && state.progress > 0 && state.progressMessage !== '项目创建完成！',
  );

  const fields = [
    { label: '书名', value: wizardData.title },
    { label: '简介', value: wizardData.description },
    { label: '主题', value: wizardData.theme },
    { label: '类型', value: wizardData.genre?.join('、') },
    { label: '视角', value: wizardData.narrative_perspective },
  ];

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      {hasGenerationError && (
        <div className="mb-5 rounded-[22px] border border-amber-200/80 bg-amber-50/90 px-4 py-3 text-sm leading-7 text-amber-700">
          上一次创建没有完整结束：{state.progressMessage}
        </div>
      )}

      <h3 className="text-xl font-semibold text-content">
        一切就绪，准备创建《{wizardData.title || '项目'}》
      </h3>
      <p className="mt-1 text-sm leading-7 text-content-secondary">
        检查一遍设定，确认后 AI 将依次生成世界观、角色和故事大纲。
      </p>

      {originalBrief && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-[#faf7f2] p-3">
          <div className="text-xs uppercase tracking-[0.14em] text-content-tertiary">原始灵感</div>
          <p className="mt-2 text-sm leading-7 text-content-secondary line-clamp-2">{originalBrief}</p>
        </div>
      )}

      <div className="mt-4 rounded-xl border border-slate-200 bg-[#faf7f2] p-4">
        <div className="divide-y divide-slate-200/80">
          {fields.map((f) => (
            <div key={f.label} className="flex items-baseline gap-3 px-1 py-2.5 first:pt-0 last:pb-0">
              <span className="w-10 shrink-0 text-xs font-medium uppercase tracking-[0.14em] text-content-tertiary">
                {f.label}
              </span>
              <span className="min-w-0 text-sm leading-7 text-content">
                {f.value || <span className="text-content-tertiary">待补充</span>}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        {NODE_META.map((node, index) => (
          <div key={node.key} className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-[#faf7f2] px-4 py-3">
            {node.key === 'worldBuilding' ? (
              <Globe className="h-4 w-4 shrink-0 text-brand" />
            ) : node.key === 'characters' ? (
              <Users className="h-4 w-4 shrink-0 text-brand" />
            ) : (
              <BookOpenText className="h-4 w-4 shrink-0 text-brand" />
            )}
            <span className="text-sm font-medium text-content">{node.label}</span>
            <span className="ml-auto text-xs text-content-tertiary">
              {index === 0 ? '先' : index === 1 ? '再' : '最后'}
            </span>
          </div>
        ))}
      </div>

      <div className="mt-5 flex items-center justify-center gap-3">
        <button
          onClick={onReset}
          className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-medium text-content-secondary transition hover:text-content"
        >
          重新开始
        </button>
        <button
          onClick={onConfirm}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand px-8 py-3.5 text-base font-medium text-white shadow-lg shadow-brand/20 transition hover:bg-brand-600 active:scale-[0.98]"
        >
          <Wand2 className="h-5 w-5" />
          {hasGenerationError ? '重新创建项目' : '开始创建项目'}
        </button>
      </div>
    </section>
  );
}

function GenerationStageCard({
  state,
  wizardData,
  originalBrief,
  onEnterProject,
}: {
  state: ReturnType<typeof useInspirationMachine>['state'];
  wizardData: Partial<WizardData>;
  originalBrief?: string;
  onEnterProject: () => void;
}) {
  const isComplete = state.currentStep === 'complete';

  if (isComplete) {
    return (
      <section className="rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50/40 to-white p-5 shadow-sm">
        <div className="text-center">
          <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100">
            <CheckCircle2 className="h-7 w-7 text-emerald-600" />
          </div>
          <h3 className="mt-4 text-xl font-semibold text-content">
            《{wizardData.title || state.projectTitle || '项目'}》创建完成
          </h3>
          <p className="mt-2 text-sm leading-7 text-content-secondary">
            世界观、角色和故事大纲都已生成完毕，可以进入项目开始创作了。
          </p>
          {state.projectId && (
            <button
              onClick={onEnterProject}
              className="mt-5 inline-flex items-center gap-2 rounded-xl bg-brand px-8 py-3.5 text-base font-medium text-white shadow-lg shadow-brand/20 transition hover:bg-brand-600 active:scale-[0.98]"
            >
              <Sparkles className="h-5 w-5" />
              进入项目开始写作
            </button>
          )}
        </div>

        <div className="mt-6 rounded-xl border border-slate-200 bg-[#faf7f2] p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-content-tertiary">项目摘要</div>
          {originalBrief && (
            <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-content-tertiary">原始灵感</div>
              <p className="mt-2 text-sm leading-7 text-content-secondary">{originalBrief}</p>
            </div>
          )}
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <SummaryField label="书名" value={wizardData.title || state.projectTitle} />
            <SummaryField label="简介" value={wizardData.description} />
            <SummaryField label="主题" value={wizardData.theme} />
            <SummaryField label="类型" value={wizardData.genre?.join('、')} />
            <SummaryField label="视角" value={wizardData.narrative_perspective} />
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div>
        <div className="text-xs uppercase tracking-[0.18em] text-content-tertiary">生成看板</div>
        <h3 className="mt-2 text-xl font-semibold text-content">
          正在为《{wizardData.title || state.projectTitle || '项目'}》搭建内容资产
        </h3>
        <p className="mt-3 text-sm leading-7 text-content-secondary">
          {state.progressMessage || '世界观 / 角色 / 大纲依次生成中。'}
        </p>
      </div>

      <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <div className="rounded-xl border border-slate-200 bg-[#faf7f2] p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-content-tertiary">项目摘要</div>
          {originalBrief && (
            <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
              <div className="text-xs uppercase tracking-[0.18em] text-content-tertiary">原始灵感</div>
              <p className="mt-2 text-sm leading-7 text-content-secondary">{originalBrief}</p>
            </div>
          )}
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <SummaryField label="书名" value={wizardData.title || state.projectTitle} />
            <SummaryField label="简介" value={wizardData.description} />
            <SummaryField label="主题" value={wizardData.theme} />
            <SummaryField label="类型" value={wizardData.genre?.join('、')} />
            <SummaryField label="视角" value={wizardData.narrative_perspective} />
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-[#faf7f2] p-4">
          <div className="text-xs uppercase tracking-[0.18em] text-content-tertiary">执行状态</div>
          <div className="mt-4 text-3xl font-semibold text-content">{Math.round(state.progress)}%</div>
          <p className="mt-2 text-sm leading-7 text-content-secondary">
            {state.progressMessage || '正在等待流式进度返回。'}
          </p>
          <div className="mt-4 h-2 rounded-full bg-surface-border">
            <div
              className="h-2 rounded-full bg-brand transition-all duration-500"
              style={{ width: `${Math.min(state.progress, 100)}%` }}
            />
          </div>
          <div className="mt-4 flex items-center justify-between text-xs text-content-tertiary">
            <span>世界观 / 角色 / 大纲依次生成</span>
            <span>{state.projectId ? '项目已创建' : '创建中'}</span>
          </div>
        </div>
      </div>
    </section>
  );
}

function HistoryPanel({
  open,
  onToggle,
  messages,
  messagesEndRef,
}: {
  open: boolean;
  onToggle: () => void;
  messages: Message[];
  messagesEndRef: React.RefObject<HTMLDivElement>;
}) {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 px-4 py-4 text-left transition hover:bg-surface-hover/60"
      >
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-content">
            <BookOpenText className="h-4 w-4 text-brand" />
            过程记录
            <span className="rounded-full border border-slate-200 bg-[#faf7f2] px-2 py-0.5 text-[11px] text-content-secondary">
              {messages.length}
            </span>
          </div>
          <p className="mt-1 text-sm text-content-secondary">已完成的对话收在这里，不干扰当前操作。</p>
        </div>
        {open ? <ChevronUp className="h-4 w-4 text-content-secondary" /> : <ChevronDown className="h-4 w-4 text-content-secondary" />}
      </button>

      {open && (
        <div className="border-t border-slate-200 px-4 py-4">
          <div className="max-h-[42vh] overflow-y-auto">
            <div className="space-y-4">
              {messages.map((message) => (
                <div key={message.id} className={cn('flex', message.type === 'user' ? 'justify-end' : 'justify-start')}>
                  <div
                    className={cn(
                      'max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-7',
                      message.type === 'user'
                        ? 'rounded-br-md bg-brand text-white'
                        : 'rounded-bl-md border border-slate-200 bg-[#faf7f2] text-content',
                    )}
                  >
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function AdvancedSection({
  open,
  onToggle,
  mcpSettings,
  setMcpSettings,
}: {
  open: boolean;
  onToggle: () => void;
  mcpSettings: MCPSelectorValue;
  setMcpSettings: React.Dispatch<React.SetStateAction<MCPSelectorValue>>;
}) {
  const summary = !mcpSettings.enable
    ? '未启用 MCP 增强'
    : mcpSettings.selected.length > 0
      ? `已启用 ${mcpSettings.selected.length} 个插件`
      : '已开启，但未选择插件';

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 px-4 py-4 text-left transition hover:bg-surface-hover/60"
      >
        <div>
          <div className="text-sm font-medium text-content">高级设置</div>
          <p className="mt-1 text-sm text-content-secondary">{summary}</p>
        </div>
        {open ? <ChevronUp className="h-4 w-4 text-content-secondary" /> : <ChevronDown className="h-4 w-4 text-content-secondary" />}
      </button>

      {open && (
        <div className="border-t border-slate-200 px-4 py-4">
          <MCPSelector value={mcpSettings} onChange={setMcpSettings} />
        </div>
      )}
    </section>
  );
}

function NodeCard({
  node,
  status,
  artifacts,
  runningNode,
  onRegenerate,
  canRegenerate,
}: {
  node: { key: GenerationNodeKey; label: string; hint: string };
  status: GenStepStatus;
  artifacts: GenerationArtifacts;
  runningNode: GenerationNodeKey | null;
  onRegenerate: (node: GenerationNodeKey) => Promise<void>;
  canRegenerate: boolean;
}) {
  const running = runningNode === node.key;
  const preview = getNodePreview(node.key, artifacts);
  const disabled = !canRegenerate || runningNode !== null || status === 'pending';
  const actionLabel = !canRegenerate
    ? '需先完成首次创建'
    : status === 'pending'
      ? '等待上游完成'
      : node.key === 'outline'
        ? '重生成大纲'
        : `从${node.label}重跑`;

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-content">{node.label}</h3>
          <p className="mt-1 text-sm leading-6 text-content-secondary">{node.hint}</p>
        </div>
        {status === 'completed' ? (
          <CheckCircle2 className="h-5 w-5 text-emerald-500" />
        ) : status === 'error' ? (
          <XCircle className="h-5 w-5 text-red-500" />
        ) : running || status === 'processing' ? (
          <Loader2 className="h-5 w-5 animate-spin text-brand" />
        ) : (
          <Clock className="h-5 w-5 text-content-tertiary" />
        )}
      </div>

      <div className="mt-4 rounded-xl border border-slate-200 bg-[#faf7f2] p-3 text-sm leading-7 text-content-secondary">
        {preview}
      </div>

      <button
        onClick={() => void onRegenerate(node.key)}
        disabled={disabled}
        className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-brand/18 bg-brand/8 px-3 py-2.5 text-sm font-medium text-brand transition hover:bg-brand/12 disabled:border-slate-200 disabled:bg-surface/70 disabled:text-content-tertiary"
      >
        <RefreshCw className={cn('h-4 w-4', running && 'animate-spin')} />
        {actionLabel}
      </button>
    </article>
  );
}


/** 重新生成操作栏：hint 输入 + 重新生成按钮 + 自己写 */
function RegenerateBar({
  flowStep,
  selectedOptionsCount,
  onRegenerate,
  onOpenManualInput,
}: {
  flowStep: FlowStep;
  selectedOptionsCount: number;
  onRegenerate: (hint?: string) => void;
  onOpenManualInput: () => void;
}) {
  const [hint, setHint] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleRegenerate = useCallback(() => {
    const trimmed = hint.trim();
    onRegenerate(trimmed || undefined);
    setHint('');
  }, [hint, onRegenerate]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleRegenerate();
      }
    },
    [handleRegenerate],
  );

  return (
    <div className="mt-5 space-y-3">
      <div className="flex items-center gap-2">
        <input
          ref={inputRef}
          type="text"
          value={hint}
          onChange={(e) => setHint(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="告诉AI你想要什么效果... (可选)"
          className="min-w-0 flex-1 rounded-full border border-slate-200 bg-[#fffdfa] px-4 py-2 text-xs text-content outline-none transition placeholder:text-content-tertiary focus:border-brand/25 focus:ring-4 focus:ring-brand/10"
        />
        <button
          onClick={handleRegenerate}
          className="inline-flex shrink-0 items-center gap-2 rounded-full border border-slate-200 bg-[#fffdfa] px-3.5 py-2 text-xs font-medium text-content-secondary transition hover:border-brand/25 hover:text-brand"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          重新生成
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={onOpenManualInput}
          className="inline-flex items-center gap-2 rounded-full border border-brand/18 bg-brand/8 px-3.5 py-2 text-xs font-medium text-brand transition hover:bg-brand/12"
        >
          <BookOpenText className="h-3.5 w-3.5" />
          {getManualInputLabel(flowStep)}
        </button>
        {flowStep === 'genre' && selectedOptionsCount > 0 && (
          <span className="rounded-full border border-slate-200 bg-[#faf7f2] px-3 py-1 text-xs text-content-secondary">
            已暂存 {selectedOptionsCount} 个类型
          </span>
        )}
      </div>
    </div>
  );
}

function FlowStepChip({
  label,
  status,
}: {
  label: string;
  status: 'done' | 'current' | 'upcoming';
}) {
  return (
    <div
      className={cn(
        'rounded-full border px-3 py-1.5 text-xs transition',
        status === 'done'
          ? 'border-brand bg-brand text-white'
          : status === 'current'
            ? 'border-brand/30 bg-brand/10 text-brand'
            : 'border-white/70 bg-white/75 text-content-secondary',
      )}
    >
      {label}
    </div>
  );
}

function SummaryField({ label, value }: { label: string; value?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-[#fffdfa] p-3">
      <div className="text-xs uppercase tracking-[0.14em] text-content-tertiary">{label}</div>
      <div className="mt-2 text-sm leading-7 text-content">{value || '待补充'}</div>
    </div>
  );
}

function getNodePreview(node: GenerationNodeKey, artifacts: GenerationArtifacts) {
  if (node === 'worldBuilding') {
    const world = artifacts.worldBuilding;
    return world
      ? `${world.time_period || '未写时代'} · ${world.location || '未写地点'} · ${world.atmosphere || '未写氛围'}`
      : '生成后会显示时代、地点和氛围摘要。';
  }

  if (node === 'characters') {
    return artifacts.characters.length > 0
      ? artifacts.characters.slice(0, 4).map((character) => character.name).join('、')
      : '生成后会显示角色样本。';
  }

  const content = artifacts.outline?.content;
  if (!content) return '生成后会显示故事前提摘要。';

  try {
    const parsed = JSON.parse(content) as { premise?: string };
    return parsed.premise || content;
  } catch {
    return content;
  }
}

function getFlowStep(step: Step): FlowStep {
  switch (step) {
    case 'loading_title':
    case 'title':
      return 'title';
    case 'loading_desc':
    case 'description':
      return 'description';
    case 'loading_theme':
    case 'theme':
      return 'theme';
    case 'loading_genre':
    case 'genre':
      return 'genre';
    case 'perspective':
      return 'perspective';
    case 'confirm':
    case 'generating':
    case 'complete':
      return 'confirm';
    default:
      return 'idea';
  }
}

function getFlowStepLabel(step: FlowStep) {
  const labels: Record<FlowStep, string> = {
    idea: '灵感',
    title: '书名',
    description: '简介',
    theme: '主题',
    genre: '类型',
    perspective: '视角',
    confirm: '确认',
  };

  return labels[step];
}

function getFlowChipStatus(index: number, activeStepIndex: number, currentStep: Step) {
  if (currentStep === 'complete') return 'done' as const;
  if (currentStep === 'generating') {
    return index < FLOW_STEPS.length - 1 ? 'done' : 'current';
  }
  if (index < activeStepIndex) return 'done' as const;
  if (index === activeStepIndex) return 'current' as const;
  return 'upcoming' as const;
}

function getFlowProgressValue(currentStep: Step, activeStepIndex: number) {
  if (currentStep === 'generating' || currentStep === 'complete') return 100;
  return Math.round((activeStepIndex / (FLOW_STEPS.length - 1)) * 100);
}

function getFlowProgressLabel(currentStep: Step, activeStepIndex: number) {
  if (currentStep === 'generating') return '已进入创建';
  if (currentStep === 'complete') return '创建完成';
  return `第 ${activeStepIndex + 1} / ${FLOW_STEPS.length} 步`;
}

function getManualInputLabel(step: FlowStep) {
  if (step === 'genre') return '自己写类型';
  if (step === 'perspective') return '其他视角';
  return '自己写这一项';
}
