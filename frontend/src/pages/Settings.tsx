import { useState, useEffect, useCallback } from 'react'
import { settingsApi } from '@/services/api'
import type { Settings as SettingsType, SettingsUpdate } from '@/types'
import { toast } from 'sonner'
import {
  Eye,
  EyeOff,
  Loader2,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Save,
  Wifi,
  RefreshCw,
} from 'lucide-react'

const PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'custom', label: '自定义' },
]

const DEFAULT_BASE_URLS: Record<string, string> = {
  openai: 'https://api.openai.com/v1',
  anthropic: 'https://api.anthropic.com',
  custom: '',
}

export default function Settings() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<'success' | 'error' | null>(null)
  const [testMessage, setTestMessage] = useState('')
  const [settings, setSettings] = useState<SettingsType | null>(null)
  const [models, setModels] = useState<Array<{ value: string; label: string; description: string }>>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)

  // 表单状态
  const [form, setForm] = useState<SettingsUpdate>({
    api_provider: 'openai',
    api_key: '',
    api_base_url: 'https://api.openai.com/v1',
    llm_model: '',
    temperature: 0.7,
    max_tokens: 4096,
    preferences: '',
  })

  // 加载设置
  useEffect(() => {
    const load = async () => {
      try {
        const data = await settingsApi.getSettings()
        setSettings(data)
        setForm({
          api_provider: data.api_provider || 'openai',
          api_key: data.api_key || '',
          api_base_url: data.api_base_url || DEFAULT_BASE_URLS[data.api_provider || 'openai'] || '',
          llm_model: data.llm_model || '',
          temperature: data.temperature ?? 0.7,
          max_tokens: data.max_tokens ?? 4096,
          preferences: data.preferences || '',
        })
      } catch {
        // 首次使用，无设置记录
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  // 更新表单字段
  const updateField = useCallback(<K extends keyof SettingsUpdate>(key: K, value: SettingsUpdate[K]) => {
    setForm(prev => ({ ...prev, [key]: value }))
    setTestResult(null)
  }, [])

  // 切换提供商时自动填充 base url
  const handleProviderChange = useCallback((provider: string) => {
    updateField('api_provider', provider)
    updateField('api_base_url', DEFAULT_BASE_URLS[provider] || '')
    setModels([])
    updateField('llm_model', '')
  }, [updateField])

  // 获取可用模型
  const fetchModels = useCallback(async () => {
    if (!form.api_key || !form.api_base_url || !form.api_provider) {
      toast.error('请先填写 API 提供商、Base URL 和 API Key')
      return
    }
    setLoadingModels(true)
    try {
      const res = await settingsApi.getAvailableModels({
        api_key: form.api_key,
        api_base_url: form.api_base_url,
        provider: form.api_provider,
      })
      setModels(res.models || [])
      if (res.models?.length) {
        toast.success(`获取到 ${res.models.length} 个可用模型`)
      } else {
        toast.warning('未获取到可用模型')
      }
    } catch {
      toast.error('获取模型列表失败')
    } finally {
      setLoadingModels(false)
    }
  }, [form.api_key, form.api_base_url, form.api_provider])

  // 测试连接
  const handleTestConnection = useCallback(async () => {
    if (!form.api_key || !form.api_base_url || !form.api_provider) {
      toast.error('请先填写 API 配置')
      return
    }
    setTesting(true)
    setTestResult(null)
    setTestMessage('')
    try {
      const res = await settingsApi.testApiConnection({
        api_key: form.api_key,
        api_base_url: form.api_base_url,
        provider: form.api_provider,
        llm_model: form.llm_model || '',
      })
      if (res.success) {
        setTestResult('success')
        setTestMessage(res.message || '连接成功')
      } else {
        setTestResult('error')
        setTestMessage(res.error || res.message || '连接失败')
      }
    } catch {
      setTestResult('error')
      setTestMessage('连接测试失败，请检查配置')
    } finally {
      setTesting(false)
    }
  }, [form])

  // 保存设置
  const handleSave = useCallback(async () => {
    if (!form.api_key) {
      toast.error('请填写 API Key')
      return
    }
    setSaving(true)
    try {
      const data = await settingsApi.saveSettings(form)
      setSettings(data)
      toast.success('设置已保存')
    } catch {
      // api 拦截器已处理 toast
    } finally {
      setSaving(false)
    }
  }, [form])

  // 重置表单
  const handleReset = useCallback(() => {
    if (settings) {
      setForm({
        api_provider: settings.api_provider || 'openai',
        api_key: settings.api_key || '',
        api_base_url: settings.api_base_url || '',
        llm_model: settings.llm_model || '',
        temperature: settings.temperature ?? 0.7,
        max_tokens: settings.max_tokens ?? 4096,
        preferences: settings.preferences || '',
      })
    } else {
      setForm({
        api_provider: 'openai',
        api_key: '',
        api_base_url: 'https://api.openai.com/v1',
        llm_model: '',
        temperature: 0.7,
        max_tokens: 4096,
        preferences: '',
      })
    }
    setTestResult(null)
    setTestMessage('')
    toast.info('已重置为上次保存的设置')
  }, [settings])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-brand" />
      </div>
    )
  }

  const inputClass =
    'w-full border border-surface-border rounded-btn px-3 py-2 text-sm focus:border-brand focus:ring-2 focus:ring-brand/20 outline-none transition-colors'
  const selectClass = inputClass + ' bg-white'
  const labelClass = 'block text-sm font-medium text-content mb-1.5'

  return (
    <div className="animate-fade-in">
      {/* 标题区 */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-content">设置</h1>
        <p className="text-content-secondary mt-1">配置 AI 接口和模型参数</p>
      </div>

      {/* 设置表单 */}
      <div className="max-w-2xl space-y-6">
        {/* API 配置区 */}
        <section className="bg-white rounded-card shadow-card p-6">
          <h2 className="text-lg font-semibold text-content mb-4">API 配置</h2>
          <div className="space-y-4">
            {/* 提供商 */}
            <div>
              <label className={labelClass}>API 提供商</label>
              <select
                className={selectClass}
                value={form.api_provider}
                onChange={e => handleProviderChange(e.target.value)}
              >
                {PROVIDERS.map(p => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>

            {/* Base URL */}
            <div>
              <label className={labelClass}>API Base URL</label>
              <input
                type="text"
                className={inputClass}
                placeholder="https://api.openai.com/v1"
                value={form.api_base_url}
                onChange={e => updateField('api_base_url', e.target.value)}
              />
            </div>

            {/* API Key */}
            <div>
              <label className={labelClass}>API Key</label>
              <div className="relative">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  className={inputClass + ' pr-10'}
                  placeholder="sk-..."
                  value={form.api_key}
                  onChange={e => updateField('api_key', e.target.value)}
                />
                <button
                  type="button"
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-content-tertiary hover:text-content-secondary transition-colors"
                  onClick={() => setShowApiKey(v => !v)}
                  aria-label={showApiKey ? '隐藏 API Key' : '显示 API Key'}
                >
                  {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* 测试连接 */}
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-btn border border-surface-border hover:bg-surface-hover transition-colors disabled:opacity-50"
                onClick={handleTestConnection}
                disabled={testing}
              >
                {testing ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Wifi className="w-4 h-4" />
                )}
                测试连接
              </button>
              {testResult && (
                <span className={`inline-flex items-center gap-1 text-sm ${testResult === 'success' ? 'text-green-600' : 'text-red-500'}`}>
                  {testResult === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                  {testMessage}
                </span>
              )}
            </div>
          </div>
        </section>

        {/* 模型配置区 */}
        <section className="bg-white rounded-card shadow-card p-6">
          <h2 className="text-lg font-semibold text-content mb-4">模型配置</h2>
          <div className="space-y-4">
            {/* LLM 模型 */}
            <div>
              <label className={labelClass}>LLM 模型</label>
              <div className="flex gap-2">
                <select
                  className={selectClass + ' flex-1'}
                  value={form.llm_model}
                  onChange={e => updateField('llm_model', e.target.value)}
                >
                  <option value="">请选择模型</option>
                  {models.map(m => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                  {/* 如果当前值不在列表中，也显示 */}
                  {form.llm_model && !models.find(m => m.value === form.llm_model) && (
                    <option value={form.llm_model}>{form.llm_model}</option>
                  )}
                </select>
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-btn border border-surface-border hover:bg-surface-hover transition-colors disabled:opacity-50"
                  onClick={fetchModels}
                  disabled={loadingModels}
                  title="刷新模型列表"
                >
                  {loadingModels ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                </button>
              </div>
              {form.llm_model && models.find(m => m.value === form.llm_model)?.description && (
                <p className="text-xs text-content-tertiary mt-1">
                  {models.find(m => m.value === form.llm_model)?.description}
                </p>
              )}
            </div>

            {/* Temperature */}
            <div>
              <label className={labelClass}>
                Temperature
                <span className="ml-2 text-content-tertiary font-normal">{form.temperature}</span>
              </label>
              <input
                type="range"
                min={0}
                max={2}
                step={0.1}
                className="w-full accent-brand"
                value={form.temperature}
                onChange={e => updateField('temperature', parseFloat(e.target.value))}
              />
              <div className="flex justify-between text-xs text-content-tertiary mt-0.5">
                <span>精确 (0)</span>
                <span>创意 (2)</span>
              </div>
            </div>

            {/* Max Tokens */}
            <div>
              <label className={labelClass}>Max Tokens</label>
              <input
                type="number"
                className={inputClass}
                min={1}
                max={128000}
                value={form.max_tokens}
                onChange={e => updateField('max_tokens', parseInt(e.target.value) || 4096)}
              />
            </div>
          </div>
        </section>

        {/* 偏好设置区 */}
        <section className="bg-white rounded-card shadow-card p-6">
          <h2 className="text-lg font-semibold text-content mb-4">偏好设置</h2>
          <div>
            <label className={labelClass}>自定义偏好（JSON 或文本）</label>
            <textarea
              className={inputClass + ' min-h-[100px] resize-y'}
              placeholder='例如：{"language": "zh-CN", "style": "concise"}'
              value={form.preferences}
              onChange={e => updateField('preferences', e.target.value)}
            />
            <p className="text-xs text-content-tertiary mt-1">
              可填写自定义偏好参数，将在 AI 生成时作为额外上下文传入
            </p>
          </div>
        </section>

        {/* 底部操作栏 */}
        <div className="flex items-center gap-3 pb-8">
          <button
            type="button"
            className="inline-flex items-center gap-1.5 px-5 py-2.5 text-sm font-medium rounded-btn bg-brand hover:bg-brand-600 text-white transition-colors disabled:opacity-50"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            保存设置
          </button>
          <button
            type="button"
            className="inline-flex items-center gap-1.5 px-5 py-2.5 text-sm font-medium rounded-btn border border-surface-border hover:bg-surface-hover transition-colors"
            onClick={handleReset}
          >
            <RotateCcw className="w-4 h-4" />
            重置
          </button>
        </div>
      </div>
    </div>
  )
}
