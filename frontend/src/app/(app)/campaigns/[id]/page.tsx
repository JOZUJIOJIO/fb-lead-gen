'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import Link from 'next/link';
import { ArrowLeft, Pause, Play, Square, Clock } from 'lucide-react';
import StatusBadge from '@/components/StatusBadge';
import { campaignApi } from '@/lib/api';

interface LeadBrief {
  id: number;
  name: string | null;
  status: string;
  profile_url: string | null;
  created_at: string;
}

interface CampaignDetail {
  id: number;
  name: string | null;
  platform: string;
  status: string;
  search_keywords: string | null;
  search_region: string | null;
  search_industry: string | null;
  persona_id: number | null;
  send_limit: number;
  progress_current: number;
  progress_total: number;
  created_at: string;
  updated_at: string;
  leads: LeadBrief[];
}

interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

export default function CampaignDetailPage({ params }: { params: { id: string } }) {
  const [campaign, setCampaign] = useState<CampaignDetail | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const logContainerRef = useRef<HTMLDivElement>(null);

  const fetchCampaign = useCallback(async () => {
    try {
      const res = await campaignApi.get(params.id);
      setCampaign(res.data);
    } catch (error) {
      console.error('Failed to load campaign:', error);
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    fetchCampaign();
  }, [fetchCampaign]);

  // Poll campaign data when running
  useEffect(() => {
    if (!campaign || campaign.status !== 'running') return;

    const interval = setInterval(() => {
      fetchCampaign();
    }, 5000);

    return () => clearInterval(interval);
  }, [campaign?.status, fetchCampaign]);

  // Auto-scroll logs
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [campaign?.leads]);

  const handlePause = async () => {
    if (!campaign) return;
    try {
      await campaignApi.pause(String(campaign.id));
      setCampaign({ ...campaign, status: 'paused' });
    } catch (error) {
      console.error('Failed to pause campaign:', error);
    }
  };

  const handleResume = async () => {
    if (!campaign) return;
    try {
      await campaignApi.start(String(campaign.id));
      setCampaign({ ...campaign, status: 'running' });
    } catch (error) {
      console.error('Failed to resume campaign:', error);
    }
  };

  const handleStop = async () => {
    if (!campaign) return;
    try {
      await campaignApi.stop(String(campaign.id));
      setCampaign({ ...campaign, status: 'failed' });
    } catch (error) {
      console.error('Failed to stop campaign:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-sm text-[#86868b]">加载中...</p>
      </div>
    );
  }

  if (!campaign) {
    return (
      <div className="text-center py-24">
        <p className="text-sm text-[#86868b]">任务不存在</p>
        <Link href="/campaigns" className="mt-4 inline-block text-sm text-[#0071e3] hover:underline">返回任务列表</Link>
      </div>
    );
  }

  const progress = campaign.send_limit > 0 ? (campaign.progress_current / campaign.send_limit) * 100 : 0;

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
              <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">
                {campaign.name || campaign.search_keywords || '未命名任务'}
              </h1>
              <StatusBadge status={campaign.status} size="md" />
            </div>
            <p className="mt-1 text-sm text-[#86868b]">创建于 {new Date(campaign.created_at).toLocaleString('zh-CN')}</p>
          </div>
          <div className="flex items-center gap-2">
            {campaign.status === 'draft' && (
              <button onClick={handleResume} className="inline-flex items-center gap-1.5 rounded-full bg-[#0071e3] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#0077ed]">
                <Play className="h-4 w-4" />
                启动
              </button>
            )}
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
          <p className="mt-1 text-sm font-medium text-[#1d1d1f] capitalize">{campaign.platform}</p>
        </div>
        <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
          <p className="text-xs text-[#86868b]">关键词</p>
          <p className="mt-1 text-sm font-medium text-[#1d1d1f]">{campaign.search_keywords || '-'}</p>
        </div>
        <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
          <p className="text-xs text-[#86868b]">地区</p>
          <p className="mt-1 text-sm font-medium text-[#1d1d1f]">{campaign.search_region || '全部'}</p>
        </div>
        <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
          <p className="text-xs text-[#86868b]">行业</p>
          <p className="mt-1 text-sm font-medium text-[#1d1d1f]">{campaign.search_industry || '全部'}</p>
        </div>
      </div>

      {/* Progress */}
      <div className="mb-6 rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm font-medium text-[#1d1d1f]">发送进度</span>
          <span className="text-sm text-[#86868b]">{campaign.progress_current} / {campaign.send_limit}</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-[#f0f0f2]">
          <div
            className="h-full rounded-full bg-[#0071e3] transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Leads Table */}
      <div className="rounded-2xl bg-white border border-[#e5e5e7]/60 shadow-sm overflow-hidden">
        <div className="border-b border-[#e5e5e7]/60 px-6 py-3.5">
          <h2 className="text-sm font-semibold text-[#1d1d1f]">获取的线索 ({campaign.leads.length})</h2>
        </div>
        {campaign.leads.length > 0 ? (
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#e5e5e7]/40">
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">姓名</th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">状态</th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">时间</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e5e5e7]/40">
              {campaign.leads.map((lead) => (
                <tr key={lead.id} className="transition-colors hover:bg-[#f5f5f7]/50">
                  <td className="px-6 py-3.5 text-sm font-medium text-[#1d1d1f]">{lead.name || '未知'}</td>
                  <td className="px-6 py-3.5"><StatusBadge status={lead.status} /></td>
                  <td className="px-6 py-3.5 text-sm text-[#86868b]">{new Date(lead.created_at).toLocaleString('zh-CN')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="py-12 text-center text-sm text-[#86868b]">暂无线索数据</div>
        )}
      </div>
    </div>
  );
}
