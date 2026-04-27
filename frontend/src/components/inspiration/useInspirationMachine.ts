/** 灵感模式状态机 Hook - 封装 reducer + API 副作用 */

import { useReducer, useCallback } from 'react';
import { toast } from 'sonner';
import { inspirationApi } from '../../services/api';
import { wizardReducer } from './reducer';
import { createInitialState } from './types';
import type { Step, WizardData } from './types';

const REGENERATE_OPTIONS = new Set(['重新生成', '让AI重新生成']);
const CUSTOM_INPUT_OPTIONS = new Set(['我自己输入书名', '我自己输入']);

/** API step → 下一个显示步骤的映射 */
const API_STEP_MAP: Record<string, { loadingStep: Step; successStep: Step }> = {
  title: { loadingStep: 'loading_title', successStep: 'title' },
  description: { loadingStep: 'loading_desc', successStep: 'description' },
  theme: { loadingStep: 'loading_theme', successStep: 'theme' },
  genre: { loadingStep: 'loading_genre', successStep: 'genre' },
};

/** 当前 step → 需要调用的 API step */
const NEXT_API_STEP: Record<string, 'title' | 'description' | 'theme' | 'genre'> = {
  idea: 'title',
  title: 'description',
  description: 'theme',
  theme: 'genre',
};

/** 构建 API context */
const buildApiContext = (step: string, data: Partial<WizardData>, userInput?: string) => {
  switch (step) {
    case 'title': return { description: userInput || data.description };
    case 'description': return { title: data.title };
    case 'theme': return { title: data.title, description: data.description };
    case 'genre': return { title: data.title, description: data.description, theme: data.theme };
    default: return {};
  }
};

