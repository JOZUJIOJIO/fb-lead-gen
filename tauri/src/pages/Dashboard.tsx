import { useEffect, useState } from 'react';
import { Send, MessageSquare, Zap, Users } from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import StatsCard from '../components/StatsCard';
import { systemApi } from '../lib/ipc';

interface Stats {
  sentToday: number;
  replyRate: string;
  activeCampaigns: number;
  totalLeads: number;
}

const defaultStats: Stats = {
  sentToday: 0,
  replyRate: '—',
  activeCampaigns: 0,
  totalLeads: 0,
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

export default function Dashboard() {
  const [stats, setStats] = useState<Stats>(defaultStats);
  const [loading, setLoading] = useState(true);
  const [chartData] = useState(mockChartData);

  useEffect(() => {
    systemApi
      .status()
      .then((data: unknown) => {
        const d = data as Record<string, unknown>;
        setStats({
          sentToday: (d.sent_today as number) ?? 0,
          replyRate: d.reply_rate ? `${d.reply_rate}%` : '—',
          activeCampaigns: (d.active_campaigns as number) ?? 0,
          totalLeads: (d.total_leads as number) ?? 0,
        });
      })
      .catch(() => {
        // Sidecar not connected yet — keep defaults
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight text-[#1d1d1f]">
          看板
        </h1>
        <p className="mt-1 text-sm text-[#86868b]">实时概览获客数据</p>
      </div>

      {loading && (
        <div className="mb-4 rounded-xl bg-yellow-50 px-4 py-2.5 text-sm text-yellow-700">
          正在连接后端服务...
        </div>
      )}

      {/* Stats Grid */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatsCard
          icon={Send}
          label="今日发送量"
          value={stats.sentToday}
        />
        <StatsCard
          icon={MessageSquare}
          label="回复率"
          value={stats.replyRate}
        />
        <StatsCard icon={Zap} label="活跃任务" value={stats.activeCampaigns} />
        <StatsCard
          icon={Users}
          label="总线索数"
          value={stats.totalLeads.toLocaleString()}
        />
      </div>

      {/* Chart */}
      <div className="rounded-2xl bg-white p-6 border border-[#e5e5e7]/60 shadow-sm">
        <h2 className="mb-6 text-base font-semibold text-[#1d1d1f]">
          近 7 日活动
        </h2>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} barGap={4}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#f0f0f2"
                vertical={false}
              />
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
              <Bar
                dataKey="sent"
                name="发送"
                fill="#0071e3"
                radius={[6, 6, 0, 0]}
              />
              <Bar
                dataKey="replied"
                name="回复"
                fill="#34c759"
                radius={[6, 6, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
