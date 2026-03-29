'use client';

import { useEffect, useState } from 'react';
import { Send, MessageSquare, Zap, Users } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import StatsCard from '@/components/StatsCard';

const mockStats = {
  sentToday: 48,
  replyRate: '12.5%',
  activeCampaigns: 3,
  totalLeads: 1247,
};

const mockChartData = [
  { day: '周一', sent: 32, replied: 4 },
  { day: '周二', sent: 45, replied: 6 },
  { day: '周三', sent: 28, replied: 3 },
  { day: '周四', sent: 51, replied: 8 },
  { day: '周五', sent: 38, replied: 5 },
  { day: '周六', sent: 15, replied: 2 },
  { day: '周日', sent: 48, replied: 6 },
];

export default function DashboardPage() {
  const [stats, setStats] = useState(mockStats);
  const [chartData, setChartData] = useState(mockChartData);

  useEffect(() => {
    // TODO: Fetch real data from API
    // const fetchStats = async () => {
    //   const res = await api.get('/api/dashboard/stats');
    //   setStats(res.data);
    // };
    // fetchStats();
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
          label="今日发送量"
          value={stats.sentToday}
          trend={{ value: '12%', positive: true }}
        />
        <StatsCard
          icon={MessageSquare}
          label="回复率"
          value={stats.replyRate}
          trend={{ value: '2.3%', positive: true }}
        />
        <StatsCard
          icon={Zap}
          label="活跃任务"
          value={stats.activeCampaigns}
        />
        <StatsCard
          icon={Users}
          label="总线索数"
          value={stats.totalLeads.toLocaleString()}
          trend={{ value: '48', positive: true }}
        />
      </div>

      {/* Chart */}
      <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
        <h2 className="mb-6 text-base font-semibold text-[#1d1d1f]">近 7 日活动</h2>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} barGap={4}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f2" vertical={false} />
              <XAxis
                dataKey="day"
                axisLine={false}
                tickLine={false}
                tick={{ fill: '#86868b', fontSize: 12 }}
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
              />
              <Bar dataKey="sent" name="发送" fill="#0071e3" radius={[6, 6, 0, 0]} />
              <Bar dataKey="replied" name="回复" fill="#34c759" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
