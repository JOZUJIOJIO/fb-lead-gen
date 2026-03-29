'use client';

import { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import { ArrowLeft, Pause, Play, Square, Clock } from 'lucide-react';
import StatusBadge from '@/components/StatusBadge';

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

interface Lead {
  id: string;
  name: string;
  status: string;
  message_preview: string;
  timestamp: string;
}

const mockCampaign = {
  id: '1',
  name: 'Facebook 外贸客户开发',
  platform: 'Facebook',
  status: 'running',
  keywords: '外贸, B2B, 供应商',
  region: '东南亚',
  persona: '专业商务顾问',
  sent: 145,
  limit: 200,
  created_at: '2024-03-15 10:30',
};

const mockLogs: LogEntry[] = [
  { timestamp: '10:45:32', level: 'info', message: '搜索中... 找到 15 个潜在目标' },
  { timestamp: '10:45:35', level: 'info', message: '正在分析用户 John Smith 的资料...' },
  { timestamp: '10:45:38', level: 'success', message: '已向 John Smith 发送个性化消息' },
  { timestamp: '10:45:42', level: 'info', message: '正在分析用户 Sarah Lee 的资料...' },
  { timestamp: '10:45:45', level: 'success', message: '已向 Sarah Lee 发送个性化消息' },
  { timestamp: '10:45:50', level: 'warn', message: '用户 Mike Chen 主页为私密，跳过' },
  { timestamp: '10:45:55', level: 'info', message: '正在分析用户 Emma Wilson 的资料...' },
];

const mockLeads: Lead[] = [
  { id: '1', name: 'John Smith', status: 'replied', message_preview: 'Hi John, I noticed your work in...', timestamp: '2024-03-15 10:45' },
  { id: '2', name: 'Sarah Lee', status: 'sent', message_preview: 'Hello Sarah, your expertise in...', timestamp: '2024-03-15 10:46' },
  { id: '3', name: 'Emma Wilson', status: 'interested', message_preview: 'Hi Emma, I came across your...', timestamp: '2024-03-15 10:47' },
  { id: '4', name: 'David Chen', status: 'sent', message_preview: 'Hello David, as a fellow...', timestamp: '2024-03-15 10:48' },
  { id: '5', name: 'Lisa Wang', status: 'not_interested', message_preview: 'Hi Lisa, I saw your recent post...', timestamp: '2024-03-15 10:49' },
];

export default function CampaignDetailPage({ params }: { params: { id: string } }) {
  const [campaign, setCampaign] = useState(mockCampaign);
  const [logs, setLogs] = useState<LogEntry[]>(mockLogs);
  const [leads, setLeads] = useState<Lead[]>(mockLeads);
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // TODO: Fetch campaign data
    // campaignApi.get(params.id).then(res => setCampaign(res.data));
  }, [params.id]);

  // Poll logs when running
  useEffect(() => {
    if (campaign.status !== 'running') return;

    const interval = setInterval(() => {
      // TODO: Poll real logs
      // campaignApi.logs(params.id).then(res => setLogs(res.data));
    }, 3000);

    return () => clearInterval(interval);
  }, [campaign.status, params.id]);

  // Auto-scroll logs
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  const handlePause = async () => {
    // TODO: campaignApi.pause(params.id)
    setCampaign({ ...campaign, status: 'paused' });
  };

  const handleResume = async () => {
    // TODO: campaignApi.resume(params.id)
    setCampaign({ ...campaign, status: 'running' });
  };

  const handleStop = async () => {
    // TODO: campaignApi.stop(params.id)
    setCampaign({ ...campaign, status: 'completed' });
  };

  const progress = (campaign.sent / campaign.limit) * 100;

  const logLevelColor = (level: string) => {
    switch (level) {
      case 'success': return 'text-emerald-600';
      case 'warn': return 'text-amber-600';
      case 'error': return 'text-red-600';
      default: return 'text-[#86868b]';
    }
  };

  return (
    <div>
      <div className="mb-8">
        <Link href="/campaigns" className="mb-4 inline-flex items-center gap-1.5 text-sm text-[#86868b] hover:text-[#1d1d1f] transition-colors">
          <ArrowLeft className="h-4 w-4" />
          返回任务列表
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">{campaign.name}</h1>
              <StatusBadge status={campaign.status} size="md" />
            </div>
            <p className="mt-1 text-sm text-[#86868b]">创建于 {campaign.created_at}</p>
          </div>
          <div className="flex items-center gap-2">
            {campaign.status === 'running' && (
              <button onClick={handlePause} className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-700 transition-colors hover:bg-amber-100">
                <Pause className="h-4 w-4" />
                暂停
              </button>
            )}
            {campaign.status === 'paused' && (
              <button onClick={handleResume} className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-100">
                <Play className="h-4 w-4" />
                继续
              </button>
            )}
            {(campaign.status === 'running' || campaign.status === 'paused') && (
              <button onClick={handleStop} className="inline-flex items-center gap-1.5 rounded-full border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-100">
                <Square className="h-4 w-4" />
                停止
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Campaign Info */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
          <p className="text-xs text-[#86868b]">平台</p>
          <p className="mt-1 text-sm font-medium text-[#1d1d1f]">{campaign.platform}</p>
        </div>
        <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
          <p className="text-xs text-[#86868b]">关键词</p>
          <p className="mt-1 text-sm font-medium text-[#1d1d1f]">{campaign.keywords}</p>
        </div>
        <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
          <p className="text-xs text-[#86868b]">地区</p>
          <p className="mt-1 text-sm font-medium text-[#1d1d1f]">{campaign.region}</p>
        </div>
        <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
          <p className="text-xs text-[#86868b]">人设</p>
          <p className="mt-1 text-sm font-medium text-[#1d1d1f]">{campaign.persona}</p>
        </div>
      </div>

      {/* Progress */}
      <div className="mb-6 rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm font-medium text-[#1d1d1f]">发送进度</span>
          <span className="text-sm text-[#86868b]">{campaign.sent} / {campaign.limit}</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-[#f0f0f2]">
          <div
            className="h-full rounded-full bg-[#0071e3] transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Real-time Logs */}
      <div className="mb-6 rounded-2xl bg-white border border-[#e5e5e7]/60 shadow-sm overflow-hidden">
        <div className="flex items-center gap-2 border-b border-[#e5e5e7]/60 px-6 py-3.5">
          <Clock className="h-4 w-4 text-[#86868b]" />
          <h2 className="text-sm font-semibold text-[#1d1d1f]">实时日志</h2>
          {campaign.status === 'running' && (
            <span className="ml-auto flex items-center gap-1.5 text-xs text-emerald-600">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse-dot" />
              实时更新中
            </span>
          )}
        </div>
        <div ref={logContainerRef} className="h-48 overflow-y-auto bg-[#fafafa] p-4 font-mono text-xs">
          {logs.map((log, i) => (
            <div key={i} className="py-0.5">
              <span className="text-[#86868b]">[{log.timestamp}]</span>{' '}
              <span className={logLevelColor(log.level)}>{log.message}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Leads Table */}
      <div className="rounded-2xl bg-white border border-[#e5e5e7]/60 shadow-sm overflow-hidden">
        <div className="border-b border-[#e5e5e7]/60 px-6 py-3.5">
          <h2 className="text-sm font-semibold text-[#1d1d1f]">获取的线索</h2>
        </div>
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#e5e5e7]/40">
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">姓名</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">状态</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">消息预览</th>
              <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">时间</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#e5e5e7]/40">
            {leads.map((lead) => (
              <tr key={lead.id} className="transition-colors hover:bg-[#f5f5f7]/50">
                <td className="px-6 py-3.5 text-sm font-medium text-[#1d1d1f]">{lead.name}</td>
                <td className="px-6 py-3.5"><StatusBadge status={lead.status} /></td>
                <td className="max-w-xs truncate px-6 py-3.5 text-sm text-[#86868b]">{lead.message_preview}</td>
                <td className="px-6 py-3.5 text-sm text-[#86868b]">{lead.timestamp}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
