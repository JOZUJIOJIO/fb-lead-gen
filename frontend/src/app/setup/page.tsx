'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { settingsApi, authApi } from '@/lib/api';

const AI_PROVIDERS = [
  {
    id: 'openai',
    name: 'OpenAI',
    description: 'GPT-4o / GPT-4o-mini，也支持任何兼容 API',
    keyLabel: 'OpenAI API Key',
    keyPlaceholder: 'sk-...',
    keyUrl: 'https://platform.openai.com/api-keys',
    hasBaseUrl: true,
  },
  {
    id: 'anthropic',
    name: 'Anthropic Claude',
    description: 'Claude 系列模型',
    keyLabel: 'Anthropic API Key',
    keyPlaceholder: 'sk-ant-...',
    keyUrl: 'https://console.anthropic.com/settings/keys',
    hasBaseUrl: false,
  },
  {
    id: 'kimi',
    name: 'Kimi / Moonshot',
    description: '月之暗面，国内可直连',
    keyLabel: 'Kimi API Key',
    keyPlaceholder: 'sk-...',
    keyUrl: 'https://platform.moonshot.cn/console/api-keys',
    hasBaseUrl: false,
  },
];

export default function SetupPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [selectedProvider, setSelectedProvider] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [proxy, setProxy] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const provider = AI_PROVIDERS.find((p) => p.id === selectedProvider);

  const handleSelectProvider = (id: string) => {
    setSelectedProvider(id);
    setApiKey('');
    setBaseUrl('');
    setStep(1);
  };

  const handleSave = async () => {
    if (!apiKey.trim()) {
      setError('请填写 API Key');
      return;
    }
    setError('');
    setSaving(true);

    try {
      // First login with default admin credentials
      const loginRes = await authApi.login('admin@leadflow.ai', 'admin123456');
      const token = loginRes.data.access_token;
      localStorage.setItem('auth_token', token);

      // Build update payload
      const payload: Record<string, unknown> = {
        ai_provider: selectedProvider,
      };
      if (selectedProvider === 'openai') {
        payload.openai_api_key = apiKey;
        if (baseUrl) payload.openai_base_url = baseUrl;
      } else if (selectedProvider === 'anthropic') {
        payload.anthropic_api_key = apiKey;
      } else if (selectedProvider === 'kimi') {
        payload.kimi_api_key = apiKey;
      }
      if (proxy) payload.proxy_server = proxy;

      await settingsApi.update(payload);
      setStep(2);

      // Redirect to dashboard after brief pause
      setTimeout(() => router.push('/dashboard'), 1500);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '保存失败，请检查后端是否启动';
      setError(message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f5f5f7] flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-semibold text-gray-900 tracking-tight">
            LeadFlow AI
          </h1>
          <p className="text-gray-500 mt-2">智能社媒获客工具</p>
        </div>

        {/* Progress */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                i <= step
                  ? 'bg-[#0071e3] w-12'
                  : 'bg-gray-200 w-8'
              }`}
            />
          ))}
        </div>

        {/* Step 0: Select Provider */}
        {step === 0 && (
          <div className="space-y-3">
            <h2 className="text-lg font-medium text-gray-900 text-center mb-6">
              选择你的 AI 供应商
            </h2>
            {AI_PROVIDERS.map((p) => (
              <button
                key={p.id}
                onClick={() => handleSelectProvider(p.id)}
                className="w-full bg-white rounded-2xl p-5 text-left border border-gray-100
                           hover:border-[#0071e3] hover:shadow-sm transition-all duration-200
                           focus:outline-none focus:ring-2 focus:ring-[#0071e3]/20"
              >
                <div className="font-medium text-gray-900">{p.name}</div>
                <div className="text-sm text-gray-500 mt-1">{p.description}</div>
              </button>
            ))}
          </div>
        )}

        {/* Step 1: Enter API Key */}
        {step === 1 && provider && (
          <div className="bg-white rounded-2xl p-6 border border-gray-100">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-medium text-gray-900">
                配置 {provider.name}
              </h2>
              <button
                onClick={() => { setStep(0); setSelectedProvider(''); }}
                className="text-sm text-[#0071e3] hover:underline"
              >
                返回
              </button>
            </div>

            <div className="space-y-4">
              {/* API Key */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  {provider.keyLabel}
                </label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={provider.keyPlaceholder}
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm
                             focus:outline-none focus:ring-2 focus:ring-[#0071e3]/20 focus:border-[#0071e3]
                             placeholder:text-gray-300"
                />
                <a
                  href={provider.keyUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-[#0071e3] hover:underline mt-1.5 inline-block"
                >
                  获取 API Key →
                </a>
              </div>

              {/* Base URL (OpenAI only) */}
              {provider.hasBaseUrl && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1.5">
                    API Base URL
                    <span className="text-gray-400 font-normal ml-1">可选</span>
                  </label>
                  <input
                    type="text"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="留空使用默认，或填入兼容 API 地址"
                    className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm
                               focus:outline-none focus:ring-2 focus:ring-[#0071e3]/20 focus:border-[#0071e3]
                               placeholder:text-gray-300"
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    如 DeepSeek、硅基流动等兼容 OpenAI 的 API
                  </p>
                </div>
              )}

              {/* Proxy */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  代理地址
                  <span className="text-gray-400 font-normal ml-1">可选</span>
                </label>
                <input
                  type="text"
                  value={proxy}
                  onChange={(e) => setProxy(e.target.value)}
                  placeholder="http://127.0.0.1:7890"
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm
                             focus:outline-none focus:ring-2 focus:ring-[#0071e3]/20 focus:border-[#0071e3]
                             placeholder:text-gray-300"
                />
                <p className="text-xs text-gray-400 mt-1">
                  访问 Facebook 需要代理时填写
                </p>
              </div>

              {/* Error */}
              {error && (
                <div className="text-sm text-red-500 bg-red-50 rounded-xl px-4 py-3">
                  {error}
                </div>
              )}

              {/* Submit */}
              <button
                onClick={handleSave}
                disabled={saving}
                className="w-full py-3 rounded-xl bg-[#0071e3] text-white font-medium text-sm
                           hover:bg-[#0066cc] transition-colors
                           disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? '保存中...' : '完成配置，开始使用'}
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Done */}
        {step === 2 && (
          <div className="bg-white rounded-2xl p-8 border border-gray-100 text-center">
            <div className="text-5xl mb-4">✅</div>
            <h2 className="text-xl font-medium text-gray-900 mb-2">
              配置完成！
            </h2>
            <p className="text-gray-500 text-sm">
              正在跳转到仪表盘...
            </p>
          </div>
        )}

        {/* Footer hint */}
        <p className="text-center text-xs text-gray-400 mt-6">
          配置随时可在「设置」页面修改
        </p>
      </div>
    </div>
  );
}
