import { useEffect, useState, useCallback } from 'react';
import { Activity } from 'lucide-react';
import { systemApi, settingsApi, campaignApi } from '../lib/ipc';

type Status = 'checking' | 'ok' | 'warn' | 'error';

interface HealthState {
  sidecar: Status;
  api: Status;
  cookie: Status;
  tasks: Status;
  runningCount: number;
  apiProvider: string;
}

const INITIAL: HealthState = {
  sidecar: 'checking',
  api: 'checking',
  cookie: 'checking',
  tasks: 'checking',
  runningCount: 0,
  apiProvider: '',
};

const CHECK_INTERVAL = 30_000; // 30s

export default function HealthIndicator() {
  const [health, setHealth] = useState<HealthState>(INITIAL);
  const [expanded, setExpanded] = useState(false);

  const runChecks = useCallback(async () => {
    const next: HealthState = { ...INITIAL };

    // 1. Sidecar connectivity
    try {
      await systemApi.ping();
      next.sidecar = 'ok';
    } catch {
      next.sidecar = 'error';
      next.api = 'error';
      next.cookie = 'error';
      next.tasks = 'error';
      setHealth(next);
      return;
    }

    // 2. API key check
    try {
      const provider = (await settingsApi.get('ai_provider')) as string | null;
      next.apiProvider = provider || 'openai';
      const keyName =
        provider === 'anthropic'
          ? 'anthropic_api_key'
          : provider === 'kimi'
            ? 'kimi_api_key'
            : provider === 'openrouter'
              ? 'openrouter_api_key'
              : 'openai_api_key';
      const key = (await settingsApi.get(keyName)) as string | null;
      next.api = key && key.length > 5 ? 'ok' : 'warn';
    } catch {
      next.api = 'warn';
    }

    // 3. Cookie check
    try {
      const cookies = (await settingsApi.get('facebook_cookies')) as string | null;
      if (cookies) {
        const parsed = JSON.parse(cookies);
        const fbCount = Array.isArray(parsed)
          ? parsed.filter((c: { domain?: string }) =>
              (c.domain || '').includes('facebook.com'),
            ).length
          : 0;
        next.cookie = fbCount > 0 ? 'ok' : 'warn';
      } else {
        next.cookie = 'warn';
      }
    } catch {
      next.cookie = 'warn';
    }

    // 4. Running tasks
    try {
      const campaigns = (await campaignApi.list('running')) as Array<{ id: number }>;
      const running = Array.isArray(campaigns) ? campaigns.length : 0;
      next.runningCount = running;
      next.tasks = running > 0 ? 'ok' : 'warn';
    } catch {
      next.tasks = 'warn';
      next.runningCount = 0;
    }

    setHealth(next);
  }, []);

  useEffect(() => {
    runChecks();
    const timer = setInterval(runChecks, CHECK_INTERVAL);
    return () => clearInterval(timer);
  }, [runChecks]);

  // Overall status color
  const overall: Status =
    health.sidecar === 'error'
      ? 'error'
      : health.api === 'warn' || health.cookie === 'warn'
        ? 'warn'
        : 'ok';

  const dotColor = {
    checking: 'bg-gray-400',
    ok: 'bg-emerald-500',
    warn: 'bg-amber-500',
    error: 'bg-red-500',
  };

  const statusLabel = {
    checking: '检查中',
    ok: '正常',
    warn: '待配置',
    error: '异常',
  };

  const statusColor = {
    checking: 'text-[#86868b]',
    ok: 'text-emerald-600',
    warn: 'text-amber-600',
    error: 'text-red-600',
  };

  return (
    <div className="relative">
      {/* Compact pill */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 rounded-full border border-[#e5e5e7]/80 bg-white/80 backdrop-blur-sm px-3 py-1.5 text-xs font-medium text-[#424245] shadow-sm transition-all hover:shadow-md hover:border-[#d1d1d6]"
      >
        <span className={`h-2 w-2 rounded-full ${dotColor[overall]} ${overall === 'ok' ? '' : 'animate-pulse'}`} />
        <Activity className="h-3.5 w-3.5 text-[#86868b]" />
        <span className={statusColor[overall]}>
          {overall === 'ok' ? '系统正常' : overall === 'warn' ? '需要配置' : overall === 'error' ? '服务离线' : '检查中'}
        </span>
      </button>

      {/* Expanded panel */}
      {expanded && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-40" onClick={() => setExpanded(false)} />
          <div className="absolute right-0 top-full z-50 mt-2 w-72 rounded-2xl bg-white border border-[#e5e5e7]/80 shadow-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-[#e5e5e7]/60">
              <h3 className="text-sm font-semibold text-[#1d1d1f]">系统健康状态</h3>
              <p className="text-[11px] text-[#86868b] mt-0.5">每 30 秒自动检查</p>
            </div>
            <div className="divide-y divide-[#e5e5e7]/40">
              {/* Sidecar */}
              <div className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-[#1d1d1f]">后端服务</p>
                  <p className="text-[11px] text-[#86868b]">Sidecar 进程</p>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`h-2 w-2 rounded-full ${dotColor[health.sidecar]}`} />
                  <span className={`text-xs font-medium ${statusColor[health.sidecar]}`}>
                    {statusLabel[health.sidecar]}
                  </span>
                </div>
              </div>

              {/* API */}
              <div className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-[#1d1d1f]">AI 服务</p>
                  <p className="text-[11px] text-[#86868b]">
                    {health.apiProvider
                      ? health.apiProvider === 'openai'
                        ? 'OpenAI'
                        : health.apiProvider === 'anthropic'
                          ? 'Claude'
                          : health.apiProvider === 'openrouter'
                            ? 'OpenRouter'
                            : health.apiProvider === 'kimi'
                              ? 'Kimi'
                              : health.apiProvider
                      : 'API Key'}
                  </p>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`h-2 w-2 rounded-full ${dotColor[health.api]}`} />
                  <span className={`text-xs font-medium ${statusColor[health.api]}`}>
                    {health.api === 'ok' ? '已配置' : health.api === 'warn' ? '未配置' : statusLabel[health.api]}
                  </span>
                </div>
              </div>

              {/* Cookie */}
              <div className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-[#1d1d1f]">Facebook 登录</p>
                  <p className="text-[11px] text-[#86868b]">Cookie 状态</p>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`h-2 w-2 rounded-full ${dotColor[health.cookie]}`} />
                  <span className={`text-xs font-medium ${statusColor[health.cookie]}`}>
                    {health.cookie === 'ok' ? '已导入' : health.cookie === 'warn' ? '未导入' : statusLabel[health.cookie]}
                  </span>
                </div>
              </div>

              {/* Tasks */}
              <div className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-[#1d1d1f]">运行中任务</p>
                  <p className="text-[11px] text-[#86868b]">Campaign 状态</p>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`h-2 w-2 rounded-full ${dotColor[health.tasks]}`} />
                  <span className={`text-xs font-medium ${statusColor[health.tasks]}`}>
                    {health.runningCount > 0 ? `${health.runningCount} 个运行中` : '无任务'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
