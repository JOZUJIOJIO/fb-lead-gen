'use client';

import { useEffect, useState } from 'react';
import { Send, MessageSquare, Zap, Users, TrendingUp, CheckCircle, Clock, XCircle, Activity } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import StatsCard from '@/components/StatsCard';
import { campaignApi } from '@/lib/api';
import api from '@/lib/api';

interface Stats {
  total_messages: number;
  total_leads: number;
  active_campaigns: number;
  total_campaigns: number;
  messaged_count: number;
  replied_count: number;
  converted_count: number;
  pending_review_count: number;
  skipped_count: number;
  outbound_messages: number;
  inbound_messages: number;
  auto_reply_rounds: number;
  reply_rate: number;
  campaign_stats: { id: number; name: string; messaged: number; replied: number; reply_rate: number; outbound: number; inbound: number }[];
  keyword_stats: { keyword: string; total_sent: number; total_replied: number; reply_rate: number }[];
}

interface AutoReplyStatus {
  running: boolean;
  last_check_at: string | null;
  interval_seconds: number;
  max_rounds: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [secondsAgo, setSecondsAgo] = useState(0);
  const [autoReplyStatus, setAutoReplyStatus] = useState<AutoReplyStatus | null>(null);

  useEffect(() => {
    const fetchStats = (isFirst: boolean) => {
      campaignApi.stats()
        .then(res => {
          setStats(res.data);
          setLastUpdated(new Date());
          setSecondsAgo(0);
        })
        .catch(err => console.error('Failed to fetch stats:', err))
        .finally(() => { if (isFirst) setLoading(false); });
    };

    fetchStats(true);
    const pollInterval = setInterval(() => fetchStats(false), 10000);
    const tickInterval = setInterval(() => setSecondsAgo(prev => prev + 1), 1000);

    return () => {
      clearInterval(pollInterval);
      clearInterval(tickInterval);
    };
  }, []);

