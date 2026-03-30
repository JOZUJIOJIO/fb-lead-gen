import { useEffect, useState } from 'react';
import {
  Save,
  Eye,
  EyeOff,
  Cookie,
  CheckCircle,
  AlertCircle,
  Upload,
} from 'lucide-react';
import { settingsApi, systemApi } from '../lib/ipc';

export default function Settings() {
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
  const [sidecarConnected, setSidecarConnected] = useState(false);

  // Cookie state
  const [cookieJson, setCookieJson] = useState('');
  const [cookieImporting, setCookieImporting] = useState(false);
  const [cookieResult, setCookieResult] = useState<{
    message: string;
    success: boolean;
  } | null>(null);

  useEffect(() => {
    // Check sidecar connectivity
    systemApi
      .ping()
      .then(() => setSidecarConnected(true))
      .catch(() => setSidecarConnected(false));

    // Load settings
    loadSettings();
  }, []);

  async function loadSettings() {
    try {
      const keys = [
        'ai_provider',
        'openai_base_url',
        'proxy_server',
        'send_interval_min',
        'send_interval_max',
        'max_daily_messages',
      ];
      const results = await Promise.allSettled(
        keys.map((k) => settingsApi.get(k)),
      );
      const vals: Record<string, string> = {};
      keys.forEach((k, i) => {
        const r = results[i];
        if (r.status === 'fulfilled' && r.value) {
          vals[k] = r.value as string;
        }
      });
      if (vals.ai_provider) setAiProvider(vals.ai_provider);
      if (vals.openai_base_url) setApiBaseUrl(vals.openai_base_url);
      if (vals.proxy_server) setProxy(vals.proxy_server);
      if (vals.send_interval_min)
        setSendIntervalMin(Number(vals.send_interval_min));
      if (vals.send_interval_max)
        setSendIntervalMax(Number(vals.send_interval_max));
      if (vals.max_daily_messages)
        setMaxDailyMessages(Number(vals.max_daily_messages));
    } catch {
      // Ignore
    }
  }

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const pairs: [string, string][] = [
        ['ai_provider', aiProvider],
        ['proxy_server', proxy],
        ['send_interval_min', String(sendIntervalMin)],
        ['send_interval_max', String(sendIntervalMax)],
        ['max_daily_messages', String(maxDailyMessages)],
      ];
      if (apiKey) {
        const keyName =
          aiProvider === 'openai'
            ? 'openai_api_key'
            : aiProvider === 'anthropic'
              ? 'anthropic_api_key'
              : 'kimi_api_key';
        pairs.push([keyName, apiKey]);
      }
      if (apiBaseUrl) pairs.push(['openai_base_url', apiBaseUrl]);

      await Promise.allSettled(pairs.map(([k, v]) => settingsApi.set(k, v)));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // Ignore
    } finally {
      setIsSaving(false);
    }
  };

  const handleImportCookies = async () => {
    if (!cookieJson.trim()) return;
    setCookieImporting(true);
    setCookieResult(null);
    try {
      JSON.parse(cookieJson); // Validate JSON
      // Store cookies via settings
      await settingsApi.set('facebook_cookies', cookieJson);
      setCookieResult({ message: 'Cookies 导入成功', success: true });
      setCookieJson('');
    } catch (e: unknown) {
      const msg =
        e instanceof SyntaxError
          ? 'JSON 格式错误，请检查复制的内容'
          : '导入失败，请检查后台服务是否运行';
      setCookieResult({ message: msg, success: false });
    } finally {
      setCookieImporting(false);
    }
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">
          设置
        </h1>
        <p className="mt-1 text-sm text-[#86868b]">
          配置 AI 服务、浏览器登录和系统参数
        </p>
      </div>

      {/* Sidecar status */}
      <div
        className={`mb-6 flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm ${
          sidecarConnected
            ? 'bg-green-50 text-green-700'
            : 'bg-yellow-50 text-yellow-700'
        }`}
      >
        <div
          className={`h-2 w-2 rounded-full ${sidecarConnected ? 'bg-green-500' : 'bg-yellow-500'}`}
        />
        {sidecarConnected ? '后端服务已连接' : '后端服务未连接（设置将在服务启动后生效）'}
      </div>

      <div className="space-y-6">
        {/* Facebook Login (Cookies) */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <Cookie className="h-5 w-5 text-[#0071e3]" />
            <h2 className="text-base font-semibold text-[#1d1d1f]">
              Facebook 登录状态
            </h2>
          </div>

          <div className="mb-4 rounded-xl bg-[#f5f5f7] p-4 text-sm text-[#424245] space-y-3">
            <p className="font-medium">通过导入 Chrome Cookies 免登录使用 Facebook：</p>
            <ol className="ml-4 list-decimal space-y-2">
              <li>
                在 Chrome 中安装{' '}
                <a
                  href="https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mx-1 text-[#0071e3] hover:underline"
                >
                  Cookie-Editor
                </a>{' '}
                扩展
              </li>
              <li>
                在 Chrome 中打开{' '}
                <span className="rounded bg-white px-1.5 py-0.5 font-mono">
                  facebook.com
                </span>{' '}
                并确保已登录
              </li>
              <li>
                点击 Cookie-Editor 图标 → 点击底部{' '}
                <span className="font-medium">Export</span> 按钮
              </li>
              <li>回到这里，粘贴到下面的输入框 → 点击导入</li>
            </ol>
          </div>

          <textarea
            value={cookieJson}
            onChange={(e) => setCookieJson(e.target.value)}
            placeholder="粘贴 Cookie-Editor 导出的 JSON..."
            rows={5}
            className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 font-mono text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
          />

          {cookieResult && (
            <div
              className={`mt-3 flex items-start gap-2 rounded-xl px-4 py-3 text-sm ${
                cookieResult.success
                  ? 'bg-green-50 text-green-700'
                  : 'bg-red-50 text-red-600'
              }`}
            >
              {cookieResult.success ? (
                <CheckCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              ) : (
                <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              )}
              <p>{cookieResult.message}</p>
            </div>
          )}

          <button
            onClick={handleImportCookies}
            disabled={cookieImporting || !cookieJson.trim()}
            className="mt-3 inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#0077ed] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Upload className="h-4 w-4" />
            {cookieImporting ? '导入中...' : '导入 Cookies'}
          </button>
        </div>

        {/* AI Provider */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">
            AI 服务提供商
          </h2>
          <div className="space-y-3">
            {[
              {
                id: 'openai',
                name: 'OpenAI',
                desc: 'GPT-4o / GPT-4o-mini，支持兼容 API',
              },
              {
                id: 'anthropic',
                name: 'Anthropic Claude',
                desc: 'Claude 系列模型',
              },
              {
                id: 'kimi',
                name: 'Kimi / Moonshot',
                desc: '月之暗面，国内直连',
              },
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
                <div
                  className={`flex h-5 w-5 items-center justify-center rounded-full border-2 ${
                    aiProvider === provider.id
                      ? 'border-[#0071e3]'
                      : 'border-[#c1c1c4]'
                  }`}
                >
                  {aiProvider === provider.id && (
                    <div className="h-2.5 w-2.5 rounded-full bg-[#0071e3]" />
                  )}
                </div>
                <div>
                  <p className="text-sm font-medium text-[#1d1d1f]">
                    {provider.name}
                  </p>
                  <p className="text-xs text-[#86868b]">{provider.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* API Configuration */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">
            API 配置
          </h2>
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">
                API Key
              </label>
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
                  {showApiKey ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>
            {aiProvider === 'openai' && (
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">
                  API Base URL{' '}
                  <span className="font-normal text-[#86868b]">（可选）</span>
                </label>
                <input
                  type="text"
                  value={apiBaseUrl}
                  onChange={(e) => setApiBaseUrl(e.target.value)}
                  placeholder="https://api.openai.com/v1"
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
                />
              </div>
            )}
          </div>
        </div>

        {/* Proxy & Rate Limits */}
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-4 text-base font-semibold text-[#1d1d1f]">
            代理与频率控制
          </h2>
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">
                代理服务器{' '}
                <span className="font-normal text-[#86868b]">（可选）</span>
              </label>
              <input
                type="text"
                value={proxy}
                onChange={(e) => setProxy(e.target.value)}
                placeholder="http://127.0.0.1:7890"
                className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm text-[#1d1d1f] placeholder-[#86868b] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">
                  最小间隔（秒）
                </label>
                <input
                  type="number"
                  value={sendIntervalMin}
                  onChange={(e) => setSendIntervalMin(Number(e.target.value))}
                  min={10}
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm outline-none focus:border-[#0071e3] focus:bg-white"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">
                  最大间隔（秒）
                </label>
                <input
                  type="number"
                  value={sendIntervalMax}
                  onChange={(e) => setSendIntervalMax(Number(e.target.value))}
                  min={10}
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm outline-none focus:border-[#0071e3] focus:bg-white"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-[#1d1d1f]">
                  每日最大消息数
                </label>
                <input
                  type="number"
                  value={maxDailyMessages}
                  onChange={(e) => setMaxDailyMessages(Number(e.target.value))}
                  min={1}
                  className="w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-4 py-3 text-sm outline-none focus:border-[#0071e3] focus:bg-white"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Save button */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="inline-flex items-center gap-2 rounded-full bg-[#0071e3] px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#0077ed] disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {isSaving ? '保存中...' : '保存设置'}
          </button>
          {saved && (
            <span className="flex items-center gap-1.5 text-sm text-green-600">
              <CheckCircle className="h-4 w-4" />
              已保存
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