export function useInspirationMachine() {
  const [state, dispatch] = useReducer(wizardReducer, undefined, createInitialState);

  /** 通用 API 调用：生成选项 */
  const callGenerateOptions = useCallback(async (
    apiStep: 'title' | 'description' | 'theme' | 'genre',
    context: Partial<WizardData>,
    userInput?: string,
    hint?: string,
  ) => {
    const mapping = API_STEP_MAP[apiStep];
    dispatch({ type: 'API_LOADING', payload: mapping.loadingStep });

    try {
      const requestData = {
        step: apiStep,
        context: buildApiContext(apiStep, context, userInput),
        ...(hint ? { hint } : {}),
      };

      const response = await inspirationApi.generateOptions(requestData);

      if (response.error || !response.options || response.options.length < 3) {
        const stepLabel = { title: '书名', description: '简介', theme: '主题', genre: '类型' }[apiStep];
        dispatch({
          type: 'API_ERROR',
          payload: {
            error: response.error
              ? `生成${stepLabel}时出错：${response.error}\n\n你可以选择：`
              : `生成的选项格式不正确（至少需要3个有效选项）\n\n你可以选择：`,
            retryContext: { step: apiStep, context: requestData.context },
            options: response.options?.length ? response.options : ['重新生成', '我自己输入'],
          },
        });
        return;
      }

      dispatch({
        type: 'API_SUCCESS',
        payload: {
          nextStep: mapping.successStep,
          aiMessage: {
            type: 'ai',
            content: response.prompt || `请选择一个${apiStep === 'genre' ? '类型标签（可多选）' : '选项'}，或者输入你自己的：`,
            options: response.options,
            isMultiSelect: apiStep === 'genre',
          },
        },
      });
    } catch (error: unknown) {
      const detail =
        typeof error === 'object' &&
        error !== null &&
        'response' in error &&
        typeof (error as { response?: { data?: { detail?: string } } }).response?.data?.detail === 'string'
          ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null;
      console.error(`生成${apiStep}失败:`, error);
      toast.error(detail || '生成失败，请重试');
      dispatch({
        type: 'API_ERROR',
        payload: {
          error: '生成失败，请重试',
          retryContext: { step: apiStep, context: buildApiContext(apiStep, context, userInput) },
        },
      });
    }
  }, []);

  /** 自定义输入处理（非 idea 阶段） */
  const handleCustomInput = useCallback(async (input: string) => {
    const updatedData = { ...state.wizardData };
    const step = state.currentStep;

    if (step === 'title') updatedData.title = input;
    else if (step === 'description') updatedData.description = input;
    else if (step === 'theme') updatedData.theme = input;
    else if (step === 'genre') {
      dispatch({ type: 'ADVANCE_TO_PERSPECTIVE', payload: { genres: [input], sourceText: input } });
      return;
    }
    else if (step === 'perspective') {
      dispatch({ type: 'SELECT_PERSPECTIVE', payload: input });
      dispatch({ type: 'SET_WIZARD_DATA', payload: { narrative_perspective: input } });
      return;
    }

    dispatch({ type: 'SET_WIZARD_DATA', payload: updatedData });

    const nextApiStep = NEXT_API_STEP[step];
    if (nextApiStep) {
      await callGenerateOptions(nextApiStep, updatedData);
    }
  }, [state.currentStep, state.wizardData, callGenerateOptions]);

  /** 发送消息（idea 阶段） */
  const sendMessage = useCallback(async (input: string) => {
    if (!input.trim()) {
      toast.warning('请输入内容');
      return;
    }
    dispatch({ type: 'SEND_MESSAGE', payload: input });

    if (state.currentStep === 'idea') {
      await callGenerateOptions('title', {}, input);
    } else {
      // 非 idea 阶段的自定义输入
      await handleCustomInput(input);
    }
  }, [callGenerateOptions, handleCustomInput, state.currentStep]);

  /** 重试 */
  const retry = useCallback(async () => {
    if (!state.retryContext) return;
    const { step, context } = state.retryContext;

    // 移除上一条错误消息
    dispatch({ type: 'RETRY' });
    await callGenerateOptions(step, context as Partial<WizardData>);
  }, [state.retryContext, callGenerateOptions]);

  /** 换一批：对当前步骤重新生成选项，可带额外提示 */
  const regenerateOptions = useCallback(async (hint?: string) => {
    const stepMap: Record<string, 'title' | 'description' | 'theme' | 'genre'> = {
      title: 'title',
      description: 'description',
      theme: 'theme',
      genre: 'genre',
    };
    const apiStep = stepMap[state.currentStep];
    if (!apiStep) return;

    dispatch({ type: 'DISABLE_LAST_OPTIONS' });
    await callGenerateOptions(apiStep, state.wizardData, undefined, hint || undefined);
  }, [state.currentStep, state.wizardData, callGenerateOptions]);

  /** 选择选项 */
  const selectOption = useCallback(async (option: string) => {
    // 重试
    if (REGENERATE_OPTIONS.has(option) && state.retryContext) {
      await retry();
      return;
    }
    // 自行输入提示
    if (CUSTOM_INPUT_OPTIONS.has(option)) {
      toast.info('请在下方输入框中输入您的内容');
      return;
    }
    // Genre 多选
    if (state.currentStep === 'genre') {
      dispatch({ type: 'TOGGLE_GENRE', payload: option });
      return;
    }
    // 视角选择
    if (state.currentStep === 'perspective') {
      dispatch({ type: 'SELECT_PERSPECTIVE', payload: option });
      dispatch({ type: 'SET_WIZARD_DATA', payload: { narrative_perspective: option } });
      return;
    }
    // 确认阶段
    if (state.currentStep === 'confirm') {
      if (option === '✅ 确认创建') {
        dispatch({ type: 'CONFIRM_CREATE' });
        return; // 由外部 useProjectGeneration 接管
      }
      if (option === '🔄 重新开始') {
        dispatch({ type: 'RESTART' });
        return;
      }
    }

    // 常规选项选择
    dispatch({ type: 'SELECT_OPTION', payload: option });
    const updatedData = { ...state.wizardData };
    if (state.currentStep === 'title') updatedData.title = option;
    else if (state.currentStep === 'description') updatedData.description = option;
    else if (state.currentStep === 'theme') updatedData.theme = option;
    dispatch({ type: 'SET_WIZARD_DATA', payload: updatedData });

    const nextApiStep = NEXT_API_STEP[state.currentStep];
    if (nextApiStep) {
      await callGenerateOptions(nextApiStep, updatedData);
    }
  }, [callGenerateOptions, retry, state.currentStep, state.retryContext, state.wizardData]);

  /** 确认 Genre */
  const confirmGenres = useCallback(() => {
    if (state.selectedOptions.length === 0) {
      toast.warning('请至少选择一个类型');
      return;
    }
    dispatch({ type: 'CONFIRM_GENRES' });
  }, [state.selectedOptions]);

  /** 快速生成：用已有信息调用 quickGenerate 补全缺失字段，直接跳到确认 */
  const quickGenerate = useCallback(async () => {
    const data = state.wizardData;
    if (!data.title && !data.description && !data.theme) {
      toast.warning('请至少提供标题、简介或主题中的一项');
      return;
    }
    dispatch({ type: 'API_LOADING', payload: 'loading_title' });
    try {
      const result = await inspirationApi.quickGenerate({
        title: data.title,
        description: data.description,
        theme: data.theme,
        genre: data.genre,
      });
      dispatch({
        type: 'SET_WIZARD_DATA',
        payload: {
          title: result.title,
          description: result.description,
          theme: result.theme,
          genre: result.genre,
          narrative_perspective: result.narrative_perspective,
        },
      });
      dispatch({
        type: 'API_SUCCESS',
        payload: {
          nextStep: 'confirm',
          aiMessage: {
            type: 'ai',
            content: `已为你快速补全所有信息：\n\n📖 书名：${result.title}\n📝 简介：${result.description}\n🎨 主题：${result.theme}\n🏷️ 类型：${result.genre.join('、')}\n👁️ 视角：${result.narrative_perspective}\n\n请确认是否开始创建项目？`,
            options: ['✅ 确认创建', '🔄 重新开始'],
          },
        },
      });
    } catch {
      toast.error('快速生成失败，请重试');
      dispatch({
        type: 'API_ERROR',
        payload: { error: '快速生成失败，请重试' },
      });
    }
  }, [state.wizardData]);

  /** 重置 */
  const reset = useCallback(() => {
    dispatch({ type: 'RESTART' });
  }, []);

  return {
    state,
    dispatch,
    sendMessage,
    selectOption,
    confirmGenres,
    quickGenerate,
    regenerateOptions,
    retry,
    reset,
  };
}