  // Fetch auto-reply status separately
  useEffect(() => {
    const fetchAutoReplyStatus = () => {
      api.get('/api/settings/auto-reply/status')
        .then(res => setAutoReplyStatus(res.data))
        .catch(() => {});
    };
    fetchAutoReplyStatus();
    const interval = setInterval(fetchAutoReplyStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const formatLastCheck = (lastCheckAt: string | null): string => {
    if (!lastCheckAt) return '暂无';
    const diff = Math.floor((Date.now() - new Date(lastCheckAt).getTime()) / 60000);
    if (diff < 1) return '刚刚';
    if (diff < 60) return `${diff} 分钟前`;
    return `${Math.floor(diff / 60)} 小时前`;
  };

  return (
    <div>
      <div className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">Dashboard</h1>
          <p className="mt-1 text-sm text-[#86868b]">实时概览获客数据</p>
        </div>
        {lastUpdated && (
          <span className="text-xs text-[#86868b] mt-2">
            上次更新: {secondsAgo < 5 ? '刚刚' : `${secondsAgo}秒前`}
          </span>
        )}
      </div>

      {/* Primary Stats */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatsCard
          icon={Send}
          label="已发送消息"
          value={loading ? '...' : (stats?.outbound_messages ?? 0)}
        />
        <StatsCard
          icon={MessageSquare}
          label="回复率"
          value={loading ? '...' : `${stats?.reply_rate ?? 0}%`}
        />
        <StatsCard
          icon={Zap}
          label="活跃任务"
          value={loading ? '...' : (stats?.active_campaigns ?? 0)}
        />
        <StatsCard
          icon={Users}
          label="总线索数"
          value={loading ? '...' : (stats?.total_leads ?? 0).toLocaleString()}
        />
      </div>

      {/* Secondary Stats */}
      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle className="h-4 w-4 text-emerald-500" />
            <span className="text-xs text-[#86868b]">收到回复</span>
          </div>
          <p className="text-lg font-semibold text-[#1d1d1f]">{loading ? '...' : stats?.inbound_messages ?? 0}</p>
        </div>
        <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className="h-4 w-4 text-purple-500" />
            <span className="text-xs text-[#86868b]">已转化</span>
          </div>
          <p className="text-lg font-semibold text-[#1d1d1f]">{loading ? '...' : stats?.converted_count ?? 0}</p>
        </div>
        <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
          <div className="flex items-center gap-2 mb-1">
            <Clock className="h-4 w-4 text-orange-500" />
            <span className="text-xs text-[#86868b]">待审核</span>
          </div>
          <p className="text-lg font-semibold text-[#1d1d1f]">{loading ? '...' : stats?.pending_review_count ?? 0}</p>
        </div>
        <div className="rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
          <div className="flex items-center gap-2 mb-1">
            <XCircle className="h-4 w-4 text-gray-400" />
            <span className="text-xs text-[#86868b]">已拒绝</span>
          </div>
          <p className="text-lg font-semibold text-[#1d1d1f]">{loading ? '...' : stats?.skipped_count ?? 0}</p>
        </div>
      </div>

      {/* Auto-Reply Status */}
      {autoReplyStatus && (
        <div className="mb-8 rounded-2xl bg-white p-4 border border-[#e5e5e7]/60 shadow-sm">
          <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-[#86868b]" />
              <span className="text-sm font-medium text-[#1d1d1f]">自动回复</span>
              <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full ${
                autoReplyStatus.running
                  ? 'bg-green-50 text-green-600'
                  : 'bg-gray-100 text-[#86868b]'
              }`}>
                <span className={`h-1.5 w-1.5 rounded-full ${autoReplyStatus.running ? 'bg-green-500' : 'bg-gray-400'}`} />
                {autoReplyStatus.running ? '运行中' : '已停止'}
              </span>
            </div>
            <div className="flex items-center gap-1 text-sm text-[#86868b]">
              <Clock className="h-3.5 w-3.5" />
              <span>上次检查: {formatLastCheck(autoReplyStatus.last_check_at)}</span>
            </div>
            <div className="text-sm text-[#86868b]">
              检查间隔: {Math.round(autoReplyStatus.interval_seconds / 60)} 分钟
            </div>
            <div className="text-sm text-[#86868b]">
              最大轮次: {autoReplyStatus.max_rounds}
            </div>
          </div>
        </div>
      )}

      {/* Campaign Performance Chart */}
      {!loading && stats && stats.campaign_stats.length > 0 && (
        <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-6 text-base font-semibold text-[#1d1d1f]">各任务回复率</h2>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.campaign_stats} barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f2" vertical={false} />
                <XAxis
                  dataKey="name"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: '#86868b', fontSize: 12 }}
                  interval={0}
                  angle={-20}
                  textAnchor="end"
                  height={60}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: '#86868b', fontSize: 12 }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#fff',
                    border: '1px solid #e5e5e7',
                    borderRadius: '12px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                    fontSize: '13px',
                  }}
                  formatter={(value: number, name: string) => {
                    const labels: Record<string, string> = { messaged: '已发送', replied: '已回复' };
                    return [value, labels[name] || name];
                  }}
                />
                <Bar dataKey="messaged" name="messaged" fill="#0071e3" radius={[6, 6, 0, 0]} />
                <Bar dataKey="replied" name="replied" fill="#34c759" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Keyword Performance Chart */}
      {!loading && stats && stats.keyword_stats && stats.keyword_stats.length > 0 && (
        <div className="mt-6 rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
          <h2 className="mb-6 text-base font-semibold text-[#1d1d1f]">关键词效果分析</h2>
          <div style={{ height: Math.max(200, stats.keyword_stats.length * 48) }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stats.keyword_stats} layout="vertical" barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f2" horizontal={false} />
                <XAxis
                  type="number"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: '#86868b', fontSize: 12 }}
                />
                <YAxis
                  type="category"
                  dataKey="keyword"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: '#86868b', fontSize: 12 }}
                  width={120}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#fff',
                    border: '1px solid #e5e5e7',
                    borderRadius: '12px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                    fontSize: '13px',
                  }}
                  formatter={(value: number, name: string) => {
                    const labels: Record<string, string> = { total_sent: '已发送', total_replied: '已回复' };
                    return [value, labels[name] || name];
                  }}
                />
                <Bar dataKey="total_sent" name="total_sent" fill="#0071e3" radius={[0, 6, 6, 0]} />
                <Bar dataKey="total_replied" name="total_replied" fill="#34c759" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && stats && stats.total_campaigns === 0 && (
        <div className="rounded-2xl bg-white p-12 border border-[#e5e5e7]/60 shadow-sm text-center">
          <Zap className="mx-auto h-12 w-12 text-[#86868b]/40" />
          <h2 className="mt-4 text-lg font-semibold text-[#1d1d1f]">开始你的第一个获客任务</h2>
          <p className="mt-2 text-sm text-[#86868b]">前往「任务」页面创建新的获客任务，数据将在此实时展示</p>
        </div>
      )}
    </div>
  );
}
