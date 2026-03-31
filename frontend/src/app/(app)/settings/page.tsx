'use client';

import { useState, useEffect } from 'react';
import { Save, Eye, EyeOff, Cookie, CheckCircle, AlertCircle, Upload } from 'lucide-react';
import { settingsApi, isAuthError } from '@/lib/api';
import api from '@/lib/api';

export default function SettingsPage() {
  const [aiProvider, setAiProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [apiBaseUrl, setApiBaseUrl] = useState('');
  const [proxy, setProxy] = useState('');
  const [sendIntervalMin, setSendIntervalMin] = useState(60);
  const [sendIntervalMax, setSendIntervalMax] = useState(180);
  const [maxDailyMessages, setMaxDailyMessages] = useState(50);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Cookie state
  const [cookieJson, setCookieJson] = useState('');
  const [cookieStatus, setCookieStatus] = useState<{imported: boolean; facebook_count: number} | null>(null);
  const [cookieImporting, setCookieImporting] = useState(false);
  const [cookieResult, setCookieResult] = useState<{message: string; success: boolean; login_verified?: boolean} | null>(null);

  useEffect(() => {
    loadSettings();
    loadCookieStatus();
  }, []);

  async function loadSettings() {
    try {
      const res = await settingsApi.get();
      const s = res.data;
      setAiProvider(s.ai_provider);
      setApiBaseUrl(s.openai_base_url || '');
      setProxy(s.proxy_server || '');
      setSendIntervalMin(s.send_interval_min);
      setSendIntervalMax(s.send_interval_max);
      setMaxDailyMessages(s.max_daily_messages);
    } catch {}
  }

  async function loadCookieStatus() {
    try {
      const res = await api.get('/api/settings/cookies/status');
      setCookieStatus(res.data);
    } catch {}
  }

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const payload: Record<string, unknown> = {
        ai_provider: aiProvider,
        proxy_server: proxy,
        send_interval_min: sendIntervalMin,
        send_interval_max: sendIntervalMax,
        max_daily_messages: maxDailyMessages,
      };
      if (apiKey) {
        if (aiProvider === 'openai') payload.openai_api_key = apiKey;
        else if (aiProvider === 'anthropic') payload.anthropic_api_key = apiKey;
        else if (aiProvider === 'kimi') payload.kimi_api_key = apiKey;
        else if (aiProvider === 'openrouter') payload.openrouter_api_key = apiKey;
      }
      if (apiBaseUrl) payload.openai_base_url = apiBaseUrl;
      await settingsApi.update(payload);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (error) {
      console.error('Failed to save settings:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleImportCookies = async () => {
    if (!cookieJson.trim()) return;
    setCookieImporting(true);
    setCookieResult(null);
    try {
      const cookies = JSON.parse(cookieJson);
      const res = await api.post('/api/settings/cookies', { cookies });
      setCookieResult(res.data);
      if (res.data.success) {
        setCookieJson('');
        loadCookieStatus();
      }
    } catch (e: unknown) {
      let msg: string;
      if (e instanceof SyntaxError) {
        msg = 'JSON 格式错误，请检查复制的内容';
      } else if (isAuthError(e)) {
        msg = '当前登录状态已失效，请重新登录后再导入 Cookies';
      } else {
        msg = '导入失败，请检查后端服务是否正常运行';
      }
      setCookieResult({ message: msg, success: false });
    } finally {
      setCookieImporting(false);
    }
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">设置</h1>
        <p className="mt-1 text-sm text-[#86868b]">配置 AI 服务、浏览器登录和系统参数</p>
      </div>

      <div className="space-y-6">
        {/* Facebook Login (Cookies) - TOP PRIORITY */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Cookie className="h-5 w-5 text-[#0071e3]" />
            <h2 className="text-base font-semibold text-[#1d1d1f]">Facebook 登录状态</h2>
            {cookieStatus?.imported && (
              <span className="ml-auto inline-flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full">
                <CheckCircle className="h-3 w-3" />
                已导入 {cookieStatus.facebook_count} 个 Cookies
              </span>
            )}
          </div>

          {/* Instructions */}
          <div className="mb-4 rounded-xl bg-[#f5f5f7] p-4 text-sm text-[#424245] space-y-3">
            <p className="font-medium">通过导入 Chrome Cookies 免登录使用 Facebook：</p>
            <ol className="list-decimal ml-4 space-y-2">
              <li>
                在 Chrome 中安装
                <a href="https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm" target="_blank" rel="noopener noreferrer" className="text-[#0071e3] hover:underline mx-1">Cookie-Editor</a>
                扩展
              </li>
              <li>在 Chrome 中打开 <span className="font-mono bg-white px-1.5 py-0.5 rounded">facebook.com</span> 并确保已登录</li>
              <li>点击 Cookie-Editor 图标 → 点击底部 <span className="font-medium">Export</span> 按钮（会自动复制 JSON）</li>
              <li>回到这里，粘贴到下面的输入框 → 点击导入</li>
            </ol>
          </div>

          {/* Cookie JSON Input */}
          <textarea
            value={cookieJson}
            onChange={(e) => setCookieJson(e.target.value)}
            placeholder='粘贴 Cookie-Editor 导出的 JSON...'
            rows={5}
            className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white font-mono"
          />

          {/* Result */}
          {cookieResult && (
            <div className={`mt-3 flex items-start gap-2 rounded-xl px-4 py-3 text-sm ${
              cookieResult.success
                ? 'bg-green-50 text-green-700'
                : 'bg-red-50 text-red-600'
            }`}>
              {cookieResult.success
                ? <CheckCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                : <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              }
              <div>
                <p>{cookieResult.message}</p>
                {cookieResult.login_verified !== undefined && (
                  <p className="mt-1 text-xs">
                    {cookieResult.login_verified
                      ? '登录验证通过 — Facebook 已识别身份'
                      : '登录验证未通过 — Cookies 可能已过期，请重新导出'}
                  </p>
                )}
              </div>
            </div>
          )}

          <button
            onClick={handleImportCookies}
            disabled={cookieImporting || !cookieJson.trim()}
            className="mt-3 inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#0077ed] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Upload className="h-4 w-4" />
            {cookieImporting ? '导入中...' : '导入 Cookies'}
          </button>
        </div>

        {/* AI Provider */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">AI 服务提供商</h2>
          <div className="space-y-3">
            {[
              { id: 'openrouter', name: 'OpenRouter', desc: 'GPT-5.4 / Claude / Gemini 等，一个 Key 用所有模型' },
              { id: 'openai', name: 'OpenAI', desc: 'GPT-4o / GPT-4o-mini，支持兼容 API' },
              { id: 'anthropic', name: 'Anthropic Claude', desc: 'Claude 系列模型' },
              { id: 'kimi', name: 'Kimi / Moonshot', desc: '月之暗面，国内直连' },
            ].map((provider) => (
              <label
                key={provider.id}
                className={`flex cursor-pointer items-center gap-3 rounded-xl border-2 p-4 transition-all ${
                  aiProvider === provider.id
                    ? 'border-[#0071e3] bg-blue-50/30'
                    : 'border-[#e5e5e7] hover:border-[#86868b]'
                }`}
              >
                <input
                  type="radio"
                  name="ai_provider"
                  value={provider.id}
                  checked={aiProvider === provider.id}
                  onChange={(e) => setAiProvider(e.target.value)}
                  className="sr-only"
                />
                <div className={`flex h-5 w-5 items-center justify-center rounded-full border-2 ${
                  aiProvider === provider.id ? 'border-[#0071e3]' : 'border-[#c1c1c4]'
                }`}>
                  {aiProvider === provider.id && (
                    <div className="h-2.5 w-2.5 rounded-full bg-[#0071e3]" />
                  )}
                </div>
                <div>
                  <p className="text-sm font-medium text-[#1d1d1f]">{provider.name}</p>
                  <p className="text-xs text-[#86868b]">{provider.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* API Configuration */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">API 配置</h2>
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">API Key</label>
              <div className="relative">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 pr-12 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#86868b] hover:text-[#1d1d1f]"
                >
                  {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            {aiProvider === 'openai' && (
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">
                  API Base URL
                  <span className="ml-1 text-xs text-[#86868b]">(可选，兼容 API 填写)</span>
                </label>
                <input
                  type="text"
                  value={apiBaseUrl}
                  onChange={(e) => setApiBaseUrl(e.target.value)}
                  placeholder="留空使用 OpenAI 默认地址"
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
              </div>
            )}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">
                代理地址
                <span className="ml-1 text-xs text-[#86868b]">(可选)</span>
              </label>
              <input
                type="text"
                value={proxy}
                onChange={(e) => setProxy(e.target.value)}
                placeholder="http://127.0.0.1:7890"
                className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
              />
            </div>
          </div>
        </div>

        {/* Send Parameters */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">发送参数</h2>
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">发送间隔 (秒)</label>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  min={10}
                  max={600}
                  value={sendIntervalMin}
                  onChange={(e) => setSendIntervalMin(Number(e.target.value))}
                  className="w-24 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
                <span className="text-sm text-[#86868b]">至</span>
                <input
                  type="number"
                  min={10}
                  max={600}
                  value={sendIntervalMax}
                  onChange={(e) => setSendIntervalMax(Number(e.target.value))}
                  className="w-24 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
                <span className="text-sm text-[#86868b]">秒</span>
              </div>
              <p className="mt-1 text-xs text-[#86868b]">每条消息之间的随机等待时间范围</p>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">每日最大发送量</label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={maxDailyMessages}
                  onChange={(e) => setMaxDailyMessages(Number(e.target.value))}
                  className="w-32 rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
                <span className="text-sm text-[#86868b]">条</span>
              </div>
            </div>
          </div>
        </div>

        {/* Save */}
        <div className="flex justify-end pt-2">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#0077ed] disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {isSaving ? '保存中...' : saved ? '已保存' : '保存设置'}
          </button>
        </div>
      </div>
    </div>
  );
}
