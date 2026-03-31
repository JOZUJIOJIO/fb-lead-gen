'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { Activity } from 'lucide-react';
import api, { campaignApi, isAuthError } from '@/lib/api';

type Status = 'checking' | 'ok' | 'warn' | 'error';

interface HealthState {
  backend: Status;
  api: Status;
  cookie: Status;
  tasks: Status;
  runningCount: number;
  apiProvider: string;
}

const INITIAL: HealthState = {
  backend: 'checking',
  api: 'checking',
  cookie: 'checking',
  tasks: 'checking',
  runningCount: 0,
  apiProvider: '',
};

const CHECK_INTERVAL = 30_000;

export default function HealthIndicator() {
  const [health, setHealth] = useState<HealthState>(INITIAL);
  const [expanded, setExpanded] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const runChecks = useCallback(async () => {
    const next: HealthState = { ...INITIAL };

    // 1. Backend health
    try {
      await api.get('/health');
      next.backend = 'ok';
    } catch {
      next.backend = 'error';
      next.api = 'error';
      next.cookie = 'error';
      next.tasks = 'error';
      setHealth(next);
      return;
    }

    // 2. API key / settings
    try {
      const res = await api.get('/api/settings');
      const s = res.data;
      next.apiProvider = s.ai_provider || 'openai';
      const hasKey =
        (s.ai_provider === 'openai' && s.openai_api_key_set) ||
        (s.ai_provider === 'anthropic' && s.anthropic_api_key_set) ||
        (s.ai_provider === 'kimi' && s.kimi_api_key_set) ||
        (s.ai_provider === 'openrouter' && s.openrouter_api_key_set);
      next.api = hasKey ? 'ok' : 'warn';
    } catch (err) {
      // 401 means auth expired — interceptor will redirect to login
      next.api = isAuthError(err) ? 'error' : 'warn';
    }

    // 3. Cookie status
    try {
      const res = await api.get('/api/settings/cookies/status');
      const c = res.data;
      next.cookie = c.imported && c.facebook_count > 0 ? 'ok' : 'warn';
    } catch (err) {
      next.cookie = isAuthError(err) ? 'error' : 'warn';
    }

    // 4. Running tasks
    try {
      const res = await campaignApi.list();
      const campaigns = res.data;
      const running = Array.isArray(campaigns)
        ? campaigns.filter((c: { status: string }) => c.status === 'running').length
        : 0;
      next.runningCount = running;
      next.tasks = running > 0 ? 'ok' : 'warn';
    } catch (err) {
      next.tasks = isAuthError(err) ? 'error' : 'warn';
    }

    setHealth(next);
  }, []);

  useEffect(() => {
    runChecks();
    const timer = setInterval(runChecks, CHECK_INTERVAL);
    return () => clearInterval(timer);
  }, [runChecks]);

  // Close panel on outside click
  useEffect(() => {
    if (!expanded) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setExpanded(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [expanded]);

  const overall: Status =
    health.backend === 'error'
      ? 'error'
      : health.api === 'warn' || health.cookie === 'warn'
        ? 'warn'
        : 'ok';

  const dotColor: Record<Status, string> = {
    checking: 'bg-gray-400',
    ok: 'bg-emerald-500',
    warn: 'bg-amber-500',
    error: 'bg-red-500',
  };

  const statusColor: Record<Status, string> = {
    checking: 'text-[#86868b]',
    ok: 'text-emerald-600',
    warn: 'text-amber-600',
    error: 'text-red-600',
  };

  const providerLabel = (p: string) =>
    p === 'openai' ? 'OpenAI'
    : p === 'anthropic' ? 'Claude'
    : p === 'openrouter' ? 'OpenRouter'
    : p === 'kimi' ? 'Kimi'
    : p || 'AI';

  const items: { label: string; desc: string; status: Status; detail: string }[] = [
    {
      label: '后端服务',
      desc: 'FastAPI',
      status: health.backend,
      detail: health.backend === 'ok' ? '已连接' : health.backend === 'error' ? '离线' : '检查中',
    },
    {
      label: 'AI 服务',
      desc: providerLabel(health.apiProvider),
      status: health.api,
      detail: health.api === 'ok' ? '已配置' : health.api === 'warn' ? '未配置' : '异常',
    },
    {
      label: 'Facebook 登录',
      desc: 'Cookie',
      status: health.cookie,
      detail: health.cookie === 'ok' ? '已导入' : health.cookie === 'warn' ? '未导入' : '异常',
    },
    {
      label: '运行中任务',
      desc: 'Campaign',
      status: health.tasks,
      detail: health.runningCount > 0 ? `${health.runningCount} 个运行中` : '无任务',
    },
  ];

  return (
    <div className="relative" ref={panelRef}>
      {/* Compact pill */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 rounded-full border border-[#e5e5e7]/80 bg-white/90 backdrop-blur-sm px-3.5 py-1.5 text-xs font-medium text-[#424245] shadow-sm transition-all hover:shadow-md hover:border-[#d1d1d6]"
      >
        <span className={`h-2 w-2 rounded-full ${dotColor[overall]} ${overall !== 'ok' ? 'animate-pulse' : ''}`} />
        <Activity className="h-3.5 w-3.5 text-[#86868b]" />
        <span className={statusColor[overall]}>
          {overall === 'ok' ? '系统正常' : overall === 'warn' ? '需要配置' : overall === 'error' ? '服务离线' : '检查中'}
        </span>
      </button>

      {/* Expanded panel */}
      {expanded && (
        <div className="absolute right-0 top-full z-50 mt-2 w-72 rounded-2xl bg-white border border-[#e5e5e7]/80 shadow-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-[#e5e5e7]/60 bg-[#fafafa]">
            <h3 className="text-sm font-semibold text-[#1d1d1f]">系统健康状态</h3>
            <p className="text-[11px] text-[#86868b] mt-0.5">每 30 秒自动检查</p>
          </div>
          <div className="divide-y divide-[#e5e5e7]/40">
            {items.map((item) => (
              <div key={item.label} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-[#1d1d1f]">{item.label}</p>
                  <p className="text-[11px] text-[#86868b]">{item.desc}</p>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`h-2 w-2 rounded-full ${dotColor[item.status]}`} />
                  <span className={`text-xs font-medium ${statusColor[item.status]}`}>
                    {item.detail}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
