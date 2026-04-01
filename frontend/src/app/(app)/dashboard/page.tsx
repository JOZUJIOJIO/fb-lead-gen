'use client';

import { useEffect, useState } from 'react';
import { Send, MessageSquare, Zap, Users, TrendingUp, CheckCircle, Clock, XCircle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import StatsCard from '@/components/StatsCard';
import { campaignApi } from '@/lib/api';

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
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    campaignApi.stats()
      .then(res => setStats(res.data))
      .catch(err => console.error('Failed to fetch stats:', err))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">Dashboard</h1>
        <p className="mt-1 text-sm text-[#86868b]">实时概览获客数据</p>
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
