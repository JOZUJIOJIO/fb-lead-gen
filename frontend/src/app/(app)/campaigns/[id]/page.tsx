'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { Fragment } from 'react';
import { ArrowLeft, Pause, Play, Square, Clock, Check, X, Eye, RotateCcw, AlertTriangle, ChevronDown, ChevronUp, Shield, Loader2 } from 'lucide-react';
import StatusBadge from '@/components/StatusBadge';
import { campaignApi, leadApi, personaApi } from '@/lib/api';

interface LeadBrief {
  id: number;
  name: string | null;
  status: string;
  profile_url: string | null;
  failure_code: string | null;
  failure_reason: string | null;
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
  review_mode: boolean;
  send_hour_start: number;
  send_hour_end: number;
  timezone: string;
  progress_current: number;
  progress_total: number;
  created_at: string;
  updated_at: string;
  leads: LeadBrief[];
}

interface PendingLead {
  id: number;
  name: string | null;
  status: string;
  profile_url: string | null;
  created_at: string;
  message?: string;
}

export default function CampaignDetailPage({ params }: { params: { id: string } }) {
  const [campaign, setCampaign] = useState<CampaignDetail | null>(null);
  const [pendingLeads, setPendingLeads] = useState<PendingLead[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewingId, setReviewingId] = useState<number | null>(null);
  const [expandedLeadId, setExpandedLeadId] = useState<number | null>(null);
  const [expandedMessages, setExpandedMessages] = useState<{id: number; direction: string; content: string; created_at: string}[]>([]);
  const [personaName, setPersonaName] = useState<string>('');
  const [progressInfo, setProgressInfo] = useState<{current_lead_name?: string; current_step?: string; current_index?: number; total?: number} | null>(null);
  const [preflightOpen, setPreflightOpen] = useState(false);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [preflightResult, setPreflightResult] = useState<{all_passed: boolean; cookies_valid: boolean; ai_connected: boolean; ai_provider?: string; search_keywords_set: boolean; persona_set: boolean} | null>(null);
  const [editTimezone, setEditTimezone] = useState('');

  const fetchCampaign = useCallback(async () => {
    try {
      const res = await campaignApi.get(params.id);
      setCampaign(res.data);
      // Fetch persona name
      if (res.data.persona_id) {
        personaApi.get(String(res.data.persona_id))
          .then(pRes => setPersonaName(pRes.data?.name || ''))
          .catch(() => {});
      }
      // Fetch pending reviews if review_mode
      if (res.data.review_mode) {
        try {
          const pendingRes = await campaignApi.pending(params.id);
          // For each pending lead, fetch message content
          const leadsWithMsg: PendingLead[] = [];
          for (const lead of pendingRes.data) {
            try {
              const detail = await leadApi.get(String(lead.id));
              const outMsg = detail.data.messages?.find((m: { direction: string }) => m.direction === 'outbound');
              leadsWithMsg.push({ ...lead, message: outMsg?.content });
            } catch {
              leadsWithMsg.push(lead);
            }
          }
          setPendingLeads(leadsWithMsg);
        } catch (err) {
          console.error('Failed to load pending reviews:', err);
        }
      }
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

  // Real-time progress polling when running
  useEffect(() => {
    if (!campaign || campaign.status !== 'running') {
      setProgressInfo(null);
      return;
    }

    const fetchProgress = async () => {
      try {
        const res = await campaignApi.progress(campaign.id);
        setProgressInfo(res.data);
      } catch {
        // ignore progress fetch errors
      }
    };

    fetchProgress();
    const interval = setInterval(fetchProgress, 3000);
    return () => clearInterval(interval);
  }, [campaign?.id, campaign?.status]);

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

  const handlePreflight = async () => {
    if (!campaign) return;
    setPreflightLoading(true);
    setPreflightOpen(true);
    setPreflightResult(null);
    try {
      const res = await campaignApi.preflight(campaign.id);
      setPreflightResult(res.data);
    } catch {
      setPreflightResult({ all_passed: false, cookies_valid: false, ai_connected: false, search_keywords_set: false, persona_set: false });
    } finally {
      setPreflightLoading(false);
    }
  };

  const handleConfirmStart = async () => {
    if (!campaign) return;
    try {
      await campaignApi.start(String(campaign.id));
      setCampaign({ ...campaign, status: 'running' });
      setPreflightOpen(false);
      setPreflightResult(null);
    } catch (error) {
      console.error('Failed to start campaign:', error);
    }
  };

  const handleReview = async (leadId: number, action: 'approve' | 'reject') => {
    if (!campaign) return;
    setReviewingId(leadId);
    try {
      await campaignApi.review(String(campaign.id), leadId, action);
      setPendingLeads(prev => prev.filter(l => l.id !== leadId));
      fetchCampaign();
    } catch (error) {
      console.error(`Failed to ${action} lead:`, error);
    } finally {
      setReviewingId(null);
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
              <button onClick={handlePreflight} className="inline-flex items-center gap-1.5 rounded-full bg-[#0071e3] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#0077ed]">
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
            {campaign.status === 'failed' && (
              <button onClick={handleResume} className="inline-flex items-center gap-1.5 rounded-full bg-[#0071e3] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#0077ed]">
                <RotateCcw className="h-4 w-4" />
                重新启动
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

      {/* Pre-Flight Check Modal */}
      {preflightOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="mx-4 w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <div className="mb-4 flex items-center gap-2">
              <Shield className="h-5 w-5 text-[#0071e3]" />
              <h3 className="text-lg font-semibold text-[#1d1d1f]">启动前检查</h3>
            </div>
            {preflightLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-[#0071e3]" />
                <span className="ml-2 text-sm text-[#86868b]">正在检查...</span>
              </div>
            ) : preflightResult ? (
              <>
                <div className="space-y-3 mb-6">
                  <div className="flex items-center gap-2.5">
                    {preflightResult.cookies_valid ? <Check className="h-4.5 w-4.5 text-emerald-600" /> : <X className="h-4.5 w-4.5 text-red-500" />}
                    <span className="text-sm text-[#1d1d1f]">Cookies 有效</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    {preflightResult.ai_connected ? <Check className="h-4.5 w-4.5 text-emerald-600" /> : <X className="h-4.5 w-4.5 text-red-500" />}
                    <span className="text-sm text-[#1d1d1f]">AI 连接正常{preflightResult.ai_provider ? ` (${preflightResult.ai_provider})` : ''}</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    {preflightResult.search_keywords_set ? <Check className="h-4.5 w-4.5 text-emerald-600" /> : <X className="h-4.5 w-4.5 text-red-500" />}
                    <span className="text-sm text-[#1d1d1f]">搜索关键词已设置</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    {preflightResult.persona_set ? <Check className="h-4.5 w-4.5 text-emerald-600" /> : <X className="h-4.5 w-4.5 text-red-500" />}
                    <span className="text-sm text-[#1d1d1f]">人设已配置</span>
                  </div>
                </div>
                {preflightResult.all_passed ? (
                  <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-2.5 mb-4">
                    <span className="text-sm font-medium text-emerald-700">全部通过</span>
                  </div>
                ) : (
                  <div className="rounded-xl bg-amber-50 border border-amber-200 px-4 py-2.5 mb-4">
                    <span className="text-sm font-medium text-amber-700">部分检查未通过，启动后可能出现问题</span>
                  </div>
                )}
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => { setPreflightOpen(false); setPreflightResult(null); }}
                    className="rounded-full border border-[#e5e5e7] px-4 py-2 text-sm font-medium text-[#1d1d1f] transition-colors hover:bg-[#f5f5f7]"
                  >
                    {preflightResult.all_passed ? '取消' : '返回修改'}
                  </button>
                  <button
                    onClick={handleConfirmStart}
                    className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                      preflightResult.all_passed
                        ? 'bg-[#0071e3] text-white hover:bg-[#0077ed]'
                        : 'border border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100'
                    }`}
                  >
                    {preflightResult.all_passed ? '确认启动' : '仍然启动'}
                  </button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}

      {/* Real-Time Progress */}
      {campaign.status === 'running' && progressInfo && (
        <div className="mb-6 rounded-2xl bg-white p-5 border border-[#e5e5e7]/60 shadow-sm">
          <div className="flex items-center gap-2 mb-3">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#0071e3] opacity-75" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#0071e3]" />
            </span>
            <span className="text-sm font-medium text-[#1d1d1f]">正在处理</span>
          </div>
          <p className="text-sm text-[#1d1d1f] mb-3">
            {progressInfo.current_lead_name || '...'} —{' '}
            <span className="animate-pulse text-[#0071e3] font-medium">{progressInfo.current_step || '处理中'}</span>
            {progressInfo.total ? (
              <span className="ml-2 text-[#86868b]">({progressInfo.current_index || 0}/{progressInfo.total})</span>
            ) : null}
          </p>
          {progressInfo.total ? (
            <div className="h-1.5 overflow-hidden rounded-full bg-[#f0f0f2]">
              <div
                className="h-full rounded-full bg-[#0071e3] transition-all duration-500"
                style={{ width: `${((progressInfo.current_index || 0) / progressInfo.total) * 100}%` }}
              />
            </div>
          ) : null}
        </div>
      )}

      {/* Campaign Info */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
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
        <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
          <p className="text-xs text-[#86868b]">人设</p>
          <p className="mt-1 text-sm font-medium text-[#1d1d1f]">{personaName || '未设置'}</p>
        </div>
        <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
          <p className="text-xs text-[#86868b]">时区</p>
          <select
            value={editTimezone || campaign.timezone || 'Asia/Shanghai'}
            onChange={async (e) => {
              const tz = e.target.value;
              setEditTimezone(tz);
              try {
                await campaignApi.update(String(campaign.id), { timezone: tz });
                setCampaign({ ...campaign, timezone: tz });
              } catch { /* ignore */ }
            }}
            className="mt-1 w-full rounded-xl border border-[#e5e5e7] bg-[#f5f5f7] px-2 py-1.5 text-xs text-[#1d1d1f] outline-none transition-colors focus:border-[#0071e3] focus:bg-white"
          >
            <option value="Asia/Shanghai">中国标准时间 (UTC+8)</option>
            <option value="Asia/Tokyo">日本标准时间 (UTC+9)</option>
            <option value="Asia/Singapore">新加坡时间 (UTC+8)</option>
            <option value="Asia/Dubai">迪拜时间 (UTC+4)</option>
            <option value="Europe/London">英国时间 (UTC+0)</option>
            <option value="Europe/Paris">中欧时间 (UTC+1)</option>
            <option value="Europe/Berlin">德国时间 (UTC+1)</option>
            <option value="America/New_York">美国东部 (UTC-5)</option>
            <option value="America/Los_Angeles">美国西部 (UTC-8)</option>
            <option value="America/Sao_Paulo">巴西时间 (UTC-3)</option>
            <option value="Australia/Sydney">澳大利亚东部 (UTC+11)</option>
            <option value="Pacific/Auckland">新西兰时间 (UTC+12)</option>
          </select>
        </div>
      </div>

      {/* Progress */}
      <div className="mb-6 rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm font-medium text-[#1d1d1f]">发送进度</span>
          <div className="flex items-center gap-3 text-sm text-[#86868b]">
            {campaign.progress_total > 0 && (
              <span>搜到 {campaign.progress_total} 人</span>
            )}
            <span>已发 {campaign.progress_current} / {campaign.send_limit}</span>
          </div>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-[#f0f0f2]">
          <div
            className="h-full rounded-full bg-[#0071e3] transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Review Mode Badge */}
      {campaign.review_mode && (
        <div className="mb-6 flex items-center gap-2 rounded-xl bg-orange-50 border border-orange-200 px-4 py-3">
          <Eye className="h-4 w-4 text-orange-600" />
          <span className="text-sm font-medium text-orange-700">审核模式已开启</span>
          <span className="text-sm text-orange-600">— 消息生成后需要手动审批才会发送</span>
        </div>
      )}

      {/* Pending Review Queue */}
      {campaign.review_mode && pendingLeads.length > 0 && (
        <div className="mb-6 rounded-2xl bg-white border border-orange-200 shadow-sm overflow-hidden">
          <div className="border-b border-orange-100 bg-orange-50/50 px-6 py-3.5">
            <h2 className="text-sm font-semibold text-orange-800">待审核消息 ({pendingLeads.length})</h2>
          </div>
          <div className="divide-y divide-[#e5e5e7]/40">
            {pendingLeads.map((lead) => (
              <div key={lead.id} className="px-6 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm font-medium text-[#1d1d1f]">{lead.name || '未知'}</span>
                      <StatusBadge status="pending_review" />
                    </div>
                    {lead.message && (
                      <div className="rounded-xl bg-blue-50 p-3 text-sm text-blue-900">
                        <p className="text-xs font-medium text-blue-600 mb-1">AI 生成的消息：</p>
                        <p>{lead.message}</p>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => handleReview(lead.id, 'approve')}
                      disabled={reviewingId === lead.id}
                      className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100 disabled:opacity-50"
                    >
                      <Check className="h-3.5 w-3.5" />
                      批准发送
                    </button>
                    <button
                      onClick={() => handleReview(lead.id, 'reject')}
                      disabled={reviewingId === lead.id}
                      className="inline-flex items-center gap-1 rounded-full bg-red-50 border border-red-200 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
                    >
                      <X className="h-3.5 w-3.5" />
                      拒绝
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Failure Summary — show if any leads failed */}
      {(() => {
        const failedLeads = campaign.leads.filter(l => l.status === 'failed' && l.failure_code);
        if (failedLeads.length === 0) return null;
        const codeCount: Record<string, { count: number; reason: string }> = {};
        for (const l of failedLeads) {
          const code = l.failure_code || 'unknown';
          if (!codeCount[code]) codeCount[code] = { count: 0, reason: l.failure_reason || code };
          codeCount[code].count++;
        }
        return (
          <div className="mb-6 rounded-2xl bg-red-50 border border-red-200 shadow-sm overflow-hidden">
            <div className="flex items-center gap-2 border-b border-red-100 px-6 py-3.5">
              <AlertTriangle className="h-4 w-4 text-red-600" />
              <h2 className="text-sm font-semibold text-red-800">失败原因分析 ({failedLeads.length} 个失败)</h2>
            </div>
            <div className="divide-y divide-red-100">
              {Object.entries(codeCount).map(([code, info]) => (
                <div key={code} className="flex items-center justify-between px-6 py-2.5">
                  <span className="text-sm text-red-800">{info.reason}</span>
                  <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-700">{info.count}</span>
                </div>
              ))}
            </div>
          </div>
        );
      })()}

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
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">失败原因</th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-[#86868b]">时间</th>
                <th className="w-10 px-6 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e5e5e7]/40">
              {campaign.leads.map((lead) => (
                <Fragment key={lead.id}>
                  <tr
                    onClick={async () => {
                      if (expandedLeadId === lead.id) {
                        setExpandedLeadId(null);
                        return;
                      }
                      setExpandedLeadId(lead.id);
                      try {
                        const res = await leadApi.get(String(lead.id));
                        setExpandedMessages(res.data.messages || []);
                      } catch { setExpandedMessages([]); }
                    }}
                    className="cursor-pointer transition-colors hover:bg-[#f5f5f7]/50"
                  >
                    <td className="px-6 py-3.5 text-sm font-medium text-[#1d1d1f]">{lead.name || '未知'}</td>
                    <td className="px-6 py-3.5"><StatusBadge status={lead.status} /></td>
                    <td className="px-6 py-3.5 text-sm text-red-600">{lead.failure_reason || ''}</td>
                    <td className="px-6 py-3.5 text-sm text-[#86868b]">{new Date(lead.created_at).toLocaleString('zh-CN')}</td>
                    <td className="px-6 py-3.5">
                      {expandedLeadId === lead.id ? <ChevronUp className="h-4 w-4 text-[#86868b]" /> : <ChevronDown className="h-4 w-4 text-[#86868b]" />}
                    </td>
                  </tr>
                  {expandedLeadId === lead.id && (
                    <tr>
                      <td colSpan={5} className="bg-[#fafafa] px-6 py-4">
                        {expandedMessages.length > 0 ? (
                          <div className="space-y-2 max-w-xl">
                            <p className="text-xs font-semibold uppercase tracking-wider text-[#86868b] mb-2">消息记录</p>
                            {expandedMessages.map((msg) => (
                              <div key={msg.id} className={`rounded-xl p-3 text-sm ${msg.direction === 'outbound' ? 'bg-blue-50 text-blue-900' : 'bg-white border border-[#e5e5e7] text-[#1d1d1f]'}`}>
                                <div className="mb-1 flex items-center justify-between">
                                  <span className="text-xs font-medium">{msg.direction === 'outbound' ? 'AI 发送' : '对方回复'}</span>
                                  <span className="text-xs text-[#86868b]">{new Date(msg.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</span>
                                </div>
                                <p>{msg.content}</p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-[#86868b]">暂无消息记录</p>
                        )}
                        {lead.profile_url && (
                          <a href={lead.profile_url} target="_blank" rel="noopener noreferrer" className="mt-3 inline-block text-xs text-[#0071e3] hover:underline">
                            查看 Facebook 主页
                          </a>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
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
