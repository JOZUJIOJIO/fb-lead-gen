"use client";

import React, { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import {
  ChartBarIcon,
  ArrowTrendingUpIcon,
  UsersIcon,
  CheckCircleIcon,
} from "@heroicons/react/24/outline";
import StatsCard from "@/components/StatsCard";
import { analyticsApi } from "@/lib/api";
import type { AnalyticsOverview } from "@/lib/types";
import { useAuth } from "@/lib/auth";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4"];

const SOURCE_LABELS: Record<string, string> = {
  csv: "CSV/Excel",
  linkedin: "LinkedIn",
  alibaba: "阿里国际站",
  trade_show: "展会",
  facebook_search: "Facebook 搜索",
  graph_api: "Graph API",
  manual: "手动录入",
};

const STAGE_LABELS: Record<string, string> = {
  cold: "冷启动",
  curious: "初步兴趣",
  interested: "有意向",
  qualified: "已验证",
  ready_to_connect: "待转化",
  converted: "已转化",
};

export default function AnalyticsPage() {
  const { user, loading: authLoading } = useAuth();
  const [data, setData] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    analyticsApi
      .overview()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user]);

  if (authLoading || !user) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">加载中...</div>
      </div>
    );
  }

  if (loading || !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">加载数据分析...</div>
      </div>
    );
  }

  const sourcePieData = Object.entries(data.leads_by_source).map(([key, value]) => ({
    name: SOURCE_LABELS[key] || key,
    value,
  }));

  const stageFunnelData = Object.entries(data.leads_by_stage).map(([key, value]) => ({
    name: STAGE_LABELS[key] || key,
    value,
  }));

  const countryData = Object.entries(data.leads_by_country)
    .slice(0, 8)
    .map(([name, value]) => ({ name, value }));

  const industryData = Object.entries(data.leads_by_industry)
    .slice(0, 8)
    .map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">数据分析</h1>
        <p className="text-sm text-gray-500 mt-1">转化漏斗、渠道效果、趋势分析</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard icon={UsersIcon} value={data.total_leads} label="总线索数" color="bg-blue-500" />
        <StatsCard icon={ChartBarIcon} value={`${data.reply_rate}%`} label="回复率" color="bg-green-500" />
        <StatsCard icon={ArrowTrendingUpIcon} value={`${data.conversion_rate}%`} label="转化率" color="bg-purple-500" />
        <StatsCard icon={CheckCircleIcon} value={data.avg_score} label="平均评分" color="bg-orange-500" />
      </div>

      {/* Row 1: Daily Trend + Source Pie */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">每日活动趋势（近30天）</h2>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data.daily_activity}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="leads" stroke="#3b82f6" name="新增线索" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="contacted" stroke="#10b981" name="已触达" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="replied" stroke="#f59e0b" name="已回复" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">线索来源分布</h2>
          {sourcePieData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-gray-400">暂无数据</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={sourcePieData} cx="50%" cy="50%" outerRadius={90} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
                  {sourcePieData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Row 2: 对话转化漏斗 + Country + Industry */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">对话转化漏斗</h2>
          {stageFunnelData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-gray-400">暂无对话数据</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={stageFunnelData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 11 }} width={80} />
                <Tooltip />
                <Bar dataKey="value" fill="#8b5cf6" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">国家/地区分布</h2>
          {countryData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-gray-400">暂无国家数据</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={countryData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#10b981" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">行业分布</h2>
          {industryData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-gray-400">暂无行业数据</div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={industryData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#f59e0b" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
