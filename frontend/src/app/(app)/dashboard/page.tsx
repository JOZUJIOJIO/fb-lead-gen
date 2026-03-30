'use client';

import { useEffect, useState } from 'react';
import { Send, MessageSquare, Zap, Users } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import StatsCard from '@/components/StatsCard';
import { campaignApi } from '@/lib/api';

interface Stats {
  total_messages: number;
  total_leads: number;
  active_campaigns: number;
  total_campaigns: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await campaignApi.stats();
        setStats(res.data);
      } catch (error) {
        console.error('Failed to fetch stats:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">Dashboard</h1>
        <p className="mt-1 text-sm text-[#86868b]">实时概览获客数据</p>
      </div>

      {/* Stats Grid */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatsCard
          icon={Send}
          label="总发送消息"
          value={loading ? '...' : (stats?.total_messages ?? 0)}
        />
        <StatsCard
          icon={Users}
          label="总线索数"
          value={loading ? '...' : (stats?.total_leads ?? 0).toLocaleString()}
        />
        <StatsCard
          icon={Zap}
          label="活跃任务"
          value={loading ? '...' : (stats?.active_campaigns ?? 0)}
        />
        <StatsCard
          icon={MessageSquare}
          label="总任务数"
          value={loading ? '...' : (stats?.total_campaigns ?? 0)}
        />
      </div>

      {/* Empty state when no data */}
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
