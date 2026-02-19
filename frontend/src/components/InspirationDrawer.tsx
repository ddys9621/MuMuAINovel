import React, { useState, useEffect, useRef } from 'react';
import { Drawer, Input, Button, Space, Typography, message, Spin, Card } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { inspirationApi, wizardStreamApi } from '../services/api';
import type { ApiError } from '../types';
import MCPSelector, { type MCPSelectorValue } from './MCPSelector';
import { GenerationProgress, CompletionResult } from './GenerationProgress';
import { freshTheme } from '../styles/theme';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

type Step = 'idea' | 'title' | 'description' | 'theme' | 'genre' | 'perspective' | 'confirm' | 'generating' | 'complete';

interface Message {
  type: 'ai' | 'user';
  content: string;
  options?: string[];
  isMultiSelect?: boolean;
}

interface WizardData {
  title: string;
  description: string;
  theme: string;
  genre: string[];
  narrative_perspective: string;
}

interface InspirationDrawerProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (projectId: string) => void;
}

const InspirationDrawer: React.FC<InspirationDrawerProps> = ({ open, onClose, onSuccess }) => {
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const [currentStep, setCurrentStep] = useState<Step>('idea');
  const [messages, setMessages] = useState<Message[]>([
    {
      type: 'ai',
      content: '你好！我是你的AI创作助手。让我们一起创作一部精彩的小说吧！\n\n请告诉我，你想写一本什么样的小说？',
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedOptions, setSelectedOptions] = useState<string[]>([]);
  
  // 收集的数据
  const [wizardData, setWizardData] = useState<Partial<WizardData>>({});
  
  // MCP 选择器状态
  const [mcpSettings, setMcpSettings] = useState<MCPSelectorValue>({
    enable: false,
    selected: []
  });
  
  // 项目生成状态
  const [projectId, setProjectId] = useState<string>('');
  const [projectTitle, setProjectTitle] = useState<string>('');
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [generationSteps, setGenerationSteps] = useState<{
    worldBuilding: 'pending' | 'processing' | 'completed' | 'error';
    characters: 'pending' | 'processing' | 'completed' | 'error';
    outline: 'pending' | 'processing' | 'completed' | 'error';
  }>({
    worldBuilding: 'pending',
    characters: 'pending',
    outline: 'pending'
  });
  
  // 滚动容器引用
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // 记录上次失败的请求参数，用于重试
  const [lastFailedRequest, setLastFailedRequest] = useState<{
    step: 'title' | 'description' | 'theme' | 'genre';
    context: Partial<WizardData>;
  } | null>(null);

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // 自动滚动到底部
  const scrollToBottom = () => {
    setTimeout(() => {
      if (chatContainerRef.current) {
        chatContainerRef.current.scrollTo({
          top: chatContainerRef.current.scrollHeight,
          behavior: 'smooth'
        });
      }
    }, 100);
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 重置状态
  const resetState = () => {
    setCurrentStep('idea');
    setMessages([
      {
        type: 'ai',
        content: '你好！我是你的AI创作助手。让我们一起创作一部精彩的小说吧！\n\n请告诉我，你想写一本什么样的小说？',
      }
    ]);
    setWizardData({});
    setSelectedOptions([]);
    setLoading(false);
    setInputValue('');
    setMcpSettings({ enable: false, selected: [] });
    setProjectId('');
    setProjectTitle('');
    setProgress(0);
    setProgressMessage('');
    setGenerationSteps({
      worldBuilding: 'pending',
      characters: 'pending',
      outline: 'pending'
    });
    setLastFailedRequest(null);
  };

  // 关闭 Drawer
  const handleClose = () => {
    if (currentStep !== 'generating') {
      resetState();
      onClose();
    }
  };

  // 重试生成
  const handleRetry = async () => {
    if (!lastFailedRequest) return;
    
    setLoading(true);
    try {
      const response = await inspirationApi.generateOptions({
        step: lastFailedRequest.step,
        context: lastFailedRequest.context
      });

      if (response.error) {
        message.error(response.error);
        return;
      }

      setMessages(prev => {
        const newMessages = [...prev];
        if (newMessages[newMessages.length - 1].type === 'ai' &&
            (newMessages[newMessages.length - 1].content.includes('生成失败') ||
             newMessages[newMessages.length - 1].content.includes('出错了'))) {
          newMessages.pop();
        }
        return newMessages;
      });

      const aiMessage: Message = {
        type: 'ai',
        content: response.prompt || '请选择一个选项，或者输入你自己的：',
        options: response.options || [],
        isMultiSelect: lastFailedRequest.step === 'genre'
      };
      setMessages(prev => [...prev, aiMessage]);
      setLastFailedRequest(null);
    } catch (error: any) {
      console.error('重试失败:', error);
      message.error('重试失败，请稍后再试');
    } finally {
      setLoading(false);
    }
  };

  // 步骤顺序
  const stepOrder: Step[] = ['idea', 'title', 'description', 'theme', 'genre', 'perspective', 'confirm'];

  const handleSendMessage = async () => {
    if (!inputValue.trim()) {
      message.warning('请输入内容');
      return;
    }

    const userMessage: Message = {
      type: 'user',
      content: inputValue,
    };
    setMessages(prev => [...prev, userMessage]);

    const userInput = inputValue;
    setInputValue('');
    setLoading(true);

    try {
      if (currentStep === 'idea') {
        const requestData = {
          step: 'title' as const,
          context: { description: userInput }
        };

        const response = await inspirationApi.generateOptions(requestData);

        if (response.error || !response.options || response.options.length < 3) {
          const errorMessage: Message = {
            type: 'ai',
            content: response.error
              ? `生成书名时出错：${response.error}\n\n你可以选择：`
              : `生成的选项格式不正确（至少需要3个有效选项）\n\n你可以选择：`,
            options: response.options && response.options.length > 0 ? response.options : ['重新生成', '我自己输入书名']
          };
          setMessages(prev => [...prev, errorMessage]);
          setLastFailedRequest(requestData);
          return;
        }

        const aiMessage: Message = {
          type: 'ai',
          content: response.prompt || '请选择一个书名，或者输入你自己的：',
          options: response.options
        };
        setMessages(prev => [...prev, aiMessage]);
        setCurrentStep('title');
        setLastFailedRequest(null);
      } else {
        await handleCustomInput(userInput);
      }
    } catch (error: any) {
      console.error('发送消息失败:', error);
      message.error(error.response?.data?.detail || '生成失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectOption = async (option: string) => {
    if (option === '重新生成' && lastFailedRequest) {
      await handleRetry();
      return;
    }

    if (option === '我自己输入书名' || option === '我自己输入') {
      message.info('请在下方输入框中输入您的内容');
      return;
    }

    if (currentStep === 'genre') {
      const newSelected = selectedOptions.includes(option)
        ? selectedOptions.filter(o => o !== option)
        : [...selectedOptions, option];
      setSelectedOptions(newSelected);
      return;
    }

    if (currentStep === 'perspective') {
      const userMessage: Message = {
        type: 'user',
        content: option,
      };
      setMessages(prev => [...prev, userMessage]);

      const updatedData = { ...wizardData, narrative_perspective: option, genre: wizardData.genre || [] } as WizardData;
      setWizardData(updatedData);

      const summary = `
太棒了！你的小说设定已完成，请确认：

📖 书名：${updatedData.title}
📝 简介：${updatedData.description}
🎯 主题：${updatedData.theme}
🏷️ 类型：${updatedData.genre.join('、')}
👁️ 视角：${updatedData.narrative_perspective}

请选择下一步操作：
      `.trim();

      const aiMessage: Message = {
        type: 'ai',
        content: summary,
        options: ['✅ 确认创建', '🔄 重新开始']
      };
      setMessages(prev => [...prev, aiMessage]);
      setCurrentStep('confirm');
      return;
    }

    if (currentStep === 'confirm') {
      if (option === '✅ 确认创建') {
        const userMessage: Message = {
          type: 'user',
          content: '确认创建',
        };
        setMessages(prev => [...prev, userMessage]);

        const aiMessage: Message = {
          type: 'ai',
          content: '好的！正在为你创建项目，这可能需要几分钟时间...'
        };
        setMessages(prev => [...prev, aiMessage]);

        await handleAutoGenerate(wizardData as WizardData);
        return;
      } else if (option === '🔄 重新开始') {
        resetState();
        return;
      }
    }

    const userMessage: Message = {
      type: 'user',
      content: option,
    };
    setMessages(prev => [...prev, userMessage]);
    setLoading(true);

    try {
      const updatedData = { ...wizardData };
      if (currentStep === 'title') {
        updatedData.title = option;
      } else if (currentStep === 'description') {
        updatedData.description = option;
      } else if (currentStep === 'theme') {
        updatedData.theme = option;
      }
      setWizardData(updatedData);

      await generateNextStep(updatedData);
    } catch (error: any) {
      console.error('选择选项失败:', error);
      message.error(error.response?.data?.detail || '生成失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleCustomInput = async (input: string) => {
    setLoading(true);
    try {
      const updatedData = { ...wizardData };

      if (currentStep === 'title') {
        updatedData.title = input;
      } else if (currentStep === 'description') {
        updatedData.description = input;
      } else if (currentStep === 'theme') {
        updatedData.theme = input;
      } else if (currentStep === 'genre') {
        updatedData.genre = [input];
      } else if (currentStep === 'perspective') {
        updatedData.narrative_perspective = input;
      }

      setWizardData(updatedData);
      await generateNextStep(updatedData);
    } catch (error: any) {
      console.error('处理自定义输入失败:', error);
      message.error(error.response?.data?.detail || '处理失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  // 自动化生成项目流程
  const handleAutoGenerate = async (data: WizardData) => {
    try {
      setLoading(true);
      setCurrentStep('generating');
      setProjectTitle(data.title);
      setProgress(0);
      setProgressMessage('开始创建项目...');

      // 步骤1: 生成世界观并创建项目
      setGenerationSteps(prev => ({ ...prev, worldBuilding: 'processing' }));
      setProgressMessage('正在生成世界观...');

      const worldResult = await wizardStreamApi.generateWorldBuildingStream(
        {
          title: data.title,
          description: data.description,
          theme: data.theme,
          genre: data.genre.join('、'),
          narrative_perspective: data.narrative_perspective,
          target_words: 100000,
          chapter_count: 30,
          character_count: 5,
          enable_mcp: mcpSettings.enable && mcpSettings.selected.length > 0,
          selected_plugins: mcpSettings.enable ? mcpSettings.selected : [],
        },
        {
          onProgress: (msg, prog) => {
            setProgress(Math.floor(prog / 3));
            setProgressMessage(msg);
          },
          onResult: (result) => {
            setProjectId(result.project_id);
            setGenerationSteps(prev => ({ ...prev, worldBuilding: 'completed' }));
          },
          onError: (error) => {
            setGenerationSteps(prev => ({ ...prev, worldBuilding: 'error' }));
            throw new Error(error);
          },
          onComplete: () => {
            console.log('世界观生成完成');
          }
        }
      );

      if (!worldResult?.project_id) {
        throw new Error('项目创建失败');
      }

      const createdProjectId = worldResult.project_id;
      setProjectId(createdProjectId);

      // 步骤2: 生成角色
      setGenerationSteps(prev => ({ ...prev, characters: 'processing' }));
      setProgressMessage('正在生成角色...');

      await wizardStreamApi.generateCharactersStream(
        {
          project_id: createdProjectId,
          count: 5,
          world_context: {
            time_period: worldResult.time_period || '',
            location: worldResult.location || '',
            atmosphere: worldResult.atmosphere || '',
            rules: worldResult.rules || '',
          },
          theme: data.theme,
          genre: data.genre.join('、'),
          enable_mcp: mcpSettings.enable && mcpSettings.selected.length > 0,
          selected_plugins: mcpSettings.enable ? mcpSettings.selected : [],
        },
        {
          onProgress: (msg, prog) => {
            setProgress(33 + Math.floor(prog / 3));
            setProgressMessage(msg);
          },
          onResult: (result) => {
            console.log(`成功生成${result.characters?.length || 0}个角色`);
            setGenerationSteps(prev => ({ ...prev, characters: 'completed' }));
          },
          onError: (error) => {
            setGenerationSteps(prev => ({ ...prev, characters: 'error' }));
            throw new Error(error);
          },
          onComplete: () => {
            console.log('角色生成完成');
          }
        }
      );

      // 步骤3: 生成高层故事大纲
      setGenerationSteps(prev => ({ ...prev, outline: 'processing' }));
      setProgressMessage('正在生成高层故事大纲...');

      await wizardStreamApi.generateCompleteOutlineStream(
        {
          project_id: createdProjectId,
          chapter_count: 30,
          narrative_perspective: data.narrative_perspective,
          target_words: 100000,
          enable_mcp: mcpSettings.enable && mcpSettings.selected.length > 0,
          selected_plugins: mcpSettings.enable ? mcpSettings.selected : [],
        },
        {
          onProgress: (msg, prog) => {
            setProgress(66 + Math.floor(prog / 3));
            setProgressMessage(msg);
          },
          onResult: () => {
            console.log('大纲生成完成');
            setGenerationSteps(prev => ({ ...prev, outline: 'completed' }));
          },
          onError: (error) => {
            setGenerationSteps(prev => ({ ...prev, outline: 'error' }));
            throw new Error(error);
          },
          onComplete: () => {
            console.log('大纲生成完成');
          }
        }
      );

      // 全部完成
      setProgress(100);
      setProgressMessage('项目创建完成！');
      setCurrentStep('complete');
      message.success('项目创建成功！');

    } catch (error) {
      const apiError = error as ApiError;
      message.error('创建项目失败：' + (apiError.response?.data?.detail || apiError.message || '未知错误'));
      setCurrentStep('confirm');
      setGenerationSteps({
        worldBuilding: 'pending',
        characters: 'pending',
        outline: 'pending'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmGenres = async () => {
    if (selectedOptions.length === 0) {
      message.warning('请至少选择一个类型');
      return;
    }

    const userMessage: Message = {
      type: 'user',
      content: selectedOptions.join('、'),
    };
    setMessages(prev => [...prev, userMessage]);

    const updatedData = { ...wizardData, genre: selectedOptions };
    setWizardData(updatedData);
    setSelectedOptions([]);

    setLoading(true);
    try {
      const aiMessage: Message = {
        type: 'ai',
        content: '很好！最后一步，请选择小说的叙事视角：',
        options: ['第一人称', '第三人称', '全知视角']
      };
      setMessages(prev => [...prev, aiMessage]);
      setCurrentStep('perspective');
    } finally {
      setLoading(false);
    }
  };

  const generateNextStep = async (data: Partial<WizardData>) => {
    const currentIndex = stepOrder.indexOf(currentStep);
    const nextStep = stepOrder[currentIndex + 1];

    if (nextStep === 'description') {
      const requestData = {
        step: 'description' as const,
        context: { title: data.title }
      };
      const response = await inspirationApi.generateOptions(requestData);

      if (response.error || !response.options || response.options.length < 3) {
        const errorMessage: Message = {
          type: 'ai',
          content: response.error
            ? `生成简介时出错：${response.error}\n\n你可以选择：`
            : `生成的选项格式不正确（至少需要3个有效选项）\n\n你可以选择：`,
          options: response.options && response.options.length > 0 ? response.options : ['重新生成', '我自己输入']
        };
        setMessages(prev => [...prev, errorMessage]);
        setLastFailedRequest(requestData);
        return;
      }

      const aiMessage: Message = {
        type: 'ai',
        content: response.prompt || '请选择一个简介，或者输入你自己的：',
        options: response.options
      };
      setMessages(prev => [...prev, aiMessage]);
      setCurrentStep('description');
      setLastFailedRequest(null);

    } else if (nextStep === 'theme') {
      const requestData = {
        step: 'theme' as const,
        context: { title: data.title, description: data.description }
      };
      const response = await inspirationApi.generateOptions(requestData);

      if (response.error || !response.options || response.options.length < 3) {
        const errorMessage: Message = {
          type: 'ai',
          content: response.error
            ? `生成主题时出错：${response.error}\n\n你可以选择：`
            : `生成的选项格式不正确（至少需要3个有效选项）\n\n你可以选择：`,
          options: response.options && response.options.length > 0 ? response.options : ['重新生成', '我自己输入']
        };
        setMessages(prev => [...prev, errorMessage]);
        setLastFailedRequest(requestData);
        return;
      }

      const aiMessage: Message = {
        type: 'ai',
        content: response.prompt || '请选择一个主题，或者输入你自己的：',
        options: response.options
      };
      setMessages(prev => [...prev, aiMessage]);
      setCurrentStep('theme');
      setLastFailedRequest(null);

    } else if (nextStep === 'genre') {
      const requestData = {
        step: 'genre' as const,
        context: {
          title: data.title,
          description: data.description,
          theme: data.theme
        }
      };
      const response = await inspirationApi.generateOptions(requestData);

      if (response.error || !response.options || response.options.length < 3) {
        const errorMessage: Message = {
          type: 'ai',
          content: response.error
            ? `生成类型时出错：${response.error}\n\n你可以选择：`
            : `生成的选项格式不正确（至少需要3个有效选项）\n\n你可以选择：`,
          options: response.options && response.options.length > 0 ? response.options : ['重新生成', '我自己输入'],
          isMultiSelect: false
        };
        setMessages(prev => [...prev, errorMessage]);
        setLastFailedRequest(requestData);
        return;
      }

      const aiMessage: Message = {
        type: 'ai',
        content: response.prompt || '请选择类型标签（可多选）：',
        options: response.options,
        isMultiSelect: true
      };
      setMessages(prev => [...prev, aiMessage]);
      setCurrentStep('genre');
      setLastFailedRequest(null);
    }
  };

  // 渲染聊天界面
  const renderChat = () => (
    <>
      {/* 对话区域 */}
      <div
        ref={chatContainerRef}
        style={{
          height: 'calc(100vh - 280px)',
          overflowY: 'auto',
          marginBottom: 16,
          padding: '16px',
        }}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          {messages.map((msg, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                justifyContent: msg.type === 'ai' ? 'flex-start' : 'flex-end',
                alignItems: 'flex-start',
              }}
              className="fresh-animate-fade-in"
            >
              <div style={{
                maxWidth: '85%',
                padding: '12px 16px',
                borderRadius: freshTheme.radius.md,
                background: msg.type === 'ai'
                  ? freshTheme.colors.primary.cream
                  : freshTheme.colors.gradients.sakuraMint,
                color: freshTheme.colors.text.primary,
                boxShadow: freshTheme.shadow.soft,
              }}>
                <Paragraph
                  style={{
                    margin: 0,
                    whiteSpace: 'pre-wrap',
                    fontSize: 14,
                  }}
                >
                  {msg.content}
                </Paragraph>

                {/* 选项卡片 */}
                {msg.options && msg.options.length > 0 && (
                  <Space
                    direction="vertical"
                    style={{ width: '100%', marginTop: 12 }}
                    size="small"
                  >
                    {msg.options.map((option, optIndex) => (
                      <Card
                        key={optIndex}
                        hoverable
                        size="small"
                        onClick={() => handleSelectOption(option)}
                        className="fresh-card"
                        style={{
                          cursor: 'pointer',
                          border: msg.isMultiSelect && selectedOptions.includes(option)
                            ? `2px solid ${freshTheme.colors.primary.mint}`
                            : `1px solid ${freshTheme.colors.background.border}`,
                          background: msg.isMultiSelect && selectedOptions.includes(option)
                            ? `${freshTheme.colors.primary.mint}20`
                            : freshTheme.colors.background.card,
                          transition: freshTheme.transition.normal,
                        }}
                      >
                        {option}
                      </Card>
                    ))}

                    {/* 多选确认按钮 */}
                    {msg.isMultiSelect && (
                      <Button
                        type="primary"
                        block
                        onClick={handleConfirmGenres}
                        disabled={selectedOptions.length === 0}
                        style={{
                          background: freshTheme.colors.gradients.sakuraMint,
                          border: 'none',
                          borderRadius: freshTheme.radius.md,
                          color: freshTheme.colors.text.primary,
                          fontWeight: 600,
                        }}
                      >
                        确认选择 ({selectedOptions.length})
                      </Button>
                    )}
                  </Space>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div style={{ textAlign: 'center', padding: 20 }}>
              <Spin tip="AI思考中..." />
            </div>
          )}

          <div ref={messagesEndRef} />
        </Space>
      </div>

      {/* MCP 插件选择器 - 仅在确认步骤显示 */}
      {currentStep === 'confirm' && (
        <div
          style={{
            marginBottom: 16,
            padding: 12,
            background: `${freshTheme.colors.primary.mint}15`,
            borderRadius: freshTheme.radius.md,
            border: `1px solid ${freshTheme.colors.background.border}`,
          }}
        >
          <div style={{ marginBottom: 8 }}>
            <Text strong style={{ color: freshTheme.colors.text.primary }}>
              🚀 AI 增强插件设置
            </Text>
            <Text type="secondary" style={{ marginLeft: 8, fontSize: '12px' }}>
              选择启用 MCP 插件来增强 AI 创作效果
            </Text>
          </div>
          <MCPSelector
            value={mcpSettings}
            onChange={setMcpSettings}
            size="middle"
          />
        </div>
      )}

      {/* 输入区域 */}
      <div style={{ padding: '0 16px 16px' }}>
        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={
              currentStep === 'idea'
                ? '例如：我想写一本关于时间旅行的科幻小说...'
                : '输入自定义内容，或点击上方选项卡片...'
            }
            autoSize={{ minRows: 2, maxRows: 4 }}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
              }
            }}
            disabled={loading}
            style={{ borderRadius: freshTheme.radius.md }}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSendMessage}
            loading={loading}
            style={{
              height: 'auto',
              background: freshTheme.colors.gradients.sakuraMint,
              border: 'none',
              color: freshTheme.colors.text.primary,
            }}
          >
            发送
          </Button>
        </Space.Compact>
        <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
          💡 提示：按 Enter 发送，Shift+Enter 换行
        </Text>
      </div>
    </>
  );

  return (
    <Drawer
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 18 }}>✨ 灵感模式</span>
          <Text type="secondary" style={{ fontSize: 12 }}>
            通过对话快速创建你的小说项目
          </Text>
        </div>
      }
      placement="right"
      open={open}
      onClose={handleClose}
      width={isMobile ? '100vw' : 520}
      closable={currentStep !== 'generating'}
      maskClosable={currentStep !== 'generating'}
      destroyOnClose
      styles={{
        body: {
          padding: 0,
          display: 'flex',
          flexDirection: 'column',
        }
      }}
    >
      {(currentStep === 'idea' || currentStep === 'title' || currentStep === 'description' ||
        currentStep === 'theme' || currentStep === 'genre' || currentStep === 'perspective' ||
        currentStep === 'confirm') && renderChat()}

      {currentStep === 'generating' && (
        <div style={{ padding: '24px' }}>
          <GenerationProgress
            projectTitle={projectTitle}
            progress={progress}
            progressMessage={progressMessage}
            generationSteps={generationSteps}
            isMobile={isMobile}
          />
        </div>
      )}

      {currentStep === 'complete' && (
        <div style={{ padding: '24px' }}>
          <CompletionResult
            projectTitle={projectTitle}
            onBackHome={() => {
              resetState();
              onClose();
            }}
            onEnterProject={() => {
              const pid = projectId;
              resetState();
              onSuccess(pid);
            }}
            isMobile={isMobile}
          />
        </div>
      )}
    </Drawer>
  );
};

export default InspirationDrawer;

