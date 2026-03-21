"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  UsersIcon,
  MegaphoneIcon,
  PaperAirplaneIcon,
  ChatBubbleLeftRightIcon,
  ArrowUpTrayIcon,
  PlusIcon,
} from "@heroicons/react/24/outline";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { format } from "date-fns";
import StatsCard from "@/components/StatsCard";
import ScoreBadge from "@/components/ScoreBadge";
import StatusBadge from "@/components/StatusBadge";
import { leadsApi, campaignsApi, messagesApi } from "@/lib/api";
import type { Lead, MessageStats } from "@/lib/types";
import { useAuth } from "@/lib/auth";

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [stats, setStats] = useState<MessageStats | null>(null);
  const [totalLeads, setTotalLeads] = useState(0);
  const [activeCampaigns, setActiveCampaigns] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    const fetchData = async () => {
      try {
        const [leadsRes, msgStats, campaigns] = await Promise.all([
          leadsApi.list({ page: 1, page_size: 10, sort_by: "created_at", sort_order: "desc" }),
          messagesApi.stats(),
          campaignsApi.list(),
        ]);
        setLeads(leadsRes.items || []);
        setTotalLeads(leadsRes.total || 0);
        setStats(msgStats);
        setActiveCampaigns(
          (campaigns || []).filter((c) => c.status === "active").length
        );
      } catch {
        // Silently handle errors for dashboard
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [user]);

  if (authLoading || !user) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">加载中...</div>
      </div>
    );
  }

  const messagesSent = stats?.sent ?? 0;
  const repliedCount = stats?.replied ?? 0;
  const replyRate = messagesSent > 0 ? ((repliedCount / messagesSent) * 100).toFixed(1) : "0";

  const funnelData = [
    { name: "已发送", value: stats?.sent ?? 0 },
    { name: "已送达", value: stats?.delivered ?? 0 },
    { name: "已读", value: stats?.read ?? 0 },
    { name: "已回复", value: stats?.replied ?? 0 },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">仪表盘</h1>
          <p className="text-sm text-gray-500 mt-1">欢迎回来，查看您的业务概况</p>
        </div>
        <div className="flex gap-3">
          <Link
            href="/leads?action=import"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <ArrowUpTrayIcon className="h-4 w-4" />
            导入线索
          </Link>
          <Link
            href="/campaigns?action=create"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-primary hover:bg-blue-700 rounded-lg transition-colors"
          >
            <PlusIcon className="h-4 w-4" />
            创建活动
          </Link>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          icon={UsersIcon}
          value={totalLeads}
          label="总线索数"
          color="bg-blue-500"
        />
        <StatsCard
          icon={MegaphoneIcon}
          value={activeCampaigns}
          label="进行中活动"
          color="bg-purple-500"
        />
        <StatsCard
          icon={PaperAirplaneIcon}
          value={messagesSent}
          label="已发消息"
          color="bg-green-500"
        />
        <StatsCard
          icon={ChatBubbleLeftRightIcon}
          value={`${replyRate}%`}
          label="回复率"
          color="bg-orange-500"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Funnel Chart */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">消息漏斗</h2>
          {loading ? (
            <div className="h-64 flex items-center justify-center text-gray-400">
              加载中...
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={funnelData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    borderRadius: "8px",
                    border: "1px solid #e2e8f0",
                    boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                  }}
                />
                <Bar dataKey="value" fill="#3b82f6" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Recent Leads */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">最新线索</h2>
            <Link
              href="/leads"
              className="text-sm text-primary hover:underline"
            >
              查看全部
            </Link>
          </div>
          {loading ? (
            <div className="h-64 flex items-center justify-center text-gray-400">
              加载中...
            </div>
          ) : leads.length === 0 ? (
            <div className="h-64 flex flex-col items-center justify-center text-gray-400">
              <UsersIcon className="h-10 w-10 mb-2" />
              <p>暂无线索数据</p>
              <Link href="/leads?action=import" className="text-primary text-sm mt-2 hover:underline">
                导入线索
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="text-left text-xs font-semibold text-gray-500 uppercase pb-2">
                      姓名
                    </th>
                    <th className="text-left text-xs font-semibold text-gray-500 uppercase pb-2">
                      公司
                    </th>
                    <th className="text-left text-xs font-semibold text-gray-500 uppercase pb-2">
                      评分
                    </th>
                    <th className="text-left text-xs font-semibold text-gray-500 uppercase pb-2">
                      状态
                    </th>
                    <th className="text-left text-xs font-semibold text-gray-500 uppercase pb-2">
                      时间
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {leads.map((lead) => (
                    <tr key={lead.id} className="hover:bg-gray-50">
                      <td className="py-2.5">
                        <Link
                          href={`/leads/${lead.id}`}
                          className="text-sm font-medium text-gray-900 hover:text-primary"
                        >
                          {lead.name}
                        </Link>
                      </td>
                      <td className="py-2.5 text-sm text-gray-500">
                        {lead.company || "-"}
                      </td>
                      <td className="py-2.5">
                        <ScoreBadge score={lead.score} />
                      </td>
                      <td className="py-2.5">
                        <StatusBadge status={lead.status} />
                      </td>
                      <td className="py-2.5 text-xs text-gray-400">
                        {format(new Date(lead.created_at), "MM-dd")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
